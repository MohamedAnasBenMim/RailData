import io
import zipfile
from datetime import date

import polars as pl
import pytest

from raildata import gtfs
from raildata.generate import write_gtfs_zip


@pytest.fixture
def feed(tmp_path):
    return write_gtfs_zip(tmp_path / "feed.zip", date(2026, 1, 1), date(2026, 12, 31))


def test_load_synthetic_feed(feed, tmp_path):
    counts = gtfs.load_gtfs(feed, tmp_path / "bronze")
    assert counts["stops"] == 43
    assert counts["routes"] == 9
    assert counts["calendar_dates"] == 0  # absent file -> empty table, same schema
    st = pl.read_parquet(tmp_path / "bronze" / "gtfs" / "stop_times.parquet")
    assert st.height == counts["stop_times"]
    assert {"trip_id", "stop_id", "stop_sequence", "arrival_time", "_source"} <= set(st.columns)


def test_load_is_idempotent(feed, tmp_path):
    first = gtfs.load_gtfs(feed, tmp_path / "bronze")
    second = gtfs.load_gtfs(feed, tmp_path / "bronze")
    assert first == second
    assert len(list((tmp_path / "bronze" / "gtfs").glob("*.tmp"))) == 0


def _rezip(src, dst, drop=(), prefix="", edit=None):
    with zipfile.ZipFile(src) as zin, zipfile.ZipFile(dst, "w") as zout:
        for name in zin.namelist():
            if name in drop:
                continue
            data = zin.read(name).decode()
            if edit and name in edit:
                data = edit[name](data)
            zout.writestr(prefix + name, data)
    return dst


def test_missing_required_file_is_rejected(feed, tmp_path):
    bad = _rezip(feed, tmp_path / "bad.zip", drop={"stop_times.txt"})
    with pytest.raises(gtfs.GTFSValidationError, match="stop_times"):
        gtfs.read_gtfs(bad)


def test_nested_folder_and_missing_optional_columns(feed, tmp_path):
    def drop_coords(text):
        lines = text.splitlines()
        return "\n".join(",".join(line.split(",")[:2]) for line in lines) + "\n"

    nested = _rezip(feed, tmp_path / "nested.zip", prefix="feed/", edit={"stops.txt": drop_coords})
    tables = gtfs.read_gtfs(nested)
    assert tables["stops"]["stop_lat"].null_count() == tables["stops"].height


def test_url_source(feed, monkeypatch):
    payload = feed.read_bytes()

    class FakeResp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(gtfs.urllib.request, "urlopen", lambda url, timeout: FakeResp(payload))
    tables = gtfs.read_gtfs("https://example.org/gtfs.zip")
    assert tables["routes"].height == 9
