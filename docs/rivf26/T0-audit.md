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

## 5. Findings that correct the handoff

1. The 18.9% queue swing reproduces from the shipped fixtures, but it comes from **S9**, not F3:
   optimistic 152,600 vs conservative 123,700 shares, 18.94%.
2. The strategy suite fails, rather than runs, at the handoff commit (4a).
3. 32 of the 37 J-scenarios skip, not about 22.
4. The single-invocation audit command fails on a `_harness` name clash (Section 3).
