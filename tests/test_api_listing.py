"""RIVF'26 T8.4: the API listing in ``docs/reference/api_listing.md`` runs as written.

The listing is read from the document and executed verbatim, so the text the
paper quotes and the code that is tested cannot drift apart. It runs on the
shipped fixture ``scenarios/fixtures/daily/`` and needs no corpus.
"""
from __future__ import annotations

import contextlib
import io
import re
from datetime import datetime
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "reference" / "api_listing.md"
MAX_LINES = 8


def _listing() -> str:
    blocks = re.findall(r"```python\n(.*?)```", DOC.read_text(encoding="utf-8"),
                        flags=re.S)
    assert len(blocks) == 1, f"expected one python block in {DOC}"
    return blocks[0]


def test_the_listing_is_at_most_eight_lines():
    lines = [ln for ln in _listing().splitlines() if ln.strip()]
    assert len(lines) <= MAX_LINES, lines


def test_the_listing_runs_on_shipped_data_and_says_what_the_doc_says(monkeypatch):
    monkeypatch.chdir(ROOT)
    namespace: dict = {"__name__": "__api_listing__"}
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(_listing(), str(DOC), "exec"), namespace)

    first, second = out.getvalue().splitlines()
    assert first == "filled 74.0 PROVEN"
    assert second.startswith("125980020.0 (HoldingTranche(quantity=1000, ")

    session, fill = namespace["s"], namespace["fill"]
    assert session.now() == datetime(2022, 11, 9, 15, 0)
    assert fill.price == Decimal("74.0") and fill.quantity == 1000
    cash = session.cash()
    assert cash.settled_balance == Decimal("125980020.0")
    holding = session.holdings("FPT")
    assert holding.settled == 0
    (tranche,) = holding.unsettled
    assert tranche.quantity == 1000
    assert tranche.settles_at == datetime(2022, 11, 11, 13, 0)

    # The documented output block matches what the listing printed.
    assert out.getvalue().strip() in DOC.read_text(encoding="utf-8")
