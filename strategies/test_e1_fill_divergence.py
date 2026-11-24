"""E1 -- population fill-policy divergence, pinned.

The measurement (``measurements/fill_divergence.py``) replaces the old
three-strategy return sweep. This test guards its two load-bearing properties on a
fast slice: the divergence is **non-uniform across order intents** (market orders
diverge ~always, deep passive limits ~never -- acceptance criterion #4 of
``EXPERIMENT-E1-FILL-DIVERGENCE.md``), and it reports **fills, never P&L**.

Gates on a daily Parquet root named by ``PLUTUS_DATA_ROOT`` and skips cleanly
otherwise. It is skipped by default because the 2022 population slice is not
shipped in the repo (publication pending the owner's call, RIVF'26 F3); build it
with ``measurements/e1_regenerate.py`` (needs DB access) and point
``PLUTUS_DATA_ROOT`` at it.

RUN
    PLUTUS_DATA_ROOT=<rivf26 data>/t2-e1 \
        .venv/bin/python -m pytest strategies/test_e1_fill_divergence.py -v
    .venv/bin/python -m measurements.fill_divergence   # full population + figure
"""
from __future__ import annotations

from pathlib import Path

import pytest

from measurements.fill_divergence import (FillOutcome, default_data_root,
                                          measure_fill_divergence)


def _corpus() -> str:
    return default_data_root() or ""


def _ready() -> bool:
    return bool(_corpus()) and (Path(_corpus()) / "quote_close.parquet").exists()


@pytest.mark.skipif(not _ready(), reason="E1 needs a daily Parquet root in "
                    "PLUTUS_DATA_ROOT (the 2022 slice is not shipped; see "
                    "measurements/e1_regenerate.py)")
def test_e1_divergence_is_non_uniform_by_intent_and_reports_no_pnl():
    r = measure_fill_divergence(_corpus(), max_tickers=5)

    # A real flow was evaluated and the policies genuinely diverge (not 0, not 1).
    assert r.questions > 1000
    assert 0 < float(r.agreement_rate) < 1

    div = {i: (1 - a.agreed / a.n) for i, a in r.by_intent.items() if a.n}

    # (4) Divergence is a function of the order mix -- market orders diverge far
    # more than deep passive limits. If it were uniform, the population or the
    # pricing would be wrong.
    assert div["market_buy"] > 0.5
    assert div["limit_sell_at_ceil"] < 0.25
    assert div["market_buy"] > div["limit_sell_at_ceil"] + 0.3

    # The strict policy abstains more than the lenient one -- INDETERMINATE is a
    # first-class column, and `hard` refuses the touch that `soft` fills.
    d = r.to_dict()
    sigs = d["signatures"]
    hard = next(s for s in sigs if s.startswith("hard"))
    soft = next(s for s in sigs if s.startswith("soft"))
    assert (d["by_policy"][hard]["indeterminate_rate"]
            > d["by_policy"][soft]["indeterminate_rate"])

    # Reports fills, not performance: no P&L / return / Sharpe in the *data*
    # (DivergenceReport's contract). The prose `finding` field is excluded -- it
    # legitimately says "reported as fills, never P&L".
    blob = str({k: v for k, v in d.items() if k != "finding"}).lower()
    for banned in ("return", "pnl", "p&l", "sharpe", "profit"):
        assert banned not in blob, banned
    # what it DOES report is quantity and outcomes.
    assert d["by_policy"][soft]["filled_quantity"] > 0
    assert FillOutcome.INDETERMINATE.value in d["by_policy"][hard]["outcomes"]
