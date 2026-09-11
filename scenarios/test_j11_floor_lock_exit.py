"""J11 — Floor-lock on the exit: a stop-loss that cannot fill.

Scenario **J11** of ``docs/reference/SCENARIO-CATALOGUE.md``, as user code.
The mirror of J2, with a sharper edge: **there is no order type in Vietnam
that gets you out at any price once a name is floor-locked.** You hold it, it
craters to the floor and locks, and your stop-loss rests unfilled.

MECHANISM
    * BAND_LIMIT: a sell *below* the floor is an illegal price — a rule,
      rejected at entry.
    * BAND_LOCK: a sell *at* the floor on a locked-down day is a legal price
      — admitted, and rests in the book. With no bid beneath it, it does not
      fill. A market fact, established at fill time, not admission.

POLICY (oracle — SCENARIO-CATALOGUE.md J11)
    * Floor = ref − ref×band, rounded UP — QĐ 352 Điều 9.1–9.2, eff.
      2021-07-05 → current (high).
    * No synthetic market-at-floor order exists in Vietnam at any date —
      negative finding across all four rulebooks (sourced absence, high).
    * Floor lock blocks the exit — INFERRED (band arithmetic + price-then-time
      priority); no Vietnamese article states it.

WORKED CASE — DIG, Oct 2022 selloff. Buy 2022-10-27 (close 19.80, tradeable),
hold; the lot settles 2022-10-31, which closes at its floor (17.70) — locked
down. The stop-loss rests, unable to get out.

EXPECTED — Tier 2
    1. BUY 2022-10-27 accepted and settles by 2022-10-31.
    2. On the locked-down day, SELL at the floor (17.70) -> Accepted: admitted
       and rests, but does not fill — no fill event is emitted for it. The
       stop-loss that cannot get out.
    3. SELL below the floor (17.00) -> Rejected(BAND_LIMIT) — an illegal
       price, a different and still-immediate refusal.

RUN
    python scenarios/test_j11_floor_lock_exit.py
    pytest scenarios/test_j11_floor_lock_exit.py -v
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from plutus.market.session import ExchangeSession, Accepted, Rejected  # noqa: F401
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side

from _harness import build_session, data_available

CONFIG = {
    "period": {"start": "2022-10-27", "end": "2022-11-01"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-J11"}},
}

TICKER = "DIG"
BUY_DAY_AFTERNOON = datetime(2022, 10, 27, 13, 0)
LOCK_DAY_AFTERNOON = datetime(2022, 10, 31, 13, 0)   # T+2 settlement, and floor-locked
FLOOR = Decimal("17.70")
BELOW_FLOOR = Decimal("17.00")


def run_j11() -> dict:
    session = build_session(CONFIG)

    # Get in while it still trades, then hold.
    buy = session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("19.80")))
    session.advance_to(BUY_DAY_AFTERNOON)          # buy fills
    settle_events = session.advance_to(LOCK_DAY_AFTERNOON)  # T+2 settles, on the locked day

    # The name is floor-locked. Try to get out.
    sell_at_floor = session.submit(Order(ticker=TICKER, side=Side.SELL, quantity=1000,
                                         order_type=OrderType.LIMIT, limit_price=FLOOR))
    sell_below = session.submit(Order(ticker=TICKER, side=Side.SELL, quantity=1000,
                                      order_type=OrderType.LIMIT, limit_price=BELOW_FLOOR))
    # Both sells were submitted after the advance above, so neither has had a
    # fill-evaluation pass yet -- the bar is evaluated by the advance that
    # lands inside its day (see ExchangeSession.advance_to). A second advance,
    # same instant, gives the resting sell its chance to cross the lock.
    events = session.advance_to(LOCK_DAY_AFTERNOON)

    holding = session.holdings(TICKER)
    held_after = holding.settled + sum(t.quantity for t in holding.unsettled)

    return {"buy": buy, "settle_events": settle_events,
            "sell_at_floor": sell_at_floor, "sell_below": sell_below,
            "events": events, "held_after": held_after}


def _settled(events):
    return [e for e in events if getattr(e.kind, "value", e.kind) == "settlement_credited"]


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_j11_floor_lock_exit():
    obs = run_j11()

    # 1. Bought and settled by the locked day.
    assert isinstance(obs["buy"], Accepted), obs["buy"]
    assert _settled(obs["settle_events"]), "the lot never settled"

    # 2. Sell at the floor into a locked-down book: admitted and rests --
    #    BAND_LOCK is now a fill-time refusal, not an admission one -- and
    #    with no bid beneath the floor it does not fill. No fill event, and
    #    the position stays fully held: the stop-loss that cannot get out.
    at_floor = obs["sell_at_floor"]
    assert isinstance(at_floor, Accepted), at_floor
    fills = [e for e in obs["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == at_floor.order_id]
    assert not fills, "a sell into a floor lock must not fill"
    assert obs["held_after"] == 1000, "the position must still be held -- it never got out"

    # 3. Sell below the floor -> BAND_LIMIT (illegal price), a different,
    #    still-immediate refusal.
    below = obs["sell_below"]
    assert isinstance(below, Rejected), below
    assert below.rule.name == "BAND_LIMIT", below.rule
    assert type(at_floor) is not type(below)


if __name__ == "__main__":
    if not data_available():
        raise SystemExit("market-data corpus not found; set PLUTUS_DATA_ROOT")
    obs = run_j11()
    af, bl = obs["sell_at_floor"], obs["sell_below"]
    af_fills = [e for e in obs["events"]
               if getattr(e.kind, "value", e.kind) == "filled"
               and e.order_id == getattr(af, "order_id", None)]
    print("J11 — Floor-lock on the exit (DIG, Oct 2022)")
    print(f"  BUY 10-27:            {type(obs['buy']).__name__}")
    print(f"  settled by 10-31:     {bool(_settled(obs['settle_events']))}")
    print(f"  SELL at floor (17.70):{type(af).__name__}"
          f"(filled={bool(af_fills)}, held_after={obs['held_after']})")
    print(f"  SELL below (17.00):   {type(bl).__name__}"
          f"({getattr(bl,'rule',None) and bl.rule.name})")
    try:
        test_j11_floor_lock_exit()
        print("  TIER 2: PASS")
    except AssertionError as exc:
        print(f"  TIER 2: FAIL — {exc}")
