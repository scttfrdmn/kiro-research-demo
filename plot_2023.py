"""The closing graph: ERA5 2023 daily global-mean temperature, area-weighted vs np.mean.

Reads what Demo 2's run produced (fetch it with scripts/fetch-results.sh):
    results/daily_2023.csv      date, area_weighted_C, unweighted_C  (365 days)
    results/era5-results.tsv    the run's own checks and annual values

    python plot_2023.py            # writes results/era5-2023.png

Every number on the graph is computed from those files, except the two C3S reference
values, which are published constants and labelled as such.
"""
import csv
import sys
from datetime import date
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt

# Copernicus C3S, from ERA5 (Global Climate Highlights 2023; C3S/WMO record-day release).
C3S_ANNUAL_2023_C = 14.98
C3S_RECORD_DAY = (date(2023, 7, 6), 17.08)

# Reference palette (light mode): categorical slots 1 and 2, text and surface tokens.
SURFACE, INK, INK_2, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#e4e3df"
WEIGHTED, UNWEIGHTED = "#2a78d6", "#eb6834"


def load(results):
    days, weighted, unweighted = [], [], []
    with open(results / "daily_2023.csv") as fh:
        for row in csv.DictReader(fh):
            days.append(date.fromisoformat(row["date"]))
            weighted.append(float(row["area_weighted_C"]))
            unweighted.append(float(row["unweighted_C"]))
    if len(days) != 365:
        sys.exit("expected 365 days in daily_2023.csv, found %d" % len(days))
    return days, weighted, unweighted


def run_values(results):
    """The run's own annual values, to cross-check the CSV (4-decimal rounding)."""
    path = results / "era5-results.tsv"
    if not path.exists():
        return {}
    rows = dict(line.rstrip("\n").split("\t", 1) for line in open(path) if "\t" in line)
    return {k: float(rows[k]) for k in ("global_mean_2023_C", "global_mean_2023_unweighted_C") if k in rows}


def main(results=Path("results")):
    days, w, u = load(results)
    ann_w, ann_u = sum(w) / len(w), sum(u) / len(u)        # every day has 24 hours
    for key, mine in (("global_mean_2023_C", ann_w), ("global_mean_2023_unweighted_C", ann_u)):
        theirs = run_values(results).get(key)
        if theirs is not None and abs(theirs - mine) > 1e-3:
            sys.exit("%s: CSV gives %.4f, the run reported %.4f" % (key, mine, theirs))
    gap = ann_w - ann_u
    k = max(range(len(w)), key=w.__getitem__)

    plt.rcParams.update({"font.size": 13, "font.family": "DejaVu Sans", "text.color": INK,
                         "axes.labelcolor": INK_2, "xtick.color": INK_2, "ytick.color": INK_2})
    fig, ax = plt.subplots(figsize=(12.8, 7.2), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    fig.subplots_adjust(left=0.07, right=0.80, top=0.78, bottom=0.14)

    ax.plot(days, w, color=WEIGHTED, lw=2.2, label="area-weighted", solid_capstyle="round")
    ax.plot(days, u, color=UNWEIGHTED, lw=2.2, label="np.mean(temp), every grid point equal",
            solid_capstyle="round")
    ax.axhline(C3S_ANNUAL_2023_C, color=INK_2, lw=1.2, ls=(0, (4, 3)), zorder=1)
    ax.text(days[8], C3S_ANNUAL_2023_C + 0.25, "C3S published 2023 mean: %.2f °C" % C3S_ANNUAL_2023_C,
            color=INK_2, fontsize=12, va="bottom")

    # The record day, from the data; C3S's value beside it for comparison.
    ax.plot([days[k]], [w[k]], "o", ms=9, color=WEIGHTED, mec=SURFACE, mew=2, zorder=4)
    ax.annotate("Warmest day: %s, %.2f °C\nC3S record: %s, %.2f °C" % (
                    days[k].strftime("%-d %B"), w[k], C3S_RECORD_DAY[0].strftime("%-d %B"), C3S_RECORD_DAY[1]),
                (days[k], w[k]), xytext=(18, 14), textcoords="offset points", fontsize=12, color=INK)

    # The gap, at mid-autumn where the two lines are calm.
    j = 290
    ax.annotate("", (days[j], u[j] + 0.15), (days[j], w[j] - 0.15),
                arrowprops=dict(arrowstyle="<->", color=INK_2, lw=1.4))
    ax.text(days[j + 4], (w[j] + u[j]) / 2, "2023 mean\n%.2f °C too cold" % gap, color=INK, fontsize=14,
            fontweight="bold", va="center")

    # Direct labels at the right end; the legend repeats them for anyone reading by colour key.
    ax.text(days[-1], w[-1], "  area-weighted\n  2023 mean %.2f °C" % ann_w, color=INK, fontsize=12.5,
            va="center", clip_on=False)
    ax.text(days[-1], u[-1], "  np.mean(temp)\n  2023 mean %.2f °C" % ann_u, color=INK, fontsize=12.5,
            va="center", clip_on=False)
    fig.legend(loc="upper left", bbox_to_anchor=(0.063, 0.855), ncol=2, frameon=False, fontsize=12,
               labelcolor=INK_2, handlelength=1.8, columnspacing=2.0)

    ax.set_ylabel("Global-mean 2 m temperature (°C)")
    lo, hi = min(u), max(w)
    ax.set_ylim(lo - 1.5, hi + 1.5)
    ax.set_xlim(days[0], days[-1])
    ax.xaxis.set_major_locator(mdates.MonthLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%b"))
    ax.grid(axis="y", color=GRID, lw=0.8)
    ax.tick_params(length=0)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)

    fig.text(0.07, 0.935, "One line of code makes 2023 read %.1f °C colder" % gap,
             fontsize=22, fontweight="bold", color=INK)
    fig.text(0.07, 0.885, "Daily global-mean 2 m temperature, ERA5 2023, from 8,760 hourly 0.25° fields",
             fontsize=14, color=INK_2)
    fig.text(0.07, 0.035, "Data: ERA5 (Copernicus C3S / ECMWF) via NSF NCAR RDA ds633.0 on AWS Open Data. "
             "C3S values: Global Climate Highlights 2023.\nDrawn by plot_2023.py from the run's own results.",
             fontsize=10, color=INK_2, linespacing=1.5)

    out = results / "era5-2023.png"
    fig.savefig(out, facecolor=SURFACE)
    print("wrote", out, "| area-weighted %.4f °C, np.mean %.4f °C, gap %.4f °C, warmest day %s %.4f °C"
          % (ann_w, ann_u, gap, days[k], w[k]))


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("results"))
