#!/usr/bin/env python
"""Write the declared extraction request for the T2 group-B daily slice.

RIVF'26 camera-ready, handoff T2 group B: ``measurements/equity_admission.py``,
``measurements/band_conformance.py`` and ``measurements/grid_conformity.py`` on
DB data. Those scripts read whole tables with their own SQL (not through the
logged adapter hooks), so the slice is a ``declared`` request, written here.

Population (the old corpus's, kept): every ``quote.ticker`` row with
``instrumenttype = 'stock'`` on a Vietnamese cash venue (``HSX``, ``HNX``,
``UPCOM``) that has at least one close in the window. ``TWOTC`` rows are a
later, non-Vietnamese addition to the DB and were never in the old corpus.

Window: the old corpus's banded span, daily bars 2021-02-05 .. 2022-12-30.

Fields, per consumer:

* ``quote_close`` ``[2021-02-04, 2022-12-31)``: equity admission needs the
  session *before* the first banded day for the ``lag()`` of 2021-02-05, and
  nothing after 2022-12-30 (the old corpus ended there, so the ``lead()`` of the
  last day is NULL and that signal drops, as it did before).
* ``quote_ceil``, ``quote_floor`` ``[2021-02-05, 2022-12-31)``: equity admission
  (the lock test) and band conformance (the vendor band).
* ``quote_reference`` ``[2021-02-05, 2022-12-31)``: band conformance (the engine's
  reconstruction input).
* ``quote_ticker``: instrument type and exchange for the population.

A second, supplementary request (``--grid-history``) reproduces the *old*
grid-conformity population, which was not the banded window but every HSX close
in the old corpus (2000-07-28 .. 2022-12-30): ``quote_close`` and
``quote_ticker`` for HSX stocks only. It goes to its own slice.

Usage (credentials are read by the extraction tool, never printed)::

    PY=<plutus-simulator>/.venv/bin/python
    $PY scripts/rivf26_t2_hsx_daily_request.py --out request.json
    $PY scripts/rivf26_extract.py declared --source db --experiment t2-hsx-daily \\
        --request request.json --reproduces "..."
    $PY scripts/rivf26_t2_hsx_daily_request.py --grid-history --out grid.json
    $PY scripts/rivf26_extract.py declared --source db \\
        --experiment t2-hsx-daily-grid-history --request grid.json --reproduces "..."
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rivf26_extract as rx  # noqa: E402

VENUES = ('HSX', 'HNX', 'UPCOM')
CLOSE_START = '2021-02-04'   # one session before the first banded day
BAND_START = '2021-02-05'    # first published band in the old corpus
END = '2022-12-31'           # exclusive; last day 2022-12-30
HISTORY_START = '2000-01-01'  # before the first HSX close (2000-07-28)

POPULATION_SQL = (
    "SELECT DISTINCT c.tickersymbol FROM quote.close c "
    "JOIN quote.ticker tk USING (tickersymbol) "
    "WHERE tk.instrumenttype = 'stock' AND tk.exchangeid = ANY(%s) "
    "AND c.datetime >= %s AND c.datetime < %s ORDER BY 1")


def build_request(tickers):
    def span(lo):
        return {t: [[lo, END]] for t in tickers}
    return {'version': 1, 'files': [
        {'file': 'quote_ceil.parquet', 'tickers': span(BAND_START)},
        {'file': 'quote_close.parquet', 'tickers': span(CLOSE_START)},
        {'file': 'quote_floor.parquet', 'tickers': span(BAND_START)},
        {'file': 'quote_reference.parquet', 'tickers': span(BAND_START)},
        {'file': 'quote_ticker.parquet', 'tickers': {t: None for t in tickers}},
    ]}


def build_history_request(tickers):
    return {'version': 1, 'files': [
        {'file': 'quote_close.parquet',
         'tickers': {t: [[HISTORY_START, END]] for t in tickers}},
        {'file': 'quote_ticker.parquet', 'tickers': {t: None for t in tickers}},
    ]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--out', type=Path, required=True)
    ap.add_argument('--grid-history', action='store_true',
                    help='HSX stocks, every close to 2022-12-30 (old grid population)')
    args = ap.parse_args()
    db = rx.PgClient()
    try:
        if args.grid_history:
            rows = db.fetch(POPULATION_SQL, [['HSX'], HISTORY_START, END])
        else:
            rows = db.fetch(POPULATION_SQL, [list(VENUES), CLOSE_START, END])
    finally:
        db.close()
    tickers = sorted(r[0] for r in rows)
    build = build_history_request if args.grid_history else build_request
    args.out.write_text(json.dumps(build(tickers), indent=1,
                                   sort_keys=True) + '\n', encoding='utf-8')
    print(f'{len(tickers)} tickers -> {args.out}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
