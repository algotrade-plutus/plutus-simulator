"""The conservative queue's *taker* arm, fed by the sized tape.

``ConservativeQueue`` puts every displayed share ahead of us, so a level yields
only what traded through it **after** the order arrived, beyond the displayed
size. Without subsequent prints it can decide nothing (``prints=absent``,
``test_book_walk.TestTheQueueAxis``). The maker arm already reads them from the
``TapeSource``. This file pins the policy wiring that hands the same tape to the
taker walk: same tape, same window (order arrival to the interval being judged),
and a provenance string that says where the prints came from.

Runs on the shipped ``strategies/fixtures/extract`` (FPT 2022-11-09), so it never
skips. The ladder at 09:16:05.290870: ask 73.400 x 5,700 | 73.500 x 200 |
73.900 x 1,000.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

import pytest

from plutus.core.order import Side
from plutus.market.adapters.depth import DepthSource
from plutus.market.exchanges.equity import HSX_EXCHANGE
from plutus.market.protocol import (BandSource, InstrumentKind, InstrumentSpec,
                                    MarketState, Order, OrderType, Resolution,
                                    SessionPhase)
from plutus.market.session.book_walk import (BookWalkFillPolicy,
                                             ConservativeQueue, OptimisticQueue)
from plutus.market.session.types import (DataField, FillOutcome, MarketInterval,
                                         OrderRecord, OrderState, TimeInForce,
                                         Venue)

EXTRACT = Path(__file__).resolve().parents[3] / 'strategies' / 'fixtures' / 'extract'
ARRIVED = datetime(2022, 11, 9, 9, 16, 5, 290870)
JUDGED = ARRIVED + timedelta(minutes=3)
HSX_LOT = InstrumentSpec(
    ticker='FPT', exchange_code='HSX', kind=InstrumentKind.STOCK,
    trading_unit=100, daily_trading_limit=Decimal('0.07'))


class FakeTape:
    def __init__(self, prints):
        self.prints = prints
        self.calls = []

    def prints_through(self, ticker, price, side, since, until):
        self.calls.append((ticker, price, side, since, until))
        return self.prints(price) if callable(self.prints) else self.prints


@pytest.fixture(scope='module')
def books():
    return DepthSource(str(EXTRACT), table_prefix='local_quote')


def _policy(books, *, tape, queue=None):
    return BookWalkFillPolicy(books, queue=queue or ConservativeQueue(),
                              max_participation=None, max_staleness=None,
                              tape=tape)


def _decide(policy, *, quantity=1000, limit=Decimal('73.4'), side=Side.BUY):
    order = OrderRecord(
        order_id='O-1', venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=ARRIVED, updated_at=ARRIVED,
        order=Order(ticker='FPT', side=side, quantity=quantity,
                    order_type=OrderType.LIMIT, limit_price=limit))
    state = MarketState(ticker='FPT', ts=JUDGED, session=SessionPhase.CONTINUOUS,
                        reference=Decimal('73.0'), ceiling=Decimal('78.1'),
                        floor=Decimal('67.9'), band_source=BandSource.PUBLISHED,
                        last=Decimal('73.4'))
    interval = MarketInterval(ticker='FPT', start=JUDGED,
                              end=JUDGED + timedelta(seconds=1),
                              resolution=Resolution.TICK, state=state,
                              volume=1_000_000, close=Decimal('73.4'))
    # The book is read as of ARRIVED's ladder: pin it by judging at the instant
    # the ladder is known, via a provider that answers for ARRIVED.
    return policy.evaluate(order, interval, HSX_EXCHANGE, instrument=HSX_LOT)


class _PinnedBooks:
    """The FPT ladder at ARRIVED, whatever instant is asked for, so the tests
    are about the queue arithmetic and not about how the ladder moved."""

    def __init__(self, books):
        self._books = books

    def book_at(self, ticker, ts, **kw):
        return self._books.book_at(ticker, ARRIVED, **kw)


@pytest.fixture(scope='module')
def pinned(books):
    return _PinnedBooks(books)


def test_a_sized_tape_lets_the_conservative_taker_decide(pinned):
    # 7,000 traded through 73.40 since we arrived; 5,700 were displayed ahead.
    d = _decide(_policy(pinned, tape=FakeTape(7000)))
    assert d.outcome is FillOutcome.FILL
    assert d.quantity == 1000


def test_a_queue_that_did_not_clear_is_a_definite_no_fill(pinned):
    # Only 100 traded through: the 5,700 ahead of us did not clear.
    d = _decide(_policy(pinned, tape=FakeTape(100)))
    assert d.outcome is FillOutcome.NO_FILL


def test_an_unserved_tape_stays_indeterminate_naming_volume(pinned):
    d = _decide(_policy(pinned, tape=FakeTape(None)))
    assert d.outcome is FillOutcome.INDETERMINATE
    assert DataField.VOLUME in d.missing


def test_the_tape_is_asked_for_the_resting_side_over_the_orders_own_window(pinned):
    tape = FakeTape(7000)
    _decide(_policy(pinned, tape=tape))
    ticker, price, side, since, until = tape.calls[0]
    assert (ticker, price) == ('FPT', Decimal('73.400000'))
    # A BUY takes asks; what clears an ask is trading at or above it -- the
    # resting SELL's view of "through".
    assert side is Side.SELL
    assert (since, until) == (ARRIVED, JUDGED)


def test_without_a_tape_nothing_changes(pinned):
    d = _decide(_policy(pinned, tape=None))
    assert d.outcome is FillOutcome.INDETERMINATE
    assert DataField.VOLUME in d.missing


def test_provenance_names_where_the_prints_came_from(pinned):
    assert 'queue=conservative(prints=tape)' in _policy(pinned, tape=FakeTape(0)).signature
    assert 'queue=conservative(prints=absent)' in _policy(pinned, tape=None).signature


def test_other_queues_are_untouched_by_a_tape(pinned):
    p = _policy(pinned, tape=FakeTape(0), queue=OptimisticQueue())
    assert 'queue=optimistic' in p.signature
    assert _decide(p).outcome is FillOutcome.FILL
