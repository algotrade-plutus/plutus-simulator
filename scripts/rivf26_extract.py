#!/usr/bin/env python
"""RIVF'26 minimal-slice extraction from the Algotrade DB, with access logging.

Handoff task T1 (``docs/HANDOFF-2026-11-24-camera-ready.md``). This is a
research script, **not** library API: nothing in ``src/plutus`` imports it.

Two modes, one extraction path
==============================

``log``
    Run a pytest selection (or any ``module:callable``) with the market-data
    adapters instrumented, record every ``(file, ticker, day range[, depth])``
    the run actually reads, then extract exactly that set from the DB.

``declared``
    Take an explicit ``(files, tickers, [start, end), depth)`` request -- or a
    ``request.json`` written by an earlier run -- and extract it. This is for
    strategies whose window is fixed up front, and it is also how a logged
    slice is replayed byte-for-byte.

Both modes reduce to the same normalised *request* (written beside the slice as
``request.json``), and the same :func:`extract` turns a request into files.

Where the logging hooks sit
===========================

At the adapter read boundary, on the methods that issue the SQL, never by
guessing from a strategy's parameters:

* ``DataHubSource._reader`` (which files the adapter looked for), ``_fetch``
  (close/ceil/floor/reference/dailyvolume over ``[start, end)``), ``_ohlc``
  (close/open/max/min for one day), ``_resolve_instrument`` (the ticker-master
  row, only on the branch that reads it); ``AuctionAwareDataHubSource._open_at``.
* ``DepthSource._reader`` / ``_load`` / ``coverage`` and the whole-table
  aggregates ``tickers`` / ``window``.
* ``TapeSource._reader`` / ``_rows`` / ``tickers``.
* ``TickSource._table`` / ``_build`` (the CSV tick archive).

Each adapter's DuckDB connection is also wrapped in a guard: a query against
the run's data root issued *outside* one of those hooks raises
:class:`UnloggedRead`. So a new read path added to an adapter later fails the
logged run loudly instead of silently producing an under-sized slice.

Not covered: code that bypasses these adapters (the ``plutus.datahub`` query
layer used by some ``measurements/``). Those reads are invisible to the hooks;
use ``declared`` mode for them.

The chicken-and-egg problem, and the choice made
================================================

To know what a run reads you must run it, and to run it you need data. The
logged run solves this with an **on-demand DB-backed cache**:

1. A scratch data root is created and pointed to by both ``PLUTUS_DATA_ROOT``
   and ``PLUTUS_DEPTH_ROOT``. Every table the adapters know is pre-created
   there, empty but correctly typed, so presence checks
   (``DataHubConfig`` needs ``quote_ticker``; ``has_field``; ``tape_available``)
   take the same branch they take on a full corpus.
2. When a hook fires, the range it is about to read is fetched from the DB
   (only the part not already cached), merged into that table's file, and the
   file is rewritten. *Then* the adapter's own, unmodified SQL runs against it.
   So the run sees exactly the DB rows for every key it reads.
3. After the run, the merged access set becomes a request, and :func:`extract`
   queries the DB afresh for exactly that set and writes the slice. Optional
   ``--verify`` re-runs the same selection in a subprocess against the slice.

Why this rather than a DB-backed adapter: it leaves every adapter code path
(SQL, joins, dtype handling, Decimal conversion) exactly as it runs against
shipped parquet, so the logged run is the real run, and the cache and the slice
answer every logged query identically by construction.

Whole-table aggregates (``DepthSource.tickers``/``window``,
``TapeSource.tickers``) are **slice-relative**: on the cache, on the slice, and
on any minimal fixture they answer from the rows present, not the full DB. The
manifest lists every such call so a reader can check it does not move a result.

Determinism
===========

Same request -> same bytes: rows deduplicated on the table key and sorted by
``(tickersymbol, datetime[, depth])``; a fixed column order and Arrow schema per
table (daily prices float64 and ``datetime`` date32, as the shipped daily
fixtures; book/tape prices decimal128(20,6) and ``datetime`` timestamp[us], as
the shipped extract); fixed writer settings (:data:`WRITER`); Arrow tables built
directly (no pandas metadata); nothing time-dependent in the file. The pyarrow
version is recorded in the manifest because its ``created_by`` string is part of
the bytes.

Credentials and confidentiality
===============================

The DB credentials are read at runtime from the cred env file into memory only.
They, and the host name, are never printed, logged, or written: DB errors are
re-raised as :class:`DbError` carrying only the exception class and SQLSTATE.
Every connection is opened with ``default_transaction_read_only=on`` and a
``statement_timeout``; every query is scoped by ticker and date range.

Usage
=====

    PY=.venv/bin/python   # or the main checkout's venv
    # logging mode, a pytest selection (everything after -- goes to pytest):
    $PY scripts/rivf26_extract.py log --experiment demo-s1 \\
        --reproduces "S1 VN30F mean-reversion forced close" --verify \\
        -- strategies/test_s1_vn30f_meanrev.py

    # logging mode, a callable (``--sys-path`` for its imports):
    $PY scripts/rivf26_extract.py log --experiment x --sys-path strategies \\
        --callable test_s1_vn30f_meanrev:run_s1

    # declared mode:
    $PY scripts/rivf26_extract.py declared --experiment demo-book \\
        --files local_quote_bidprice,local_quote_askprice --tickers FPT \\
        --start 2022-11-09 --end 2022-11-10 --max-depth 3
    # replay a request written by an earlier run:
    $PY scripts/rivf26_extract.py declared --experiment again \\
        --request "$RIVF26_DATA/demo-s1/request.json"

Output goes to ``$RIVF26_DATA/<experiment>/`` (default: ``rivf26/data`` beside
this checkout)
(``--out-root`` to change): one file per table, ``request.json``, and
``DATA-MANIFEST.md``.
"""
from __future__ import annotations

import argparse
import contextlib
import csv
import functools
import hashlib
import importlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

import pyarrow as pa
import pyarrow.parquet as pq

REPO_ROOT = Path(__file__).resolve().parents[1]
#: Local roots come from the environment, never from paths written in the repo.
#: The fallbacks reproduce the owner's layout relative to this checkout.
DEFAULT_OUT_ROOT = Path(os.environ.get(
    'RIVF26_DATA', REPO_ROOT.parent / 'rivf26' / 'data'))
