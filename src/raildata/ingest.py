"""Landing -> bronze ingestion for realised events.

Bronze is an append-only, schema-enforced copy of what was delivered: no
deduplication or business rules here (that is the job of the dbt layers),
only typing plus lineage columns. Each delivery day is one Hive partition
``ingest_date=YYYY-MM-DD`` that is fully overwritten on re-run, which makes
ingestion idempotent.
"""

from __future__ import annotations

import shutil
from datetime import date
from pathlib import Path

import polars as pl

EVENT_SCHEMA = {
    "event_id": pl.String,
    "service_date": pl.String,
    "trip_id": pl.String,
    "stop_id": pl.String,
    "stop_sequence": pl.Int32,
    "event_type": pl.String,
    "status": pl.String,
    "actual_ts": pl.String,
    "recorded_at": pl.String,
    "source": pl.String,
}


def ingest_events(landing_file: Path, bronze_dir: Path, ingest_day: date) -> int:
    """Write one landing JSONL file to its bronze partition. Returns row count."""
    df = pl.read_ndjson(landing_file, schema=EVENT_SCHEMA)
    df = df.with_columns(
        pl.col("service_date").str.to_date("%Y-%m-%d", strict=False),
        pl.col("actual_ts").str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False),
        pl.col("recorded_at").str.to_datetime("%Y-%m-%dT%H:%M:%S", strict=False),
        pl.lit(landing_file.name).alias("_source_file"),
        pl.int_range(pl.len(), dtype=pl.Int64).alias("_source_line"),
    )
    part = bronze_dir / "events" / f"ingest_date={ingest_day.isoformat()}"
    tmp = part.with_name(part.name + ".tmp")
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True)
    df.write_parquet(tmp / "part-0.parquet")
    shutil.rmtree(part, ignore_errors=True)
    tmp.rename(part)
    return df.height
