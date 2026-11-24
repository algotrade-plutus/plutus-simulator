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
