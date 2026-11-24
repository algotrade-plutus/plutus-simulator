"""Unit tests for scripts/rivf26_extract.py -- no DB needed (a fake client).

The fake answers the tool's own parameterised SQL from in-memory rows, so the
logged run, the guard and the extraction run end to end against the real
adapters.
"""
from __future__ import annotations

import importlib.util
import re
import sys
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path

import pyarrow.parquet as pq
import pytest

_PATH = Path(__file__).resolve().parents[2] / 'scripts' / 'rivf26_extract.py'
_spec = importlib.util.spec_from_file_location('rivf26_extract', _PATH)
rx = importlib.util.module_from_spec(_spec)
sys.modules['rivf26_extract'] = rx
_spec.loader.exec_module(rx)

D = date
T = lambda *a: datetime(*a)  # noqa: E731


class FakeDb:
    """Answers ``range_query``/``MASTER_QUERY`` SQL from in-memory rows."""

    def __init__(self, tables):
        self.tables = tables
        self.calls = []
        self.queries = 0

    def fetch(self, sql, params):
        self.calls.append((sql, list(params)))
        self.queries += 1
        if 'FROM quote.ticker' in sql:
            return [r for r in self.tables.get('ticker', []) if r[0] in params[0]]
        table = re.search(r'FROM quote\.(\w+)', sql).group(1)
        ticker, lo, hi, *rest = params
        dmin = rest.pop(0) if 'depth >= %s' in sql else None
        dmax = rest.pop(0) if 'depth <= %s' in sql else None
        out = []
        for r in self.tables.get(table, []):
            ts = r[0]
            lo_v, hi_v = (lo, hi) if not isinstance(ts, datetime) else (
                datetime.combine(lo, time()), datetime.combine(hi, time()))
            if r[1] != ticker or not (lo_v <= ts < hi_v):
                continue
            if dmin is not None and r[3] < dmin:
                continue
            if dmax is not None and r[3] > dmax:
                continue
            out.append(r)
        # A DB returns rows in whatever order it likes; shuffle-proof the tool.
        return list(reversed(out))


def _daily(ticker, start, n, base):
    rows, d, i = [], start, 0
    while i < n:
        if d.weekday() < 5:
            rows.append((d, ticker, Decimal(str(base + i))))
            i += 1
        d += timedelta(days=1)
    return rows


def make_db():
    close = _daily('FPT', D(2022, 11, 1), 10, 80) + _daily('HPG', D(2022, 11, 1), 10, 20)
    tables = {
        'close': close,
        'open': [(d, t, p - 1) for d, t, p in close],
        'max': [(d, t, p + 1) for d, t, p in close],
        'min': [(d, t, p - 2) for d, t, p in close],
        'ceil': [(d, t, p + 5) for d, t, p in close],
        'floor': [(d, t, p - 5) for d, t, p in close],
        'reference': close,
        'dailyvolume': [(d, t, 1000) for d, t, _ in close],
        'ticker': [('FPT', 'HSX', D(2024, 1, 1), 'stock', D(2006, 12, 13), None),
                   ('HPG', 'HSX', D(2024, 1, 1), 'stock', D(2007, 11, 15), None)],
        'bidprice': [(T(2022, 11, 9, 9, 15 + i), 'FPT', Decimal('80.1') - i, d)
                     for i in range(5) for d in (1, 2, 3, 4)],
        'askprice': [(T(2022, 11, 9, 9, 15 + i), 'FPT', Decimal('80.3') + i, d)
                     for i in range(5) for d in (1, 2, 3, 4)],
        'bidsize': [(T(2022, 11, 9, 9, 15 + i), 'FPT', 100 * (i + 1), d)
                    for i in range(5) for d in (1, 2, 3)],
        'asksize': [(T(2022, 11, 9, 9, 15 + i), 'FPT', 200 * (i + 1), d)
                    for i in range(5) for d in (1, 2, 3)],
        'matched': [(T(2022, 11, 9, 9, 16 + i), 'FPT', Decimal('80.2')) for i in range(3)],
        'total': [(T(2022, 11, 9, 9, 16 + i), 'FPT', 100 * (i + 1)) for i in range(3)]
                 + [(T(2022, 11, 10, 9, 16), 'FPT', 999)],
    }
    return FakeDb(tables)


# -- interval arithmetic ---------------------------------------------------