CRED_FILE = Path(os.environ.get(
    'RIVF26_CRED_FILE', REPO_ROOT.parents[1] / 'system' / 'cred' / 'amz-database.env'))
#: The owner's local parquet archive. It holds bid/ask **sizes from 2021-07-01**,
#: which the remote DB lacks before 2023-01-03 (see its README).
ARCHIVE_ROOT = Path(os.environ.get(
    'VN_QUOTE_ARCHIVE',
    Path.home() / 'data' / 'plutus-open-source' / 'vn_quote_2020-12_2024-09'))
STATEMENT_TIMEOUT_MS = 120_000
#: Slices above this many bytes are flagged in the manifest for a justification.
SIZE_FLAG_BYTES = 3 * 1024 * 1024

#: Fixed parquet writer settings. Changing any of these changes every sha256.
WRITER = dict(
    compression='zstd', compression_level=9, use_dictionary=True,
    write_statistics=True, version='2.6', data_page_version='1.0',
    row_group_size=1 << 20, store_schema=True,
)

# ---------------------------------------------------------------------------
# Table registry: file stem -> DB table, fixed columns and Arrow types
# ---------------------------------------------------------------------------

DEC = pa.decimal128(20, 6)
_DAILY_PRICE = (('datetime', pa.date32()), ('tickersymbol', pa.string()),
                ('price', pa.float64()))
_DAILY_QTY = (('datetime', pa.date32()), ('tickersymbol', pa.string()),
              ('quantity', pa.int64()))
_BOOK_PRICE = (('datetime', pa.timestamp('us')), ('tickersymbol', pa.string()),
               ('price', DEC), ('depth', pa.int64()))
_BOOK_QTY = (('datetime', pa.timestamp('us')), ('tickersymbol', pa.string()),
             ('quantity', pa.int64()), ('depth', pa.int64()))
_TICK_PRICE = (('datetime', pa.timestamp('us')), ('tickersymbol', pa.string()),
               ('price', DEC))
_TICK_QTY = (('datetime', pa.timestamp('us')), ('tickersymbol', pa.string()),
             ('quantity', pa.int64()))
_MASTER = (('tickersymbol', pa.string()), ('exchangeid', pa.string()),
           ('lastupdated', pa.date32()), ('instrumenttype', pa.string()),
           ('startdate', pa.date32()), ('expdate', pa.date32()))

#: DB table (``quote.<name>``) -> columns. Unknown tables are refused, never guessed.
DB_TABLES: Dict[str, Tuple[Tuple[str, pa.DataType], ...]] = {
    **{t: _DAILY_PRICE for t in ('close', 'open', 'max', 'min', 'ceil',
                                 'floor', 'reference')},
    'dailyvolume': _DAILY_QTY,
    'bidprice': _BOOK_PRICE, 'askprice': _BOOK_PRICE,
    'bidsize': _BOOK_QTY, 'asksize': _BOOK_QTY,
    'matched': _TICK_PRICE, 'total': _TICK_QTY, 'matchedvolume': _TICK_QTY,
    'ticker': _MASTER,
}
PREFIXES = ('local_quote', 'quote')
MASTER_STEM = 'quote_ticker'
#: Tables pre-created (empty) in the logged run's cache, mirroring a full corpus.
DAILY_STEMS = tuple(f'quote_{t}' for t in (
    'close', 'open', 'max', 'min', 'ceil', 'floor', 'reference', 'dailyvolume',
    'ticker'))
BOOK_SUFFIXES = ('bidprice', 'askprice', 'bidsize', 'asksize', 'matched', 'total')
TICK_CSV_STEMS = ('quote_matched', 'quote_askprice', 'quote_bidprice')


def split_stem(stem: str) -> Tuple[str, str]:
    """``'local_quote_bidprice'`` -> ``('local_quote', 'bidprice')``."""
    for prefix in PREFIXES:
        if stem.startswith(prefix + '_'):
            table = stem[len(prefix) + 1:]
            if table not in DB_TABLES:
                raise ValueError(f'unknown table {stem!r}; known DB tables: '
                                 f'{sorted(DB_TABLES)}')
            return prefix, table
    raise ValueError(f'{stem!r} does not start with one of {PREFIXES}')


def columns_for(stem: str):
    return DB_TABLES[split_stem(stem)[1]]


def key_columns(stem: str) -> Tuple[str, ...]:
    names = [n for n, _ in columns_for(stem)]
    if names[0] == 'tickersymbol':
        return ('tickersymbol',)
    return ('tickersymbol', 'datetime') + (('depth',) if 'depth' in names else ())


def is_daily(stem: str) -> bool:
    return dict(columns_for(stem)).get('datetime') == pa.date32()


def file_name(stem: str, fmt: str) -> str:
    return f'{stem}.{fmt}'


# ---------------------------------------------------------------------------
# Interval arithmetic on half-open day ranges
# ---------------------------------------------------------------------------

class IntervalSet:
    """A union of half-open ``[lo, hi)`` date ranges, kept merged and sorted."""

    def __init__(self, items: Iterable[Tuple[date, date]] = ()):
        self._iv: List[Tuple[date, date]] = []
        for lo, hi in items:
            self.add(lo, hi)

    def add(self, lo: date, hi: date) -> None:
        if not lo < hi:
            return
        merged = []
        for a, b in self._iv:
            if b < lo or a > hi:          # disjoint and not touching
                merged.append((a, b))
            else:
                lo, hi = min(a, lo), max(b, hi)
        merged.append((lo, hi))
        self._iv = sorted(merged)

    def missing(self, lo: date, hi: date) -> List[Tuple[date, date]]:
        """The parts of ``[lo, hi)`` not already covered."""
        out, cur = [], lo
        for a, b in self._iv:
            if b <= cur or a >= hi:
                continue
            if a > cur:
                out.append((cur, a))
            cur = max(cur, b)
        if cur < hi:
            out.append((cur, hi))
        return out

    def intervals(self) -> List[Tuple[date, date]]:
        return list(self._iv)

    def __bool__(self):
        return bool(self._iv)


def as_day(value) -> date:
    """Mirror the adapters' ``str(x)[:10]`` day truncation."""
    return date.fromisoformat(str(value)[:10])


