"""PlutusBackend: builds from a config dict and drives a real session.

Runs entirely on the shipped fixtures (``strategies/fixtures/parquet``), which
carry FPT for 2022-11-09 at a close of 74.0 — the J1 settlement case — so the
fill assertion needs no external corpus.
"""
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from plutus.execution import PlutusBackend
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side
from plutus.market.session import Accepted, Cancelled, Amended

FIXTURES = str(Path(__file__).resolve().parents[1].parent / "strategies" / "fixtures" / "parquet")

BASE_CONFIG = {
    "period": {"start": "2022-11-09", "end": "2022-11-15"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-P0"}},
    "fill_policy": {"kind": "soft"},
    "data": {"adapter": "plutus.market.adapters.datahub.DataHubSource", "root": FIXTURES},
}


def test_backend_builds_and_reads_account():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    assert backend.cash().settled_balance == Decimal("200000000")
    assert backend.holdings("FPT").total == 0


def test_backend_submits_and_fills_the_j1_buy():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("74.0")))
    assert isinstance(ack, Accepted)
    fills = PlutusBackend.fills(backend.advance_to(datetime(2022, 11, 9, 13, 0)))
    assert fills, "expected a fill for the marketable FPT buy at the day's close"
    assert fills[0].price == Decimal("74.0")
    assert fills[0].quantity == 1000


def test_backend_cancels_a_resting_order():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    # a buy LIMIT below the 74.0 close is not marketable, so it rests
    # (70.0 stays inside that day's price band; the band floor is 68.2)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("70.0")))
    assert isinstance(ack, Accepted)
    out = backend.cancel(ack.order_id)
    assert isinstance(out, Cancelled)
    assert out.cancelled_quantity == 1000


def test_backend_amends_a_resting_equity_order():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("70.0")))
    out = backend.amend(ack.order_id, quantity=500)
    assert isinstance(out, Amended)


@pytest.mark.skipif(not os.environ.get("PLUTUS_DATA_ROOT"),
                    reason="needs the full corpus")
def test_backend_over_full_corpus():
    cfg = dict(BASE_CONFIG,
               data={"adapter": BASE_CONFIG["data"]["adapter"],
                     "root": os.environ["PLUTUS_DATA_ROOT"]})
    backend = PlutusBackend.from_config(cfg)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("74.0")))
    assert isinstance(ack, Accepted)
