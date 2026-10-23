from datetime import date

import polars as pl

from raildata.generate import write_landing_day
from raildata.ingest import ingest_events

DAY = date(2026, 3, 3)


def test_ingest_overwrites_partition(tmp_path):
    write_landing_day(3, DAY, tmp_path / "landing")
    f = tmp_path / "landing" / "events" / f"{DAY}.jsonl"
    n1 = ingest_events(f, tmp_path / "bronze", DAY)
    n2 = ingest_events(f, tmp_path / "bronze", DAY)
    assert n1 == n2
    files = list((tmp_path / "bronze" / "events").rglob("*.parquet"))
    assert len(files) == 1
    df = pl.read_parquet(files[0])
    assert df.height == n1
    assert df.schema["actual_ts"] == pl.Datetime("us")
    assert df["recorded_at"].null_count() == 0