# ---------------------------------------------------------------------------
# The access log
# ---------------------------------------------------------------------------

@dataclass
class TableAccess:
    intervals: Dict[str, IntervalSet] = field(default_factory=dict)  # ticker ->
    min_depth: Optional[int] = None
    max_depth: Optional[int] = None
    depth_unbounded_low: bool = False


class AccessLog:
    """Every ``(file, ticker, day range[, depth])`` a run read, merged."""

    def __init__(self):
        self.present: set = set()                 # {(stem, fmt)}
        self.tables: Dict[Tuple[str, str], TableAccess] = {}
        self.master: set = set()                  # tickers looked up in quote_ticker
        self.aggregates: set = set()              # {(stem, call, ticker|'*')}
        self.foreign: set = set()                 # {(root, stem)} reads off the cache
        self.absent: set = set()                  # {(stem, fmt)} asked for, not served
        self.unlogged: List[str] = []

    def touch(self, stem: str, fmt: str) -> None:
        self.present.add((stem, fmt))

    def read(self, stem: str, fmt: str, ticker: str, lo: date, hi: date, *,
             depth: Optional[Tuple[Optional[int], int]] = None) -> None:
        self.touch(stem, fmt)
        acc = self.tables.setdefault((stem, fmt), TableAccess())
        acc.intervals.setdefault(ticker, IntervalSet()).add(lo, hi)
        if depth is not None:
            dmin, dmax = depth
            if dmin is None:
                acc.depth_unbounded_low = True
            else:
                acc.min_depth = dmin if acc.min_depth is None else min(acc.min_depth, dmin)
            acc.max_depth = dmax if acc.max_depth is None else max(acc.max_depth, dmax)

    def lookup_master(self, ticker: str) -> None:
        self.touch(MASTER_STEM, 'parquet')
        self.master.add(ticker)

    def to_request(self) -> dict:
        """The normalised, deterministic extraction request."""
        entries = []
        present = set(self.present) | {(MASTER_STEM, 'parquet')}
        for stem, fmt in sorted(present):
            entry = {'file': file_name(stem, fmt), 'tickers': {}}
            if stem == MASTER_STEM:
                entry['tickers'] = {t: None for t in sorted(self.master)}
            acc = self.tables.get((stem, fmt))
            if acc is not None:
                entry['tickers'] = {
                    t: [[lo.isoformat(), hi.isoformat()]
                        for lo, hi in acc.intervals[t].intervals()]
                    for t in sorted(acc.intervals)}
                if acc.max_depth is not None:
                    entry['depth'] = [None if acc.depth_unbounded_low
                                      else acc.min_depth, acc.max_depth]
            entries.append(entry)
        return {'version': 1, 'files': entries}


# ---------------------------------------------------------------------------
# DB access (credentials stay in memory; errors are scrubbed)
# ---------------------------------------------------------------------------

class DbError(RuntimeError):
    """A DB failure with every host/credential detail removed."""


def _scrub(exc: BaseException) -> DbError:
    code = getattr(exc, 'pgcode', None)
    return DbError(f'{type(exc).__name__}' + (f' (SQLSTATE {code})' if code else ''))


def read_cred_file(path: Path = CRED_FILE) -> Dict[str, str]:
    cfg = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.removeprefix('export ').split('=', 1)
        cfg[key.strip()] = value.strip().strip('"').strip("'")
    missing = [k for k in ('HOST', 'PORT', 'NAME', 'USER', 'PASSWORD')
               if f'SOURCE_DB_{k}' not in cfg]
    if missing:
        raise DbError(f'cred file lacks keys: {", ".join("SOURCE_DB_" + k for k in missing)}')
    return cfg


class PgClient:
    """Read-only psycopg2 connection. ``fetch(sql, params) -> list[tuple]``."""

    def __init__(self, cred_file: Path = CRED_FILE):
        import psycopg2  # local: the unit tests never need it
        self._psycopg2 = psycopg2
        cfg = read_cred_file(cred_file)
        try:
            self._conn = psycopg2.connect(
                host=cfg['SOURCE_DB_HOST'], port=cfg['SOURCE_DB_PORT'],
                dbname=cfg['SOURCE_DB_NAME'], user=cfg['SOURCE_DB_USER'],
                password=cfg['SOURCE_DB_PASSWORD'], connect_timeout=20,
                options=(f'-c default_transaction_read_only=on '
                         f'-c statement_timeout={STATEMENT_TIMEOUT_MS}'))
        except Exception as exc:
            raise _scrub(exc) from None
        finally:
            cfg.clear()
        self.queries = 0

    def fetch(self, sql: str, params: Sequence) -> List[tuple]:
        try:
            with self._conn.cursor() as cur:
                cur.execute(sql, list(params))
                self.queries += 1
                return cur.fetchall()
        except Exception as exc:
            with contextlib.suppress(Exception):
                self._conn.rollback()
            raise _scrub(exc) from None

    def close(self):
        with contextlib.suppress(Exception):
            self._conn.close()

    @staticmethod
    def describe() -> str:
        return ('Algotrade PostgreSQL DB, schema `quote` (read-only transaction). '
                'File `<prefix>_<x>.<ext>` holds rows of DB table `quote.<x>`.')


