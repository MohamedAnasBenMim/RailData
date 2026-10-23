"""Seeded synthetic data generator.

Produces two things:

1. A static GTFS feed (agency, stops, routes, trips, stop_times, calendar) as a
   zip file, exactly what an operator would publish.
2. A daily stream of *realised* stop events (actual arrival / departure times)
   written as JSON Lines, one landing file per delivery day.

The delay model aims to be plausible rather than calibrated:

* most trips leave roughly on time, ~30 % carry a moderate exponential delay,
  ~5 % a Pareto heavy-tail delay;
* delays are amplified during weekday rush hours and on bad "days";
* delay propagates along the trip: each segment can recover a little thanks
  to schedule padding, or pick up an incident; hub stations add dwell delay;
* a small share of trips is fully or partially cancelled, and some days have
  a line-level disruption with many cancellations.

On top of the clean stream, deliberately dirty records are injected so the
cleaning and quality layers have real work to do. Every injected anomaly is
counted in a manifest so tests can check the pipeline catches exactly them.

Everything is a pure function of ``(seed, date)``: re-generating a day gives
byte-identical output.
"""

from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

from raildata.network import AGENCIES, ROUTES, SPEED_KMH, STATIONS

SERVICE_START = "05:30"
SERVICE_END = "22:30"
PEAKS = [(6 * 60, 9 * 60), (16 * 60 + 30, 19 * 60 + 30)]

# Share of clean OK events that get corrupted, per anomaly type.
ANOMALY_RATES = {
    "out_of_order_timestamp": 0.003,
    "unknown_stop_id": 0.003,
    "missing_actual_ts": 0.002,
    "implausible_delay": 0.001,
    "superseded_version": 0.010,  # an earlier, wrong version later corrected
    "duplicate_event": 0.015,  # exact re-delivery of the same record
    "late_arriving": 0.020,  # delivered in the next day's file (valid data)
}


# --------------------------------------------------------------------------- #
# Static GTFS
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StopTime:
    trip_id: str
    stop_id: str
    stop_sequence: int
    arrival_s: int  # seconds after midnight of the service day
    departure_s: int


def _haversine_km(a: str, b: str) -> float:
    _, lat1, lon1, _ = STATIONS[a]
    _, lat2, lon2, _ = STATIONS[b]
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371 * math.asin(math.sqrt(h))


def _hhmm(s: str) -> int:
    h, m = s.split(":")
    return int(h) * 60 + int(m)


def _fmt_gtfs_time(seconds: int) -> str:
    return f"{seconds // 3600:02d}:{seconds % 3600 // 60:02d}:{seconds % 60:02d}"


def _departure_minutes(headway: int, weekend: bool) -> list[int]:
    """Origin departure minutes for one direction of a route."""
    start, end = _hhmm(SERVICE_START), _hhmm(SERVICE_END)
    if weekend:
        start, headway = start + 90, max(headway, 60)
    out, t = [], start
    while t <= end:
        out.append(t)
        in_peak = any(a <= t < b for a, b in PEAKS)
        step = headway // 2 if (in_peak and not weekend and headway >= 30) else headway
        t += step
    return out


def build_timetable() -> tuple[list[dict], list[StopTime]]:
    """Return (trips, stop_times) for the whole synthetic network."""
    trips: list[dict] = []
    stop_times: list[StopTime] = []
    for route_id, (agency_id, _short, _long, stops, headway, _rel) in ROUTES.items():
        speed = SPEED_KMH[agency_id]
        for direction in (0, 1):
            seq = stops if direction == 0 else list(reversed(stops))
            # Scheduled running time: track ~1.25x crow-fly, +2 min accel/brake,
            # +7 % recovery margin (this is what lets trains catch up).
            runtimes = [
                round((_haversine_km(a, b) * 1.25 / speed * 60 + 2) * 1.07)
                for a, b in zip(seq, seq[1:], strict=False)
            ]
            for service_id, weekend in (("WKDY", False), ("WKND", True)):
                for i, dep_min in enumerate(_departure_minutes(headway, weekend)):
                    trip_id = f"{route_id}_{service_id}_{direction}_{i:03d}"
                    trips.append(
                        {
                            "route_id": route_id,
                            "service_id": service_id,
                            "trip_id": trip_id,
                            "trip_headsign": STATIONS[seq[-1]][0],
                            "direction_id": direction,
                        }
                    )
                    t = dep_min * 60
                    for k, stop_id in enumerate(seq):
                        if k == 0:
                            arr = dep = t
                        else:
                            arr = t + runtimes[k - 1] * 60
                            is_hub = STATIONS[stop_id][3]
                            dwell = 0 if k == len(seq) - 1 else (180 if is_hub else 60)
                            dep = arr + dwell
                        stop_times.append(StopTime(trip_id, stop_id, k + 1, arr, dep))
                        t = dep
    return trips, stop_times


