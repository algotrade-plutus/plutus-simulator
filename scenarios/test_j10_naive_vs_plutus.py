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
does not fill: whether it crosses the lock is a market fact, established at
fill time from the whole session's bar. So the naive backtest books an exit
it could never have achieved and makes risk management look free; Plutus
shows the identical gap one layer later, in the fill, not the admission.

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
closes at its floor (17.70). ``band_lock_decision`` grades a lock from the
whole daily bar, not the close alone (see fills.py): DIG's real 2022-10-31 bar
is O=18.50 H=18.70 L=17.70 C=17.70, volume 19,026,400 — it closed AT the floor
but *traded through* it earlier (high 18.70 > floor), so it is not a proven
lock. Nor does any ticker-day in the shipped corpus prove one
(``quote_dailyvolume`` never records a literal 0; corpus-wide minimum traded
quantity is 1 share). So 2022-10-31's bar is overridden here to a hand-built
full-session collapse at DIG's own real floor that day (17.70, unchanged from
the real corpus) with zero volume — the genuine lock this scenario's delta
depends on, per this task's brief ("if it hand-builds the interval/state:
set ... ==floor ... and volume=0").

EXPECTED — Tier 2
    * Naive arm: the stop "fills at the close" — it exits, booking proceeds and
      going flat.
    * Plutus arm: the same stop is Accepted — admitted into the book — but
      does not fill on the (hand-built) locked day: no fill event, no exit,
      the position is still held, riding the drawdown.
    * The delta is the whole position: naive holds 0, Plutus holds 1,000. Only
      the *layer* at which the refusal shows up has moved, from admission to
      fill time — naive fills the stop, Plutus admits it but it does not
      fill — the same economic point, one layer later.

RUN
    python scenarios/test_j10_naive_vs_plutus.py
    pytest scenarios/test_j10_naive_vs_plutus.py -v
"""
from __future__ import annotations

from dataclasses import replace
from datetime import date, datetime
from decimal import Decimal

import pytest

from plutus.market.session import ExchangeSession, Accepted, Rejected  # noqa: F401
from plutus.market.protocol import LockEvidence, Order, Resolution
from plutus.market.adapters.datahub import DataHubSource
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (DataField, OrderRecord, OrderState,
                                         TimeInForce, Venue)
from plutus.core.order import OrderType, Side

from _harness import build_session, data_available, data_root

TICKER = "DIG"
QTY = 1000
CLOSE_ON_LOCK_DAY = Decimal("17.70")   # DIG 2022-10-31 close == floor
BUY_DAY = datetime(2022, 10, 27, 13, 0)
LOCK_DAY = "2022-10-31"
LOCK_DAY_TS = datetime(2022, 10, 31, 13, 0)

CONFIG = {
    "period": {"start": "2022-10-27", "end": "2022-11-01"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-J10"}},
}


class FrozenLockSource(DataHubSource):
    """The live corpus, with one ticker-day's bar overridden to a **proven**
    zero-volume band lock.

    ``band_lock_decision``'s NO_FILL branch requires ``interval.volume == 0``
    exactly — a *proven* lock, distinct from a lock whose volume is merely
    unknown (INDETERMINATE). The Hermes corpus's ``quote_dailyvolume`` table
    never records a literal 0 anywhere (corpus-wide minimum non-null
    quantity is 1 share): a no-trade day simply carries no row, which this
    adapter reports as ``volume=None`` — UNKNOWN, not zero. So no ticker-day
    in the live corpus can produce that proof, and this task's brief
    sanctions the fallback: "if it hand-builds the interval/state: set
    open==high==low==close==ceiling/floor and volume=0."

    Every ticker-day except the one named here is served untouched, straight
    off the real corpus — the instrument spec, admission, and every other
    day's fill all stay genuine. Only the named day's bar is overridden, and
    only ``open``/``high``/``low``/``close``/``volume``/``last`` change: the
    real ceiling/floor/reference for that day (already real HSX ±7% band
    arithmetic) are kept as-is.
    """

    def __init__(self, root, *, ticker: str, day: str, side: Side):
        super().__init__(root)
        self._ticker = ticker
        self._day = date.fromisoformat(day)
        self._side = side

    def _is_locked(self, ticker, ts) -> bool:
        d = ts.date() if isinstance(ts, datetime) else ts
        return ticker == self._ticker and d == self._day

    def _frozen(self, state):
        edge = state.ceiling if self._side is Side.BUY else state.floor
        return replace(state, last=edge, locked_side=self._side,
                       lock_evidence=LockEvidence.BAR_PROXY)

    def state_at(self, ticker, ts):
        state = super().state_at(ticker, ts)
        if state is None or not self._is_locked(ticker, ts):
            return state
        return self._frozen(state)

    def states(self, ticker, start, end, *, resolution=Resolution.DAILY):
        for state in super().states(ticker, start, end, resolution=resolution):
            yield self._frozen(state) if self._is_locked(ticker, state.ts) else state

    def interval(self, ticker, start, end, *, resolution=Resolution.DAILY):
        interval = super().interval(ticker, start, end, resolution=resolution)
        if interval is None or not self._is_locked(ticker, start):
            return interval
        state = self._frozen(interval.state)
        edge = state.ceiling if self._side is Side.BUY else state.floor
        return replace(
            interval, state=state, open=edge, high=edge, low=edge, close=edge,
            volume=0,
            missing=interval.missing - {DataField.VOLUME, DataField.OPEN,
                                        DataField.HIGH, DataField.LOW,
                                        DataField.CLOSE, DataField.LAST})


def naive_fill_at_close(qty: int, close: Decimal) -> dict:
    """Arm A — what a naive backtester assumes: the stop always fills at the
    session's close, so the position exits and books the proceeds."""
    return {"exited": True, "held_after": 0, "proceeds": close * qty * 1000}


