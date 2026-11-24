# DATA-MANIFEST: strategies/fixtures/parquet (daily)

- **Reproduces:** the daily strategy tests S1-S7 and F3, plus the daily price/band rows S8/S9 price against (`strategies/`).
- **Source:** Algotrade PostgreSQL DB, schema `quote` (read-only transaction). File `quote_<x>.parquet` holds rows of DB table `quote.<x>`.
- **Extraction mode:** `log`: the rows are exactly what the tests read through the adapters, recorded by `scripts/rivf26_extract.py`.
- **Command:** `rivf26_extract.py log --source db --experiment strategies-daily --force --allow-fail --reproduces Strategy tests S1-S9, F3 (strategies/): daily prices and bands, with session high/low (RIVF'26 T3) -- strategies/test_f3_cross_policy.py strategies/test_s1_vn30f_meanrev.py strategies/test_s2_equity_margin_momentum.py strategies/test_s2_lock_queue.py strategies/test_s3_basket_vs_future.py strategies/test_s4_auction_rebalancer.py strategies/test_s5_advance_turnover.py strategies/test_s6_krx_regime.py strategies/test_s7_fill_sensitivity.py strategies/test_s8_market_maker.py strategies/test_s9_queue_sensitivity.py -q -p no:cacheprovider`
- **Shipped here:** only the daily files of that logged run. Its book/tape files are not shipped: S8/S9 and F3 read the book from `../extract/` (see its PROVENANCE.md), because the DB has no bid/ask sizes before 2023-01-03.
- **Why this is minimal:** logged, not chosen. Each test pins one mechanism on a short real window (e.g. S1: VN30F2210 2022-08-19..10-19; S2: DIG 2022-09-05..11-15), and only the days and fields read are present.
- **Change from the 2026-08-29 fixture (RIVF'26 T3):** adds `quote_max`/`quote_min` (the session high/low the adapter has read since 2026-08-30), whose absence made 7 strategy tests fail; values are from the DB, which matched the old fixture's `quote_close` exactly on all 202 ticker-days it held.

| File | Rows | Bytes | Tickers | Range | sha256 |
|---|---:|---:|---|---|---|
| `quote_ceil.parquet` | 178 | 2,059 | DIG, FPT, HPG, MBB, SSI, VN30F2210, VN30F2212, VN30F2504 | 2022-08-19 .. 2025-04-08 | `439f71be9e12e26bc859199f1d2bbf101c9d495e9bb0339870e038370c8556da` |
| `quote_close.parquet` | 208 | 2,234 | DIG, FPT, HPG, MBB, SSI, VN30, VN30F2210, VN30F2212, VN30F2504 | 2022-08-19 .. 2025-04-08 | `0d8379db593e871d0195fb1cc6ac1513d2de8e23960c111da00b2c330064ee27` |
| `quote_dailyvolume.parquet` | 208 | 2,415 | DIG, FPT, HPG, MBB, SSI, VN30, VN30F2210, VN30F2212, VN30F2504 | 2022-08-19 .. 2025-04-08 | `746095ff91491cbc553821aa464eb92c5322f43a52ed90eeb3e129184d3257fd` |
| `quote_floor.parquet` | 178 | 2,037 | DIG, FPT, HPG, MBB, SSI, VN30F2210, VN30F2212, VN30F2504 | 2022-08-19 .. 2025-04-08 | `bd85699f9249d0c56a0e50a86b7fa32e08d2556dfbb65adec4bea302000c0580` |
| `quote_max.parquet` | 77 | 1,583 | DIG, FPT, HPG, MBB, SSI, VN30F2210, VN30F2212 | 2022-09-07 .. 2022-11-17 | `494cbb0732abff9bfbd280d6c94b46eee069e6d4e76951c32d0ae7887acc24be` |
| `quote_min.parquet` | 77 | 1,575 | DIG, FPT, HPG, MBB, SSI, VN30F2210, VN30F2212 | 2022-09-07 .. 2022-11-17 | `d2c89d277c3c5c871fa1b5abefc633c747703d0d6a49bfb4dec96b8991669622` |
| `quote_open.parquet` | 77 | 1,573 | DIG, FPT, HPG, MBB, SSI, VN30F2210, VN30F2212 | 2022-09-07 .. 2022-11-17 | `93b32b95bad30b4ff17d8cb81a4596fea10c273e58ffcd28a78bf3c3460740b2` |
| `quote_reference.parquet` | 178 | 2,017 | DIG, FPT, HPG, MBB, SSI, VN30F2210, VN30F2212, VN30F2504 | 2022-08-19 .. 2025-04-08 | `852e5d450a36bfbbc7976cde81934f5b1ec98871a188723310178f2d5fd151d0` |
| `quote_ticker.parquet` | 6 | 1,776 | DIG, FPT, HPG, MBB, SSI, VN30 |  | `3bb16fb44b3b47f45e6badb98861965383b85674db6dc2b8bb80f1eb4daf5172` |
