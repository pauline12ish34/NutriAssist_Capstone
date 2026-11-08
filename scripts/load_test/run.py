"""Run the Locust load test at several numbers of users, then chart "before" against "after".

    python scripts/load_test/run.py run --label before          # the API must be running on port 8000
    python scripts/load_test/run.py run --label after
    python scripts/load_test/run.py plot                        # docs/results/load_test/load_test.png

Each run has one ``UrgentCaregiver`` and one ``HealthWorker`` (see locustfile.py) plus N ``Caregiver`` users
asking the model, for N in --users. Results go to docs/results/load_test/<label>.csv: one row per number of
model users and request type, with the median and 95th percentile response time in milliseconds.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parents[1] / "docs" / "results" / "load_test"
FIELDS = ["model_users", "name", "requests", "failures", "median_ms", "p95_ms", "max_ms", "requests_per_s"]
TARGET_MS = 2500   # the response-time target for the presentation: under 2.5 s


def run(label: str, users: list[int], duration_s: int, host: str) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    rows = []
    for n in users:
        print(f"[{label}] {n} model users + 1 urgent + 1 health worker, {duration_s} s ...", flush=True)
        with tempfile.TemporaryDirectory() as tmp:
            prefix = Path(tmp) / "run"
            subprocess.run([sys.executable, "-m", "locust", "-f", str(HERE / "locustfile.py"), "--headless",
                            "--host", host, "-u", str(n + 2), "-r", str(n + 2), "-t", f"{duration_s}s",
                            "--csv", str(prefix), "--only-summary", "--stop-timeout", "1",
                            *([] if n else ["UrgentCaregiver", "HealthWorker"])],
                           check=False, cwd=HERE)
            with open(f"{prefix}_stats.csv", encoding="utf-8") as handle:
                for row in csv.DictReader(handle):
                    if row["Name"] == "Aggregated":
                        continue
                    rows.append({"model_users": n, "name": row["Name"], "requests": row["Request Count"],
                                 "failures": row["Failure Count"], "median_ms": row["Median Response Time"],
                                 "p95_ms": row["95%"], "max_ms": row["Max Response Time"],
                                 "requests_per_s": f"{float(row['Requests/s']):.3f}"})
    out = RESULTS / f"{label}.csv"
    with out.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Saved {out}")
    return out


def load(label: str) -> dict[str, dict[int, dict]]:
    by_name: dict[str, dict[int, dict]] = {}
    with (RESULTS / f"{label}.csv").open(encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            by_name.setdefault(row["name"], {})[int(row["model_users"])] = row
    return by_name


def plot() -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # Reference palette (dataviz skill): categorical slots 1 and 2, validated together for colour blindness.
    colours = {"before": "#2a78d6", "after": "#eb6834"}
    names = {"before": "Before: whole request locked", "after": "After: only the model locked"}
    text, muted, grid, surface = "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
    panels = [("chat: danger sign", "Urgent danger-sign answer"), ("growth check", "Growth check"),
              ("chat: model answer", "Answer written by the model")]
    data = {label: load(label) for label in ("before", "after") if (RESULTS / f"{label}.csv").exists()}

    fig, axes = plt.subplots(1, 3, figsize=(15, 4.8), facecolor=surface)
    for ax, (name, title) in zip(axes, panels):
        ax.set_facecolor(surface)
        for label, results in data.items():
            points = sorted(results.get(name, {}).items())
            xs = [n for n, row in points if int(row["requests"])]
            ys = [float(results[name][n]["median_ms"]) / 1000 for n in xs]
            ax.plot(xs, ys, color=colours[label], linewidth=2, marker="o", markersize=7,
                    markeredgecolor=surface, markeredgewidth=2, label=names[label], zorder=3)
            if xs:   # direct label at the last point, in text ink beside the coloured mark
                ax.annotate(f"{ys[-1]:.1f} s" if ys[-1] >= 1 else f"{ys[-1] * 1000:.0f} ms", (xs[-1], ys[-1]),
                            xytext=(6, 0), textcoords="offset points", va="center", fontsize=9, color=text)
        ax.axhline(TARGET_MS / 1000, color=muted, linewidth=1, linestyle=(0, (4, 3)), zorder=2)
        ax.annotate("2.5 s target", (0, TARGET_MS / 1000), xytext=(2, 4), textcoords="offset points",
                    fontsize=8, color=muted)
        ax.set_yscale("log")
        ax.set_title(title, loc="left", fontsize=11, color=text)
        ax.set_xlabel("People asking the model at the same time", fontsize=9, color=muted)
        ax.set_xticks(sorted({n for r in data.values() for n in r.get(name, {})}))
        ax.grid(axis="y", color=grid, linewidth=0.8, zorder=0)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(grid)
        ax.tick_params(colors=muted, labelsize=8)
    axes[0].set_ylabel("Median response time (s, log scale)", fontsize=9, color=muted)
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="upper right", ncol=2, frameon=False, fontsize=9, labelcolor=text)
    fig.suptitle("NutriAssist-RW API under load (laptop CPU, Locust)", x=0.01, ha="left", fontsize=13, color=text)
    fig.tight_layout(rect=(0, 0, 1, 0.92))
    out = RESULTS / "load_test.png"
    fig.savefig(out, dpi=150, facecolor=surface)
    print(f"Saved {out}")
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    r = sub.add_parser("run")
    r.add_argument("--label", required=True)
    r.add_argument("--users", default="0,1,2,4,8", help="numbers of model users, comma-separated")
    r.add_argument("--duration", type=int, default=90, help="seconds per run")
    r.add_argument("--host", default="http://127.0.0.1:8000")
    sub.add_parser("plot")
    args = parser.parse_args()
    if args.command == "run":
        run(args.label, [int(n) for n in args.users.split(",")], args.duration, args.host)
    else:
        plot()


if __name__ == "__main__":
    main()
