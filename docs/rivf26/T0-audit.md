# T0 audit: setup, DB access, and what runs with no corpus (2026-11-24)

Handoff: `docs/HANDOFF-2026-11-24-camera-ready.md`, task T0. Branch `rivf26` (from `master` @ `5b54b53`).

## 1. Setup

| Repo | Branch | Base |
|---|---|---|
| `plutus-simulator` | `rivf26` | `master` @ `5b54b53` |
| `proto/ProtoSmartBeta` | `rivf26` | `main` @ `f5c9e8e` (public, pre-RIVF) |
| `proto/ProtoMarketMaker` | `rivf26` | `main` @ `44acefc` (public, pre-RIVF) |
| `proto/ProtoGrid` | `rivf26` | new empty repo (`git init`) |
| `proto/ProtoPair` | `rivf26` | new empty repo (`git init`) |

Working data folder created: `$RIVF26_DATA/` (outside every repo).

Python: the only Python ≥3.12 on this machine is Homebrew 3.15.2, and `uv` is not installed. The env is
`plutus-simulator/.venv` (gitignored), created with `python3.15 -m venv` and then
`pip install -e ".[test]" psycopg2-binary` (pandas 3.1.1, pyarrow 26.0.1, duckdb 2.0.1, pytest 9.2).

`.gitignore` now also ignores `*.env`, `.env*`, `cred/`, `*credential*`, `*.pgpass` and `rivf26-raw/`.

## 2. DB access

- PostgreSQL 13.5. Credentials are read at runtime from `system/cred/amz-database.env` (`SOURCE_DB_*`
  keys) into memory only. Connections are opened with `default_transaction_read_only=on`, which was verified.
- **The schema mirrors the parquet layout one-to-one:** table `quote.<x>` ↔ file `quote_<x>.parquet`, with the same
  columns (`datetime, tickersymbol, price|quantity[, depth]`). Slices can therefore be written in the layout
  `DataHubSource`, `DepthSource` and `TapeSource` already read, with no engine change.
- Cross-check: on all 202 ticker-days in `strategies/fixtures/parquet/quote_close.parquet`, DB `quote.close`
  matches to 4 decimal places (**0 mismatches**). The DB has the same prices as the old hermes corpus, in thousands of đồng.

Coverage of the tables the engine reads (min..max `datetime`, exact `count(*)`):

| Table | From | To | Rows |
|---|---|---|---|
| close / open / max / min | (long history) | 2026-11-23 | 6.74–6.80 M |
| ceil / floor | 2021-02-05 | 2026-11-23 | 2.36 M |
| reference | 2021-01-04 | 2026-11-23 | 2.36 M |
| dailyvolume | 2000-07-28 | 2026-11-23 | 4.83 M |
| matched (tick) | 2020-12-02 | 2026-11-23 | 117 M |
| matchedvolume (tick) | 2021-01-15 | 2026-11-23 | 305 M |
| high / low (intraday running) | 2021-01-15 | 2026-11-23 | 5.4 / 5.9 M |
| total, bid/ask price, bid/ask size | — | — | too large for `count(*)` in 90 s; scope every query by ticker and date |
| futurecontractcode | 2021-06-01 | 2030-01-01 | 8,757 |
| vn30 (membership) | 2016-07-25 | 2026-08-03 | 540 |
| settlementprice | 2022-06-13 | 2026-11-19 | 13,040 |
| ticker | — | — | 4,940 (HSX 423 stocks, HNXDS 80 futures, …) |

Notes for T1:
- `pg_stat` row estimates are stale. `futurecontractcode` and `vn30` show 0 there but are populated.
- The DB has no `local_quote_*` tables. Those were a separate extract format in the corpus. T1 must decide
  whether to write the book and tape as `quote_*` or `local_quote_*` per consumer. S8 already reads both
  prefixes, so check each J-test's expected prefix.
- `futurecontractcode` starts on 2021-06-01. Any futures roll before that needs another source or a
  rule-based mapping.

## 3. What runs today with no corpus

