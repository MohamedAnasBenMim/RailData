"""GTFS static feed loader: zip (local path or http(s) URL) -> bronze Parquet.

Works with any standard GTFS feed, not only the synthetic one. Only the
columns used downstream are kept; optional columns missing from a feed are
added as nulls so the dbt staging models always see the same schema.
"""

from __future__ import annotations

import io
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import polars as pl

# table -> (required columns, optional columns)
GTFS_TABLES: dict[str, tuple[list[str], list[str]]] = {
    "agency": (["agency_name", "agency_timezone"], ["agency_id", "agency_url"]),
    "stops": (
        ["stop_id", "stop_name"],
        ["stop_lat", "stop_lon", "location_type", "parent_station"],
    ),
    "routes": (["route_id", "route_type"], ["agency_id", "route_short_name", "route_long_name"]),
    "trips": (["route_id", "service_id", "trip_id"], ["trip_headsign", "direction_id"]),
    "stop_times": (["trip_id", "stop_id", "stop_sequence"], ["arrival_time", "departure_time"]),
    "calendar": (
        [
            "service_id",
            "monday",
            "tuesday",
            "wednesday",
            "thursday",
            "friday",
            "saturday",
            "sunday",
            "start_date",
            "end_date",
        ],
        [],
    ),
    "calendar_dates": (["service_id", "date", "exception_type"], []),
}
# A feed must provide calendar.txt and/or calendar_dates.txt.
OPTIONAL_FILES = {"calendar", "calendar_dates"}


class GTFSValidationError(ValueError):
    """Raised when a feed is missing required files or columns."""


def _open_source(source: str | Path) -> bytes:
    s = str(source)
    if s.startswith(("http://", "https://")):
        with urllib.request.urlopen(s, timeout=60) as resp:  # noqa: S310 (explicit URL)
            return resp.read()
    return Path(s).read_bytes()


def read_gtfs(source: str | Path) -> dict[str, pl.DataFrame]:
    """Read and validate a GTFS zip; every column is read as string."""
    with zipfile.ZipFile(io.BytesIO(_open_source(source))) as zf:
        # Some feeds nest files in a folder; index by basename.
        names = {Path(n).name: n for n in zf.namelist() if n.endswith(".txt")}
        present = {t for t in GTFS_TABLES if f"{t}.txt" in names}
        missing = set(GTFS_TABLES) - OPTIONAL_FILES - present
        if missing:
            raise GTFSValidationError(f"missing required GTFS files: {sorted(missing)}")
        if not present & OPTIONAL_FILES:
            raise GTFSValidationError("feed needs calendar.txt or calendar_dates.txt")

        tables: dict[str, pl.DataFrame] = {}
        for table, (required, optional) in GTFS_TABLES.items():
            if table not in present:
                df = pl.DataFrame(schema={c: pl.String for c in required + optional})
            else:
                raw = zf.read(names[f"{table}.txt"]).decode("utf-8-sig")
                df = pl.read_csv(io.StringIO(raw), infer_schema=False)
                df = df.rename({c: c.strip() for c in df.columns})
                lacking = [c for c in required if c not in df.columns]
                if lacking:
                    raise GTFSValidationError(f"{table}.txt lacks columns {lacking}")
                for c in optional:
                    if c not in df.columns:
                        df = df.with_columns(pl.lit(None, dtype=pl.String).alias(c))
                df = df.select(required + optional).with_columns(
                    pl.col(c).str.strip_chars() for c in required + optional
                )
            tables[table] = df
    return tables


def load_gtfs(source: str | Path, bronze_dir: Path) -> dict[str, int]:
    """Load a GTFS feed into ``bronze_dir/gtfs/<table>.parquet``. Idempotent."""
    tables = read_gtfs(source)
    out_dir = bronze_dir / "gtfs"
    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, df in tables.items():
        df = df.with_columns(pl.lit(str(source)).alias("_source"))
        # Write to a temp file then rename, so a crash never leaves half a file.
        with tempfile.NamedTemporaryFile(dir=out_dir, suffix=".tmp", delete=False) as tmp:
            df.write_parquet(tmp.name)
        Path(tmp.name).replace(out_dir / f"{name}.parquet")
        counts[name] = df.height
    return counts
