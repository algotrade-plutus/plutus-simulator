# Data provenance (RIVF'26 camera-ready): DRAFT, MarketMaker section pending its reruns

**Source.** All market data is **Algotrade's Plutus data** (https://www.algotrade.vn/), from two stores:

- **Algotrade database** (read-only queries, scoped by ticker and date): daily data and ticks to today; bid/ask
  sizes from 2023-01-03.
- **Algotrade Vietnam market dataset archive** (`vn_quote_2020-12_2024-09`): used **only** where book sizes before
  2023 are needed. Its book rows come from backup dumps, offset from the trade tables by tens of ms.

Table `quote.<x>` ↔ file `quote_<x>.parquet` (same columns); the book scenarios use the `local_quote_<x>` file
prefix. Prices are in thousands of đồng in the data and converted to đồng where results are reported.

**Extraction.** Every slice is written by `scripts/rivf26_extract.py`. In `log` mode it records exactly what a test
or experiment reads through the adapters; in `declared` mode it takes an explicit (ticker, date, field) request.
Output is deterministic (same request, same bytes, same sha256). Each slice has a `DATA-MANIFEST.md` with: source,
query description (no credentials or hosts), tickers, dates, fields, row counts, sizes, sha256, the result it
reproduces, and why the window is the minimum. Working copies are in `$RIVF26_DATA/`
(not a repo).

**Publication rule** (owner): minimal slices that prove a finding, nothing more. Nothing is pushed until the owner
signs off on the slices and their sizes. Population measurements ship statistics only.

## Per experiment

Committed bytes = the exact sum of the file sizes git tracks in the folder (data, manifests and request files), in bytes (B).

| Experiment | Tickers / instruments | Window | Selection | Source | Shipped in repo | Committed bytes |
|---|---|---|---|---|---|---:|
| Scenarios J1–J37 (daily) | as logged (21 scenarios) | per scenario | logged reads | DB | `scenarios/fixtures/daily/` | 65,178 B |
| Scenarios J13, J21, J28–J36 (book/tape) | FPT, HPG (book); FPT (tape) | 2022-11-09 | logged reads; HPG tape left out on purpose (J35) | archive | `scenarios/fixtures/book/` | 192,379 B |
| Strategy tests S1–S9, F3 (daily) | as logged | per test | logged reads | DB | `strategies/fixtures/parquet/` | 20,875 B |
| S8/S9 book/tape | FPT 2022-11-09; VN30F2504 2025-04-08 | 1 day each | carried from 2026-08-29, checked against DB and archive | old extract (identical values) | `strategies/fixtures/extract/` | 402,877 B |
| S2 lock-queue proof | DIG | 14 floor-close days in 2022-09-05..11-15 | close == floor | archive | `strategies/fixtures/s2_lock/` | 1,058,677 B |
| E1 fill divergence | 391 HSX stocks, ≥200 sessions | 2022 | `SELECTION_SQL` in `e1_regenerate.py` | DB | **statistics only** (`docs/reference/tables/t2/e1_published/`) | — |
| F2 indeterminate rate | FPT, HPG, HTV | 2022-10-20..11-30 | logged reads | DB (daily) + archive (book) | not shipped | — |
| Equity admission, band, grid | stocks on HSX/HNX/UPCOM | 2021-02-05..2022-12-30 (grid: all history) | script rules | DB | not shipped | — |
| Margin incidence, regime split | VN30F front month (20 contracts) | 2021-06-01..2022-12-30 | `futurecode='VN30F1M'` | DB | not shipped (6,573 B in 2 files, eligible) | — |
| ProtoSmartBeta | names the strategy ranks (71 / 79) | 2022, 2023 (12 rebalances each) | per-rebalance filter | DB | `proto/ProtoSmartBeta/data/` | 967,897 B |
| ProtoPair | equal-lot VN30 basket + VN30F1M | 2022-08-01..2023-08-04; 2023-08-07..2024-02-02 | VN30 membership + roll map | DB | `proto/ProtoPair/data/` | 359,593 B |
| ProtoGrid | SSI, TCH, POW | 2022-10-03..11-30; 2021-11-01..12-31 | spec names | DB (tick) | `proto/ProtoGrid/data/` | 2,932,667 B |
| ProtoMarketMaker | VN30F1M/F2M (dated contracts) | ±20 sessions around 2025-05-05 and 2022-12-15 | spec | DB (2025) + archive (2022 book) | `proto/ProtoMarketMaker/data/` | **25,078,745 B** (krx2025 16,352,393; im2022 8,726,352): over the flag, owner sign-off |

## Preprocessing

- **Bands:** published ceil/floor/reference where present. Otherwise the engine's `reconstruct_bands`, keyed on the
  resulting band price; such bands are tagged `RECONSTRUCTED`, or `ABSENT` when no reference exists.
- **Book:** depth 1–3, reconstructed as-of per side. There is no deletion record, so a side that empties keeps
  stale quotes, and the book walk refuses crossed or stale books.
- **Tape:** volume per event is the consecutive delta of cumulative `total`; the price is the last `matched` at or
  before it. The end-of-day `00:00:00` row is excluded.
- **Units:** prices × 1,000 to đồng; VN30F multiplier 100,000 đ/point.

## Not shipped, and why

- Population slices (E1, the HSX measures, F2 books): confidential. E1 ships statistics only (owner decision);
  the rest can be rebuilt by anyone with database access from the committed scripts and requests.
- Full-universe CSVs in `ProtoSmartBeta/data/{is,os}` (gitignored, 117 MB): pre-RIVF inputs, not used by the
  camera-ready results.
- Grid's tick CSV cache (`data/.cache/`, gitignored): regenerated from the committed parquet.

## Headline map

Pending. It will map every number in the paper to: repo, commit, command, data slice and sha256, value. Built
after the MarketMaker reruns, as `docs/camera-ready-numbers.md`.
