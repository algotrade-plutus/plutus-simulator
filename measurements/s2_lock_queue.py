"""S2: was the broker's floor sale blocked on DIG's limit-down days? Read the queue.

Backs the S2 lock claim in the RIVF'26 paper (camera-ready). The daily S2 run
(``strategies/test_s2_equity_margin_momentum.py``) can only *assume* a sale at the
floor filled on a day DIG closed there: a daily bar shows the price, not the
sell queue. This reads the queue.

The question, per floor-close day
---------------------------------
S2 decides at 10:00 (``strategies/_harness.OPEN_MARK``), and the broker's forced
sale is a LIMIT at the floor (``ForcedSalePrice.FLOOR``). Submitted then, it joins
the **back** of the queue at the floor. Under price-time priority it fills only if
the volume that trades at the floor afterwards -- the closing auction included,
since an unfilled LO carries into it -- exceeds the queue already ahead of it.

Verdict, from three observations at or after the decision time:

``blocked``
    the best ask at 10:00 is the floor, **every** print after 10:00 is at the
    floor (so no bid above it was ever hit), and the queue ahead at 10:00 is
    larger than everything that traded afterwards. The sale fills only if more
    than ``cancel_share_needed`` of the queue ahead cancelled first -- the one
    assumption left, and it is stated with its size rather than hidden.
``cleared``
    the ask sat at the floor, but at least as much traded afterwards as was
    queued ahead: the sale could have filled.
``not locked``
    at 10:00 the best ask was above the floor, or something traded above the
    floor afterwards. A close at the floor is not a lock at 10:00.

What this does not read: the bid ladder. The depth data has no deletion record,
so a bid side that empties at a lock leaves its last (auction) quotes behind as a
stale "ghost" (``src/plutus/market/session/book_walk.py``, module docstring). The
tape is what proves nobody bought above the floor.

Data
----
Two minimal slices written by ``scripts/rivf26_extract.py`` from the owner's
local archive (the remote DB has no bid/ask sizes before 2023-01-03):

* ``daily/``: DIG ``quote_close``/``quote_floor``/``quote_max`` over S2's window,
  to find the floor-close days;
* ``book/``: on those days only, level-1 ``local_quote_askprice``/``asksize`` and
  the tape ``local_quote_matched``/``local_quote_total``. The request for it is
  produced here (``request`` subcommand), so the slice is exactly what is read.

RUN
    python measurements/s2_lock_queue.py report --daily D --book B
    python measurements/s2_lock_queue.py request --daily D > request.json
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Sequence

import duckdb

TICKER = "DIG"
START, END = date(2022, 9, 5), date(2022, 11, 15)      # S2's window, END exclusive
DECISION = time(10, 0)                                  # S2's decision mark
#: The book/tape files the measurement reads, at level 1 only where depth applies.
BOOK_FILES = (("local_quote_askprice.parquet", True),
              ("local_quote_asksize.parquet", True),
              ("local_quote_matched.parquet", False),
              ("local_quote_total.parquet", False))


@dataclass(frozen=True)
class DayBar:
    day: date
    close: Decimal
    floor: Decimal
    high: Decimal

    @property
    def full_floor(self) -> bool:
        """Pinned at the floor all session: the high never left it."""
        return self.high == self.floor


@dataclass(frozen=True)
class Row:
    day: date
    full_floor: bool
    floor: Decimal
    ask_price: Optional[Decimal]      # best ask as of the decision time
    queue_ahead: Optional[int]        # its displayed size: all of it is ahead of us
    ask_at_floor: bool
    prints_only_at_floor: bool        # every print after the decision was at the floor
    volume_after: int                 # shares traded after the decision, ATC included
    cancel_share_needed: Optional[float]
    verdict: str


def _dec(x) -> Optional[Decimal]:
    return None if x is None else Decimal(str(x)).quantize(Decimal("0.000001"))


def _con() -> duckdb.DuckDBPyConnection:
    return duckdb.connect()


def floor_close_days(daily_root: Path, ticker: str = TICKER, start: date = START,
                     end: date = END) -> List[DayBar]:
    """The days in ``[start, end)`` on which ``ticker`` closed at its floor."""
    r = Path(daily_root)
    rows = _con().execute(f"""
        SELECT c.datetime, c.price, f.price, m.price
        FROM read_parquet('{r / 'quote_close.parquet'}') c
        JOIN read_parquet('{r / 'quote_floor.parquet'}') f USING (datetime, tickersymbol)
        JOIN read_parquet('{r / 'quote_max.parquet'}')   m USING (datetime, tickersymbol)
        WHERE c.tickersymbol = ? AND c.datetime >= ? AND c.datetime < ?
        ORDER BY c.datetime""", [ticker, start, end]).fetchall()
    bars = [DayBar(d if isinstance(d, date) else d.date(), _dec(c), _dec(f), _dec(h))
            for d, c, f, h in rows]
    return [b for b in bars if b.close == b.floor]


def book_request(days: Sequence[DayBar], ticker: str = TICKER) -> dict:
    """The ``rivf26_extract.py declared --request`` input: the book/tape files on
    exactly these days, level 1 only."""
    spans = [[b.day.isoformat(), (b.day + timedelta(days=1)).isoformat()]
             for b in days]
    files = []
    for name, has_depth in BOOK_FILES:
        entry = {"file": name, "tickers": {ticker: spans}}
        if has_depth:
            entry["depth"] = [1, 1]
        files.append(entry)
    return {"version": 1, "files": files}


def _as_of(con, path: Path, col: str, ticker: str, lo: datetime, at: datetime):
    """The last level-1 value of ``col`` in ``[lo, at]`` (the book is stored on change)."""
    return con.execute(f"""
        SELECT {col} FROM read_parquet('{path}')
        WHERE tickersymbol = ? AND depth = 1 AND datetime >= ? AND datetime <= ?
          AND {col} IS NOT NULL
        ORDER BY datetime DESC LIMIT 1""", [ticker, lo, at]).fetchone()


def measure_day(book_root: Path, bar: DayBar, ticker: str = TICKER,
                at: time = DECISION) -> Row:
    b, con = Path(book_root), _con()
    open_ = datetime.combine(bar.day, time(9, 0))
    t = datetime.combine(bar.day, at)
    eod = datetime.combine(bar.day + timedelta(days=1), time())

    ap = _as_of(con, b / "local_quote_askprice.parquet", "price", ticker, open_, t)
    az = _as_of(con, b / "local_quote_asksize.parquet", "quantity", ticker, open_, t)
    ask_price = _dec(ap[0]) if ap else None
    queue = int(az[0]) if az else None

    # Cumulative volume. The tape carries an end-of-day row stamped 00:00:00 of
    # its own day; starting at the 09:00 open excludes this day's, and the
    # exclusive upper bound excludes the *next* day's, which a multi-day slice
    # also holds (it would add that day's whole volume).
    total = b / "local_quote_total.parquet"
    def cum(lo, hi):
        v = con.execute(f"""SELECT max(quantity) FROM read_parquet('{total}')
            WHERE tickersymbol = ? AND datetime >= ? AND datetime < ?""",
                        [ticker, lo, hi]).fetchone()[0]
        return int(v or 0)
    volume_after = cum(open_, eod) - cum(open_, t + timedelta(microseconds=1))

    top = con.execute(f"""SELECT max(price) FROM read_parquet('{b / 'local_quote_matched.parquet'}')
        WHERE tickersymbol = ? AND datetime > ? AND datetime < ?""",
                      [ticker, t, eod]).fetchone()[0]
    prints_only_at_floor = top is None or _dec(top) <= bar.floor

    ask_at_floor = ask_price is not None and ask_price == bar.floor
    if not (ask_at_floor and prints_only_at_floor):
        verdict, need = "not locked", None
    elif queue is not None and queue > volume_after:
        verdict, need = "blocked", 1 - volume_after / queue
    else:
        verdict, need = "cleared", None
    return Row(bar.day, bar.full_floor, bar.floor, ask_price, queue, ask_at_floor,
               prints_only_at_floor, volume_after, need, verdict)


def measure(daily_root: Path, book_root: Path, ticker: str = TICKER,
            start: date = START, end: date = END, at: time = DECISION) -> List[Row]:
    return [measure_day(book_root, bar, ticker, at)
            for bar in floor_close_days(daily_root, ticker, start, end)]


def report(rows: Sequence[Row]) -> str:
    out = ["| Day | Pinned all day | Floor | Ask @10:00 | Queue ahead | Volume after "
           "| Queue / volume | Verdict |",
           "|---|---|---|---|---:|---:|---:|---|"]
    for r in rows:
        ratio = (f"{r.queue_ahead / r.volume_after:.1f}x"
                 if r.queue_ahead and r.volume_after else "")
        out.append(f"| {r.day} | {'yes' if r.full_floor else ''} | {r.floor.normalize()} "
                   f"| {r.ask_price.normalize() if r.ask_price is not None else ''} "
                   f"| {r.queue_ahead or 0:,} | {r.volume_after:,} | {ratio} "
                   f"| {r.verdict}"
                   + (f" (needs >{r.cancel_share_needed:.0%} of the queue to cancel)"
                      if r.cancel_share_needed is not None else "") + " |")
    blocked = sum(r.verdict == "blocked" for r in rows)
    out.append("")
    out.append(f"{len(rows)} floor-close days in [{START}, {END}); "
               f"{sum(r.full_floor for r in rows)} pinned all day; "
               f"{blocked} with the 10:00 floor sale blocked.")
    return "\n".join(out)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    rq = sub.add_parser("request", help="print the book-slice request.json")
    rq.add_argument("--daily", type=Path, required=True)
    rp = sub.add_parser("report", help="print the measurement")
    rp.add_argument("--daily", type=Path, required=True)
    rp.add_argument("--book", type=Path, required=True)
    rp.add_argument("--json", type=Path, help="also write rows as JSON here")
    a = ap.parse_args(argv)
    if a.cmd == "request":
        print(json.dumps(book_request(floor_close_days(a.daily)), indent=1))
        return 0
    rows = measure(a.daily, a.book)
    print(report(rows))
    if a.json:
        a.json.write_text(json.dumps([asdict(r) for r in rows], indent=1, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
