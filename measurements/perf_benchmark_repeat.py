"""Repeat the T8.3 benchmark N times, each in its own process, and report median and spread.

One run of ``measurements/perf_benchmark.py`` measures each figure once. This wrapper runs it ``--runs`` times
as separate processes, so every run starts with a cold interpreter, gets its own peak-RSS reading and inherits
no cache from the run before. It keeps every run's JSON and writes:

- ``docs/reference/tables/t8_perf_benchmark.json``: the same layout as a single run, with every numeric value
  replaced by its **median** over the runs (so existing readers keep working), plus ``repeats`` (per-measure
  median / min / max / coefficient of variation, and the per-run load averages);
- ``docs/reference/tables/t8_perf_benchmark.md``: median, min–max and CV for each measure;
- ``docs/reference/tables/t8_perf_runs/run_NN.json``: each run as it came out.

Per-run progress (start, end, wall time, ETA) goes to the ``--log`` file and to stderr.

RUN
    PYTHONPATH=src:. python measurements/perf_benchmark_repeat.py --runs 10 --e1-root <t2-e1 slice> \
        --log <log file>
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from statistics import mean, median, pstdev

REPO = Path(__file__).resolve().parents[1]
TABLES = REPO / "docs" / "reference" / "tables"
BENCH = REPO / "measurements" / "perf_benchmark.py"

# Headline measures: (label, path into a run's JSON, unit, format)
MEASURES = [
    ("Rulebook build + first `at()` (cold)", ("rulebook", "cold_build_and_first_at_ms"), "ms", "{:,.2f}"),
    ("`Rulebook.at(ts)` (warm)", ("rulebook", "at_per_second"), "/ s", "{:,.0f}"),
    ("Daily: `submit` (admission)", ("daily", "submit_per_second"), "orders / s", "{:,.0f}"),
    ("Daily: fill evaluation (`advance_to`)", ("daily", "fill_evaluations_per_second"), "orders / s", "{:,.0f}"),
    ("Tick maker, optimistic queue", ("tick", "optimistic", "orders_per_second"), "orders / s", "{:,.0f}"),
    ("Tick maker, conservative queue", ("tick", "conservative", "orders_per_second"), "orders / s", "{:,.0f}"),
    ("E1 wall time (484,949 decisions × 3 policies)", ("e1", "wall_s"), "s", "{:,.2f}"),
    ("E1 peak RSS", ("e1", "peak_rss_mb"), "MB", "{:,.1f}"),
]


def log(fh, msg: str) -> None:
    line = f"[{datetime.now():%H:%M:%S}] {msg}"
    print(line, file=sys.stderr, flush=True)
    fh.write(line + "\n")
    fh.flush()


def _power_source() -> str:
    """macOS: 'AC Power' or 'Battery Power' (laptops throttle on battery); 'unknown' elsewhere."""
    try:
        out = subprocess.check_output(["pmset", "-g", "batt"], text=True, stderr=subprocess.DEVNULL)
        return out.split("'")[1] if "'" in out else "unknown"
    except Exception:
        return "unknown"


def _get(d: dict, path):
    for k in path:
        d = d[k]
    return d


def _stats(xs: list[float]) -> dict:
    m = mean(xs)
    return {"median": round(median(xs), 4), "min": min(xs), "max": max(xs), "n": len(xs),
            "cv_pct": round(pstdev(xs) / m * 100, 2) if m else None}


def _median_tree(runs: list):
    """Same layout as one run; numeric leaves become the median across runs (max for ``max_us``)."""
    first = runs[0]
    if isinstance(first, dict):
        return {k: _median_tree([r[k] for r in runs]) for k in first}
    if isinstance(first, bool) or not isinstance(first, (int, float)):
        return first
    return round(median(runs), 4)


def aggregate(runs: list[dict], run_files: list[str]) -> dict:
    out = _median_tree(runs)
    for rule, v in out["rulebook"]["resolve_per_rule"].items():   # worst case over runs, not median of maxima
        v["max_us"] = max(r["rulebook"]["resolve_per_rule"][rule]["max_us"] for r in runs)
    out["machine"] = copy.deepcopy(runs[0]["machine"])
    out["machine"].pop("load_average_at_start", None)
    out["machine"].pop("load_average_at_end", None)
    out["repeats"] = {
        "runs": len(runs), "run_files": run_files,
        "note": "each run is a separate process; headline values above are medians across runs",
        "measures": {".".join(p): {"label": lbl, "unit": u, **_stats([_get(r, p) for r in runs])}
                     for lbl, p, u, _ in MEASURES},
        "load_average_at_start": [r["machine"]["load_average_at_start"] for r in runs],
        "commits": sorted({r["machine"]["plutus_simulator_commit"] for r in runs}),
        "src_dirty_any": any(r["machine"]["plutus_simulator_dirty"] for r in runs),
    }
    return out


def to_md(agg: dict) -> str:
    m, rep = agg["machine"], agg["repeats"]
    loads = [round(x[0], 2) for x in rep["load_average_at_start"]]
    lines = [
        "# T8.3 performance benchmark", "",
        "## Machine", "",
        "| | |", "|---|---|",
        f"| CPU | {m['cpu']} ({m['physical_cores']} physical / {m['logical_cores']} logical cores) |",
        f"| Memory | {m['memory_gb']} GB |",
        f"| OS | {m['os']} |",
        f"| Power | {m.get('power_source', 'unknown')} |",
        f"| Python | {m['python']} (DuckDB {m['duckdb']}, pyarrow {m['pyarrow']}, pandas {m['pandas']}) |",
        f"| plutus-simulator | `{', '.join(rep['commits'])}` (src dirty: {rep['src_dirty_any']}) |",
        f"| Run date | {rep.get('run_date', 'unknown')} |", "",
        "## Results", "",
        f"**{rep['runs']} runs, each a separate process.** Values are the median across runs; min–max and the "
        f"coefficient of variation (CV) show the spread. 1-min load average at the start of each run: "
        f"{min(loads)}–{max(loads)}.", "",
        "| Measure | Median | Min – max | CV |", "|---|---:|---:|---:|",
    ]
    for lbl, p, unit, fmt in MEASURES:
        s = rep["measures"][".".join(p)]
        lines.append(f"| {lbl} | {fmt.format(s['median'])} {unit} | "
                     f"{fmt.format(s['min'])} – {fmt.format(s['max'])} | {s['cv_pct']}% |")
    lines += ["", "Per-rule `RuleSet.resolve` latency (µs; median of the per-run medians, worst max over all runs):",
              "", "| Rule | Keys | Calls per run | Median | Max | Raised (unresolved) |", "|---|---:|---:|---:|---:|---:|"]
    for k, v in sorted(agg["rulebook"]["resolve_per_rule"].items()):
        lines.append(f"| {k} | {v['keys']} | {v['calls']} | {v['median_us']} | {v['max_us']} | "
                     f"{v['raised_unresolved']} |")
    e1 = agg["e1"]
    lines += ["", "Workloads: rulebook 200,000 `at()` calls and 50 `resolve` calls per key; daily 5,000 FPT orders on "
              "the shipped daily fixture; tick an S8/S9-style maker requoting every 15 s on the shipped FPT 2022-11-09 "
              f"book and tape ({agg['tick']['optimistic']['orders']} orders); E1 the full 2022 population "
              f"({e1.get('decisions', '—'):,} decisions).", "",
              "Regenerate: `PYTHONPATH=src:. python measurements/perf_benchmark_repeat.py --runs "
              f"{rep['runs']} --e1-root <t2-e1 slice> --log <log file>` on an otherwise idle machine. "
              "Each run's own output is in `docs/reference/tables/t8_perf_runs/`."]
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--runs", type=int, default=10)
    ap.add_argument("--e1-root", required=True)
    ap.add_argument("--log", type=Path, required=True)
    ap.add_argument("--runs-dir", type=Path, default=TABLES / "t8_perf_runs")
    ap.add_argument("--json", type=Path, default=TABLES / "t8_perf_benchmark.json")
    ap.add_argument("--md", type=Path, default=TABLES / "t8_perf_benchmark.md")
    a = ap.parse_args(argv)
    a.runs_dir.mkdir(parents=True, exist_ok=True)
    env = {**os.environ, "PYTHONPATH": f"{REPO / 'src'}:{REPO}"}
    runs, files, walls = [], [], []
    power = _power_source()
    with a.log.open("a") as fh:
        log(fh, f"start: {a.runs} runs of {BENCH.name}; power: {power}")
        for i in range(1, a.runs + 1):
            out = a.runs_dir / f"run_{i:02d}.json"
            t = time.perf_counter()
            log(fh, f"run {i}/{a.runs}: start (1-min load {os.getloadavg()[0]:.2f})")
            subprocess.run([sys.executable, str(BENCH), "--e1-root", a.e1_root, "--json", str(out)],
                           check=True, cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            walls.append(time.perf_counter() - t)
            r = json.loads(out.read_text())
            runs.append(r)
            files.append(str(out.relative_to(REPO)) if out.is_relative_to(REPO) else out.name)
            eta = mean(walls) * (a.runs - i)
            log(fh, f"run {i}/{a.runs}: done in {walls[-1]:.1f}s; at/s {r['rulebook']['at_per_second']:,.0f}, "
                    f"fill eval/s {r['daily']['fill_evaluations_per_second']:,.0f}, E1 {r['e1'].get('wall_s')}s; "
                    f"ETA {eta:.0f}s")
        agg = aggregate(runs, files)
        agg["machine"]["power_source"] = power
        agg["repeats"]["run_date"] = f"{datetime.now():%Y-%m-%d}"
        a.json.write_text(json.dumps(agg, indent=1, default=str) + "\n")
        md = to_md(agg)
        a.md.write_text(md)
        log(fh, f"wrote {a.json.name} and {a.md.name}")
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