class ArchiveClient:
    """The local parquet archive, answering the same SQL :class:`PgClient` gets.

    ``fetch(sql, params)`` takes the tool's own parameterised queries
    (:func:`range_query`, :data:`MASTER_QUERY`) and runs them in DuckDB with
    ``quote.<x>`` replaced by every archive file named ``<x>.parquet`` under
    ``{stock,futures,index}/{daily,intraday,book}/`` (``_meta/`` for the ticker
    master). The ticker filter then picks the instrument, so the caller need not
    say which file a ticker lives in. Values arrive as the archive stores them
    (prices as floats) and :func:`normalise_rows` coerces them exactly as it does
    the DB's, so a slice is byte-identical in layout whichever source wrote it.
    """

    _INSTRUMENTS = ('stock', 'futures', 'index')
    _GROUPS = ('daily', 'intraday', 'book')

    def __init__(self, root: Path = ARCHIVE_ROOT):
        import duckdb  # local: only this source needs it here
        self.root = Path(root)
        if not self.root.is_dir():
            raise FileNotFoundError(f'archive root not found: {self.root}')
        self._conn = duckdb.connect()
        self.queries = 0

    def _files(self, table: str) -> List[Path]:
        if table in ('ticker', 'futurecontractcode'):
            meta = self.root / '_meta' / f'{table}.parquet'
            return [meta] if meta.exists() else []
        return [p for i in self._INSTRUMENTS for g in self._GROUPS
                if (p := self.root / i / g / f'{table}.parquet').exists()]

    def fetch(self, sql: str, params: Sequence) -> List[tuple]:
        table = re.search(r'FROM quote\.(\w+)', sql).group(1)
        files = self._files(table)
        if not files:
            return []
        source = ('read_parquet([' + ', '.join(f"'{f}'" for f in files)
                  + '], union_by_name=true)')
        q = (sql.replace(f'quote.{table}', source)
                .replace('tickersymbol = ANY(%s)', 'list_contains(?, tickersymbol)')
                .replace('%s', '?'))
        self.queries += 1
        return self._conn.execute(q, list(params)).fetchall()

    def close(self):
        with contextlib.suppress(Exception):
            self._conn.close()

    @staticmethod
    def describe() -> str:
        return ('Algotrade Vietnam market dataset, local parquet archive '
                '`vn_quote_2020-12_2024-09` (bid/ask sizes from 2021-07-01; book '
                'rows from the 2025-10 backup dumps, timestamps offset from the '
                'trade tables by tens of ms). File `<prefix>_<x>.<ext>` holds rows '
                'of archive table `<x>`.')


def range_query(stem: str, depth: Optional[Sequence[Optional[int]]] = None
                ) -> str:
    """The parameterised SQL for one ``(ticker, [lo, hi))`` scoped read."""
    _, table = split_stem(stem)
    cols = [n for n, _ in columns_for(stem)]
    where = ['tickersymbol = %s', 'datetime >= %s', 'datetime < %s']
    if depth is not None:
        if depth[0] is not None:
            where.append('depth >= %s')
        where.append('depth <= %s')
    order = ', '.join(c for c in key_columns(stem) if c != 'tickersymbol')
    return (f'SELECT {", ".join(cols)} FROM quote.{table} '
            f'WHERE {" AND ".join(where)} ORDER BY {order}')


MASTER_QUERY = ('SELECT tickersymbol, exchangeid, lastupdated, instrumenttype, '
                'startdate, expdate FROM quote.ticker '
                'WHERE tickersymbol = ANY(%s) ORDER BY tickersymbol')


def fetch_range(db, stem: str, ticker: str, lo: date, hi: date,
                depth: Optional[Sequence[Optional[int]]] = None) -> List[tuple]:
    params: list = [ticker, lo, hi]
    if depth is not None:
        if depth[0] is not None:
            params.append(depth[0])
        params.append(depth[1])
    return db.fetch(range_query(stem, depth), params)


def fetch_master(db, tickers: Sequence[str]) -> List[tuple]:
    return db.fetch(MASTER_QUERY, [sorted(tickers)]) if tickers else []


# ---------------------------------------------------------------------------
# Deterministic writing
# ---------------------------------------------------------------------------

def _coerce(value, typ: pa.DataType):
    if value is None:
        return None
    if pa.types.is_floating(typ):
        return float(value)
    if pa.types.is_integer(typ):
        return int(value)
    if pa.types.is_decimal(typ):
        return value if isinstance(value, Decimal) else Decimal(str(value))
    if pa.types.is_date(typ):
        return value.date() if isinstance(value, datetime) else (
            date.fromisoformat(value) if isinstance(value, str) else value)
    if pa.types.is_timestamp(typ):
        return value if isinstance(value, datetime) else datetime.fromisoformat(str(value))
    return str(value)


def normalise_rows(stem: str, rows: Iterable[Sequence]) -> List[tuple]:
    """Coerce to the registry's types, drop key duplicates, sort by key."""
    cols = columns_for(stem)
    names = [n for n, _ in cols]
    key_idx = [names.index(k) for k in key_columns(stem)]
    by_key = {}
    for row in rows:
        if len(row) != len(cols):
            raise ValueError(f'{stem}: expected {len(cols)} columns, got {len(row)}')
        typed = tuple(_coerce(v, t) for v, (_, t) in zip(row, cols))
        by_key[tuple(typed[i] for i in key_idx)] = typed
    return [by_key[k] for k in sorted(by_key)]


def arrow_table(stem: str, rows: List[tuple]) -> pa.Table:
    cols = columns_for(stem)
    schema = pa.schema([pa.field(n, t) for n, t in cols])
    arrays = [pa.array([r[i] for r in rows], type=t)
              for i, (_, t) in enumerate(cols)]
    return pa.Table.from_arrays(arrays, schema=schema)


def _csv_cell(v) -> str:
    if v is None:
        return ''
    if isinstance(v, datetime):
        return v.isoformat(sep=' ')
    return str(v)


def write_file(path: Path, stem: str, rows: List[tuple]) -> None:
    """Write already-normalised rows. ``.parquet`` or ``.csv`` by suffix."""
    tmp = path.with_name(path.name + '.tmp')
    if path.suffix == '.parquet':
        pq.write_table(arrow_table(stem, rows), tmp, **WRITER)
    elif path.suffix == '.csv':
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator='\n')
        w.writerow([n for n, _ in columns_for(stem)])
        for r in rows:
            w.writerow([_csv_cell(v) for v in r])
        tmp.write_text(buf.getvalue(), encoding='utf-8')
    else:
        raise ValueError(f'unsupported output format {path.suffix}')
    os.replace(tmp, path)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b''):
            h.update(chunk)
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Extraction: request -> files
# ---------------------------------------------------------------------------

@dataclass
class FileResult:
    file: str
    stem: str
    rows: int
    bytes: int
    sha256: str
    tickers: Dict[str, Optional[List[List[str]]]]
    depth: Optional[List[Optional[int]]]


