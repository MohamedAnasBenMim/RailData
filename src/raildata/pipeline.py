"""Pipeline orchestration: generate -> land -> bronze -> dbt build -> metrics.

Every step is idempotent, so a daily run can be retried or a date range
backfilled safely:

* landing files and bronze partitions are overwritten per delivery day;
* the GTFS bronze tables are replaced atomically;
* the incremental fact table rebuilds whole service-date partitions.
"""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

import duckdb

from raildata.generate import write_gtfs_zip, write_landing_day
from raildata.gtfs import load_gtfs
from raildata.ingest import ingest_events

log = logging.getLogger("raildata")

DBT_DIR = Path(__file__).resolve().parents[2] / "dbt"


@dataclass
class Paths:
    data_dir: Path

    @property
    def landing(self) -> Path:
        return self.data_dir / "landing"

    @property
    def bronze(self) -> Path:
        return self.data_dir / "bronze"

    @property
    def warehouse(self) -> Path:
        return self.data_dir / "warehouse" / "raildata.duckdb"

    @property
    def synthetic_gtfs(self) -> Path:
        return self.landing / "gtfs" / "synthetic_gtfs.zip"


@dataclass
class RunResult:
    timings_s: dict[str, float] = field(default_factory=dict)
    dbt_results: dict[str, int] = field(default_factory=dict)
    landing_records: int = 0
    gtfs_rows: dict[str, int] = field(default_factory=dict)


def daterange(start: date, end: date) -> list[date]:
    return [start + timedelta(days=i) for i in range((end - start).days + 1)]


def dbt_env(paths: Paths) -> None:
    """Point dbt at this data directory (absolute paths, so views keep working)."""
    os.environ["RAILDATA_DATA_DIR"] = str(paths.data_dir.resolve())
    os.environ["RAILDATA_DUCKDB"] = str(paths.warehouse.resolve())
    paths.warehouse.parent.mkdir(parents=True, exist_ok=True)


def run_dbt(args: list[str], paths: Paths) -> dict[str, int]:
    """Run dbt in a subprocess (it holds the DuckDB file lock while running).

    Raises if dbt fails; returns ``{"<resource_type>:<status>": count}`` read
    from dbt's run_results.json.
    """
    dbt_env(paths)
    cmd = [
        sys.executable,
        "-c",
        "from dbt.cli.main import cli; cli()",
        *args,
        "--project-dir",
        str(DBT_DIR),
        "--profiles-dir",
        str(DBT_DIR),
    ]
    proc = subprocess.run(cmd, cwd=DBT_DIR, env=os.environ.copy(), text=True, capture_output=True)
    counts: dict[str, int] = {}
    results_file = DBT_DIR / "target" / "run_results.json"
    if results_file.exists():
        for r in json.loads(results_file.read_text())["results"]:
            kind = r["unique_id"].split(".")[0]
            key = f"{kind}:{r['status']}"
            counts[key] = counts.get(key, 0) + 1
    if proc.returncode != 0:
        log.error("dbt output:\n%s", proc.stdout[-5000:] + proc.stderr[-3000:])
        raise RuntimeError(f"dbt {' '.join(args)} failed: {counts}")
    return dict(sorted(counts.items()))


def run(
    start: date,
    end: date,
    data_dir: Path,
    seed: int = 42,
    gtfs_source: str | None = None,
    synthetic: bool = True,
    full_refresh: bool = False,
) -> RunResult:
    """Run the pipeline for delivery days ``start..end`` (inclusive)."""
    paths = Paths(data_dir)
    result = RunResult()
    t_all = time.perf_counter()

    t = time.perf_counter()
    if gtfs_source is None:
        # Calendar validity covers the whole year so any run date is in service.
        gtfs_source = str(
            write_gtfs_zip(paths.synthetic_gtfs, date(start.year, 1, 1), date(end.year, 12, 31))
        )
    result.gtfs_rows = load_gtfs(gtfs_source, paths.bronze)
    result.timings_s["gtfs_load"] = time.perf_counter() - t
    log.info("GTFS loaded from %s: %s", gtfs_source, result.gtfs_rows)

    t = time.perf_counter()
    for day in daterange(start, end):
        if synthetic:
            write_landing_day(seed, day, paths.landing)
    result.timings_s["generate_landing"] = time.perf_counter() - t

    t = time.perf_counter()
    for day in daterange(start, end):
        landing_file = paths.landing / "events" / f"{day.isoformat()}.jsonl"
        if not landing_file.exists():
            raise FileNotFoundError(f"no landing file for {day}: {landing_file}")
        result.landing_records += ingest_events(landing_file, paths.bronze, day)
    result.timings_s["bronze_ingest"] = time.perf_counter() - t
    log.info("ingested %d landing records into bronze", result.landing_records)

    t = time.perf_counter()
    dbt_vars = json.dumps({"start_date": start.isoformat(), "end_date": end.isoformat()})
    args = ["build", "--vars", dbt_vars, "--quiet"]
    if full_refresh:
        args.append("--full-refresh")
    result.dbt_results = run_dbt(args, paths)
    result.timings_s["dbt_build"] = time.perf_counter() - t
    result.timings_s["total"] = time.perf_counter() - t_all
    return result


def collect_metrics(data_dir: Path) -> dict:
    """Row counts per layer and quarantine breakdown, straight from the warehouse."""
    paths = Paths(data_dir)
    dbt_env(paths)
    con = duckdb.connect(str(paths.warehouse), read_only=True)

    def one(sql: str):
        return con.execute(sql).fetchone()[0]

    tables = {
        "bronze.events (stg_events view)": "staging.stg_events",
        "silver.int_events_validated (1 row per event_id)": "intermediate.int_events_validated",
        "gold.fct_stop_events": "marts.fct_stop_events",
        "gold.fct_trip_runs": "marts.fct_trip_runs",
        "gold.mart_punctuality_line_daily": "marts.mart_punctuality_line_daily",
        "gold.mart_punctuality_station": "marts.mart_punctuality_station",
        "gold.mart_punctuality_hourly": "marts.mart_punctuality_hourly",
        "gold.mart_delay_propagation": "marts.mart_delay_propagation",
        "quarantine.dq_quarantine_events": "quarantine.dq_quarantine_events",
    }
    rows = {k: one(f"select count(*) from {v}") for k, v in tables.items()}
    quarantine = dict(
        con.execute(
            "select dq_reason, count(*) from quarantine.dq_quarantine_events "
            "group by 1 order by 2 desc"
        ).fetchall()
    )
    trip_status = dict(
        con.execute(
            "select run_status, count(*) from marts.fct_trip_runs group by 1 order by 2 desc"
        ).fetchall()
    )
    headline = con.execute(
        """
        select
            round(avg(case when is_on_time then 1.0 else 0.0 end) * 100, 2),
            round(avg(delay_min), 2),
            round(quantile_cont(delay_min, 0.9), 2),
            min(service_date)::varchar,
            max(service_date)::varchar
        from marts.fct_stop_events
        where event_type = 'ARR' and not is_cancelled
        """
    ).fetchone()
    late = one("select count(*) from marts.fct_stop_events where ingest_date > service_date")
    con.close()
    return {
        "rows_per_layer": rows,
        "quarantine_by_reason": quarantine,
        "trip_runs_by_status": trip_status,
        "late_events_accepted": late,
        "arrivals_on_time_pct": headline[0],
        "arrivals_avg_delay_min": headline[1],
        "arrivals_p90_delay_min": headline[2],
        "service_date_range": [headline[3], headline[4]],
    }
