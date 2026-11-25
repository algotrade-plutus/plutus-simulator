"""Pin the camera-ready numbers that were quoted only in prose to one committed result file.

Before this script, these values lived in ``docs/rivf26/T0-audit.md`` and ``NOTES-FOR-OWNER.md`` and the tests
pinned them only qualitatively (``end < start / 2``, ``0.30 < jump < 0.32``), so
``measurements/check_numbers.py`` could not verify them. This script recomputes each one from the committed
code and fixtures and writes ``docs/reference/tables/camera_ready_pins.json``.

What it computes
----------------
``s2``        the S2 daily run (``strategies/test_s2_equity_margin_momentum.run_s2``) on the committed
              fixture corpus: start/end equity, return, margin calls, forced-sale tranches.
``s2_queue``  the 2022-11-07 lock-queue row of ``measurements/s2_lock_queue.py`` on the committed
              ``strategies/fixtures/s2_lock`` slices.
``j18``       the J18 deposit step at the 13% → 17% initial-margin change
              (``scenarios/test_j18_margin_change.run_j18``).
``rules``     the uncovered rule-table edges (``tests/market/session/test_rule_tables.OPEN_EDGES``).
``properties`` Hypothesis properties under ``tests/properties``: count, the sum of their ``max_examples``,
              and their explicit ``@example`` boundary cases (read from the source, not run).
``tests``     (only with ``--tests``) pass/skip counts of the three suites, each run on its own:
              ``tests/``, ``scenarios/`` and ``strategies/``, each on its own shipped fixtures
              (``PLUTUS_DATA_ROOT`` unset, as in a fresh checkout).

Run::

    PYTHONPATH=src:. .venv/bin/python measurements/camera_ready_pins.py --tests

Each stage logs its elapsed time to stderr. The whole run takes about a minute.
"""
from __future__ import annotations

import argparse
import ast
import importlib.util
import json
import os
import re
import subprocess
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "docs" / "reference" / "tables" / "camera_ready_pins.json"
T0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - T0:6.1f}s] {msg}", file=sys.stderr, flush=True)


def _load(name: str, path: Path, extra_path: Path):
    """Import a test module by path, with its directory first on ``sys.path`` (each has its own _harness)."""
    for mod in [m for m in sys.modules if m == "_harness" or m.startswith("_harness.")]:
        del sys.modules[mod]
    sys.path.insert(0, str(extra_path))
    try:
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = mod
        spec.loader.exec_module(mod)
        return mod
    finally:
        sys.path.remove(str(extra_path))


def s2() -> dict:
    m = _load("s2_run", REPO / "strategies" / "test_s2_equity_margin_momentum.py", REPO / "strategies")
    ledger = m.run_s2()
    acc = ledger.account
    start, end = ledger.equity_curve[0][1], ledger.equity_curve[-1][1]
    completed = m._count_events(acc, "forced_sale_result_sent")
    return {
        "start_equity": float(start), "end_equity": float(end),
        "return_pct": round((float(end) / float(start) - 1) * 100, 2),
        "margin_calls": len(acc.calls()),
        "forced_sale_orders": len(acc.forced_sale_orders),
        "forced_sale_instructed_events": m._count_events(acc, "forced_sale_instructed"),
        "forced_sale_completed_events": completed,
        "note": "forced_sale_orders counts tranches; each tranche logs FORCED_SALE_INSTRUCTED twice "
                "(unrounded at the 15:00 notice, lot-rounded at the next open).",
    }


def s2_queue() -> dict:
    spec = importlib.util.spec_from_file_location("s2_lock_queue", REPO / "measurements" / "s2_lock_queue.py")
    lq = importlib.util.module_from_spec(spec)
    sys.modules["s2_lock_queue"] = lq
    spec.loader.exec_module(lq)
    fx = REPO / "strategies" / "fixtures" / "s2_lock"
    rows = {r.day: r for r in lq.measure(fx / "daily", fx / "book", "DIG", date(2022, 9, 5), date(2022, 11, 15))}
    r = rows[date(2022, 11, 7)]
    return {"day": "2022-11-07", "verdict": r.verdict, "queue_ahead": int(r.queue_ahead),
            "volume_after": int(r.volume_after), "cancel_share_needed": round(float(r.cancel_share_needed), 4),
            "floor_close_days": len(rows), "blocked_days": sorted(str(d) for d, x in rows.items()
                                                                  if x.verdict == "blocked")}