def test_interval_set_merges_and_reports_gaps():
    s = rx.IntervalSet()
    s.add(D(2022, 1, 5), D(2022, 1, 10))
    s.add(D(2022, 1, 1), D(2022, 1, 3))
    s.add(D(2022, 1, 3), D(2022, 1, 4))       # touching -> merged
    s.add(D(2022, 1, 7), D(2022, 1, 12))      # overlapping -> merged
    s.add(D(2022, 1, 20), D(2022, 1, 20))     # empty -> ignored
    assert s.intervals() == [(D(2022, 1, 1), D(2022, 1, 4)),
                             (D(2022, 1, 5), D(2022, 1, 12))]
    assert s.missing(D(2021, 12, 30), D(2022, 1, 14)) == [
        (D(2021, 12, 30), D(2022, 1, 1)), (D(2022, 1, 4), D(2022, 1, 5)),
        (D(2022, 1, 12), D(2022, 1, 14))]
    assert s.missing(D(2022, 1, 6), D(2022, 1, 8)) == []


def test_split_stem_refuses_unknown_tables():
    assert rx.split_stem('local_quote_bidprice') == ('local_quote', 'bidprice')
    assert rx.split_stem('quote_close') == ('quote', 'close')
    with pytest.raises(ValueError):
        rx.split_stem('quote_account')
    with pytest.raises(ValueError):
        rx.split_stem('orders_close')


# -- the logger ------------------------------------------------------------

def _daily_run():
    from plutus.market.adapters.datahub import DataHubSource
    import os
    src = DataHubSource.for_root(os.environ['PLUTUS_DATA_ROOT'])
    states = list(src.states('FPT', D(2022, 11, 2), D(2022, 11, 5)))
    bar = src.interval('FPT', T(2022, 11, 8), T(2022, 11, 9))
    src.instrument('FPT')            # stock -> reads the ticker master
    src.instrument('VN30F2211')      # future -> typed by prefix, no master read
    return len(states), bar


def test_logged_run_records_exactly_what_the_adapter_read():
    db = make_db()
    log, (n_states, bar) = rx.run_logged(_daily_run, db)
    assert n_states == 3                       # Nov 2, 3, 4
    assert bar.high == Decimal('86') and bar.low == Decimal('83')  # max/min served
    req = log.to_request()
    by_file = {e['file']: e for e in req['files']}
    assert by_file['quote_close.parquet']['tickers'] == {
        'FPT': [['2022-11-02', '2022-11-05'], ['2022-11-08', '2022-11-09']]}
    # interval() reads close/ceil/floor/reference/dailyvolume via _fetch and
    # open/max/min via _ohlc, for that day only
    for f in ('quote_max.parquet', 'quote_min.parquet', 'quote_open.parquet'):
        assert by_file[f]['tickers'] == {'FPT': [['2022-11-08', '2022-11-09']]}
    for f in ('quote_ceil.parquet', 'quote_floor.parquet',
              'quote_reference.parquet', 'quote_dailyvolume.parquet'):
        assert by_file[f]['tickers']['FPT'][0] == ['2022-11-02', '2022-11-05']
    assert by_file['quote_ticker.parquet']['tickers'] == {'FPT': None}
    assert 'HPG' not in str(req)               # never read -> never extracted
    assert not log.unlogged and not log.foreign
    # every DB read was scoped by ticker and date range
    for sql, params in db.calls:
        assert 'tickersymbol' in sql
        if 'quote.ticker' not in sql:
            assert 'datetime >= %s AND datetime < %s' in sql


def _book_run():
    import os
    from plutus.market.adapters.depth import DepthSource
    from plutus.market.adapters.tape import TapeSource
    root = os.environ['PLUTUS_DEPTH_ROOT']
    book = DepthSource(root, table_prefix='local_quote', max_depth=3)
    tape = TapeSource(root, table_prefix='local_quote')
    b = book.book_at('FPT', T(2022, 11, 9, 9, 18))
    events = tape.sized_tape('FPT', D(2022, 11, 9))
    return b, events


def test_logged_book_and_tape_reads_with_depth_bound():
    db = make_db()
    log, (book, events) = rx.run_logged(_book_run, db)
    assert book.bid.best.price == Decimal('77.1')
    assert [e.volume for e in events] == [100, 100, 100]
    req = {e['file']: e for e in log.to_request()['files']}
    bp = req['local_quote_bidprice.parquet']
    assert bp['tickers'] == {'FPT': [['2022-11-09', '2022-11-10']]}
    assert bp['depth'] == [1, 3]
    assert req['local_quote_total.parquet']['tickers'] == {
        'FPT': [['2022-11-09', '2022-11-10']]}
    assert 'depth' not in req['local_quote_total.parquet']


def test_guard_refuses_an_unlogged_read_of_the_data_root():
    def sneaky():
        import os
        from plutus.market.adapters.datahub import DataHubSource
        src = DataHubSource.for_root(os.environ['PLUTUS_DATA_ROOT'])
        path = Path(os.environ['PLUTUS_DATA_ROOT']) / 'quote_close.parquet'
        src._conn.execute(f"SELECT * FROM read_parquet('{path}')")

    with pytest.raises(rx.UnloggedRead):
        rx.run_logged(sneaky, make_db())


