# DATA-MANIFEST: s2-lock-book

- **Reproduces:** S2 lock-queue measurement (measurements/s2_lock_queue.py): the floor sell queue and tape on DIG's floor-close days
- **Extraction mode:** `declared`
- **Command:** `rivf26_extract.py declared --source archive --experiment s2-lock-book --reproduces S2 lock-queue measurement (measurements/s2_lock_queue.py): the floor sell queue and tape on DIG's floor-close days --request request.json`
- **Source:** Algotrade Vietnam market dataset, local parquet archive `vn_quote_2020-12_2024-09` (bid/ask sizes from 2021-07-01; book rows from the 2025-10 backup dumps, timestamps offset from the trade tables by tens of ms). File `<prefix>_<x>.<ext>` holds rows of archive table `<x>`.
- **Extracted on:** 2026-11-24 with `scripts/rivf26_extract.py` (pyarrow 26.0.1; writer settings fixed in `WRITER`).
- **Total size:** 1,041,172 bytes (1016.8 KiB) in 4 files.

## Why this window is minimal

Only the 14 days in S2's window on which DIG closed at its floor (listed by `measurements/s2_lock_queue.py request` from the daily slice), and only what the measurement reads: the level-1 best ask price and its displayed size (the queue a floor sale joins), plus the tape (`matched` for the print prices after 10:00, `total` for the volume after 10:00). No bid ladder, no deeper levels, no other tickers. Size note: ~1.0 MB, almost all level-1 ask-size updates (the floor queue changes thousands of times a day on a lock day); the day is the extraction unit.

## Files

| File | Rows | Bytes | sha256 |
|---|---:|---:|---|
| `local_quote_askprice.parquet` | 2,556 | 18,858 | `f2d8a92cbdd4dc525d2a26cd414195f4e65edcf969e1f81f497faef13e9aba31` |
| `local_quote_asksize.parquet` | 71,104 | 589,670 | `39eaaa04bc9ca5624e461d5d4984fe66e44d7106a2323e2c876c69342f2a1290` |
| `local_quote_matched.parquet` | 8,728 | 54,102 | `d942d6eaeb2baf927c0541d611a2e157a96f1441a46c9b6e95822be42dc11826` |
| `local_quote_total.parquet` | 41,685 | 378,542 | `da9ec34e0e91e7a16296b39366e954d969420d94856ea4c1e1b03d28d97f5e04` |

## Contents (tickers, ranges, fields, query)

### `local_quote_askprice.parquet`
- Fields: `datetime, tickersymbol, price, depth`
- Query: `quote.askprice WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi> AND depth BETWEEN 1 AND 1`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `DIG`: [2022-10-03, 2022-10-04), [2022-10-11, 2022-10-12), [2022-10-21, 2022-10-22), [2022-10-24, 2022-10-25), [2022-10-25, 2022-10-26), [2022-10-26, 2022-10-27), [2022-10-31, 2022-11-01), [2022-11-04, 2022-11-05), [2022-11-07, 2022-11-08), [2022-11-08, 2022-11-09), [2022-11-09, 2022-11-10), [2022-11-10, 2022-11-11), [2022-11-11, 2022-11-12), [2022-11-14, 2022-11-15)

### `local_quote_asksize.parquet`
- Fields: `datetime, tickersymbol, quantity, depth`
- Query: `quote.asksize WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi> AND depth BETWEEN 1 AND 1`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `DIG`: [2022-10-03, 2022-10-04), [2022-10-11, 2022-10-12), [2022-10-21, 2022-10-22), [2022-10-24, 2022-10-25), [2022-10-25, 2022-10-26), [2022-10-26, 2022-10-27), [2022-10-31, 2022-11-01), [2022-11-04, 2022-11-05), [2022-11-07, 2022-11-08), [2022-11-08, 2022-11-09), [2022-11-09, 2022-11-10), [2022-11-10, 2022-11-11), [2022-11-11, 2022-11-12), [2022-11-14, 2022-11-15)

### `local_quote_matched.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.matched WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `DIG`: [2022-10-03, 2022-10-04), [2022-10-11, 2022-10-12), [2022-10-21, 2022-10-22), [2022-10-24, 2022-10-25), [2022-10-25, 2022-10-26), [2022-10-26, 2022-10-27), [2022-10-31, 2022-11-01), [2022-11-04, 2022-11-05), [2022-11-07, 2022-11-08), [2022-11-08, 2022-11-09), [2022-11-09, 2022-11-10), [2022-11-10, 2022-11-11), [2022-11-11, 2022-11-12), [2022-11-14, 2022-11-15)

### `local_quote_total.parquet`
- Fields: `datetime, tickersymbol, quantity`
- Query: `quote.total WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `DIG`: [2022-10-03, 2022-10-04), [2022-10-11, 2022-10-12), [2022-10-21, 2022-10-22), [2022-10-24, 2022-10-25), [2022-10-25, 2022-10-26), [2022-10-26, 2022-10-27), [2022-10-31, 2022-11-01), [2022-11-04, 2022-11-05), [2022-11-07, 2022-11-08), [2022-11-08, 2022-11-09), [2022-11-09, 2022-11-10), [2022-11-10, 2022-11-11), [2022-11-11, 2022-11-12), [2022-11-14, 2022-11-15)