def j18() -> dict:
    m = _load("j18_run", REPO / "scenarios" / "test_j18_margin_change.py", REPO / "scenarios")
    obs = m.run_j18()
    jump = obs["after"] / obs["before"] - 1
    return {"reserved_before": float(obs["before"]), "reserved_after": float(obs["after"]),
            "ratio_before": float(obs["ratio_before"]), "ratio_after": float(obs["ratio_after"]),
            "deposit_step_pct": round(float(jump * Decimal(100)), 2)}


def rules() -> dict:
    m = _load("rule_tables", REPO / "tests" / "market" / "session" / "test_rule_tables.py",
              REPO / "tests" / "market" / "session")
    return {"open_edges": len(m.OPEN_EDGES)}


def properties() -> dict:
    n_props = n_examples = n_boundary = 0
    per_file = {}
    for f in sorted((REPO / "tests" / "properties").glob("test_*.py")):
        tree = ast.parse(f.read_text())
        props = ex = bnd = 0
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            names = [d.func.id if isinstance(d, ast.Call) and isinstance(d.func, ast.Name) else
                     d.func.attr if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) else None
                     for d in node.decorator_list]
            if "given" not in names:
                continue
            props += 1
            bnd += names.count("example")
            for d in node.decorator_list:
                if isinstance(d, ast.Call) and getattr(d.func, "id", None) == "settings":
                    for kw in d.keywords:
                        if kw.arg == "max_examples":
                            ex += ast.literal_eval(kw.value)
        per_file[f.name] = {"properties": props, "max_examples": ex, "boundary_examples": bnd}
        n_props, n_examples, n_boundary = n_props + props, n_examples + ex, n_boundary + bnd
    return {"properties": n_props, "max_examples_total": n_examples, "boundary_examples": n_boundary,
            "per_file": per_file}


def _pytest(target: str) -> dict:
    env = dict(os.environ, PYTHONPATH=f"{REPO / 'src'}:{REPO}")
    out = subprocess.run([sys.executable, "-m", "pytest", target, "-q", "-p", "no:cacheprovider"],
                         cwd=REPO, env=env, capture_output=True, text=True).stdout
    last = [l for l in out.splitlines() if re.search(r"\d+ (passed|failed|skipped)", l)][-1]
    counts = {k: int(v) for v, k in re.findall(r"(\d+) (passed|failed|skipped|xfailed|xpassed|errors?)", last)}
    return {k: counts.get(k, 0) for k in ("passed", "failed", "skipped", "xfailed")}


def tests() -> dict:
    return {"unit": _pytest("tests"), "scenarios": _pytest("scenarios"), "strategies": _pytest("strategies")}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--tests", action="store_true", help="also run the three suites and record their counts")
    ap.add_argument("--out", type=Path, default=OUT)
    a = ap.parse_args(argv)
    for var in ("PLUTUS_DATA_ROOT", "PLUTUS_DEPTH_ROOT"):   # every number here comes from shipped fixtures
        os.environ.pop(var, None)
    head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, capture_output=True,
                          text=True).stdout.strip()
    res = {"plutus_simulator_commit": head}
    stages = [("s2", s2), ("s2_queue", s2_queue), ("j18", j18), ("rules", rules), ("properties", properties)]
    if a.tests:
        stages.append(("tests", tests))
    elif a.out.exists():
        res["tests"] = json.loads(a.out.read_text()).get("tests")
    for i, (name, fn) in enumerate(stages, 1):
        log(f"stage {i}/{len(stages)}: {name}")
        res[name] = fn()
        log(f"  done: {json.dumps(res[name], default=str)[:160]}")
    a.out.write_text(json.dumps(res, indent=1, ensure_ascii=False) + "\n")
    log(f"wrote {a.out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