The handoff's command `env -u PLUTUS_DATA_ROOT pytest scenarios strategies` **cannot work as one
invocation**. Both directories have a top-level `_harness.py`, so the strategy tests import the scenarios
copy and fail at collection with `ImportError: CorpusFeed`. Each directory has to be run on its own (or the
harnesses renamed or packaged; that decision belongs to T3).

### scenarios/: 5 passed, 34 skipped, 0 failed (39 tests)

| Status | Tests |
|---|---|
| pass (no data needed) | J7, J8, J14, J19, J37 |
| skip: daily corpus | J1, J2 (×2), J3, J4, J5, J6, J9, J10, J11, J12, J15, J16, J17, J18, J20, J22, J23, J24, J25, J26, J27 |
| skip: order-book depth extract | J13, J21, J28, J29, J30, J31 |
| skip: sized tape (`local_quote_total`) | J32 (×2), J33, J34, J35, J36 |

The handoff estimated about 22 of 37 skipping. The real figure is **34 of 39 test functions (32 of 37 J-scenarios)**.
J17 and J18, which the paper cites, skip. J19 (KRX cutover) passes.

### strategies/: 5 passed, 2 skipped, 7 failed (14 tests)

Column A is the repo as it stands. Column B adds `quote_max` and `quote_min` from the DB, for exactly the 202
ticker-days the fixture already holds (scratch copy only; nothing committed).

| Test | A: as shipped | B: + max/min |
|---|---|---|
| E1 fill divergence | skip (needs corpus) | n/a (needs full corpus; T2) |
| F2 resolution indeterminacy | skip (needs daily + tick) | skip |
| F3 cross policy | **FAIL** (0 fills) | pass |
| S1 VN30F mean-reversion | **FAIL** (never traded) | pass |
| S2 equity margin momentum | **FAIL** (no margin call) | pass |
| S2 forced sale blocked by down-lock | **FAIL** | **FAIL** (see 4b) |
| S3 basket vs future | **FAIL** (nothing held) | pass |
| S4 auction rebalancer | pass | pass |
| S5 advance turnover | **FAIL** (no fee accrued) | pass |
| S6 KRX regime | pass | pass |
| S7 fill sensitivity | **FAIL** (0 fills, every policy) | pass |
| S8 market maker (×2) | pass | pass |
| S9 queue sensitivity | pass | pass |

The handoff says the strategy tests run from the shipped fixtures. **At `5b54b53` they don't: 7 fail.**

## 4. Root causes

### 4a. The daily fixture predates the HIGH/LOW wiring (fixed in B)

- `strategies/fixtures/` was cut on 2026-08-29 (commit `c44082b`), and `regenerate.py`'s `DAILY_TABLES` has
  no `quote_max`/`quote_min`.
- On 2026-08-30, `DataHubSource` started serving session HIGH/LOW from those tables (see its docstring).
- Without them, every marketable order on a daily bar resolves to INDETERMINATE: `BAND_LOCK … the session
  carries no price to test against it`, with `missing: ['book', 'low']`. So no signal-driven test ever fills.
- Adding the two tables from the DB, on the same keys, restores every test except one.
- Fix (T3): add `quote_max` and `quote_min` to `regenerate.py`'s `DAILY_TABLES` and regenerate from the DB.

### 4b. S2's "down-lock" day is a close-equals-floor proxy, not a full-day lock (open question)

DIG on 2022-10-24: open 23.3, high 23.5, low = close = floor 21.95, volume 4,999,500. The test treats the day as
a down-lock, so a sale must not fill. Now that the session high is known, the engine correctly sees the
stock trading above the floor for part of the day, and the sale fills.

This is the **test's premise going stale, not an engine regression**. The test needs a lock day where the
whole range is pinned (high = low = floor). The paper's S2 claim ("only three sales before the broker
force-sold it, under repeated floor locks") has to be re-verified with session HIGH/LOW in T3.3. Its
counts may change.

### 4b resolved: owner chose the weaker, graded claim (2026-11-24)

