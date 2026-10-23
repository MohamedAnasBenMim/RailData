"""End-to-end tests: generator ground truth vs. what the warehouse caught."""

import json
from collections import Counter
from datetime import date, timedelta

import duckdb

from raildata import pipeline

from .conftest import END, START


def _manifests(data_dir):
    out = {}
    for day in pipeline.daterange(START, END):
        path = data_dir / "landing" / "events" / "_manifest" / f"{day}.json"
        out[day] = json.loads(path.read_text())
    return out


def _con(data_dir):
    return duckdb.connect(str(pipeline.Paths(data_dir).warehouse), read_only=True)


def test_dbt_build_passed(pipeline_run):
    _, result = pipeline_run
    assert result.dbt_results.get("test:pass", 0) > 40
    assert not [k for k in result.dbt_results if k.endswith((":fail", ":error"))]


def test_quarantine_matches_injected_anomalies(pipeline_run):
    data_dir, _ = pipeline_run
    expected = Counter()
    for m in _manifests(data_dir).values():
        for k, v in m["anomalies_for_service_date"].items():
            if k not in ("late_arriving", "clean_events", "total_records"):
                expected[k] += v
    with _con(data_dir) as con:
        got = dict(
            con.execute(
                "select dq_reason, count(*) from quarantine.dq_quarantine_events group by 1"
            ).fetchall()
        )
    assert got == dict(expected)


def test_late_events_are_kept(pipeline_run):
    data_dir, _ = pipeline_run
    late_delivered = sum(m["late_records_from_previous_day"] for m in _manifests(data_dir).values())
    with _con(data_dir) as con:
        late_in_gold = con.execute(
            "select count(*) from marts.fct_stop_events where ingest_date > service_date"
        ).fetchone()[0]
    assert late_in_gold == late_delivered


def test_clean_rows_match_generator(pipeline_run):
    data_dir, _ = pipeline_run
    manifests = _manifests(data_dir)
    with _con(data_dir) as con:
        per_day = dict(
            con.execute(
                "select service_date, count(*) from marts.fct_stop_events group by 1"
            ).fetchall()
        )
    # Fully delivered days (their late events arrived in the next file).
    for day in pipeline.daterange(START, END - timedelta(days=1)):
        assert per_day[day] == manifests[day]["anomalies_for_service_date"]["clean_events"]


def _fingerprint(data_dir):
    with _con(data_dir) as con:
        return con.execute(
            "select service_date, count(*), "
            "md5(string_agg(event_id || coalesce(actual_ts::varchar, ''), ',' order by event_id)) "
            "from marts.fct_stop_events group by 1 order by 1"
        ).fetchall()


def test_rerun_of_a_day_is_idempotent(pipeline_run):
    data_dir, _ = pipeline_run
    before = _fingerprint(data_dir)
    day = date(2026, 3, 3)
    pipeline.run(day, day, data_dir, seed=7)
    assert _fingerprint(data_dir) == before