def extract(db, request: dict, out_dir: Path) -> List[FileResult]:
    """Query the DB for exactly ``request`` and write it into ``out_dir``."""
    out_dir.mkdir(parents=True, exist_ok=True)
    results = []
    for entry in sorted(request['files'], key=lambda e: e['file']):
        fname = entry['file']
        stem, _, _fmt = fname.rpartition('.')
        depth = entry.get('depth')
        if stem == MASTER_STEM:
            raw = fetch_master(db, list(entry['tickers']))
        else:
            raw = []
            for ticker, ivs in sorted(entry['tickers'].items()):
                for lo, hi in ivs:
                    raw.extend(fetch_range(db, stem, ticker, date.fromisoformat(lo),
                                           date.fromisoformat(hi), depth))
        rows = normalise_rows(stem, raw)
        path = out_dir / fname
        write_file(path, stem, rows)
        results.append(FileResult(fname, stem, len(rows), path.stat().st_size,
                                  sha256(path), entry['tickers'], depth))
    return results


def request_from_declared(files: Sequence[str], tickers: Sequence[str],
                          start: date, end: date,
                          max_depth: Optional[int] = None,
                          ticker_master: bool = True) -> dict:
    log = AccessLog()
    for spec in files:
        stem, _, fmt = spec.partition('.')
        fmt = fmt or 'parquet'
        has_depth = 'depth' in dict(columns_for(stem))
        for t in tickers:
            log.read(stem, fmt, t, start, end,
                     depth=(1, max_depth) if (has_depth and max_depth) else None)
    if ticker_master:
        for t in tickers:
            log.lookup_master(t)
    return log.to_request()


# ---------------------------------------------------------------------------
# The logged run: on-demand cache + adapter hooks
# ---------------------------------------------------------------------------

class UnloggedRead(RuntimeError):
    """An adapter queried the data root outside every logging hook."""


class CacheStore:
    """The scratch data root the logged run reads. Fills itself from the DB."""

    def __init__(self, root: Path, db):
        self.root = root
        self.db = db
        self._rows: Dict[Tuple[str, str], Dict[tuple, tuple]] = {}
        self._covered: Dict[Tuple[str, str, str], IntervalSet] = {}
        self._master_done: set = set()
        for stem in DAILY_STEMS:
            self._write(stem, 'parquet')
        for prefix in PREFIXES:
            for suffix in BOOK_SUFFIXES:
                self._write(f'{prefix}_{suffix}', 'parquet')
        for stem in TICK_CSV_STEMS:
            self._write(stem, 'csv')

    def exists(self, stem: str, fmt: str) -> bool:
        return (self.root / file_name(stem, fmt)).exists()

    def _write(self, stem, fmt):
        rows = self._rows.get((stem, fmt), {})
        write_file(self.root / file_name(stem, fmt), stem,
                   normalise_rows(stem, rows.values()))

    def _merge(self, stem, fmt, raw):
        store = self._rows.setdefault((stem, fmt), {})
        for row in normalise_rows(stem, raw):
            names = [n for n, _ in columns_for(stem)]
            store[tuple(row[names.index(k)] for k in key_columns(stem))] = row

    def ensure(self, stem: str, fmt: str, ticker: str, lo: date, hi: date):
        # The cache fetches every depth; the extraction applies the logged bound.
        cov = self._covered.setdefault((stem, fmt, ticker), IntervalSet())
        gaps = cov.missing(lo, hi)
        if not gaps:
            return
        raw = []
        for a, b in gaps:
            raw.extend(fetch_range(self.db, stem, ticker, a, b))
            cov.add(a, b)
        self._merge(stem, fmt, raw)
        self._write(stem, fmt)

    def ensure_master(self, ticker: str):
        if ticker in self._master_done:
            return
        self._master_done.add(ticker)
        self._merge(MASTER_STEM, 'parquet', fetch_master(self.db, [ticker]))
        self._write(MASTER_STEM, 'parquet')


class _GuardedConn:
    """Delegates to a DuckDB connection; refuses unlogged reads of the cache."""

    def __init__(self, conn, recorder: 'Recorder'):
        self._conn = conn
        self._rec = recorder

    def execute(self, sql, *args, **kwargs):
        if self._rec.cache_marker in str(sql) and self._rec.depth == 0:
            self._rec.log.unlogged.append(str(sql)[:200])
            raise UnloggedRead(
                'adapter queried the logged data root outside every logging '
                f'hook; add a hook for it in {Path(__file__).name}: {str(sql)[:120]}')
        return self._conn.execute(sql, *args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._conn, name)


_DAILY_FETCH = ('close_price', 'ceiling_price', 'floor_price', 'ref_price',
                'daily_volume')
_DAILY_OHLC = ('close_price', 'open_price', 'max_price', 'min_price')