def test_hooks_are_removed_after_the_run():
    from plutus.market.adapters.datahub import DataHubSource
    before = DataHubSource._fetch
    rx.run_logged(lambda: None, make_db())
    assert DataHubSource._fetch is before


# -- extraction and determinism ------------------------------------------

def test_extract_is_deterministic_and_minimal(tmp_path):
    log, _ = rx.run_logged(_daily_run, make_db())
    req = log.to_request()
    a = rx.extract(make_db(), req, tmp_path / 'a')
    b = rx.extract(make_db(), req, tmp_path / 'b')
    assert [(r.file, r.sha256) for r in a] == [(r.file, r.sha256) for r in b]
    for r in a:
        assert (tmp_path / 'a' / r.file).read_bytes() == (tmp_path / 'b' / r.file).read_bytes()
    close = pq.read_table(tmp_path / 'a' / 'quote_close.parquet')
    assert close.column_names == ['datetime', 'tickersymbol', 'price']
    assert str(close.schema.field('datetime').type) == 'date32[day]'
    assert str(close.schema.field('price').type) == 'double'
    assert close.num_rows == 4                 # 3 + the one interval() day
    days = close.column('datetime').to_pylist()
    assert days == sorted(days)                # fake returns them reversed
    md = pq.ParquetFile(tmp_path / 'a' / 'quote_close.parquet').metadata.metadata
    assert b'pandas' not in md                 # no pandas metadata


def test_row_order_from_db_does_not_change_bytes(tmp_path):
    req = rx.request_from_declared(['quote_close', 'local_quote_bidprice'],
                                   ['FPT', 'HPG'], D(2022, 11, 1), D(2022, 11, 15),
                                   max_depth=3)
    db1, db2 = make_db(), make_db()
    db2.fetch_orig = db2.fetch
    db2.fetch = lambda sql, p: list(reversed(db2.fetch_orig(sql, p)))
    a = rx.extract(db1, req, tmp_path / 'a')
    b = rx.extract(db2, req, tmp_path / 'b')
    assert [r.sha256 for r in a] == [r.sha256 for r in b]
    bp = pq.read_table(tmp_path / 'a' / 'local_quote_bidprice.parquet')
    assert set(bp.column('depth').to_pylist()) == {1, 2, 3}   # depth 4 excluded
    assert str(bp.schema.field('price').type) == 'decimal128(20, 6)'
    assert str(bp.schema.field('datetime').type) == 'timestamp[us]'


def test_declared_slice_loads_through_the_adapters(tmp_path):
    from plutus.market.adapters.depth import DepthSource
    from plutus.market.adapters.tape import TapeSource
    from plutus.market.adapters.datahub import DataHubSource
    req = rx.request_from_declared(
        ['quote_close', 'quote_max', 'quote_min'] +
        [f'local_quote_{s}' for s in ('bidprice', 'askprice', 'bidsize',
                                      'asksize', 'matched', 'total')],
        ['FPT'], D(2022, 11, 9), D(2022, 11, 10), max_depth=3)
    rx.extract(make_db(), req, tmp_path)
    assert DepthSource(tmp_path).book_at('FPT', T(2022, 11, 9, 9, 20)).is_two_sided
    assert len(TapeSource(tmp_path).sized_tape('FPT', D(2022, 11, 9))) == 3
    assert DataHubSource.for_root(str(tmp_path)).instrument('FPT').exchange_code == 'HSX'


def test_manifest_has_hashes_and_no_secrets(tmp_path):
    req = rx.request_from_declared(['quote_close'], ['FPT'], D(2022, 11, 1),
                                   D(2022, 11, 15))
    res = rx.extract(make_db(), req, tmp_path)
    path = rx.write_manifest(tmp_path, experiment='t', mode='declared',
                             reproduces='unit', command='x', results=res)
    text = path.read_text()
    for r in res:
        assert r.sha256 in text
    assert 'Why this window is minimal' in text
    assert 'SOURCE_DB' not in text and 'password' not in text.lower()


def test_db_errors_are_scrubbed_of_host_and_credentials():
    class OperationalError(Exception):
        pgcode = None
    exc = OperationalError('connection to server at "db.secret.example" (10.0.0.1), '
                           'port 5432 failed: password authentication failed for user "u"')
    scrubbed = rx._scrub(exc)
    assert str(scrubbed) == 'OperationalError'
    assert 'secret' not in str(scrubbed) and '10.0.0.1' not in str(scrubbed)
