"""E1, published as statistics only -- at a grain a reader can check.

Owner decision (2026-11-24): E1's 2022 data is published as **statistics only**,
not as a raw slice, but at a finer grain than the paper's single numbers so a
reader can check them. This writes two outcome-only breakdowns of the same run
that produces the headline (``measure_fill_divergence``), from its per-decision
``on_row`` hook, so they add up to the headline exactly:

* ``by_month_intent.csv``  -- month x intent
* ``by_ticker_intent.csv`` -- ticker x intent

Columns: ``n`` decisions, ``agreed`` (all three policies indistinguishable: same
outcome, quantity and price -- the headline's definition), and per policy the
counts of ``fill`` / ``no_fill`` / ``indeterminate``. **No price, volume or
quantity column**: executed quantity is min(order, 10% of the day's volume), so
even it would leak volume per ticker. The month table is the only one that also
carries soft/hard filled quantity, summed over ~390 tickers.

RUN
    PYTHONPATH=src:. python measurements/e1_publish.py --data-root <t2-e1 slice> \\
        --out docs/reference/tables/t2/e1_published
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from measurements.fill_divergence import measure_fill_divergence  # noqa: E402
from plutus.market.session.types import FillOutcome  # noqa: E402

POLICIES = ("soft", "hard", "probabilistic")
OUTCOMES = (("fill", FillOutcome.FILL), ("no_fill", FillOutcome.NO_FILL),
            ("indeterminate", FillOutcome.INDETERMINATE))


def _short(signature: str) -> str:
    for p in POLICIES:
        if signature.startswith(p):
            return p
    raise ValueError(f"unknown policy signature {signature!r}")


def _new():
    return {"n": 0, "agreed": 0, "qty_soft": 0, "qty_hard": 0,
            **{f"{p}_{o}": 0 for p in POLICIES for o, _ in OUTCOMES}}


def collect(data_root: str):
    month, ticker = defaultdict(_new), defaultdict(_new)

    def on_row(row):
        day = row.start.date() if hasattr(row.start, "date") else row.start
        keys = ((month, (f"{day:%Y-%m}", row.name)), (ticker, (row.ticker, row.name)))
        for table, key in keys:
            a = table[key]
            a["n"] += 1
            a["agreed"] += bool(row.agreed)
            for sig, dec in row.decisions.items():
                p = _short(sig)
                for label, outcome in OUTCOMES:
                    if dec.outcome is outcome:
                        a[f"{p}_{label}"] += 1
                if p in ("soft", "hard"):
                    a[f"qty_{p}"] += int(dec.quantity or 0)

    result = measure_fill_divergence(data_root, on_row=on_row)
    return result, month, ticker


def _write(path: Path, key_names, table, *, quantities: bool):
    cols = ["n", "agreed"] + [f"{p}_{o}" for p in POLICIES for o, _ in OUTCOMES]
    if quantities:
        cols += ["qty_soft", "qty_hard"]
    with path.open("w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(list(key_names) + cols)
        for key in sorted(table):
            w.writerow(list(key) + [table[key][c] for c in cols])


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--data-root", required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    result, month, ticker = collect(a.data_root)

    # The breakdowns must add up to the headline, or they are not the same run.
    for table in (month, ticker):
        assert sum(v["n"] for v in table.values()) == result.questions
        assert sum(v["agreed"] for v in table.values()) == result.agreed

    a.out.mkdir(parents=True, exist_ok=True)
    _write(a.out / "by_month_intent.csv", ("month", "intent"), month, quantities=True)
    _write(a.out / "by_ticker_intent.csv", ("ticker", "intent"), ticker, quantities=False)
    (a.out / "totals.json").write_text(json.dumps({
        "questions": result.questions, "agreed": result.agreed,
        "agreement_rate": result.agreed / result.questions,
        "tickers": result.tickers, "ticker_days": result.ticker_days,
        "population": result.population}, indent=1))
    print(f"wrote {a.out}: {len(month)} month x intent rows, {len(ticker)} ticker x intent rows; "
          f"{result.questions:,} decisions, agreement {result.agreed / result.questions:.2%}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