What the evidence showed:
- DIG 2022-10-03 → 11-15 has 15 floor-close days. Only 3 (11-07, 11-08, 11-15) were pinned at the floor
  all session (high = floor), and even those traded at the floor: 2.48M, 1.24M and 1.08M shares.
- The DB's 2022 price ladder confirms a one-sided book at the floor on those 3 days. It has **no queue sizes
  before 2023-01-03** (DIG's first `bidsize` row), and `totalask`/`totalbid` are empty, so no day in the
  window can **prove** the forced sale was blocked.
- S2's 7 forced sales are all LIMIT at the floor, and all fill under `soft`. 6 are graded `TRADED_THROUGH`;
  the one on 11-07 is graded `TOUCHED_AT_LIMIT` (assumed). `hard` answers INDETERMINATE there.
- The old check `instructed (15) > completed (7)` passed for a bookkeeping reason: each tranche logs
  `FORCED_SALE_INSTRUCTED` twice (unrounded at the 15:00 notice, lot-rounded at the next open).

Paper wording to replace "completed only three sales … under repeated floor locks": *the leveraged long
lost 77% (100M → 23.3M), drew 10 margin calls and was force-sold in 7 tranches; on the day the book sat
pinned at the floor all session the simulator only assumes the fill (TOUCHED_AT_LIMIT), and the strict
policy refuses to call it.* (Numbers are on the patched fixture; T3 regenerates them from DB slices.)

Test changes (`strategies/test_s2_equity_margin_momentum.py`):
- `test_s2_forced_sale_is_blocked_by_a_downlock` is replaced by `test_s2_floor_sale_is_graded_by_evidence`.
  It sells LIMIT at the floor, as the broker does. On 11-07, soft gives a TOUCHED_AT_LIMIT fill and hard
  gives INDETERMINATE with the position still held. On 10-20, both fill TRADED_THROUGH.
- In the main test, the double-counted check is replaced by "the 11-07 forced fill is graded TOUCHED_AT_LIMIT".
- Both pass on the fixture plus DB `quote_max`/`quote_min`. As shipped, they still fail until T3 regenerates
  the fixture (4a).

### 4b, continued: the lock is proven from the sell queue (2026-11-24)

The owner pointed to the local archive `vn_quote_2020-12_2024-09`, which has bid/ask **sizes from 2021-07-01**
(the remote DB has none before 2023-01-03). Running S2 itself on the book is blocked by the depth data
having no deletion records: on the lock days the reconstructed bid side is a stale "ghost" (09:00 auction
bids, 60 min old), so the book walk correctly refuses to decide. The owner chose a measurement instead:
`measurements/s2_lock_queue.py`, pinned by `strategies/test_s2_lock_queue.py` on the slice
`strategies/fixtures/s2_lock/` (DIG, 5 KB daily + 1.0 MB book/tape on the 14 floor-close days, level 1 only).

A floor sale at S2's 10:00 mark joins the back of the floor queue. It is **blocked** when the best ask is the
floor, every later print is at the floor, and the queue ahead exceeds all volume after 10:00 (closing auction
included):

| Day | Pinned all day | Queue ahead @10:00 | Volume after | Verdict |
|---|---|---:|---:|---|
| 2022-11-07 | yes | 8,657,000 | 775,000 | **blocked**: fills only if >91% of the queue cancels |
| 2022-11-08 | yes | 26,674,900 | 875,500 | **blocked** (>97%) |
| 2022-11-14 | no | 1,463,000 | 1,149,600 | blocked, weak evidence (>21%) |
| other 11 floor-close days | no | | | not locked at 10:00 (ask above the floor, or prints above it later) |

S2's daily run sold at the floor on 2022-11-07, a blocked day, and graded that fill TOUCHED_AT_LIMIT.
Its other six forced tranches fell on days that were not locked at 10:00. Proposed paper wording: *the
leveraged long lost 77% and was force-sold in tranches; on the day the broker's floor sale met a full lock,
8.7M shares were queued ahead of it and 0.78M traded all day, so it could not fill; the simulator grades its
daily fill there as an assumption, never as observed.* "Completed only three sales" cannot be restored: it
came from the close == floor proxy.

Not assessed: how S2's equity path changes if the 11-07 tranche is carried (11-08 was also blocked, so the
next chance was 11-09, at least 1 tick lower). That needs the engine to model a locked book, which the
ghost-bid problem prevents for now.

