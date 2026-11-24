"""S2 — Leveraged equity momentum, force-sold when a stop can't clear a lock.

Strategy **S2** of ``docs/reference/STRATEGY-BOARD.md``, written as a user writes
it: a real momentum strategy run on borrowed money, against Plutus as broker.

TRADING RATIONALE
    Momentum: strength begets strength. We buy a large-cap on a **breakout** — a
    strong up-day (≥ 5%) after a base — and we do it **on margin** (2:1) to press
    the edge. A disciplined momentum trader carries a **stop**: if it falls back,
    get out. On paper the stop caps the loss.

THE FLAW THE MARKET PUNISHES
    A stop only works if you can *sell*. In a real crash the tape gaps **limit
    down** and locks: everyone is a seller, there are no bids, and your stop
    order rests unfilled (``BAND_LOCK``) day after day while the position
    bleeds. The leverage that pressed the edge now works in reverse. In **Oct
    2022** DIG did exactly this — a breakout on 18 Oct, then a **four-day
    limit-down waterfall** (21–26 Oct, −6.9/−6.8/−6.8/−6.8%). A leveraged long
    can neither be stopped nor cured, the maintenance ratio craters, and the
    broker force-sells (*bán giải chấp*) into the same locked tape.

WHAT THE SIMULATOR MUST GET RIGHT (emergent, not staged)
    The position is built by the breakout signal; the loss is real DIG P&L; the
    margin call and forced sale must **emerge** from the equity-margin algebra;
    and orders into a locked book must **rest unfilled**, never filled at a
    fantasy price.

MECHANISM / POLICY (oracle — SCENARIO-CATALOGUE.md, folded scenarios)
    * Equity margin lending: imr ≥ 50%, mmr ≥ 30% — QĐ 87/QĐ-UBCK Điều 5(1),(2)
      (VERIFIED). Call → cure ≤ 3 business days → forced sale — QĐ 87 Điều 7.1, 8
      (J5). The call/force LEVELS are a broker term, UNSOURCED.
    * A locked book admits an order but rests it unfilled — ``BAND_LOCK`` is a
      fill-time market fact, not an illegal price; the forced sale itself is
      subject to it (J2/J11).
    * Purchases settle T+2, so proceeds and re-entry are gated (J1/J16); the
      leveraged account can run out of purchasing power (J24).

SETUP — DIG (HSX), 2022-09-05 → 2022-11-15, 100,000,000đ cash, 2:1 margin.

EXPECTED — Tier 2
    * Emergence: the breakout signal opens a leveraged long (a loan is drawn,
      margin_debt > 0), and not on day one.
    * A margin CALL is issued as DIG's slide erodes the maintenance ratio.
    * A forced sale FIRES and EXECUTES — the account is sold out, not carried.
    * The exit is graded, not granted: the broker's forced sale is a LIMIT at
      the floor, and on the day DIG sat pinned at its floor all session
      (2022-11-07: O=H=L=C=15.45, 2,477,300 shares matched at the floor) its
      fill rests on ``TOUCHED_AT_LIMIT`` — an assumption about queue position,
      not an observation. ``hard`` refuses to call that sale (INDETERMINATE);
      on a day that traded above the floor both policies fill it.

    CORRECTION (2026-11-24, RIVF'26 camera-ready). An earlier version claimed
    the forced sale was *blocked* by limit-down locks. That rested on the
    ``close == floor`` proxy. With the session high wired, most of DIG's
    floor-close days in this window traded above the floor first, so a daily
    bar proves no block, and this test claims only the graded fill above.
    The block itself is measured from the sell queue, which a daily bar cannot
    see, in ``measurements/s2_lock_queue.py`` (pinned by
    ``test_s2_lock_queue.py``): on 2022-11-07, the day S2's broker sold at the
    floor, 8,657,000 shares were queued ahead at 10:00 and 775,000 traded
    afterwards, so that sale could not have filled unless >91% of the queue
    cancelled first. The daily run's fill there is the assumption it is graded as.

RUN
    .venv/bin/python strategies/test_s2_equity_margin_momentum.py
    .venv/bin/python -m pytest strategies/test_s2_equity_margin_momentum.py -v
"""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

import pytest

