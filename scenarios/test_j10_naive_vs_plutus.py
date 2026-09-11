"""J10 — A strategy that passes a naive fill-at-close backtest and fails here.

Scenario **J10** of ``docs/reference/SCENARIO-CATALOGUE.md``, as user code —
the headline. One strategy, two runs over the same window and data:
    * Arm A (naive): fills every signal at that session's close — what a naive
      backtester assumes.
    * Arm B (Plutus): runs through the exchange — admission, band, settlement.
**The gap between them is the whole value proposition.**

MECHANISM — everything composed. Here the delta is carried by the band lock,
which a naive backtester does not model at all: a stop-loss "sells at the
close" on a floor-locked day in the naive arm. In Plutus the same stop is
admitted — BAND_LOCK is a fill-time check now, not an admission rule — but it
does not fill: the floor-locked book has no bid beneath it. So the naive
backtest books an exit it could never have achieved and makes risk management
look free; Plutus shows the identical gap one layer later, in the fill, not
the admission.

POLICY (oracle — SCENARIO-CATALOGUE.md J10, the band-lock delta)
    QĐ 352 Điều 9.1–9.6 band arithmetic + price-then-time priority (high);
    the lock's one-sidedness is INFERRED, the evidence ladder UNSOURCED.
    (Catalogue's own worked case: a floor-locked day, forced sale admitted but
    unfilled — "a fill-at-close backtester sells; this one is never able to
    cross the lock.")

DISCLOSURE (rides with the headline, per the catalogue): on the daily corpus a
limit order fills at its own limit and the whole-day bar is returned at any
instant (§16.4 conflicts 3 & 4), so limit == fill == close on continuous fills.
That is why this delta is drawn from a *refusal* (which conflicts 3/4 cannot
manufacture), not from a fill-price difference.

SETUP — DIG, Oct 2022. Buy 2022-10-27, hold to settlement (2022-10-31), which
closes at its floor (17.70) — locked down. A stop-loss fires that day.

EXPECTED — Tier 2
    * Naive arm: the stop "fills at the close" — it exits, booking proceeds and
      going flat.
    * Plutus arm: the same stop is Accepted — admitted into the book — but
      does not fill on the locked day: no fill event, no exit, the position
      is still held, riding the drawdown.
    * The delta is the whole position: naive holds 0, Plutus holds 1,000. Only
      the *layer* at which the refusal shows up has moved, from admission to
      fill time — naive fills the stop, Plutus admits it but it does not
      fill — the same economic point, one layer later.

RUN
    python scenarios/test_j10_naive_vs_plutus.py
    pytest scenarios/test_j10_naive_vs_plutus.py -v
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from plutus.market.session import ExchangeSession, Accepted, Rejected  # noqa: F401
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side

from _harness import build_session, data_available

TICKER = "DIG"
QTY = 1000
CLOSE_ON_LOCK_DAY = Decimal("17.70")   # DIG 2022-10-31 close == floor
BUY_DAY = datetime(2022, 10, 27, 13, 0)
LOCK_DAY = datetime(2022, 10, 31, 13, 0)

CONFIG = {
    "period": {"start": "2022-10-27", "end": "2022-11-01"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-J10"}},
}


def naive_fill_at_close(qty: int, close: Decimal) -> dict:
    """Arm A — what a naive backtester assumes: the stop always fills at the
    session's close, so the position exits and books the proceeds."""
    return {"exited": True, "held_after": 0, "proceeds": close * qty * 1000}


def plutus_arm() -> dict:
    """Arm B — the same stop through the exchange."""
    session = build_session(CONFIG)
    session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=QTY,
                         order_type=OrderType.LIMIT, limit_price=Decimal("19.80")))
    session.advance_to(BUY_DAY)
    session.advance_to(LOCK_DAY)   # settles; the name is floor-locked
    stop = session.submit(Order(ticker=TICKER, side=Side.SELL, quantity=QTY,
                                order_type=OrderType.LIMIT, limit_price=CLOSE_ON_LOCK_DAY))
    # The stop was submitted after the advance above, so it has not yet had a
    # fill-evaluation pass -- advance again (same instant) to give it one.
    events = session.advance_to(LOCK_DAY)
    holding = session.holdings(TICKER)
    held = holding.settled + sum(t.quantity for t in holding.unsettled)
    return {"stop": stop, "held_after": held, "events": events}


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_j10_naive_vs_plutus():
    naive = naive_fill_at_close(QTY, CLOSE_ON_LOCK_DAY)
    plutus = plutus_arm()

    # Arm A exits and books proceeds.
    assert naive["exited"] and naive["held_after"] == 0

    # Arm B is admitted -- BAND_LOCK is a fill-time check now, not an
    # admission rule -- but never crosses the floor lock: no fill event.
    stop = plutus["stop"]
    assert isinstance(stop, Accepted), stop
    fills = [e for e in plutus["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == stop.order_id]
    assert not fills, "a stop-loss into a floor lock must not fill"

    # The delta is the whole position: the naive backtest thinks it is flat;
    # Plutus is still holding, trapped in the drawdown.
    assert plutus["held_after"] == QTY
    assert plutus["held_after"] != naive["held_after"]


if __name__ == "__main__":
    if not data_available():
        raise SystemExit("market-data corpus not found; set PLUTUS_DATA_ROOT")
    naive = naive_fill_at_close(QTY, CLOSE_ON_LOCK_DAY)
    plutus = plutus_arm()
    print("J10 — Naive fill-at-close vs Plutus (DIG floor lock, 2022-10-31)")
    print(f"  Arm A naive:  exited={naive['exited']}  held_after={naive['held_after']}")
    stop = plutus["stop"]
    stop_fills = [e for e in plutus["events"]
                 if getattr(e.kind, "value", e.kind) == "filled"
                 and e.order_id == getattr(stop, "order_id", None)]
    print(f"  Arm B Plutus: stop={type(stop).__name__}"
          f"(filled={bool(stop_fills)})  held_after={plutus['held_after']}")
    print(f"  DELTA: naive holds {naive['held_after']}, Plutus holds {plutus['held_after']} "
          f"— the naive exit is fictional")
    try:
        test_j10_naive_vs_plutus()
        print("  TIER 2: PASS")
    except AssertionError as exc:
        print(f"  TIER 2: FAIL — {exc}")