### Pre-existing failure, not caused by RIVF'26 work

`tests/validation/test_runner.py::test_a_forced_liquidation_reports_and_executes` fails at `5b54b53` (the
handoff commit) as well as now. Not investigated yet. Full unit suite at this commit: 2,006 passed, 533
skipped, this 1 failed (with the `[mcp]` extra installed; without it, collection stops on `fastmcp`).

### 4c. Open defect for the OWNER: soft grades every market-family fill `TRADED_THROUGH`

`SoftFillPolicy._continuous` (`src/plutus/market/session/fills.py`, market-family branch) labels every
MTL/MOK/MAK fill `TRADED_THROUGH`, even when `band_lock_decision` passed it through as matched-at-the-edge
(the ASSUMED tier, rows B6/S6). Example: a soft MTL sell of DIG on 2022-11-07 (O=H=L=C=floor) is graded
TRADED_THROUGH. The fill *outcome* is as designed (soft fills the assumed tier); only the evidence *label* is
wrong, so per-evidence tallies (E1 and similar) overstate observed fills. `hard` is unaffected: it never
fills the market family. S2's forced sales are LIMIT orders and are unaffected. Not fixed: changing it
moves evidence counts the paper reports, so it needs an owner decision before T2.

## 4d. T3 result: scenarios and strategies run from shipped data (2026-11-24)

With **no** `PLUTUS_*` variables set, at this commit:

| Directory | Collected | Before (T0) | After (T3) |
|---|---:|---|---|
| `scenarios/` | 39 | 5 passed, 34 skipped | **39 passed, 0 skipped** |
| `strategies/` | 20 | 5 passed, 7 failed, 2 skipped (of 14) | **18 passed, 2 skipped** (E1, F2: need a full corpus / tick archive, T2) |
| `tests/` | 2,540 | not run at T0 | 2,006 passed, **533 skipped**, 1 failed (pre-existing, see above) |

What changed:
- `scenarios/_harness.py` falls back to `scenarios/fixtures/{daily,book}` and gains `depth_root()`. The 11
  book/tape scenarios no longer hard-code the old machine's paths.
- `scenarios/fixtures/daily/` (88 KB): from the **DB**, by a logged run of the 21 daily J-scenarios (22 tests).
- `scenarios/fixtures/book/` (224 KB): from the **archive** (book sizes before 2023), by a logged run of J13,
  J21, J28–J36, with HPG's tape deliberately left out (J35 tests a ticker the tape does not cover).
- `strategies/fixtures/parquet/`: regenerated from the DB by a logged run, now with `quote_max`/`quote_min`.
  `strategies/fixtures/extract/` kept as shipped. Its VN30F2504 part is identical to the DB row for row, and
  its FPT book is value-identical to the archive (`extract/PROVENANCE.md`).
- **J32 and J33 re-pinned** (2,000 → 2,300; 1,000 → 400). The old tape stamped each price change ~70 µs
  after the trade that caused it, so 344 of 1,569 FPT trades carried the previous price. The DB and archive
  stamp both at the same instant. Both versions of each number were reproduced by a direct count over the raw
  tape that doesn't use `TapeSource`; the engine is unchanged.

Paper-cited findings, re-checked on the shipped fixtures: S2 (−77%, 10 calls; 11-07 floor sale blocked by
the queue), S6 (opens pre-KRX, refuses post-KRX with `UnresolvedRule`), J17 (50 shares: no ROUND_LOT
rejection on 2020-12-31, ROUND_LOT on 2021-01-05), J18 (13% → 17% IM: deposit **+30.8%**, the F1
expectation), J19 (pre-KRX `pre_margin`, post-KRX `UnresolvedRule`). All hold.