class Recorder:
    """Installs the adapter hooks for the duration of a ``with`` block."""

    def __init__(self, log: AccessLog, store: Optional[CacheStore]):
        self.log = log
        self.store = store
        self.root = store.root.resolve() if store else None
        self.cache_marker = str(self.root) if self.root else '\0never\0'
        self._local = threading.local()
        self._saved: List[Tuple[type, str, object]] = []

    # -- hook plumbing -----------------------------------------------------

    @property
    def depth(self) -> int:
        return getattr(self._local, 'depth', 0)

    def _wrap(self, cls, name, before: Optional[Callable] = None,
              after_init: bool = False):
        orig = cls.__dict__[name]
        rec = self

        if after_init:
            @functools.wraps(orig)
            def init(obj, *a, **k):
                orig(obj, *a, **k)
                obj._conn = _GuardedConn(obj._conn, rec)
            wrapper = init
        else:
            @functools.wraps(orig)
            def wrapper(obj, *a, **k):
                if before is not None:
                    before(obj, *a, **k)
                rec._local.depth = rec.depth + 1
                try:
                    return orig(obj, *a, **k)
                finally:
                    rec._local.depth -= 1
        self._saved.append((cls, name, orig))
        setattr(cls, name, wrapper)

    def _on_cache(self, root, stem) -> bool:
        if self.root is not None and Path(root).resolve() == self.root:
            return True
        self.log.foreign.add((str(root), stem))
        return False

    def _read(self, root, stem, fmt, ticker, lo, hi, depth=None):
        if not lo < hi:
            return
        if self._on_cache(root, stem) and self.store.exists(stem, fmt):
            self.log.read(stem, fmt, ticker, lo, hi, depth=depth)
            self.store.ensure(stem, fmt, ticker, lo, hi)

    def _touch(self, root, stem, fmt):
        if self.root is not None and Path(root).resolve() == self.root:
            if self.store.exists(stem, fmt):
                self.log.touch(stem, fmt)
            else:
                self.log.absent.add((stem, fmt))
        else:
            self.log.foreign.add((str(root), stem))

    # -- install -----------------------------------------------------------

    def __enter__(self):
        from plutus.datahub.config import DataHubConfig
        from plutus.market.adapters import datahub as dh_mod
        from plutus.market.adapters.auction_daily import AuctionAwareDataHubSource
        from plutus.market.adapters.datahub import DataHubSource
        from plutus.market.adapters.depth import DepthSource
        from plutus.market.adapters.tape import TapeSource
        from plutus.market.adapters.tick import MAX_DEPTH as TICK_DEPTH, TickSource
        from plutus.core.constant import is_covered_warrant, is_etf

        def stem_of(field_name):
            return DataHubConfig.FIELD_MAPPINGS[field_name].rsplit('.', 1)[0]

        # DataHubSource ----------------------------------------------------
        def dh_root(obj):
            return obj.config.data_root

        def dh_reader(obj, field_name):
            if field_name in DataHubConfig.FIELD_MAPPINGS:
                self._touch(dh_root(obj), stem_of(field_name), 'parquet')

        def dh_fetch(obj, ticker, start, end, close):
            for f in _DAILY_FETCH:
                self._read(dh_root(obj), stem_of(f), 'parquet', ticker,
                           as_day(start), as_day(end))

        def dh_ohlc(obj, ticker, day):
            for f in _DAILY_OHLC:
                self._read(dh_root(obj), stem_of(f), 'parquet', ticker,
                           as_day(day), as_day(day) + timedelta(days=1))

        def dh_instrument(obj, ticker):
            if (dh_mod._FUTURES_RE.match(ticker) or is_covered_warrant(ticker)
                    or is_etf(ticker)):
                return
            if self._on_cache(dh_root(obj), MASTER_STEM):
                self.log.lookup_master(ticker)
                self.store.ensure_master(ticker)

        def auction_open(obj, ticker, ts):
            self._read(dh_root(obj), 'quote_open', 'parquet', ticker,
                       as_day(ts), as_day(ts) + timedelta(days=1))

        self._wrap(DataHubSource, '__init__', after_init=True)
        self._wrap(DataHubSource, '_reader', dh_reader)
        self._wrap(DataHubSource, '_fetch', dh_fetch)
        self._wrap(DataHubSource, '_ohlc', dh_ohlc)
        self._wrap(DataHubSource, '_resolve_instrument', dh_instrument)
        self._wrap(AuctionAwareDataHubSource, '_open_at', auction_open)

        # DepthSource / TapeSource ----------------------------------------
        def prefixed_reader(obj, suffix):
            self._touch(obj.root, f'{obj.table_prefix}_{suffix}', 'parquet')

        def depth_load(obj, ticker, day, suffix, column):
            self._read(obj.root, f'{obj.table_prefix}_{suffix}', 'parquet',
                       ticker, as_day(day), as_day(day) + timedelta(days=1),
                       depth=(1, obj.max_depth))

        def depth_coverage(obj, ticker, day):
            for suffix in ('bidprice', 'askprice', 'bidsize', 'asksize'):
                depth_load(obj, ticker, day, suffix, None)

        def aggregate(call, suffixes):
            def before(obj, *args):
                ticker = args[0] if args else '*'
                if not self._on_cache(obj.root, obj.table_prefix):
                    return
                for s in suffixes:
                    stem = f'{obj.table_prefix}_{s}'
                    self.log.touch(stem, 'parquet')
                    self.log.aggregates.add((stem, call, ticker))
            return before

        def tape_rows(obj, ticker, day, suffix, column):
            self._read(obj.root, f'{obj.table_prefix}_{suffix}', 'parquet',
                       ticker, as_day(day), as_day(day) + timedelta(days=1))

        self._wrap(DepthSource, '__init__', after_init=True)
        self._wrap(DepthSource, '_reader', prefixed_reader)
        self._wrap(DepthSource, '_load', depth_load)
        self._wrap(DepthSource, 'coverage', depth_coverage)
        self._wrap(DepthSource, 'tickers',
                   aggregate('DepthSource.tickers', ('bidprice', 'askprice')))
        self._wrap(DepthSource, 'window',
                   aggregate('DepthSource.window', ('bidprice', 'askprice')))
        self._wrap(TapeSource, '__init__', after_init=True)
        self._wrap(TapeSource, '_reader', prefixed_reader)
        self._wrap(TapeSource, '_rows', tape_rows)
        self._wrap(TapeSource, 'tickers', aggregate('TapeSource.tickers', ('total',)))

        # TickSource (CSV archive) ----------------------------------------
        def tick_table(obj, name):
            self._touch(obj.root, name, 'csv')

        def tick_build(obj, ticker, start, end, matched):
            lo, hi = as_day(start), as_day(end)
            self._read(obj.root, 'quote_matched', 'csv', ticker, lo, hi)
            for stem in ('quote_askprice', 'quote_bidprice'):
                self._read(obj.root, stem, 'csv', ticker, lo, hi,
                           depth=(None, TICK_DEPTH))

        self._wrap(TickSource, '__init__', after_init=True)
        self._wrap(TickSource, '_table', tick_table)
        self._wrap(TickSource, '_build', tick_build)
        return self

    def __exit__(self, *exc):
        for cls, name, orig in reversed(self._saved):
            setattr(cls, name, orig)
        self._saved.clear()
        return False


@contextlib.contextmanager
def _env(**values):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update({k: str(v) for k, v in values.items()})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def run_logged(target: Callable[[], object], db, work_dir: Optional[Path] = None
               ) -> Tuple[AccessLog, object]:
    """Run ``target`` against an on-demand DB cache; return the access log."""
    # Resolved, so the guard's path match agrees with every adapter's spelling.
    cache = Path(tempfile.mkdtemp(prefix='rivf26-cache-', dir=work_dir)).resolve()
    try:
        store = CacheStore(cache, db)
        log = AccessLog()
        with _env(PLUTUS_DATA_ROOT=cache, PLUTUS_DEPTH_ROOT=cache), \
                Recorder(log, store):
            outcome = target()
        return log, outcome
    finally:
        shutil.rmtree(cache, ignore_errors=True)


