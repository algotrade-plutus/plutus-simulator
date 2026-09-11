"""J2 — Momentum chaser into a limit-UP lock: the stock runs, you don't get in.

Scenario **J2** of ``docs/reference/SCENARIO-CATALOGUE.md``, as user code.

MECHANISM — two outcomes a reader conflates, and separating them is the point:
    * BAND_LIMIT: a price *outside* the band is illegal — rejected at entry,
      regardless of the book. A rule.
    * BAND_LOCK: a price *at* the ceiling is legal — admitted, and rests in
      the book. On a locked-up day no ask sits at or below it, so the order
      does not fill. A market fact, established at fill time, not admission.

POLICY (oracle — SCENARIO-CATALOGUE.md J2)
    * Ordinary band HSX ±7% — QĐ 352 Điều 9.6 → VNX QĐ 17 Phụ lục III §1.3,
      eff. 2021-07-05 → current (high).
    * Ceiling = ref + ref×band, rounded DOWN to the quotation unit —
      QĐ 352 Điều 9.1–9.2 (high).
    * A limit-UP lock blocks BUYS only — INFERRED from band arithmetic +
      price-then-time priority; no Vietnamese article states it.

KNOWN OVER-ASSERTION (published with the scenario, per the catalogue):
    On the shipped ``DataHubSource`` — the daily adapter, outdated and slated
    for reimplementation — the lock is inferred from ``close == ceiling``
    alone, which over-asserts ~10×. HPG 2022-11-16 closed at its ceiling
    (13.35) but traded down to 11.80 intraday, so a real tick book would have
    allowed some fills. The strict lock (``open==high==low==close``) lives in
    ``validation/``, not in the shipped library. This scenario therefore tests
    the *shipped proxy* behaviour and declares the over-assertion.

WORKED CASE — HPG, 2022-11-16: reference 12.5, ceiling 13.35, close 13.35.

EXPECTED — Tier 2
    A. BUY above the ceiling (14.00) -> Rejected(BAND_LIMIT): an illegal price,
       a rule, rejected regardless of the book.
    B. BUY at the ceiling (13.35) on a locked-up day -> Accepted: a legal
       price is admitted and rests in the book, but it does not fill on the
       locked day — no fill event is emitted for it. On the daily adapter the
       lock is known (not merely suspected) via ``lock_evidence ==
       'bar_proxy'`` (close == ceiling), so the fill-time check resolves to a
       definite no-fill rather than an INDETERMINATE.
    The teaching point: A and B are DIFFERENT outcomes — an illegal price
    rejected outright vs a legal-but-unfillable one admitted and left
    resting — which a naive backtest conflates into "rejected".

RUN
    python scenarios/test_j2_limit_up_lock.py
    pytest scenarios/test_j2_limit_up_lock.py -v
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
    "period": {"start": "2022-11-16", "end": "2022-11-18"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-J2"}},
}

TICKER = "HPG"
CEILING = Decimal("13.35")
ABOVE_CEILING = Decimal("14.00")
LOCK_DAY_AFTERNOON = datetime(2022, 11, 16, 13, 0)


def run_j2() -> dict:
    session = build_session(CONFIG)

    # A) chase the breakout ABOVE the ceiling — illegal, rejected at entry.
    above = session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                                 order_type=OrderType.LIMIT, limit_price=ABOVE_CEILING))

    # B) submit AT the ceiling — legal, but the book is locked.
    at_ceiling = session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                                      order_type=OrderType.LIMIT, limit_price=CEILING))
    events = session.advance_to(LOCK_DAY_AFTERNOON)

    holding = session.holdings(TICKER)
    held_after = holding.settled + sum(t.quantity for t in holding.unsettled)

    return {"above": above, "at_ceiling": at_ceiling, "events": events,
            "held_after": held_after}


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_j2_limit_up_lock():
    obs = run_j2()

    # A. Above the ceiling: an illegal price — rejected as BAND_LIMIT, a rule.
    above = obs["above"]
    assert isinstance(above, Rejected), above
    assert above.rule.name == "BAND_LIMIT", above.rule

    # B. At the ceiling: a legal price into a locked book — admitted and
    #    rests (BAND_LOCK is now a fill-time refusal, not an admission one).
    #    On the locked-up day it does not fill: the bar proxy (close ==
    #    ceiling) makes the lock a known fact, so the fill policy resolves a
    #    definite no-fill, which emits no event at all. NOT the flattering
    #    free fill.
    at_ceiling = obs["at_ceiling"]
    assert isinstance(at_ceiling, Accepted), at_ceiling
    fills = [e for e in obs["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == at_ceiling.order_id]
    assert not fills, "a buy into a limit-up lock must not fill"
    assert obs["held_after"] == 0, "the buy into the lock must not have filled"


if __name__ == "__main__":
    if not data_available():
        raise SystemExit("market-data corpus not found; set PLUTUS_DATA_ROOT")
    obs = run_j2()
    above, at_ceiling = obs["above"], obs["at_ceiling"]
    at_ceiling_fills = [e for e in obs["events"]
                        if getattr(e.kind, "value", e.kind) == "filled"
                        and e.order_id == getattr(at_ceiling, "order_id", None)]
    print("J2 — Momentum chaser into a limit-UP lock (HPG 2022-11-16)")
    print(f"  BUY above ceiling (14.00): {type(above).__name__}"
          f"({getattr(above,'rule',None) and above.rule.name})")
    print(f"  BUY at ceiling (13.35):    {type(at_ceiling).__name__}"
          f"(filled={bool(at_ceiling_fills)})")
    try:
        test_j2_limit_up_lock()
        print("  TIER 2: PASS")
    except AssertionError as exc:
        print(f"  TIER 2: FAIL — {exc}")
