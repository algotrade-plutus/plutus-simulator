"""A hand-written market and a session over it, for the property tests.

Everything here goes through the engine's public entry points --
``ExchangeSession.from_mapping`` / ``build``, ``advance_to``, ``submit``,
``holdings``, ``cash`` -- so a property that holds here holds for a caller.
The oracles (tick grid, band width, lot) are written out **independently** of
the engine from the rulebook document, not read back from ``rulebook.py``:
an oracle that called the code under test would make every property a
tautology.
"""

from datetime import date, datetime, timedelta
from decimal import ROUND_CEILING, ROUND_FLOOR, Decimal
from typing import Mapping, Optional, Tuple

from plutus.core.order import OrderType, Side
from plutus.market.protocol import (BandSource, InstrumentKind,
                                    InstrumentSpec, MarketState, Order,
                                    SessionPhase)
from plutus.market.session import ExchangeSession, parse_config
from plutus.market.session.calendar import (weekday_settlement_calendar,
                                            weekday_trading_calendar)

D = Decimal

#: One ordinary stock per cash venue. The names are stand-ins; only the venue
#: the stub classifies them on matters.
TICKER = {'HSX': 'FPT', 'HNX': 'SHS', 'UPCOM': 'ABC'}
KINDS = {t: (v, InstrumentKind.STOCK) for v, t in TICKER.items()}

#: The rulebook window. Outside it the engine refuses to extrapolate.
COVERAGE_START = date(2020, 1, 1)
COVERAGE_END = date(2026, 8, 25)

#: QD 894/QD-SGDHCM: HOSE's round lot is 10 until 2021-01-03, 100 from here.
HSX_LOT_CHANGE = date(2021, 1, 4)

#: VSD QD 109 Art. 4: from this date shares reach the client at 13:00 on T+2.
SETTLEMENT_1300_FROM = date(2022, 8, 29)

#: The dated tick revision the paper cites (Vo & Doan 2023). Before the
#: rulebook window, so the engine carries no grid on either side of it.
TICK_REVISION_2016 = date(2016, 9, 12)


# --------------------------------------------------------------------------
# Oracles, from docs/reference/citable/vn-exchange-rulebook-2020-2026.md
# --------------------------------------------------------------------------

def oracle_tick(venue: str, price: Decimal) -> Decimal:
    """The matched-order stock tick, in thousand VND.

    HOSE: three tiers, breakpoints inclusive-below -- <10 -> 0.01,
    10..49.95 -> 0.05, >=50 -> 0.1 (QD 352 Dieu 8.4(a); unchanged 2020-2026).
    HNX and UPCoM: flat 100d = 0.1.
    """
    if venue == 'HSX':
        if price < 10:
            return D('0.01')
        if price < 50:
            return D('0.05')
        return D('0.1')
    return D('0.1')


def on_grid(venue: str, price: Decimal) -> bool:
    return price > 0 and price % oracle_tick(venue, price) == 0


def oracle_band(venue: str) -> Decimal:
    """Ordinary daily band: HSX 7 %, HNX 10 %, UPCoM 15 %, all 2020-2026."""
    return {'HSX': D('0.07'), 'HNX': D('0.10'), 'UPCOM': D('0.15')}[venue]


#: Widened bands: (case, venue) -> (width, in force from).
WIDENED = {
    ('first_trading_day', 'HSX'): (D('0.20'), date(2021, 7, 5)),
    ('first_trading_day', 'HNX'): (D('0.30'), date(2022, 3, 31)),
    ('first_trading_day', 'UPCOM'): (D('0.40'), date(2022, 11, 16)),
    ('resumption', 'HSX'): (D('0.20'), date(2021, 7, 5)),
    ('resumption', 'HNX'): (D('0.30'), date(2022, 3, 31)),
}


def oracle_lot(venue: str, on: date) -> int:
    if venue == 'HSX' and on < HSX_LOT_CHANGE:
        return 10
    return 100