def plutus_arm() -> dict:
    """Arm B — the same stop through the exchange."""
    source = FrozenLockSource(data_root(), ticker=TICKER, day=LOCK_DAY, side=Side.SELL)
    session = build_session(CONFIG, source=source)
    session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=QTY,
                         order_type=OrderType.LIMIT, limit_price=Decimal("19.80")))
    session.advance_to(BUY_DAY)
    session.advance_to(LOCK_DAY_TS)   # settles; the name is (hand-built) floor-locked
    stop = session.submit(Order(ticker=TICKER, side=Side.SELL, quantity=QTY,
                                order_type=OrderType.LIMIT, limit_price=CLOSE_ON_LOCK_DAY))
    # The stop was submitted after the advance above, so it has not yet had a
    # fill-evaluation pass -- advance again (same instant) to give it one.
    events = session.advance_to(LOCK_DAY_TS)
    holding = session.holdings(TICKER)
    held = holding.settled + sum(t.quantity for t in holding.unsettled)

    # Mechanism-level proof, alongside the session-level one: the same
    # (hand-built) interval this session's fill pass saw, fed straight to
    # band_lock_decision, must itself name a proven BAND_LOCK NO_FILL.
    interval = source.interval(TICKER, datetime(2022, 10, 31), datetime(2022, 11, 1))
    order_record = OrderRecord(
        order_id="J10-CHECK", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=LOCK_DAY_TS,
        updated_at=LOCK_DAY_TS, fills=(),
        order=Order(ticker=TICKER, side=Side.SELL, quantity=QTY,
                    order_type=OrderType.LIMIT, limit_price=CLOSE_ON_LOCK_DAY))
    decision = band_lock_decision(order_record, interval)

    return {"stop": stop, "held_after": held, "events": events, "decision": decision}


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_j10_naive_vs_plutus():
    naive = naive_fill_at_close(QTY, CLOSE_ON_LOCK_DAY)
    plutus = plutus_arm()

    # Arm A exits and books proceeds.
    assert naive["exited"] and naive["held_after"] == 0

    # Arm B is admitted -- BAND_LOCK is a fill-time check now, not an
    # admission rule -- but never crosses the (hand-built) floor lock: no
    # fill event.
    stop = plutus["stop"]
    assert isinstance(stop, Accepted), stop
    fills = [e for e in plutus["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == stop.order_id]
    assert not fills, "a stop-loss into a floor lock must not fill"

    # Mechanism-level proof: band_lock_decision itself names a proven
    # BAND_LOCK NO_FILL for this interval, not merely "nothing happened".
    decision = plutus["decision"]
    assert decision is not None and decision.outcome.value == "no_fill", decision
    assert "BAND_LOCK" in decision.reason, decision.reason

    # The delta is the whole position: the naive backtest thinks it is flat;
    # Plutus is still holding, trapped in the drawdown.
    assert plutus["held_after"] == QTY
    assert plutus["held_after"] != naive["held_after"]


if __name__ == "__main__":
    if not data_available():
        raise SystemExit("market-data corpus not found; set PLUTUS_DATA_ROOT")
    naive = naive_fill_at_close(QTY, CLOSE_ON_LOCK_DAY)
    plutus = plutus_arm()
    print("J10 — Naive fill-at-close vs Plutus (DIG floor lock, 2022-10-31 hand-built)")
    print(f"  Arm A naive:  exited={naive['exited']}  held_after={naive['held_after']}")
    stop = plutus["stop"]
    stop_fills = [e for e in plutus["events"]
                 if getattr(e.kind, "value", e.kind) == "filled"
                 and e.order_id == getattr(stop, "order_id", None)]
    print(f"  Arm B Plutus: stop={type(stop).__name__}"
          f"(filled={bool(stop_fills)})  held_after={plutus['held_after']}")
    print(f"  band_lock_decision: {plutus['decision'].outcome.value} — "
          f"{plutus['decision'].reason}")
    print(f"  DELTA: naive holds {naive['held_after']}, Plutus holds {plutus['held_after']} "
          f"— the naive exit is fictional")
    try:
        test_j10_naive_vs_plutus()
        print("  TIER 2: PASS")
    except AssertionError as exc:
        print(f"  TIER 2: FAIL — {exc}")