from plutus.market.adapters.datahub import DataHubSource
from plutus.market.session import ExchangeSession, Accepted, Venue  # noqa: F401
from plutus.market.session.calendar import weekday_settlement_calendar
from plutus.market.session.equity_margin import EquityMarginAccount
from plutus.market.session.types import FillEvidence
from plutus.market.session.margin_lending import (
    BrokerMarginTerms, DayCount, ForcedSalePrice, InterestTier,
    LiquidationOrder, MarginEligibility, ProceedsComponent, SecurityEligibility)
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side

from _harness import (build_session, data_available, data_root, CorpusFeed,
                      Strategy, Context, run)

TICKER = "DIG"
START = date(2022, 9, 5)
END = date(2022, 11, 15)

BREAKOUT_PCT = Decimal("0.05")     # a strong up-day: momentum entry trigger
LEVERAGE = Decimal("1.8")          # press the edge on borrowed money (imr 50% floor)
LOT = 100                          # HSX round lot (post-2021)
INITIAL_CASH = 100_000_000
PRICE_SCALE = 1000                 # corpus prices are in thousands of đồng (27.0 == 27,000đ)

# The two days the graded-exit check compares (DB daily bars, thousands of đồng):
FULL_FLOOR_DAY = date(2022, 11, 7)   # O=H=L=C=floor 15.45; 2,477,300 matched at the floor
TRADEABLE_DAY = date(2022, 10, 20)   # floor 24.30, high 26.25: traded well above the floor

CONFIG = {
    "period": {"start": "2022-09-05", "end": "2022-11-15"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": INITIAL_CASH,
                                "account_no": "SEC-S2"}},
}


def _held(session: ExchangeSession, ticker: str) -> int:
    h = session.holdings(ticker)
    unsettled = sum((t.quantity for t in getattr(h, "unsettled", ()) or ()), 0)
    return int(getattr(h, "settled", 0) or 0) + int(unsettled)