Not done in T3: the 533 skipped **unit** tests. They are corpus-gated too (384 "No daily corpus found",
94 "No depth extract found", 26 "No corpus found", 14 "No tick archive found", …). The handoff's T3 target
names scenarios and strategies only, but the paper's unit-test count (F4) depends on how these are counted.
That is for T2/F4.

## 5. Findings that correct the handoff

1. The 18.9% queue swing reproduces from the shipped fixtures, but it comes from **S9**, not F3:
   optimistic 152,600 vs conservative 123,700 shares, 18.94%.
2. The strategy suite fails, rather than runs, at the handoff commit (4a).
3. 32 of the 37 J-scenarios skip, not about 22.
4. The single-invocation audit command fails on a `_harness` name clash (Section 3).

## 4e. Change 2: the conservative queue reads the sized tape for taker sweeps (2026-11-24)

Owner-approved. `BookWalkFillPolicy` given `queue=conservative` and a tape now swaps in a
`TapeConservativeQueue` (`src/plutus/market/session/book_walk.py`). Each taker walk counts the prints at a
level from the resting side's view, over the maker arm's window `[submitted_at, interval.start)`, so a
marketable order fills at a level only once more than its displayed depth has traded there since it
arrived. Provenance reads `queue=conservative(prints=tape)`. Without a tape nothing changes. Pinned by
`tests/market/session/test_book_walk_conservative_tape.py` (7 tests, on the in-repo extract, no skip).

Effect on shipped results:
- **S9: unchanged.** Maker fills 152,600 / 123,700 / 137,600, so **18.9%**. Conservative's incidental taker
  fills go 0 → 3,100 (now decided).
- **F3 figure (paper): changes.** The queue panel's conservative arm goes from **16.7% indeterminate to
  0%**. The spread is unchanged. The fill panel is identical. F3's test and docstring are updated; the PNG
  and JSON are regenerated. **Paper session:** the F3 caption or text claiming the conservative arm leaves a
  sixth of its flow undecided must change.
- MM (T5) is the main consumer. Its conservative headline can now decide fills.
- Unit suite: +7 tests, same single pre-existing failure. The 12 hidden `test_book_walk.py` failures
  (with `PLUTUS_DEPTH_ROOT`) are unchanged.

## Owner decisions, 2026-11-24 (late)

- **E1 publication: statistics only**, at a finer grain than the paper's single numbers so readers can check
  them: `docs/reference/tables/t2/e1_published/` (month × intent, ticker × intent, outcome counts only, summing
  exactly to the headline). The raw 2022 slice and the per-decision table stay unpublished.
- **SB 2022 tie (457 = 457 fills): report as is.** SB is the null anchor (admission-limited only), and a zero
  fill gap is what that predicts. §6 criterion 1's "<" is read as "≤" for SB. Return is still lower
  (−26.21% → −27.08%).
- **SB base check: Google Drive check skipped (owner decision).** The DB is the settled source; the coordinator's
  recommendation was to skip it, since the DB is the settled source and the drift is documented with evidence.

## 4f. Numbers moved by the VM-baseline fix (`8295502`)

The fix corrects contracts added to (or flipped from) a derivatives position after a daily settlement. Rechecked:

- **F3 fill axis, S1 under `soft`: −75.5% → −76.4%**, forced liquidations 2 → 3 (end equity 9,801,722 → 9,421,686đ
  on 40,000,000đ). S1 adds to a settled position, so its deposit had been overstated. Figure JSON and PNG are
  regenerated. **Paper: the S1 return in F3 / T4 changes.**
- Unchanged:
  - F3 hard/probabilistic and the whole queue panel;
  - margin incidence (all six rows);
  - ProtoPair (both windows, all variants);
  - scenarios (39 pass) and strategies (18 pass, 2 skip).
- Not affected by construction: SB, Grid, E1, HSX daily (equities only); the old flat-each-session MM anchor.
- MM faithful-A (overnight carry) is being rerun on `8295502`.