def _csv(rows: list[dict], fields: list[str]) -> str:
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=fields, lineterminator="\n")
    w.writeheader()
    w.writerows(rows)
    return buf.getvalue()


def write_gtfs_zip(path: Path, start: date, end: date) -> Path:
    """Write the static synthetic feed as a standard GTFS zip."""
    trips, stop_times = build_timetable()
    files = {
        "agency.txt": _csv(
            [
                {
                    "agency_id": k,
                    "agency_name": n,
                    "agency_url": u,
                    "agency_timezone": "Europe/Paris",
                }
                for k, (n, u) in AGENCIES.items()
            ],
            ["agency_id", "agency_name", "agency_url", "agency_timezone"],
        ),
        "stops.txt": _csv(
            [
                {
                    "stop_id": k,
                    "stop_name": n,
                    "stop_lat": lat,
                    "stop_lon": lon,
                    "location_type": 1 if hub else 0,
                }
                for k, (n, lat, lon, hub) in STATIONS.items()
            ],
            ["stop_id", "stop_name", "stop_lat", "stop_lon", "location_type"],
        ),
        "routes.txt": _csv(
            [
                {
                    "route_id": k,
                    "agency_id": a,
                    "route_short_name": s,
                    "route_long_name": ln,
                    "route_type": 2,
                }
                for k, (a, s, ln, *_rest) in ROUTES.items()
            ],
            ["route_id", "agency_id", "route_short_name", "route_long_name", "route_type"],
        ),
        "trips.txt": _csv(
            trips, ["route_id", "service_id", "trip_id", "trip_headsign", "direction_id"]
        ),
        "stop_times.txt": _csv(
            [
                {
                    "trip_id": s.trip_id,
                    "arrival_time": _fmt_gtfs_time(s.arrival_s),
                    "departure_time": _fmt_gtfs_time(s.departure_s),
                    "stop_id": s.stop_id,
                    "stop_sequence": s.stop_sequence,
                }
                for s in stop_times
            ],
            ["trip_id", "arrival_time", "departure_time", "stop_id", "stop_sequence"],
        ),
        "calendar.txt": _csv(
            [
                {
                    "service_id": sid,
                    "monday": wd,
                    "tuesday": wd,
                    "wednesday": wd,
                    "thursday": wd,
                    "friday": wd,
                    "saturday": we,
                    "sunday": we,
                    "start_date": start.strftime("%Y%m%d"),
                    "end_date": end.strftime("%Y%m%d"),
                }
                for sid, wd, we in (("WKDY", 1, 0), ("WKND", 0, 1))
            ],
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
        ),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, content in files.items():
            # Fixed timestamp so the zip itself is reproducible.
            info = zipfile.ZipInfo(name, date_time=(2020, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            zf.writestr(info, content)
    return path


# --------------------------------------------------------------------------- #
# Realised events
# --------------------------------------------------------------------------- #
def _rng(seed: int, day: date, salt: str = "") -> np.random.Generator:
    digest = hashlib.sha256(f"{seed}|{day.isoformat()}|{salt}".encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


def _event_id(day: date, trip_id: str, seq: int, etype: str) -> str:
    return hashlib.sha1(f"{day}|{trip_id}|{seq}|{etype}".encode()).hexdigest()[:20]


def _iso(base: datetime, seconds: float) -> str:
    return (base + timedelta(seconds=int(round(seconds)))).isoformat()


def simulate_day(seed: int, day: date) -> tuple[list[dict], dict[str, int]]:
    """Simulate all realised events of one service day, including dirty records.

    Returns ``(rows, manifest)``. Each row carries an internal ``_late`` flag
    telling whether it is delivered in the next day's landing file.
    """
    rng = _rng(seed, day)
    weekend = day.weekday() >= 5
    service_id = "WKND" if weekend else "WKDY"
    midnight = datetime.combine(day, datetime.min.time())

    trips, stop_times = build_timetable()
    by_trip: dict[str, list[StopTime]] = {}
    for st in stop_times:
        by_trip.setdefault(st.trip_id, []).append(st)

    # Day-level conditions: weather/ops factor + an occasional line disruption.
    day_factor = float(rng.lognormal(0.0, 0.3))
    disrupted_route = None
    if rng.random() < 0.12:
        disrupted_route = str(rng.choice(sorted(ROUTES)))

    rows: list[dict] = []
    for trip in trips:
        if trip["service_id"] != service_id:
            continue
        route_id, trip_id = trip["route_id"], trip["trip_id"]
        reliability = ROUTES[route_id][5]
        sts = by_trip[trip_id]
        dep0_min = sts[0].departure_s / 60
        rush = 1.6 if (not weekend and any(a <= dep0_min < b for a, b in PEAKS)) else 1.0
        f = rush * day_factor / reliability

        # Cancellations
        p_cancel = 0.012 / reliability + (0.25 if route_id == disrupted_route else 0.0)
        cancel_from = None  # index of first cancelled stop
        u = rng.random()
        if u < p_cancel:
            cancel_from = 0
        elif u < p_cancel + 0.01:
            cancel_from = int(rng.integers(1, len(sts) - 1)) if len(sts) > 2 else None

        # Initial departure delay (seconds): on-time / moderate / heavy tail.
        m = rng.random()
        if m < 0.65:
            delay = max(0.0, rng.normal(20, 40))
        elif m < 0.95:
            delay = rng.exponential(180 * f)
        else:
            delay = 300 * (1 + rng.pareto(1.6)) * min(f, 2.0)
        delay = min(delay, 3 * 3600)

        actual_dep = sts[0].departure_s + delay
        for k, st in enumerate(sts):
            cancelled = cancel_from is not None and k >= cancel_from
            if k == 0:
                actual_arr = None
            else:
                sched_run = st.arrival_s - sts[k - 1].departure_s
                # The schedule holds ~7 % recovery margin: a late train uses part
                # of it to catch up, an on-time train arrives at most ~1 min early.
                current_delay = actual_dep - sts[k - 1].departure_s
                recovery = sched_run * rng.uniform(0.0, 0.065)
                run = sched_run - min(recovery, max(current_delay, 0.0) + 60.0)
                if rng.random() < 0.015 * f:  # incident on the segment
                    run += min(rng.exponential(360 * f), 1800.0)
                actual_arr = actual_dep + run
                extra_dwell = rng.exponential((75 if STATIONS[st.stop_id][3] else 20) * f)
                actual_dep = max(st.departure_s, actual_arr + 30) + extra_dwell
            for etype, sched, actual in (
                ("ARR", st.arrival_s, actual_arr),
                ("DEP", st.departure_s, actual_dep),
            ):
                if (etype == "ARR" and k == 0) or (etype == "DEP" and k == len(sts) - 1):
                    continue
                if cancelled:
                    rec = sched - rng.uniform(1800, 7200)
                    status, actual_s = "CANCELLED", None
                else:
                    rec = actual + rng.uniform(5, 90)
                    status, actual_s = "OK", actual
                rows.append(
                    {
                        "event_id": _event_id(day, trip_id, st.stop_sequence, etype),
                        "service_date": day.isoformat(),
                        "trip_id": trip_id,
                        "stop_id": st.stop_id,
                        "stop_sequence": st.stop_sequence,
                        "event_type": etype,
                        "status": status,
                        "_actual_s": actual_s,
                        "_sched_s": sched,
                        "_rec_s": rec,
                        "_late": False,
                    }
                )

    manifest = _inject_anomalies(rows, rng)

    out: list[dict] = []
    for r in rows:
        late = r.pop("_late")
        actual_s, rec_s = r.pop("_actual_s"), r.pop("_rec_s")
        r.pop("_sched_s")
        if late:
            # Delivered the next morning, after the daily batch has run.
            rec_s = 86400 + rng.uniform(1800, 6 * 3600)
        r["actual_ts"] = None if actual_s is None else _iso(midnight, actual_s)
        r["recorded_at"] = _iso(midnight, rec_s)
        r["source"] = "synthetic-avl"
        r["_late"] = late
        out.append(r)
    return out, manifest


def _inject_anomalies(rows: list[dict], rng: np.random.Generator) -> dict[str, int]:
    """Corrupt disjoint subsets of clean OK events in place; return the counts."""
    n = len(rows)
    ok = [i for i, r in enumerate(rows) if r["status"] == "OK"]
    used: set[int] = set()
    manifest: dict[str, int] = {}

    def pick(rate: float, eligible: list[int]) -> list[int]:
        cand = [i for i in eligible if i not in used]
        k = min(len(cand), int(round(rate * len(ok))))
        chosen = sorted(rng.choice(cand, size=k, replace=False).tolist()) if k else []
        used.update(chosen)
        return chosen

    # Out-of-order first: needs a clean predecessor in the same trip.
    ooo_eligible = [
        i
        for i in ok
        if i > 0
        and rows[i - 1]["trip_id"] == rows[i]["trip_id"]
        and rows[i - 1]["status"] == "OK"
        and rows[i]["_sched_s"] - rows[i - 1]["_sched_s"] <= 30 * 60
    ]
    ooo = []
    for i in pick(ANOMALY_RATES["out_of_order_timestamp"], ooo_eligible):
        if i - 1 in used and i - 1 not in ooo:
            # predecessor already corrupted by another out-of-order pick: skip it
            used.discard(i)
            continue
        used.add(i - 1)  # keep the predecessor clean
        rows[i]["_actual_s"] = rows[i - 1]["_actual_s"] - rng.uniform(120, 480)
        rows[i]["_rec_s"] = rows[i - 1]["_rec_s"] + 30
        ooo.append(i)
    manifest["out_of_order_timestamp"] = len(ooo)

    chosen = pick(ANOMALY_RATES["unknown_stop_id"], ok)
    for i in chosen:
        rows[i]["stop_id"] = f"UNKNOWN_{int(rng.integers(1000, 9999))}"
    manifest["unknown_stop_id"] = len(chosen)

    chosen = pick(ANOMALY_RATES["missing_actual_ts"], ok)
    for i in chosen:
        rows[i]["_actual_s"] = None
    manifest["missing_actual_ts"] = len(chosen)

    chosen = pick(ANOMALY_RATES["implausible_delay"], ok)
    for i in chosen:  # e.g. a device clock stuck on the wrong timezone / day
        rows[i]["_actual_s"] += rng.uniform(8, 20) * 3600
    manifest["implausible_delay"] = len(chosen)

    extra: list[dict] = []
    chosen = pick(ANOMALY_RATES["superseded_version"], ok)
    for i in chosen:
        wrong = dict(rows[i])
        wrong["_actual_s"] = rows[i]["_actual_s"] - rng.uniform(60, 600)
        wrong["_rec_s"] = rows[i]["_rec_s"]
        rows[i]["_rec_s"] += rng.uniform(600, 3600)  # correction arrives later
        extra.append(wrong)
    manifest["superseded_version"] = len(chosen)

    chosen = pick(ANOMALY_RATES["duplicate_event"], ok)
    extra.extend(dict(rows[i]) for i in chosen)
    manifest["duplicate_event"] = len(chosen)

    chosen = pick(ANOMALY_RATES["late_arriving"], ok)
    for i in chosen:
        rows[i]["_late"] = True
    manifest["late_arriving"] = len(chosen)

    rows.extend(extra)
    manifest["clean_events"] = n - sum(
        manifest[k]
        for k in (
            "out_of_order_timestamp",
            "unknown_stop_id",
            "missing_actual_ts",
            "implausible_delay",
        )
    )
    manifest["total_records"] = len(rows)
    return manifest


def write_landing_day(seed: int, day: date, landing_dir: Path) -> dict:
    """Write the landing file delivered on ``day``.

    It contains that day's events except late ones, plus the late events of
    the previous service day. Returns the manifest of what is in the file.
    """
    today_rows, today_manifest = simulate_day(seed, day)
    prev_rows, _ = simulate_day(seed, day - timedelta(days=1))
    late_from_prev = [r for r in prev_rows if r["_late"]]
    rows = [r for r in today_rows if not r["_late"]] + late_from_prev
    for r in rows:
        r.pop("_late")
    rows.sort(key=lambda r: (r["recorded_at"], r["event_id"]))

    out = landing_dir / "events" / f"{day.isoformat()}.jsonl"
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w") as fh:
        for r in rows:
            fh.write(json.dumps(r, separators=(",", ":")) + "\n")

    manifest = {
        "delivery_date": day.isoformat(),
        "records_in_file": len(rows),
        "late_records_from_previous_day": len(late_from_prev),
        "anomalies_for_service_date": today_manifest,
    }
    mpath = landing_dir / "events" / "_manifest" / f"{day.isoformat()}.json"
    mpath.parent.mkdir(parents=True, exist_ok=True)
    mpath.write_text(json.dumps(manifest, indent=2))
    return manifest