def next_up(venue: str, price: Decimal) -> Decimal:
    """The smallest on-grid price strictly above ``price``."""
    p = price + D('0.001')
    while not on_grid(venue, p):
        p += D('0.001')
    return p


def next_down(venue: str, price: Decimal) -> Decimal:
    """The largest on-grid price strictly below ``price``."""
    p = price - D('0.001')
    while not on_grid(venue, p):
        p -= D('0.001')
    return p


def band_edges(venue: str, reference: Decimal,
               width: Decimal) -> Tuple[Decimal, Decimal]:
    """Published ceiling / floor: truncate inward to the tick of the result."""
    raw_c = reference * (1 + width)
    raw_f = reference * (1 - width)
    tc = oracle_tick(venue, raw_c)
    tf = oracle_tick(venue, raw_f)
    ceiling = (raw_c / tc).to_integral_value(rounding=ROUND_FLOOR) * tc
    floor = (raw_f / tf).to_integral_value(rounding=ROUND_CEILING) * tf
    return ceiling, floor


# --------------------------------------------------------------------------
# The market and the session
# --------------------------------------------------------------------------

class StubSource:
    """A ``MarketDataSource`` over a dict of daily states."""

    def __init__(self, rows: Mapping[Tuple[str, date], MarketState]):
        self._rows = dict(rows)

    def state_at(self, ticker, ts):
        return self._rows.get((ticker, ts.date()))

    def states(self, ticker, start, end, *, resolution=None):
        for (name, _), state in sorted(self._rows.items(),
                                       key=lambda kv: kv[0][1]):
            if name == ticker:
                yield state

    def instrument(self, ticker):
        code, kind = KINDS.get(ticker, ('', InstrumentKind.UNKNOWN))
        return InstrumentSpec(ticker=ticker, exchange_code=code, kind=kind,
                              trading_unit=100,
                              daily_trading_limit=D('0.07'))


def state(ticker: str, day: date, last: Decimal, *,
          ceiling: Optional[Decimal] = None,
          floor: Optional[Decimal] = None) -> MarketState:
    """One day's state. Default band is so wide it never binds."""
    return MarketState(
        ticker=ticker, ts=datetime.combine(day, datetime.min.time()),
        reference=last,
        ceiling=ceiling if ceiling is not None else D('100000'),
        floor=floor if floor is not None else D('0.001'),
        band_source=BandSource.PUBLISHED, last=last,
        session=SessionPhase.CONTINUOUS)


def session(rows, start: date, *, days: int = 10, cash: int = 10**12,
            holdings: Optional[Mapping[str, int]] = None,
            venues=('HSX', 'HNX', 'UPCOM')) -> ExchangeSession:
    """A soft-fill session over ``rows`` with weekday calendars injected.

    Calendars are injected because the pre-2022-08-29 settlement branch
    refuses to guess without one; weekday calendars keep the properties
    about the rules and not about Tet.
    """
    payload = {
        'period': {'start': start.isoformat(),
                   'end': (start + timedelta(days=days)).isoformat()},
        'resolution': '1d',
        'exchange_rules': {'venues': list(venues), 'rulebook': 'vn-2020-2026'},
        'broker_profile': {'name': 'prop'},
        'accounts': {'securities': {'initial_cash': cash},
                     'derivatives': {'initial_deposit': 0}},
        'fill_policy': {'kind': 'soft'},
        'data': {'adapter': '', 'root': ''},
    }
    return ExchangeSession.build(
        parse_config(payload), source=StubSource(rows),
        settlement=weekday_settlement_calendar(),
        trading=weekday_trading_calendar(),
        initial_holdings=holdings)


def limit(ticker: str, side: Side, quantity: int, price: Decimal) -> Order:
    return Order(ticker=ticker, side=side, quantity=quantity,
                 order_type=OrderType.LIMIT, limit_price=price)


def at(day: date, hh: int = 10, mm: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hh, mm)


def weekday_on_or_after(day: date) -> date:
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day