class LeveragedMomentum(Strategy):
    """Buy a breakout on 2:1 margin and hold. The stop is the broker's."""

    name = "leveraged equity momentum"

    def __init__(self, ticker=TICKER, *, breakout=BREAKOUT_PCT, leverage=LEVERAGE,
                 lot=LOT, cash=INITIAL_CASH, start=START):
        self.ticker = ticker
        self.breakout = breakout
        self.leverage = leverage
        self.lot = lot
        self.cash = Decimal(cash)
        self.start = start
        self.account: EquityMarginAccount | None = None
        self.entered = False

    def on_day(self, ctx: Context) -> None:
        s, feed, day = ctx.session, ctx.feed, ctx.day

        # Already carrying the position? Hold — a momentum trader rides the
        # trend and lets the (broker's) stop do the work.
        if _held(s, self.ticker) > 0:
            return

        closes = feed.closes_before(self.ticker, day, 2, start=self.start)
        if len(closes) < 2:
            return
        prev, prev2 = closes[-1], closes[-2]
        if prev2 == 0:
            return
        ret = (prev - prev2) / prev2
        if ret < self.breakout:
            return                                   # no breakout -> no entry

        # Size to ~leverage x cash (in đồng — the price field is in thousands)
        # and buy the breakout on margin with a market order (MTL/MP, legal on
        # HSX): it fills at the print, and on a locked book it rests unfilled,
        # which is the point.
        target_notional = self.leverage * self.cash
        shares = int((target_notional / (prev * PRICE_SCALE)) // self.lot) * self.lot
        if shares <= 0:
            return
        verdict = s.submit(Order(
            ticker=self.ticker, side=Side.BUY, quantity=shares,
            order_type=OrderType.MARKET_WITH_LEFTOVER_AS_LIMIT, on_margin=True))
        if isinstance(verdict, Accepted):
            self.entered = True
        else:
            ctx.ledger.record_reject(day, verdict)


def _make_account(source) -> EquityMarginAccount:
    terms = BrokerMarginTerms(
        maintenance_margin_ratio=Decimal("0.40"),    # broker call level (UNSOURCED)
        liquidation_margin_ratio=Decimal("0.30"),    # broker force level (UNSOURCED)
        forced_sale_price=ForcedSalePrice.FLOOR,
        day_count=DayCount.ACT_365,
        liquidation_order=LiquidationOrder.LARGEST_POSITION_FIRST,
        proceeds_application_order=tuple(ProceedsComponent),
        initial_margin_ratio=Decimal("0.50"),        # QĐ 87 Điều 5(1) floor
        rate_schedule=(InterestTier(0, None, Decimal("0.135")),))
    eligibility = {TICKER: SecurityEligibility(
        ticker=TICKER, as_of=START, result=MarginEligibility.ELIGIBLE,
        venue=Venue.HSX, on_broker_list=True, note="ASSERTED by this strategy")}
    return EquityMarginAccount(
        account_id="KQ-S2", terms=terms, calendar=weekday_settlement_calendar(),
        market_feed=source.state_at, eligibility=eligibility, tickers=(TICKER,),
        execute_forced_sale=True)


def run_s2():
    source = DataHubSource.for_root(data_root())
    session = build_session(CONFIG, source=source)
    account = _make_account(source)
    session.attach_equity_margin(account)

    feed = CorpusFeed(source=source)
    strategy = LeveragedMomentum()
    strategy.account = account
    ledger = run(strategy, session=session, feed=feed,
                 start=START, end=END, universe=[TICKER])
    ledger.strategy = strategy
    ledger.account = account
    return ledger


def _count_events(account, kind_value: str) -> int:
    return sum(1 for e in account.events
               if getattr(e.kind, "value", e.kind) == kind_value)


def _sale_at_floor(sell_day: date, fill_policy: dict):
    """Hold real DIG, then offer it at the floor on ``sell_day`` under
    ``fill_policy`` -- the order the broker's forced sale sends
    (``ForcedSalePrice.FLOOR``). Returns the held quantity, the verdict, the
    sale's own events from evaluating it, and the quantity still held after.

    The setup buy is a LIMIT at 2022-10-04's ceiling rather than a market order,
    so it fills under ``hard`` too (``hard`` never fills the market family: the
    depth it would walk is not observable). The buy is not the point."""
    src = DataHubSource.for_root(data_root())
    session = build_session(
        {**CONFIG, "period": {"start": "2022-10-03", "end": "2022-11-15"},
         "fill_policy": fill_policy},
        source=src)
    buy_time = datetime(2022, 10, 4, 11, 0)
    session.advance_to(buy_time)
    session.submit(Order(ticker=TICKER, side=Side.BUY, quantity=2000,
                         order_type=OrderType.LIMIT,
                         limit_price=src.state_at(TICKER, buy_time).ceiling))
    session.advance_to(datetime(2022, 10, 4, 14, 0))
    session.advance_to(datetime(2022, 10, 11, 11, 0))     # settle T+2
    held = int(getattr(session.holdings(TICKER), "settled", 0) or 0)
    sell_time = datetime(sell_day.year, sell_day.month, sell_day.day, 11, 0)
    floor = src.state_at(TICKER, sell_time).floor
    session.advance_to(sell_time)
    verdict = session.submit(Order(ticker=TICKER, side=Side.SELL,
                                   quantity=held or 1000,
                                   order_type=OrderType.LIMIT, limit_price=floor))
    # The sell was submitted after the advance above, so it has not had a
    # fill-evaluation pass yet -- the bar is evaluated by the advance that
    # lands inside its day (see ExchangeSession.advance_to).
    events = session.advance_to(sell_time)
    own = [e for e in events
           if e.order_id == getattr(verdict, "order_id", None)]
    return held, verdict, own, _held(session, TICKER)


def _kinds(events) -> list:
    return [getattr(e.kind, "value", e.kind) for e in events]


def _evidence(events):
    return [(e.detail or {}).get("evidence") for e in events
            if getattr(e.kind, "value", e.kind) == "filled"]


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_s2_equity_margin_momentum():
    ledger = run_s2()
    account = ledger.account

    # Tier 1 — it ran and it traded on margin.
    assert ledger.strategy.entered, "the breakout signal never opened a position"

    # Emergence — a loan was drawn from the signal, and a call emerged from DIG's slide.
    assert account.draws, "no margin loan was drawn"
    assert account.calls(), "no margin call emerged from the drawdown"

    # Forced — the broker sold the account out, and it executed (real orders,
    # real completions), not merely reported.
    assert account.forced_sale_orders, "no forced sale order was placed"
    assert _count_events(account, "forced_sale_result_sent") >= 1, \
        "the forced sale never completed a sale"

    # The forced sale is graded by its evidence. (The former check here,
    # ``instructed > completed``, passed for a bookkeeping reason: each tranche
    # logs FORCED_SALE_INSTRUCTED twice, once unrounded at the 15:00 notice and
    # once lot-rounded at the next open.) On the pinned-at-floor day the fill
    # is an assumption, and the run must say so rather than call it traded.
    forced_ids = {getattr(o, "order_id", o) for o in account.forced_sale_orders}
    forced_fills = [e for _, e in ledger.events
                    if e.order_id in forced_ids
                    and getattr(e.kind, "value", e.kind) == "filled"]
    assert forced_fills, "no forced-sale fill was recorded"
    touched = [e for e in forced_fills
               if (e.detail or {}).get("evidence") is FillEvidence.TOUCHED_AT_LIMIT]
    assert any(e.ts.date() == FULL_FLOOR_DAY for e in touched), \
        "the forced sale on the pinned-at-floor day was not graded TOUCHED_AT_LIMIT"

    # The leverage did its work in reverse: the account was blown up.
    start_eq, end_eq = ledger.equity_curve[0][1], ledger.equity_curve[-1][1]
    assert end_eq < start_eq / 2, f"no blow-up: {start_eq} -> {end_eq}"


@pytest.mark.skipif(not data_available(),
                    reason="market-data corpus not found; set PLUTUS_DATA_ROOT")
def test_s2_floor_sale_is_graded_by_evidence():
    """J11's contract on real DIG data, graded by evidence.

    A sale at the floor is a legal price: admitted, never refused at entry.
    Whether it fills is a market fact the data may not settle. On 2022-11-07
    DIG was pinned at its floor all session, and sellers did get out
    (2,477,300 shares matched at 15.45), but whether *this* order was reached
    depends on the sell queue ahead of it, which no 2022 data records. So:
    ``soft`` fills it and labels the fill TOUCHED_AT_LIMIT (an assumption);
    ``hard`` refuses to call it (INDETERMINATE) and the position stays held.
    On a day that traded above the floor both fill it, TRADED_THROUGH."""
    soft = {"kind": "soft", "max_participation": 0.10}
    hard = {"kind": "hard", "max_participation": 0.10}

    for policy in (soft, hard):
        for day in (FULL_FLOOR_DAY, TRADEABLE_DAY):
            held, verdict, _, _ = _sale_at_floor(day, policy)
            assert held > 0, (policy["kind"], day, "setup buy never settled")
            assert isinstance(verdict, Accepted), \
                (policy["kind"], day, "a sale at the floor was refused at entry")

    # Pinned-at-floor day.
    _, _, ev, _ = _sale_at_floor(FULL_FLOOR_DAY, soft)
    assert _evidence(ev) == [FillEvidence.TOUCHED_AT_LIMIT], \
        f"soft on the pinned day must fill as an assumption, got {_kinds(ev)} {_evidence(ev)}"

    held, _, ev, after = _sale_at_floor(FULL_FLOOR_DAY, hard)
    assert "filled" not in _kinds(ev) and "indeterminate" in _kinds(ev), \
        f"hard must refuse to call the pinned-day sale, got {_kinds(ev)}"
    assert after == held, "hard: the position must still be held"

    # Tradeable day: both policies fill, on observed evidence, and clear it.
    for policy in (soft, hard):
        _, _, ev, after = _sale_at_floor(TRADEABLE_DAY, policy)
        assert _evidence(ev) == [FillEvidence.TRADED_THROUGH], \
            (policy["kind"], _kinds(ev), _evidence(ev))
        assert after == 0, (policy["kind"], "the sale must clear the position")


if __name__ == "__main__":
    if not data_available():
        raise SystemExit("market-data corpus not found; set PLUTUS_DATA_ROOT")
    ledger = run_s2()
    acc = ledger.account
    print("S2 — Leveraged equity momentum, force-sold (DIG, Sep–Nov 2022)")
    print(f"  {ledger.summary()}")
    print(f"  margin debt drawn:   {acc.margin_debt:,}")
    print(f"  determinations:      {len(acc.determinations)} sessions assessed")
    print(f"  margin calls:        {len(acc.calls())}")
    print(f"  forced sale: instructed {_count_events(acc,'forced_sale_instructed')}, "
          f"completed {_count_events(acc,'forced_sale_result_sent')} "
          f"(each tranche is logged twice)")
    for label, test in (("lifecycle", test_s2_equity_margin_momentum),
                        ("floor sale graded by evidence (J11)",
                         test_s2_floor_sale_is_graded_by_evidence)):
        try:
            test()
            print(f"  TIER 2 [{label}]: PASS")
        except AssertionError as exc:
            print(f"  TIER 2 [{label}]: FAIL — {exc}")
