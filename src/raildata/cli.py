"""Command-line entry point: ``raildata run --date 2026-03-02``."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import date
from pathlib import Path

from raildata import pipeline
from raildata.generate import write_landing_day
from raildata.gtfs import load_gtfs


def _date(s: str) -> date:
    return date.fromisoformat(s)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="raildata", description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("-v", "--verbose", action="store_true")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_run = sub.add_parser("run", help="run the pipeline for one day or a date range")
    p_run.add_argument("--date", type=_date, help="single delivery day (daily run)")
    p_run.add_argument("--start", type=_date)
    p_run.add_argument("--end", type=_date)
    p_run.add_argument("--seed", type=int, default=42)
    p_run.add_argument("--gtfs", help="path or URL of a GTFS zip (default: synthetic feed)")
    p_run.add_argument(
        "--no-generate",
        action="store_true",
        help="do not generate synthetic events; use existing landing files",
    )
    p_run.add_argument("--full-refresh", action="store_true")
    p_run.add_argument("--metrics-out", type=Path, help="write run metrics JSON here")

    p_gen = sub.add_parser("generate", help="only write synthetic landing files")
    p_gen.add_argument("--start", type=_date, required=True)
    p_gen.add_argument("--end", type=_date, required=True)
    p_gen.add_argument("--seed", type=int, default=42)

    p_gtfs = sub.add_parser("load-gtfs", help="load a GTFS zip (path or URL) into bronze")
    p_gtfs.add_argument("source")

    p_rep = sub.add_parser("report", help="render charts from the marts")
    p_rep.add_argument("--out", type=Path, default=Path("docs/charts"))

    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    paths = pipeline.Paths(args.data_dir)

    if args.cmd == "run":
        if args.date:
            start = end = args.date
        elif args.start and args.end:
            start, end = args.start, args.end
        else:
            parser.error("give --date or both --start and --end")
        res = pipeline.run(
            start,
            end,
            args.data_dir,
            seed=args.seed,
            gtfs_source=args.gtfs,
            synthetic=not args.no_generate,
            full_refresh=args.full_refresh,
        )
        metrics = pipeline.collect_metrics(args.data_dir)
        out = {
            "window": [start.isoformat(), end.isoformat()],
            "landing_records_ingested": res.landing_records,
            "gtfs_rows": res.gtfs_rows,
            "dbt_results": res.dbt_results,
            "timings_s": {k: round(v, 2) for k, v in res.timings_s.items()},
            **metrics,
        }
        text = json.dumps(out, indent=2, default=str)
        print(text)
        if args.metrics_out:
            args.metrics_out.parent.mkdir(parents=True, exist_ok=True)
            args.metrics_out.write_text(text + "\n")
    elif args.cmd == "generate":
        for day in pipeline.daterange(args.start, args.end):
            m = write_landing_day(args.seed, day, paths.landing)
            print(day, m["records_in_file"], "records")
    elif args.cmd == "load-gtfs":
        print(json.dumps(load_gtfs(args.source, paths.bronze), indent=2))
    elif args.cmd == "report":
        from raildata.report import render

        for p in render(paths.warehouse, args.out):
            print(p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
