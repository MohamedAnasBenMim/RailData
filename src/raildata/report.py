"""Static report: a few PNG charts rendered from the gold marts."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb
import matplotlib

matplotlib.use("Agg")
logging.getLogger("matplotlib").setLevel(logging.WARNING)
import matplotlib.pyplot as plt  # noqa: E402

SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_2 = "#52514e"
GRID = "#e4e3df"


def _style(ax, title: str, ylabel: str) -> None:
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", fontsize=12, color=INK, pad=12)
    ax.set_ylabel(ylabel, color=INK_2)
    ax.tick_params(colors=INK_2, labelsize=9)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)


def _fig():
    fig, ax = plt.subplots(figsize=(8, 4.2), dpi=120)
    fig.patch.set_facecolor(SURFACE)
    return fig, ax


def render(warehouse: Path, out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(warehouse), read_only=True)
    written = []

    # 1. Punctuality by hour of day, weekday vs weekend.
    df = con.execute(
        "select day_type, scheduled_hour, on_time_pct from marts.mart_punctuality_hourly "
        "where scheduled_hour >= 5 and n_arrivals >= 200 order by 1, 2"
    ).pl()
    fig, ax = _fig()
    for color, day_type in zip(SERIES, ["weekday", "weekend"], strict=False):
        part = df.filter(df["day_type"] == day_type)
        ax.plot(
            part["scheduled_hour"],
            part["on_time_pct"],
            color=color,
            linewidth=2,
            marker="o",
            markersize=4,
            label=day_type,
        )
    _style(ax, "Arrivals on time (< 5 min) by scheduled hour, 05:00-23:59", "% on time")
    ax.set_xlabel("scheduled hour of day", color=INK_2)
    ax.set_xticks(range(5, 24, 2))
    ax.legend(frameon=False, labelcolor=INK_2)
    fig.tight_layout()
    written.append(out_dir / "punctuality_by_hour.png")
    fig.savefig(written[-1], facecolor=SURFACE)
    plt.close(fig)

    # 2. Delay propagation along the trip for four lines (direction 0).
    df = con.execute(
        """
        select p.route_id, r.route_short_name || ' ' || r.route_long_name as label,
               p.stop_sequence, p.avg_delay_min
        from marts.mart_delay_propagation p
        join marts.dim_routes r using (route_id)
        where p.direction_id = 0 and p.route_id in ('R_BOU', 'R_SAO', 'R_COT', 'R_ALS')
        order by p.route_id, p.stop_sequence
        """
    ).pl()
    fig, ax = _fig()
    for color, route in zip(SERIES, ["R_BOU", "R_SAO", "R_COT", "R_ALS"], strict=False):
        part = df.filter(df["route_id"] == route)
        if part.height:
            ax.plot(
                part["stop_sequence"],
                part["avg_delay_min"],
                color=color,
                linewidth=2,
                marker="o",
                markersize=4,
                label=part["label"][0],
            )
    _style(ax, "Delay propagation along the trip (mean delay at each stop)", "mean delay (min)")
    ax.set_xlabel("stop number along the trip (1 = origin departure)", color=INK_2)
    ax.legend(frameon=False, labelcolor=INK_2, fontsize=8)
    fig.tight_layout()
    written.append(out_dir / "delay_propagation.png")
    fig.savefig(written[-1], facecolor=SURFACE)
    plt.close(fig)

    # 3. Daily cancellation rate across the network.
    df = con.execute(
        """
        select service_date,
               sum(cancelled_trips) * 100.0 / sum(scheduled_trips) as cancel_pct
        from marts.mart_punctuality_line_daily group by 1 order by 1
        """
    ).pl()
    fig, ax = _fig()
    ax.bar(df["service_date"], df["cancel_pct"], color=SERIES[0], width=0.8)
    _style(ax, "Share of scheduled trips fully cancelled, per day", "% of trips")
    fig.autofmt_xdate()
    fig.tight_layout()
    written.append(out_dir / "daily_cancellation_rate.png")
    fig.savefig(written[-1], facecolor=SURFACE)
    plt.close(fig)

    con.close()
    return written