def pytest_target(args: Sequence[str]) -> Callable[[], int]:
    def target():
        import pytest
        os.chdir(REPO_ROOT)
        return int(pytest.main(['-p', 'no:cacheprovider', *args]))
    return target


def callable_target(spec: str) -> Callable[[], object]:
    module, _, attr = spec.partition(':')
    if not attr:
        raise SystemExit('--callable must be module:function')

    def target():
        obj = importlib.import_module(module)
        for part in attr.split('.'):
            obj = getattr(obj, part)
        return obj()
    return target


# ---------------------------------------------------------------------------
# Manifest
# ---------------------------------------------------------------------------

def _human(n: int) -> str:
    return f'{n / 1024:.1f} KiB' if n < 1024 * 1024 else f'{n / 1024 / 1024:.2f} MiB'


def query_description(stem: str, depth) -> str:
    _, table = split_stem(stem)
    if stem == MASTER_STEM:
        return '`quote.ticker WHERE tickersymbol = ANY(<tickers>)`'
    d = ''
    if depth is not None:
        d = (f' AND depth <= {depth[1]}' if depth[0] is None
             else f' AND depth BETWEEN {depth[0]} AND {depth[1]}')
    return (f'`quote.{table} WHERE tickersymbol = <t> AND datetime >= <lo> '
            f'AND datetime < <hi>{d}`, once per (ticker, interval) below')


def write_manifest(out_dir: Path, *, experiment: str, mode: str,
                   reproduces: str, command: str, results: List[FileResult],
                   log: Optional[AccessLog] = None,
                   run_outcome: Optional[str] = None,
                   verify_outcome: Optional[str] = None,
                   source: Optional[str] = None) -> Path:
    total = sum(r.bytes for r in results)
    L = [f'# DATA-MANIFEST: {experiment}', '',
         f'- **Reproduces:** {reproduces or "TODO: name the result (table/figure/test) this slice reproduces."}',
         f'- **Extraction mode:** `{mode}`',
         f'- **Command:** `{command}`',
         f'- **Source:** {source or PgClient.describe()}',
         f'- **Extracted on:** {date.today().isoformat()} with '
         f'`scripts/rivf26_extract.py` (pyarrow {pa.__version__}; writer '
         f'settings fixed in `WRITER`).',
         f'- **Total size:** {total:,} bytes ({_human(total)}) in {len(results)} files.']
    if run_outcome is not None:
        L.append(f'- **Logged run outcome:** {run_outcome}')
    if verify_outcome is not None:
        L.append(f'- **Verification run on this slice:** {verify_outcome}')
    L += ['', '## Why this window is minimal', '',
          'TODO (caller): explain why these tickers, dates and fields are the '
          'least that still proves the result (warm-up, trade count, the dated '
          'rule change inside the window).', '']
    if any(r.bytes > SIZE_FLAG_BYTES for r in results) or total > SIZE_FLAG_BYTES:
        L += ['## Size flag', '',
              f'**Over {_human(SIZE_FLAG_BYTES)}. Needs a one-line justification '
              f'before publication:** TODO.', '']
    empty = [r.file for r in results if r.rows == 0 and r.tickers
             and any(v is not None for v in r.tickers.values())]
    if empty:
        L += ['## Empty-result flag', '',
              'The DB returned **no rows** for these requested ranges. A consumer '
              'that needs them (e.g. book sizes for queue position) cannot be '
              'reproduced from this slice:', '']
        L += [f'- `{f}`' for f in empty] + ['']
    L += ['## Files', '',
          '| File | Rows | Bytes | sha256 |', '|---|---:|---:|---|']
    for r in results:
        flag = ' ⚠' if r.bytes > SIZE_FLAG_BYTES else ''
        L.append(f'| `{r.file}`{flag} | {r.rows:,} | {r.bytes:,} | `{r.sha256}` |')
    L += ['', '## Contents (tickers, ranges, fields, query)', '']
    for r in results:
        cols = ', '.join(n for n, _ in columns_for(r.stem))
        L.append(f'### `{r.file}`')
        L.append(f'- Fields: `{cols}`')
        L.append(f'- Query: {query_description(r.stem, r.depth)}')
        if r.stem.startswith('local_quote_'):
            L.append('- Note: the DB has no `local_quote_*` tables. This file '
                     'carries `quote.*` rows under the `local_quote` name because '
                     'its consumer reads that prefix. The old corpus\'s '
                     '`local_quote_*` came from a second observer, so values can '
                     'differ from it.')
        if not r.tickers:
            L.append('- Tickers: none (the file is required to exist, or was '
                     'looked for, but no row was read).')
        for t, ivs in sorted(r.tickers.items()):
            if ivs is None:
                L.append(f'- `{t}`: ticker-master row')
            else:
                spans = ', '.join(f'[{a}, {b})' for a, b in ivs)
                L.append(f'- `{t}`: {spans}')
        L.append('')
    if log is not None:
        L += ['## Access-log notes', '']
        if log.aggregates:
            L.append('Whole-table aggregate calls (answered from the slice, not '
                     'the full DB; check they do not move the result):')
            for stem, call, ticker in sorted(log.aggregates):
                L.append(f'- `{call}` on `{stem}` (ticker `{ticker}`)')
        if log.foreign:
            L.append('Reads from roots other than the logged root (NOT in this '
                     'slice):')
            for root, stem in sorted(log.foreign):
                L.append(f'- `{stem}` under `{root}`')
        if log.absent:
            L.append('Tables an adapter looked for that the logged root did not '
                     'serve (absent in the slice too):')
            for stem, fmt in sorted(log.absent):
                L.append(f'- `{file_name(stem, fmt)}`')
        if not (log.aggregates or log.foreign or log.absent):
            L.append('None: every read was a ticker- and date-scoped range read.')
        L.append('')
    path = out_dir / 'DATA-MANIFEST.md'
    path.write_text('\n'.join(L), encoding='utf-8')
    return path


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

_OUR_FILES = ('*.parquet', '*.csv', 'DATA-MANIFEST.md', 'request.json')


