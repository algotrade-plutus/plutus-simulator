"""J2 — Momentum chaser into a limit-UP lock: the stock runs, you don't get in.

Scenario **J2** of ``docs/reference/SCENARIO-CATALOGUE.md``, as user code.

MECHANISM — two outcomes a reader conflates, and separating them is the point:
    * BAND_LIMIT: a price *outside* the band is illegal — rejected at entry,
      regardless of the book. A rule.
    * BAND_LOCK: a price *at* the ceiling is legal — admitted, and rests in
      the book. Whether it fills is a market fact, established at fill time
      from the whole session's bar, not admission.

POLICY (oracle — SCENARIO-CATALOGUE.md J2)
    * Ordinary band HSX ±7% — QĐ 352 Điều 9.6 → VNX QĐ 17 Phụ lục III §1.3,
      eff. 2021-07-05 → current (high).
    * Ceiling = ref + ref×band, rounded DOWN to the quotation unit —
      QĐ 352 Điều 9.1–9.2 (high).
    * A limit-UP lock blocks BUYS only — INFERRED from band arithmetic +
      price-then-time priority; no Vietnamese article states it.

CORRECTED BEHAVIOUR (was published as a known over-assertion; fixed here):
    ``band_lock_decision`` used to infer a lock from ``close == ceiling``
    alone (Increment 1's proxy), which over-asserted ~10× — it answered
    NO_FILL for every close-at-the-ceiling bar, including the majority that
    had traded below the cap earlier in the session. It now grades from the
    **whole daily bar**: a session that ever traded below the ceiling
    (``low < ceiling``) passes through to the ordinary fill policy; only a
    bar that **collapsed on the ceiling with zero volume**
    (``open==high==low==close==ceiling``, no trade at all) is a proven
    NO_FILL. HPG 2022-11-16 closed at its ceiling (13.35) but traded down to
    11.80 intraday — it *traded through*, so under the corrected contract the
    at-ceiling order now fills. That is case B below. Case C, a true lock
    with zero volume, does not occur anywhere in the shipped corpus (its
    ``quote_dailyvolume`` table never records a literal 0 — a no-trade day
    simply carries no row, i.e. UNKNOWN, not zero — corpus-wide minimum
    traded quantity is 1 share) and is hand-built accordingly, per this
    task's brief.

WORKED CASES
    B. HPG, 2022-11-16: reference 12.5, ceiling 13.35 — closed AT the
       ceiling (13.35) but the session traded down to 11.80: a real book
       would have crossed it. *Traded-through*, not a lock.
    C. HPG, 2022-11-15: reference 12.2, ceiling 13.05 — an ordinary trading
       day in reality (O=12.0 H=12.55 L=12.0 C=12.5, unremarkable), used here
       only as a source of a genuine HSX ceiling; its bar is overridden to
       ``open==high==low==close==13.05``, volume 0 — a hand-built, clearly
       synthetic full-session lock, since the real corpus cannot supply one.

EXPECTED — Tier 2
    A. BUY above the ceiling (14.00) -> Rejected(BAND_LIMIT): an illegal
       price, a rule, rejected regardless of the book.
    B. BUY at the ceiling (13.35) on HPG's traded-through day -> Accepted,
       and now FILLS (evidence TRADED_THROUGH): the corrected behaviour —
       no longer the flattering free no-fill Increment 1 gave every
       close-at-band bar.
    C. BUY at the ceiling (13.05) on the hand-built full-session lock ->
       Accepted: a legal price is admitted and rests in the book, but it
       does not fill — no fill event is emitted for it, and
       ``band_lock_decision`` names the reason ``BAND_LOCK`` with a proven
       zero-volume lock.
    The teaching point: A and B/C are DIFFERENT outcomes — an illegal price
    rejected outright vs a legal price that is either fillable (B) or truly
    locked (C) depending on the *whole bar*, not the close alone — which a
    naive backtest (and Increment 1's own proxy) conflates.

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
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import OrderRecord, OrderState, TimeInForce, Venue
from plutus.core.order import OrderType, Side

from _harness import FrozenLockSource, build_session, data_available, data_root

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

# -- Case C: the hand-built true lock -------------------------------------
#
# See the module docstring's "CORRECTED BEHAVIOUR": no ticker-day in the
# shipped corpus can prove a zero-volume lock (quote_dailyvolume never
# records a literal 0), so this overrides one real, ordinary HSX trading
# day's bar to a synthetic full-session collapse at its own real ceiling.
TRUE_LOCK_CONFIG = {
    "period": {"start": "2022-11-15", "end": "2022-11-17"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-J2C"}},
}
TRUE_LOCK_DAY = "2022-11-15"
TRUE_LOCK_DAY_AFTERNOON = datetime(2022, 11, 15, 13, 0)


def run_j2() -> dict:
    session = build_session(CONFIG)

    # A) chase the breakout ABOVE the ceiling — illegal, rejected at entry.
    above = session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                                 order_type=OrderType.LIMIT, limit_price=ABOVE_CEILING))

    # B) submit AT the ceiling on the traded-through day — legal, and (per
    #    the corrected contract) marketable: the session dipped to 11.80.
    at_ceiling = session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                                      order_type=OrderType.LIMIT, limit_price=CEILING))
    events = session.advance_to(LOCK_DAY_AFTERNOON)

    holding = session.holdings(TICKER)
    held_after = holding.settled + sum(t.quantity for t in holding.unsettled)

    return {"above": above, "at_ceiling": at_ceiling, "events": events,
            "held_after": held_after}


def run_j2_true_lock() -> dict:
    """Case C — the hand-built full-session lock (see module docstring)."""
    source = FrozenLockSource(data_root(), ticker=TICKER, day=TRUE_LOCK_DAY,
                              side=Side.BUY)
    interval = source.interval(TICKER, datetime(2022, 11, 15), datetime(2022, 11, 16))
    ceiling = interval.state.ceiling

    session = build_session(TRUE_LOCK_CONFIG, source=source)
    at_ceiling = session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                                      order_type=OrderType.LIMIT, limit_price=ceiling))
    events = session.advance_to(TRUE_LOCK_DAY_AFTERNOON)

    holding = session.holdings(TICKER)
    held_after = holding.settled + sum(t.quantity for t in holding.unsettled)

    # Mechanism-level proof, alongside the session-level one: the same
    # interval this session's fill pass saw, fed straight to
    # band_lock_decision, must itself name a proven BAND_LOCK NO_FILL.
    order_record = OrderRecord(
        order_id="J2-C-CHECK", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=TRUE_LOCK_DAY_AFTERNOON,
        updated_at=TRUE_LOCK_DAY_AFTERNOON, fills=(),
        order=Order(ticker=TICKER, side=Side.BUY, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=ceiling))
    decision = band_lock_decision(order_record, interval)

    return {"at_ceiling": at_ceiling, "events": events, "held_after": held_after,
            "decision": decision, "ceiling": ceiling}


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_j2_limit_up_lock():
    obs = run_j2()

    # A. Above the ceiling: an illegal price — rejected as BAND_LIMIT, a rule.
    above = obs["above"]
    assert isinstance(above, Rejected), above
    assert above.rule.name == "BAND_LIMIT", above.rule

    # B. At the ceiling on the traded-through day: a legal price, admitted,
    #    and now FILLS — HPG dipped to 11.80 intraday, so a real book would
    #    have crossed a resting buy at 13.35. This is the corrected
    #    behaviour: Increment 1's close==band proxy answered NO_FILL here,
    #    over-asserting a lock the session's own low disproves.
    at_ceiling = obs["at_ceiling"]
    assert isinstance(at_ceiling, Accepted), at_ceiling
    fills = [e for e in obs["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == at_ceiling.order_id]
    assert fills, "a buy into a day that traded through the ceiling must fill"
    assert fills[0].detail["evidence"].value == "traded_through", fills[0].detail
    assert obs["held_after"] == 1000, "the traded-through buy must have filled"


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_j2_true_lock():
    obs = run_j2_true_lock()

    # C. At the ceiling into a hand-built full-session lock: admitted and
    #    rests — BAND_LOCK is a fill-time refusal, not an admission one —
    #    but zero volume traded, so it cannot cross. No fill event at all.
    at_ceiling = obs["at_ceiling"]
    assert isinstance(at_ceiling, Accepted), at_ceiling
    fills = [e for e in obs["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == at_ceiling.order_id]
    assert not fills, "a buy into a true limit-up lock must not fill"
    assert obs["held_after"] == 0, "the buy into the true lock must not have filled"

    # Mechanism-level proof: band_lock_decision itself names a proven
    # BAND_LOCK NO_FILL for this interval, not merely "nothing happened".
    decision = obs["decision"]
    assert decision is not None and decision.outcome.value == "no_fill", decision
    assert "BAND_LOCK" in decision.reason, decision.reason


if __name__ == "__main__":
    if not data_available():
        raise SystemExit("market-data corpus not found; set PLUTUS_DATA_ROOT")
    obs = run_j2()
    above, at_ceiling = obs["above"], obs["at_ceiling"]
    at_ceiling_fills = [e for e in obs["events"]
                        if getattr(e.kind, "value", e.kind) == "filled"
                        and e.order_id == getattr(at_ceiling, "order_id", None)]
    print("J2 — Momentum chaser into a limit-UP lock (HPG 2022-11-16, traded-through)")
    print(f"  BUY above ceiling (14.00): {type(above).__name__}"
          f"({getattr(above,'rule',None) and above.rule.name})")
    print(f"  BUY at ceiling (13.35):    {type(at_ceiling).__name__}"
          f"(filled={bool(at_ceiling_fills)}, held_after={obs['held_after']})")

    obs_c = run_j2_true_lock()
    at_ceiling_c = obs_c["at_ceiling"]
    fills_c = [e for e in obs_c["events"]
              if getattr(e.kind, "value", e.kind) == "filled"
              and e.order_id == getattr(at_ceiling_c, "order_id", None)]
    print("J2 — Case C: hand-built true lock (HPG 2022-11-15, synthetic)")
    print(f"  BUY at ceiling ({obs_c['ceiling']}): {type(at_ceiling_c).__name__}"
          f"(filled={bool(fills_c)}, held_after={obs_c['held_after']})")
    print(f"  band_lock_decision: {obs_c['decision'].outcome.value} — "
          f"{obs_c['decision'].reason}")

    try:
        test_j2_limit_up_lock()
        test_j2_true_lock()
        print("  TIER 2: PASS")
    except AssertionError as exc:
        print(f"  TIER 2: FAIL — {exc}")
