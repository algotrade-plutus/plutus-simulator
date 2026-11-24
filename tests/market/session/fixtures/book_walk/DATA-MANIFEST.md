# DATA-MANIFEST: tests/market/session/fixtures/book_walk

- **Reproduces:** `tests/market/session/test_book_walk.py`, the default depth root of the whole file
  (`PLUTUS_DEPTH_ROOT` still overrides it). 96 passed, 2 xfailed (strict; the band-lock engine gap).
- **Extracted on:** 2026-11-24 with `scripts/rivf26_extract.py` (pyarrow 26.0.1; writer settings fixed in
  `WRITER`), two sources, one per prefix, merged into this one directory.
- **Total size:** 212,456 bytes (207.5 KiB) in 8 parquet files. Under the ~3 MB flag.

## How it was made

1. A logged run of the test file (`rivf26_extract.py log -- tests/market/session/test_book_walk.py`, once
   per source) recorded every `(file, ticker, day, depth)` the tests read. Both sources gave the same access
   set: `local_quote_{bid,ask}{price,size}` for FPT and HTV on 2022-11-09, `quote_{bid,ask}{price,size}` for
   HTV on 2022-11-09 and HPG on 2025-04-10, all at depth 1..3.
2. That request was split by prefix and replayed in `declared` mode, one source each:
   - `request-archive.json` -> `--source archive` (Algotrade Vietnam market dataset, local parquet archive
     `vn_quote_2020-12_2024-09`): the four `local_quote_*` files.
   - `request-db.json` -> `--source db` (Algotrade PostgreSQL DB, schema `quote`, read-only): the four
     `quote_*` files.
3. `quote_ticker.parquet` (0 rows, written by the tool because the adapters look for it) is left out; no test
   here reads it.

Replay: `rivf26_extract.py declared --source archive --request request-archive.json --experiment ...` and the
same with `--source db --request request-db.json`, then copy the parquet files into one directory.

## Why this split, and why it is minimal

The tests read two prefixes on purpose, and the old dev extract gave them different contents:

- **`local_quote_*` = archive.** FPT and HTV 2022-11-09 need bid/ask *sizes* (every sweep, queue and
  staleness test). The DB has no sizes before 2023-01-03; the archive has them from 2021-07-01.
- **`quote_*` = DB.** HTV 2022-11-09 read through `quote` must have prices at every level and **no size rows
  at all** (`test_an_unsized_ladder_is_indeterminate_naming_book_size`,
  `test_the_same_ticker_day_is_sizeable_through_the_other_prefix`). The DB is exactly that: same 40 bid and
  23 ask price rows as the archive, zero size rows. HPG 2025-04-10 (the ceiling-locked session) is after the
  archive ends (2024-09), so it can only come from the DB; the test counts every book of that session
  (16,707 books, 14,775 locked), which is why its full day is here and why `quote_bidsize` is most of the
  bytes.

One ticker-day per name, depth 1..3 (the adapter's ladder), only the fields the logged run touched.

## Files

| File | Source | Rows | Bytes | sha256 |
|---|---|---:|---:|---|
| `local_quote_askprice.parquet` | archive | 592 (FPT 569, HTV 23) | 3,352 | `049bb4a282f85d9a7c59af1b14029082704505c873f89474270c0222be83d48d` |
| `local_quote_asksize.parquet` | archive | 2,517 (FPT 2,497, HTV 20) | 16,882 | `89ba6cc113de7920bbdb38bd541bae347bc95516f25d8f0c79af11af8359d7ee` |
| `local_quote_bidprice.parquet` | archive | 618 (FPT 578, HTV 40) | 3,540 | `14ad8b4bba995a93bfad9c677273c1fa4d6ab112df6fa51b49ef495079b4adbf` |
| `local_quote_bidsize.parquet` | archive | 1,285 (FPT 1,244, HTV 41) | 8,447 | `d03a4ce07f82bb70cc24598c200f7f757130224ee4da3cb94423bebfa63a5484` |
| `quote_askprice.parquet` | DB | 30 (HPG 7, HTV 23) | 1,655 | `a493298a81ac2b176ce4f431a554468c5f7a14d1728b466e9155e19ee6e211f7` |
| `quote_asksize.parquet` | DB | 44 (HPG 44, HTV 0) | 1,803 | `26cc45ca7b9ecbc415a166448e274a8cea68bc471bd75c5aac7a14e23cc8df92` |
| `quote_bidprice.parquet` | DB | 50 (HPG 10, HTV 40) | 1,714 | `e96ea30c7e9f2f8afca7d6312d5dfc3d934db03e35e694170ef0e61ccb0f7987` |
| `quote_bidsize.parquet` | DB | 19,718 (HPG 19,718, HTV 0) | 175,063 | `d7e08bbd92ac49342c650451f7434cef2b05ad3a2d3290a10ef5aacd107547aa` |

Columns: `datetime` timestamp[us], `tickersymbol` string, `price` decimal128(20,6) (thousands of đồng) or
`quantity` int64, `depth` int64. Ranges: FPT/HTV `[2022-11-09, 2022-11-10)`, HPG `[2025-04-10, 2025-04-11)`.

## Differences from the old extract, and what they moved

- The archive's book rows are the old extract's rows, same values in the same sequence, stamped a median
  ~45 ms earlier (FPT, by rank: 848/2,064/203/195 rows per file, both sources; tails -2.0 s to +1.2 s).
  The DB's HTV price rows are the archive's, stamped ~40-190 ms later.
- One pinned number moved: HTV's cross-side skew at 09:19:15.185364, **259.7 s -> 259.086221 s**. The
  archive stamps a bid size update 0.627 s before that instant; the old extract stamped it at the instant.
  See the docstring of `test_the_cross_side_skew_is_reported_on_every_walk` for the raw-row arithmetic.
- Whole-table aggregates (`DepthSource.tickers` / `window`) answer from these rows only, not a full corpus.
  The logged run touched `tickers` on both prefixes and `window` for HTV; no assertion depends on another
  ticker being present.

No credentials, host names or machine paths are in this directory.
