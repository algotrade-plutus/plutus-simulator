"""Band-lock ladder audit -- concrete ticker-days through band_lock_decision.

Design section 4d's owner sign-off script: for each named case, build the real
daily interval via :class:`DataHubSource`, construct a marketable order at the
band edge, call :func:`band_lock_decision` (session/fills.py) unchanged, and
print the raw evidence next to the resolver's verdict. Nothing here re-derives
the ladder; it only exercises the shipped function and reports what it did.

RUN
    source .venv/bin/activate
    export PYTHONPATH=/Users/dan/algotrade-research/plutus/src
    python measurements/band_lock_ladder_audit.py --root <corpus-root> \
        | tee /tmp/band_lock_audit.txt

Corpus root
------------------------------------------------------------------------
The SB frozen slice (``proto/.../data/market/``) only carries the OOS
universe and cannot serve most of the cases below. :func:`_default_root`
checks, in the brief's stated order, the first of three roots that exists on
this machine: ``/Users/dan/dataset/hermes-parquet`` (found -- Parquet, all
daily fields, bands 2021-02-05..2022-12-30), then
``/Users/dan/algotrade-research/dataset/hermes-parquet`` (absent here), then
``/Users/dan/dataset/stock_quote_12.2020-09.2024`` (present but CSV/tick-only
and far larger -- a fallback, not the default). ``--root`` overrides.

Why every case here is a real, verified ticker-day, not the design's list
------------------------------------------------------------------------
The design (docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md
section 4d) named DAN 2022-01-04 for the true-lock rung. Task 2 (and this
task, independently) verified that is wrong: DAN is UPCOM and its real bar is
a *collapse with volume=1800* -- the ASSUMED tier, not a proven lock. So every
row below was found by scanning the corpus with DuckDB first and verifying
the candidate through :func:`band_lock_decision` second; see each case's
comment for what was checked and, where a design-named case is kept, what its
*verified* verdict actually is (which is not always what a reader would
guess -- that gap is this audit's main finding, below).

THE KEY FINDING -- option B's NO_FILL is real but almost never fires here
------------------------------------------------------------------------
A full-corpus DuckDB scan (2021-02-05..2022-12-30, every ticker) for
BUY-side true full-session collapses (``open==high==low==close==ceiling``)
found **8,611** candidate ticker-days. Of those:

* **8,610 (99.99%)** carry a positive ``quote_dailyvolume`` -> the ASSUMED
  tier -> ``band_lock_decision`` returns ``None`` (passthrough to the active
  fill policy), *not* ``NO_FILL``.
* **1 (0.01%)** carries no volume row at all -> the proven ``NO_FILL`` branch.
  That single ticker-day is PTG 2021-02-17 (used as Case A below) -- and PTG
  is not a name that got squeezed to its limit by order flow: it is a
  UPCOM penny stock parked at 0.1-0.3 (thousand VND) with almost no recorded
  trading across its entire ~13-year history in this corpus (two nonzero
  volume rows sampled in 3,243 daily rows).
* Zero ticker-days anywhere in ``quote_dailyvolume`` carry a *literal* 0
  (confirmed: ``MIN(quantity)=1`` over 2,562,664 rows) -- exactly the
  fills.py docstring's claim that "the corpus never stores a literal 0",
  verified rather than assumed.
* The mirror (SELL-side floor collapses) and the ATO-only test
  (``open==ceiling``, any of 15,903 candidates) show the identical shape:
  absent-volume rows exist but are rare (183/5,535 floor collapses; 1/15,903
  ATO-opens) and, in both scans, trace to this same single dormant ticker.

**So: yes, option B's ``NO_FILL`` does fire on a real corpus lock (it is not
dead code) -- but at this daily OHLC+volume resolution, a lock the data can
*prove* is a no-fill is close to nonexistent among real, liquid band-lock
events. The corpus's daily ``quote_dailyvolume`` is a whole-session figure:
even a bar that never leaves the edge almost always shows *some* volume
(matched at the edge, or a token print elsewhere that day), which is exactly
row B6/S6's ``ASSUMED`` tier, deferred to the active fill policy rather than
settled by the resolver. The rare true ``NO_FILL`` we did find came from a
stock nobody was trading at all, not from a name that hit real buying or
selling pressure.** This is the same coarsening design section 2 already
flags ("volume is the session-daily figure ... not necessarily at the
band") -- this audit is what puts numbers on it, as section 4d asks for.

A second instance of the same coarsening shows up on Case D (below): NXT
2022-01-27 is a real ATO-lock candidate (open==ceiling), but its *day*
volume (4,900) is nonzero because the price fell later in continuous
trading -- so the ATO test also lands on ``ASSUMED``/passthrough, not the
``NO_FILL`` a reader would naively expect from "opened locked". The daily
volume field cannot tell "the opening cross traded" apart from "the
afternoon traded"; only a denser (tick/auction-specific) volume signal
could, and design section 2 names that as the dense-tier refinement this
adapter does not supply. Case D' substitutes the same dormant PTG ticker to
show the ATO ``NO_FILL`` branch *can* fire when the evidence really is
absent.

No resolver bug was found: every printed verdict below was hand-checked
against the printed raw evidence before this docstring was written (see
task-6-report.md), and every one matches what section 1's ladder (tables
1a/1b) says it should for the printed inputs.
"""
import argparse
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path

