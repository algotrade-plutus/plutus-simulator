"""DataHubSource.state_at answers from a per-(ticker, day) cache.

A daily state is a fact about the whole day, and the session asks for it about six
times per tick (observe, interval, margin marks). Profiling one MarketMaker session
put 84% of its time in re-running the same day's SQL. The cache must not change
any answer: it is keyed by ticker and calendar day, and MarketState is frozen.
"""
from datetime import date, datetime
from pathlib import Path

from plutus.market.adapters.datahub import DataHubSource

ROOT = Path(__file__).resolve().parents[2] / 'strategies' / 'fixtures' / 'parquet'
DAY = date(2022, 11, 9)


def _counting(src):
    calls = []
    original = src._fetch

    def fetch(*args, **kwargs):
        calls.append(args[:3])
        return original(*args, **kwargs)
    src._fetch = fetch
    return calls


def test_one_day_is_fetched_once_however_often_it_is_asked():
    src = DataHubSource.for_root(str(ROOT))
    calls = _counting(src)
    first = src.state_at('FPT', datetime(2022, 11, 9, 9, 30))
    for minute in range(1, 30):
        assert src.state_at('FPT', datetime(2022, 11, 9, 10, minute)) is first
    assert len(calls) == 1


def test_the_cached_answer_is_the_uncached_answer():
    cached = DataHubSource.for_root(str(ROOT))
    cached.state_at('FPT', datetime(2022, 11, 9, 9, 30))
    fresh = DataHubSource.for_root(str(ROOT))
    for ticker in ('FPT', 'DIG', 'VN30F2212'):
        for day in (DAY, date(2022, 11, 10), date(2022, 11, 12)):  # 11-12 is a Saturday
            assert cached.state_at(ticker, day) == fresh.state_at(ticker, day)


def test_another_ticker_or_day_is_a_separate_entry():
    src = DataHubSource.for_root(str(ROOT))
    calls = _counting(src)
    src.state_at('FPT', DAY)
    src.state_at('FPT', date(2022, 11, 10))
    src.state_at('DIG', DAY)
    src.state_at('FPT', DAY)
    assert len(calls) == 3


def test_a_day_with_no_bar_is_cached_as_none():
    src = DataHubSource.for_root(str(ROOT))
    calls = _counting(src)
    assert src.state_at('FPT', date(2022, 11, 12)) is None
    assert src.state_at('FPT', date(2022, 11, 12)) is None
    assert len(calls) == 1


# --------------------------------------------------------------------------
# interval(): the day's bar data is fetched once per (ticker, day); each call
# still builds its own MarketInterval with its own start/end.
# --------------------------------------------------------------------------

def _counting_both(src):
    calls = {'fetch': 0, 'ohlc': 0}
    f, o = src._fetch, src._ohlc

    def fetch(*a, **k):
        calls['fetch'] += 1
        return f(*a, **k)

    def ohlc(*a, **k):
        calls['ohlc'] += 1
        return o(*a, **k)
    src._fetch, src._ohlc = fetch, ohlc
    return calls


def test_many_intervals_on_one_day_query_the_day_once():
    src = DataHubSource.for_root(str(ROOT))
    calls = _counting_both(src)
    for minute in range(30):
        src.interval('FPT', datetime(2022, 11, 9, 9, minute), datetime(2022, 11, 9, 15))
    assert calls == {'fetch': 1, 'ohlc': 1}


def test_each_interval_keeps_its_own_window_and_equals_the_uncached_one():
    cached = DataHubSource.for_root(str(ROOT))
    cached.interval('FPT', datetime(2022, 11, 9, 9, 0), datetime(2022, 11, 9, 15))
    a = cached.interval('FPT', datetime(2022, 11, 9, 10, 0), datetime(2022, 11, 9, 14))
    fresh = DataHubSource.for_root(str(ROOT)).interval(
        'FPT', datetime(2022, 11, 9, 10, 0), datetime(2022, 11, 9, 14))
    assert a == fresh
    assert (a.start, a.end) == (datetime(2022, 11, 9, 10, 0), datetime(2022, 11, 9, 14))


def test_an_absent_day_interval_is_none_and_cached():
    src = DataHubSource.for_root(str(ROOT))
    calls = _counting_both(src)
    for _ in range(3):
        assert src.interval('FPT', datetime(2022, 11, 12), datetime(2022, 11, 13)) is None
    assert calls['fetch'] == 1
