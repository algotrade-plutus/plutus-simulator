# Known limitations at the RIVF'26 camera-ready (for the paper's limitations paragraph)

Everything here is known, reproducible and left as is on purpose. In each case the engine reports the limit
(INDETERMINATE, UNKNOWN, or a counted event) rather than guessing. Fixed during camera-ready work, so **no longer**
limitations: the conservative queue's taker sweeps (`e528633`); the derivatives VM baseline on adds and flips
(`8295502`); brokers relaxing VSDC derivatives terms (`52c6d5c`); band-edge orders on book (tick) sessions, now
decided from the book walk (`a729b7e`); `soft` labelling every market-order fill `TRADED_THROUGH`, now graded like
a limit at the band edge (`694ae11`). Their numbers (1 and 5) are kept as stubs so references to the others stay
valid.

## Engine

1. *(Fixed in `a729b7e`: band-edge orders on book sessions are decided from the book walk.)*
2. **A locked book cannot be read from the depth data.** The data has no deletion records, so when one side empties
   at a lock it keeps its last (auction) quotes as a stale "ghost". The book walk refuses crossed or stale books
   rather than trading on them. Consequence: a lock is proven from the queue size and the tape outside the engine
   (`measurements/s2_lock_queue.py`), not by the engine's fill decision.
3. **Orders beyond the observed depth cannot be placed in a conservative queue.** Book data has 3 levels. A resting
   order priced further out (MarketMaker quotes about 31 ticks away) has no observable queue ahead, so the
   conservative and probabilistic queues leave it INDETERMINATE (`book_size`). The optimistic arm and the queue
   spread carry the result.
4. **After the KRX cutover (2025-05-05) the engine admits derivatives orders** although its margin model is
   unresolved there (`margin_model()` raises `UnresolvedRule`). Margin is then computed on the pre-KRX shape and
   each such mark is counted (`margin_model.unsourced`). Only a strategy-side guard refuses to trade (S6, MM). A
   strategy without the guard is simulated on an unsourced margin rule, and the run says so in its counters.
5. *(Fixed in `694ae11`: `soft` grades a market-order fill like a limit at the band edge.)*
6. **The book walk has no auction arm by default**: orders resting into the ATC come back INDETERMINATE unless an
   auction policy is composed in.

## Rules

7. **The rulebook starts on 2020-01-01.** Earlier dates resolve to UNKNOWN (orders INDETERMINATE). The 2016-09-12
   tick revision is therefore **not** encoded; the pre-2016 grid was never sourced.
8. **12 uncovered rule edges**, all resolving to UNKNOWN, never to a wrong value (T8.1 validator). They are widened
   bands and some ticks before their source dates (HSX, HNX, UPCoM), and two deliberate VSDC charge switches.
   They are pinned in `tests/market/session/test_rule_tables.py::OPEN_EDGES`.

## Data

9. **The remote DB has no bid/ask sizes before 2023-01-03.** Book work before 2023 uses the local Algotrade archive
   (sizes from 2021-07-01; book rows from backup dumps, offset from the trade tables by tens of ms).
10. **The DB ticker master holds only each ticker's current exchange.** Historical exchange moves are invisible.
    This lowers the band-agreement measure to 91.90% (old 97.59%): 28 tickers that moved to HSX after 2022 carry
    most of the misses.
11. **Gaps found in the source data**:
    - ceil/floor missing for VN30F2212 on 2022-12-02, 12-05 and 12-06 (DB and archive);
    - 3 futures days per Pair window where the daily close lies outside the day's min–max;
    - DIG 2022-11-07 archive book at 87% of the DB's price rows.

## Measurement caveats

12. **Overlapping windows:** the margin-incidence intervals (381 overlapping entries) are too narrow. E1 adds a
    ticker-cluster bootstrap for its headline numbers.
13. **Population drift vs the old corpus** (more tickers or days in E1, F2 and the HSX measures) comes from the
    DB's coverage, not the selection rules, which are unchanged. The old runs did not save their ticker lists, so
    the difference cannot be itemised.