from plutus.market.protocol import Order, OrderType, SessionPhase, Side
from plutus.market.adapters.datahub import DataHubSource
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (OrderRecord, OrderState, TimeInForce,
                                         Venue)

#: Checked in this order; the first that exists on this machine is the
#: default. See the module docstring's "Corpus root" section.
_CANDIDATE_ROOTS = [
    "/Users/dan/dataset/hermes-parquet",
    "/Users/dan/algotrade-research/dataset/hermes-parquet",
    "/Users/dan/dataset/stock_quote_12.2020-09.2024",
]


def _default_root() -> str:
    for root in _CANDIDATE_ROOTS:
        if Path(root).exists():
            return root
    return _CANDIDATE_ROOTS[0]


# (label, ticker, YYYY-MM-DD, side, order_type, note)
#
# Every row was found by a DuckDB scan of the corpus first, then verified by
# actually calling band_lock_decision (not just reasoned about) -- see
# task-6-report.md for the queries and the full output.
CASES = [
    ("A1 true lock (BUY, PROVEN no-fill)", "PTG", "2021-02-17", Side.BUY,
     OrderType.LIMIT,
     "Design named DAN 2022-01-04 for this rung; VERIFIED WRONG (task-2 and "
     "this task, independently): DAN is UPCOM and its real bar is a collapse "
     "with volume=1800 (the ASSUMED tier), not a proven lock. Substituted "
     "PTG 2021-02-17 -- the ONLY buy-side full-session collapse "
     "(O=H=L=C=ceiling) with absent quote_dailyvolume in the whole corpus "
     "(8,611 candidates scanned, 8,610 carry positive volume). PTG is a "
     "dormant UPCOM penny stock (~13y of history, almost no recorded "
     "volume); its ceiling(0.1)/floor(0.2) are inverted from the usual "
     "ceiling>floor shape on this, its very first row in the corpus -- a "
     "data artifact worth flagging, but irrelevant to a BUY test, which "
     "never reads the floor."),
    ("A2 true lock (SELL mirror)", "PTG", "2021-05-28", Side.SELL,
     OrderType.LIMIT,
     "Not in the design's list; added because the floor-side scan (5,535 "
     "candidates) found the same shape -- 183 absent-volume days, and every "
     "single one of them is this same PTG, now trading a normal (floor < "
     "ceiling) band. Confirms the Case A finding is not one anomalous row."),
    ("B  traded-through", "DMN", "2022-01-06", Side.BUY, OrderType.LIMIT,
     "Design's own candidate. Verified as named, no substitution: real bar "
     "is O=12.7 H=14.7 L=12.7 C=14.7 ceiling=14.7 -- closed AT the cap but "
     "traded up from 12.7 intraday, so low < ceiling -> traded-through -> "
     "passthrough. This is exactly the over-assertion the design fixes: the "
     "old close==ceiling proxy would have called this a lock."),
    ("D  ATO-lock, as named", "NXT", "2022-01-27", Side.BUY,
     OrderType.AT_THE_OPENING,
     "Design's own candidate. The ticker-day is real and IS a genuine "
     "ATO-lock candidate (open=13.4=ceiling) -- verified, no substitution of "
     "the day. But the naive expectation (NO_FILL) is WRONG: real day "
     "volume is 4,900 (>0) because the price fell to 11.6 later in "
     "continuous trading, and the daily volume field cannot separate "
     "'the opening cross traded' from 'the afternoon traded'. So the "
     "verified verdict is PASSTHROUGH via the ASSUMED tier, not NO_FILL -- "
     "the same daily-volume coarsening as the key finding, on the ATO "
     "instant instead of the whole-session one."),
    ("D  same-day continuous contrast", "NXT", "2022-01-27", Side.BUY,
     OrderType.LIMIT,
     "Added to show the phase-appropriate instant in action on the SAME "
     "underlying day the design paired with Case D: a continuous order "
     "tests the session low (11.6 < 13.4 -> traded-through), which is the "
     "'fill for a continuous order same day' half of the design's Case D "
     "narrative (section 3c). Lands on the same PASSTHROUGH outcome as the "
     "ATO row above for this real day, but by the traded-through path B4 "
     "(low < ceiling), not the ASSUMED path B6 (collapsed-at-open, "
     "volume>0) the ATO row takes -- band_lock_decision returns a bare "
     "None for a passthrough either way, with no field that tells the two "
     "apart, so only the OHLC row printed above (open vs low, against the "
     "same ceiling) distinguishes which path fired."),
    ("D' ATO-lock, clean NO_FILL", "PTG", "2021-02-17", Side.BUY,
     OrderType.AT_THE_OPENING,
     "Bonus: no ticker-day in the corpus satisfies the textbook 'opened "
     "locked, fell later, whole-day volume absent' pattern (checked: of "
     "15,903 real open==ceiling candidates corpus-wide, exactly 1 has "
     "absent volume, and it is this same flat PTG day, not a 'fell later' "
     "one). Reused PTG here only to show the ATO NO_FILL branch genuinely "
     "fires when the evidence supports it, on the same dormant name as "
     "Case A."),
    ("U  INDETERMINATE (data gap)", "CFPT2010", "2021-02-17", Side.BUY,
     OrderType.LIMIT,
     "Design asked for 'an UNKNOWN/data-gap example' if findable. Found by "
     "scanning for close+ceiling present but the session LOW (quote_min) "
     "row absent: CFPT2010 (an FPT covered warrant) closed AT its ceiling "
     "(26.15) that day -- marketable -- but carries no LOW at all, so the "
     "continuous BUY test has no instant to check the edge against."),
]


