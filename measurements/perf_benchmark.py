"""T8.3 performance benchmark (RIVF'26 camera-ready, reviewer R1).

Measures, on the machine it runs on (spec recorded with the results):

1. **Rulebook**: construction (cold), ``Rulebook.at(ts)`` resolutions per second (warm), and per-rule
   ``RuleSet.resolve`` latency over every table and key.
2. **Orders through ``ExchangeSession``**:
   - *daily*: admission (``submit``) and fill evaluation (``advance_to``) rates on the shipped daily fixture;
   - *tick*: an S8/S9-style maker requoting every 15 s on the shipped FPT 2022-11-09 book and tape.
3. **E1**: wall time and peak RSS of the full 2022 population run (needs its DB slice; skipped if absent).

All workloads use shipped fixtures except E1. Run on a quiet machine; the results file records the
plutus-simulator commit and the machine.

RUN
    PYTHONPATH=src:. python measurements/perf_benchmark.py [--quick] [--e1-root <t2-e1 slice>] \
        [--json out.json] [--md out.md]
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import random
import resource
import subprocess
import sys
import time
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import median

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "strategies"))


def _sh(*cmd) -> str:
    try:
        return subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return "unknown"


def machine() -> dict:
    return {
        "cpu": _sh("sysctl", "-n", "machdep.cpu.brand_string"),
        "physical_cores": _sh("sysctl", "-n", "hw.physicalcpu"),
        "logical_cores": os.cpu_count(),
        "memory_gb": round(int(_sh("sysctl", "-n", "hw.memsize") or 0) / 2**30, 1)
        if _sh("sysctl", "-n", "hw.memsize").isdigit() else None,
        "os": platform.platform(),
        "python": platform.python_version(),
        "duckdb": __import__("duckdb").__version__,
        "pyarrow": __import__("pyarrow").__version__,
        "pandas": __import__("pandas").__version__,
        "plutus_simulator_commit": _sh("git", "-C", str(REPO), "rev-parse", "--short", "HEAD"),
        "plutus_simulator_dirty": bool(_sh("git", "-C", str(REPO), "status", "--porcelain", "src")),
        "load_average_at_start": os.getloadavg(),
    }


def _rate(n, seconds):
    return round(n / seconds, 1) if seconds > 0 else None


# -- 1. Rulebook -------------------------------------------------------------

def bench_rulebook(n_at: int, n_resolve_per_key: int) -> dict:
    from plutus.market.session.rulebook import Rulebook
    t = time.perf_counter()
    book = Rulebook()
    first = book.at(datetime(2023, 1, 4, 10))
    cold_build = time.perf_counter() - t

    rnd = random.Random(20261124)
    span = (datetime(2026, 8, 25) - datetime(2020, 1, 1)).total_seconds()
    stamps = [datetime(2020, 1, 1) + timedelta(seconds=rnd.random() * span) for _ in range(n_at)]
    t = time.perf_counter()
    for ts in stamps:
        book.at(ts)
    warm = time.perf_counter() - t

    per_rule = {}
    for rule, table in book._tables.items():
        keys = list(table)
        lat, unknown = [], 0
        for key in keys:
            for ts in stamps[:n_resolve_per_key]:
                rs = book.at(ts)
                t0 = time.perf_counter()
                try:
                    rs.resolve(rule, *key)
                except Exception:
                    unknown += 1
                lat.append(time.perf_counter() - t0)
        per_rule[rule.value] = {"keys": len(keys), "calls": len(lat),
                                "median_us": round(median(lat) * 1e6, 2),
                                "max_us": round(max(lat) * 1e6, 2),
                                "raised_unresolved": unknown}
    return {"cold_build_and_first_at_ms": round(cold_build * 1e3, 2),
            "at_calls": n_at, "at_per_second": _rate(n_at, warm),
            "resolve_per_rule": per_rule, "first_ruleset_edition": str(first.edition)}


# -- 2a. Daily workload ------------------------------------------------------

def bench_daily(n_orders: int) -> dict:
    import tempfile
    from plutus.market import Order, Side
    from plutus.market.session import ExchangeSession
    cfg = {"period": {"start": "2022-11-09", "end": "2022-11-15"}, "resolution": "1d",
           "exchange_rules": {"venues": ["HSX"]},
           "accounts": {"securities": {"initial_cash": 10**13}},
           "fill_policy": {"kind": "hard"},
           "data": {"adapter": "plutus.market.adapters.datahub.DataHubSource",
                    "root": str(REPO / "scenarios" / "fixtures" / "daily")}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
        json.dump(cfg, fh)
        path = fh.name
    s = ExchangeSession.from_config(path)
    prices = [Decimal("70.0") + Decimal(i % 40) / 10 for i in range(n_orders)]  # on the 0.1 grid
    t = time.perf_counter()
    acks = [s.submit(Order("FPT", Side.BUY, 100, limit_price=p)) for p in prices]
    submit_s = time.perf_counter() - t
    t = time.perf_counter()
    events = s.advance_to(s.now().replace(hour=15))
    advance_s = time.perf_counter() - t
    accepted = sum(type(a).__name__ == "Accepted" for a in acks)
    return {"orders": n_orders, "accepted": accepted,
            "submit_per_second": _rate(n_orders, submit_s),
            "fill_evaluations_per_second": _rate(accepted, advance_s),
            "events": len(events)}


# -- 2b. Tick workload -------------------------------------------------------

def bench_tick() -> dict:
    os.environ.pop("PLUTUS_DATA_ROOT", None)
    os.environ.pop("PLUTUS_DEPTH_ROOT", None)
    from _intraday_mm import InventoryMarketMaker, run_market_maker
    marks, t0 = [], datetime(2022, 11, 9, 9, 15)
    while t0.time() <= dtime(14, 25):
        if not (dtime(11, 30) <= t0.time() < dtime(13, 0)):
            marks.append(t0.time())
        t0 += timedelta(seconds=15)
    mm = InventoryMarketMaker(ticker="FPT", target=400000, band=10**9, size=1000, skew=False)
    out = {}
    for queue in ("optimistic", "conservative"):
        t = time.perf_counter()
        led = run_market_maker(mm, queue=queue, marks=marks)
        wall = time.perf_counter() - t
        orders = len(led._session.orders())
        out[queue] = {"marks": len(marks), "orders": orders, "fills": len(led.fills),
                      "wall_s": round(wall, 2), "orders_per_second": _rate(orders, wall),
                      "advances_per_second": _rate(len(marks), wall)}
    return out


# -- 3. E1 -------------------------------------------------------------------

def bench_e1(root: str | None) -> dict:
    if not root or not Path(root).is_dir():
        return {"skipped": "E1 slice not available (pass --e1-root)"}
    before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    t = time.perf_counter()
    subprocess.run([sys.executable, str(REPO / "measurements" / "fill_divergence.py"),
                    "--data-root", root], check=True, capture_output=True,
                   env={**os.environ, "PYTHONPATH": f"{REPO / 'src'}:{REPO}"})
    wall = time.perf_counter() - t
    peak = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    scale = 1 if sys.platform == "darwin" else 1024   # macOS reports bytes, Linux KiB
    return {"wall_s": round(wall, 2), "decisions": 484949,
            "decisions_per_second": _rate(484949, wall),
            "peak_rss_mb": round(max(peak, before) * scale / 2**20, 1)}


def to_md(r: dict) -> str:
    m, rb, d, tk, e1 = r["machine"], r["rulebook"], r["daily"], r["tick"], r["e1"]
    lines = [
        "# T8.3 performance benchmark", "",
        f"Machine: {m['cpu']}, {m['physical_cores']} physical / {m['logical_cores']} logical cores, "
        f"{m['memory_gb']} GB; {m['os']}; Python {m['python']}, DuckDB {m['duckdb']}, pyarrow {m['pyarrow']}. "
        f"plutus-simulator `{m['plutus_simulator_commit']}` (src dirty: {m['plutus_simulator_dirty']}); "
        f"load average at start {tuple(round(x, 2) for x in m['load_average_at_start'])}.", "",
        "| Measure | Value |", "|---|---:|",
        f"| Rulebook build + first `at()` (cold) | {rb['cold_build_and_first_at_ms']} ms |",
        f"| `Rulebook.at(ts)` (warm) | {rb['at_per_second']:,} / s |",
        f"| Daily: `submit` (admission) | {d['submit_per_second']:,} orders / s |",
        f"| Daily: fill evaluation (`advance_to`) | {d['fill_evaluations_per_second']:,} orders / s |",
    ]
    for q, v in tk.items():
        lines.append(f"| Tick maker, {q} queue ({v['marks']} requotes, {v['orders']} orders) | "
                     f"{v['orders_per_second']:,} orders / s ({v['wall_s']} s) |")
    if "wall_s" in e1:
        lines.append(f"| E1, 484,949 decisions × 3 policies | {e1['wall_s']} s, peak RSS {e1['peak_rss_mb']} MB |")
    else:
        lines.append(f"| E1 | {e1['skipped']} |")
    lines += ["", "Per-rule `RuleSet.resolve` latency (median / max, µs):", "",
              "| Rule | Keys | Calls | Median | Max | Raised (unresolved) |", "|---|---:|---:|---:|---:|---:|"]
    for k, v in sorted(rb["resolve_per_rule"].items()):
        lines.append(f"| {k} | {v['keys']} | {v['calls']} | {v['median_us']} | {v['max_us']} | {v['raised_unresolved']} |")
    return "\n".join(lines) + "\n"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--quick", action="store_true", help="small sizes, for a smoke run")
    ap.add_argument("--e1-root")
    ap.add_argument("--json", type=Path)
    ap.add_argument("--md", type=Path)
    a = ap.parse_args(argv)
    t0 = time.perf_counter()

    def stage(name, fn):
        print(f"[{datetime.now():%H:%M:%S}] start {name} (elapsed {time.perf_counter() - t0:.0f}s)",
              file=sys.stderr, flush=True)
        out = fn()
        print(f"[{datetime.now():%H:%M:%S}] done  {name} (elapsed {time.perf_counter() - t0:.0f}s)",
              file=sys.stderr, flush=True)
        return out

    r = {"machine": machine()}
    r["rulebook"] = stage("rulebook", lambda: bench_rulebook(2_000 if a.quick else 200_000, 5 if a.quick else 50))
    r["daily"] = stage("daily", lambda: bench_daily(200 if a.quick else 5_000))
    r["tick"] = stage("tick", bench_tick)
    r["e1"] = stage("e1", lambda: bench_e1(None if a.quick else a.e1_root))
    r["machine"]["load_average_at_end"] = os.getloadavg()
    if a.json:
        a.json.write_text(json.dumps(r, indent=1, default=str))
    md = to_md(r)
    if a.md:
        a.md.write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(main())