def _prepare_out(out_dir: Path, force: bool) -> None:
    if out_dir.exists():
        ours = [p for pat in _OUR_FILES for p in out_dir.glob(pat)]
        others = [p for p in out_dir.iterdir() if p not in ours]
        if others:
            raise SystemExit(f'{out_dir} holds files this tool did not write: '
                             f'{[p.name for p in others][:5]}')
        if ours and not force:
            raise SystemExit(f'{out_dir} already holds a slice; pass --force')
        for p in ours:
            p.unlink()
    out_dir.mkdir(parents=True, exist_ok=True)


def _write_request(out_dir: Path, request: dict) -> None:
    (out_dir / 'request.json').write_text(
        json.dumps(request, indent=1, sort_keys=True) + '\n', encoding='utf-8')


def _print_results(out_dir: Path, results: List[FileResult]) -> None:
    print(f'\nslice -> {out_dir}')
    for r in results:
        print(f'  {r.file:32} rows={r.rows:>8,}  bytes={r.bytes:>10,}  {r.sha256}')
    total = sum(r.bytes for r in results)
    print(f'  TOTAL {total:,} bytes ({_human(total)})')


def _verify(pytest_args: Sequence[str], out_dir: Path) -> str:
    env = {**os.environ, 'PLUTUS_DATA_ROOT': str(out_dir),
           'PLUTUS_DEPTH_ROOT': str(out_dir)}
    proc = subprocess.run(
        [sys.executable, '-m', 'pytest', '-p', 'no:cacheprovider', '-q', '-rs',
         *pytest_args], cwd=REPO_ROOT, env=env, capture_output=True, text=True)
    tail = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()][-1:]
    return f'pytest exit {proc.returncode}: {tail[0] if tail else "(no output)"}'


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    command = 'rivf26_extract.py ' + ' '.join(argv)
    passthrough: List[str] = []
    if '--' in argv:
        i = argv.index('--')
        argv, passthrough = argv[:i], argv[i + 1:]

    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0],
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='mode', required=True)
    for name in ('log', 'declared'):
        p = sub.add_parser(name)
        p.add_argument('--experiment', required=True,
                       help='slice name; output goes to <out-root>/<experiment>/')
        p.add_argument('--out-root', type=Path, default=DEFAULT_OUT_ROOT)
        p.add_argument('--reproduces', default='',
                       help='which result this slice reproduces (manifest)')
        p.add_argument('--force', action='store_true',
                       help='replace a slice this tool wrote earlier')
        p.add_argument('--cred-file', type=Path, default=CRED_FILE)
        p.add_argument('--source', choices=('db', 'archive'), default='db',
                       help='db: the remote Algotrade DB (default); archive: the '
                            'local parquet archive, for book sizes before 2023')
        p.add_argument('--archive-root', type=Path, default=ARCHIVE_ROOT)
    lp = sub.choices['log']
    lp.add_argument('--callable', help='module:function to run instead of pytest')
    lp.add_argument('--sys-path', action='append', default=[],
                    help='prepend to sys.path (repo-relative) for --callable')
    lp.add_argument('--verify', action='store_true',
                    help='re-run the pytest selection against the written slice')
    lp.add_argument('--allow-fail', action='store_true',
                    help='write the slice even if the logged run fails')
    dp = sub.choices['declared']
    dp.add_argument('--request', type=Path, help='request.json to replay')
    dp.add_argument('--files', help='comma list of file stems, e.g. quote_close,'
                    'local_quote_bidprice (add .csv for the tick archive)')
    dp.add_argument('--tickers', help='comma list of tickers')
    dp.add_argument('--start', type=date.fromisoformat, help='first day (inclusive)')
    dp.add_argument('--end', type=date.fromisoformat, help='last day (exclusive)')
    dp.add_argument('--max-depth', type=int, help='book depth bound (1..N)')
    dp.add_argument('--no-ticker-master', action='store_true',
                    help='omit quote_ticker rows for the declared tickers')
    args = ap.parse_args(argv)

    out_dir = args.out_root / args.experiment
    _prepare_out(out_dir, args.force)

    db = (ArchiveClient(args.archive_root) if args.source == 'archive'
          else PgClient(args.cred_file))
    try:
        log = None
        run_outcome = verify_outcome = None
        if args.mode == 'log':
            if bool(args.callable) == bool(passthrough):
                raise SystemExit('log needs exactly one of --callable or -- <pytest args>')
            for p in reversed(args.sys_path):
                sys.path.insert(0, str(REPO_ROOT / p))
            target = (callable_target(args.callable) if args.callable
                      else pytest_target(passthrough))
            log, outcome = run_logged(target, db)
            if log.unlogged:
                raise SystemExit(f'{len(log.unlogged)} unlogged read(s); refusing')
            if not args.callable:
                run_outcome = f'pytest exit {outcome}'
                if outcome != 0 and not args.allow_fail:
                    raise SystemExit(f'logged run failed ({run_outcome}); '
                                     'pass --allow-fail to write anyway')
            else:
                run_outcome = 'callable returned'
            request = log.to_request()
        else:
            if args.request:
                request = json.loads(args.request.read_text())
            else:
                if not (args.files and args.tickers and args.start and args.end):
                    raise SystemExit('declared needs --request or '
                                     '--files/--tickers/--start/--end')
                request = request_from_declared(
                    [f.strip() for f in args.files.split(',') if f.strip()],
                    [t.strip() for t in args.tickers.split(',') if t.strip()],
                    args.start, args.end, args.max_depth,
                    ticker_master=not args.no_ticker_master)
        results = extract(db, request, out_dir)
        print(f'{args.source} queries issued: {db.queries}')
    finally:
        db.close()

    _write_request(out_dir, request)
    if args.mode == 'log' and args.verify and passthrough:
        verify_outcome = _verify(passthrough, out_dir)
        print(f'verify: {verify_outcome}')
    write_manifest(out_dir, experiment=args.experiment, mode=args.mode,
                   reproduces=args.reproduces, command=command, results=results,
                   log=log, run_outcome=run_outcome, verify_outcome=verify_outcome,
                   source=db.describe())
    _print_results(out_dir, results)
    return 0


if __name__ == '__main__':
    sys.exit(main())