def _order(ticker, day, side, order_type, edge):
    """The marketable probe order for one case: a limit AT the edge, or a
    market-family ATO/ATC order (no price -- the auction prices it)."""
    price = (None if order_type in (OrderType.AT_THE_OPENING,
                                    OrderType.AT_THE_CLOSE) else edge)
    tif = (TimeInForce.AUCTION_ONLY
           if order_type in (OrderType.AT_THE_OPENING, OrderType.AT_THE_CLOSE)
           else TimeInForce.DAY)
    ts = datetime.fromisoformat(day)
    return OrderRecord(order_id="audit", venue=Venue.HSX,
                       state=OrderState.RESTING, time_in_force=tif,
                       submitted_at=ts, updated_at=ts, fills=(),
                       order=Order(ticker=ticker, side=side, quantity=1000,
                                   order_type=order_type, limit_price=price))


def _auction_view(interval, order_type):
    """The same daily bar, viewed through the auction phase an ATO/ATC order
    tests -- OPENING_AUCTION for ATO, CLOSING_AUCTION for ATC.

    :class:`DataHubSource` always stamps a daily bar's ``state.session`` as
    ``CONTINUOUS`` ("set, never inferred": a daily ts is midnight and cannot
    be read back into a phase -- datahub.py's module docstring). But
    ``band_lock_decision``'s ``_lock_instant`` branches on exactly that field
    to decide whether to test the open, the close, or the session low/high
    (fills.py). So testing an ATO/ATC order against this corpus's daily bars
    needs the same phase override the unit tests use directly
    (tests/market/session/test_band_lock_fill.py's ``_interval(phase=...)``)
    -- this function is that override, applied to a real adapter-built
    interval instead of a hand-built test one. Every other field (the OHLC,
    the volume, the band) is untouched real data; only the phase tag the
    order type needs to be read against changes.
    """
    if order_type is OrderType.AT_THE_OPENING:
        phase = SessionPhase.OPENING_AUCTION
    elif order_type is OrderType.AT_THE_CLOSE:
        phase = SessionPhase.CLOSING_AUCTION
    else:
        return interval
    return replace(interval, state=replace(interval.state, session=phase))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default=_default_root(),
                    help="Corpus root DataHubSource.for_root() reads. "
                         f"Default (first that exists): {_CANDIDATE_ROOTS}")
    args = ap.parse_args()
    print(f"# root: {args.root}\n")

    src = DataHubSource.for_root(args.root)
    for label, ticker, day, side, ot, note in CASES:
        d0 = datetime.fromisoformat(day)
        iv = src.interval(ticker, d0, d0 + timedelta(days=1))
        print(f"[{label}] {ticker} {day} {side.value} {ot.value}")
        print(f"    note: {note}")
        if iv is None:
            print("    --> NO BAR in this root\n")
            continue

        iv = _auction_view(iv, ot)
        edge = iv.state.ceiling if side is Side.BUY else iv.state.floor
        order = _order(ticker, day, side, ot, edge)
        decision = band_lock_decision(order, iv)
        verdict = ("PASSTHROUGH (policy fills)" if decision is None else
                   f"{decision.outcome.value.upper()}: {decision.reason}")

        print(f"    band  ceil={iv.state.ceiling} floor={iv.state.floor} "
              f"(session read as {iv.session.value})")
        print(f"    ohlc  O={iv.open} H={iv.high} L={iv.low} C={iv.close} "
              f"vol={iv.volume} book={'yes' if iv.book else 'no'} "
              f"missing={sorted(f.value for f in iv.missing)}")
        print(f"    -->   {verdict}\n")


if __name__ == "__main__":
    main()
