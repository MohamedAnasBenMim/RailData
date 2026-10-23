import hashlib
import json
from datetime import date

from raildata.generate import build_timetable, simulate_day, write_landing_day

DAY = date(2026, 3, 3)


def _digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_same_seed_same_bytes(tmp_path):
    write_landing_day(1, DAY, tmp_path / "a")
    write_landing_day(1, DAY, tmp_path / "b")
    a = tmp_path / "a" / "events" / f"{DAY}.jsonl"
    b = tmp_path / "b" / "events" / f"{DAY}.jsonl"
    assert _digest(a) == _digest(b)


def test_different_seed_differs(tmp_path):
    write_landing_day(1, DAY, tmp_path / "a")
    write_landing_day(2, DAY, tmp_path / "b")
    assert _digest(tmp_path / "a" / "events" / f"{DAY}.jsonl") != _digest(
        tmp_path / "b" / "events" / f"{DAY}.jsonl"
    )


def test_timetable_is_consistent():
    trips, stop_times = build_timetable()
    trip_ids = {t["trip_id"] for t in trips}
    assert len(trip_ids) == len(trips)
    assert {s.trip_id for s in stop_times} == trip_ids
    for s in stop_times:
        assert s.departure_s >= s.arrival_s


def test_dirty_records_are_present_and_counted():
    rows, manifest = simulate_day(42, DAY)
    for key in (
        "duplicate_event",
        "superseded_version",
        "unknown_stop_id",
        "missing_actual_ts",
        "implausible_delay",
        "out_of_order_timestamp",
        "late_arriving",
    ):
        assert manifest[key] > 0, key
    ids = [r["event_id"] for r in rows]
    # duplicates + superseded versions are extra copies of existing event ids
    assert len(ids) - len(set(ids)) == manifest["duplicate_event"] + manifest["superseded_version"]
    assert sum(r["stop_id"].startswith("UNKNOWN_") for r in rows) == manifest["unknown_stop_id"]
    assert sum(r["_late"] for r in rows) == manifest["late_arriving"]


def test_late_events_land_in_next_day_file(tmp_path):
    m = write_landing_day(42, DAY, tmp_path)
    _, prev_manifest = simulate_day(42, date(2026, 3, 2))
    assert m["late_records_from_previous_day"] == prev_manifest["late_arriving"]
    lines = (tmp_path / "events" / f"{DAY}.jsonl").read_text().splitlines()
    service_dates = {json.loads(line)["service_date"] for line in lines}
    assert service_dates == {"2026-03-02", "2026-03-03"}
