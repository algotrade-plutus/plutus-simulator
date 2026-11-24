# DATA-MANIFEST: s2-lock-daily

- **Reproduces:** S2 lock-queue measurement (measurements/s2_lock_queue.py): which days DIG closed at its floor
- **Extraction mode:** `declared`
- **Command:** `rivf26_extract.py declared --source archive --experiment s2-lock-daily --reproduces S2 lock-queue measurement (measurements/s2_lock_queue.py): which days DIG closed at its floor --files quote_close,quote_floor,quote_max --tickers DIG --start 2022-09-05 --end 2022-11-15 --no-ticker-master`
- **Source:** Algotrade Vietnam market dataset, local parquet archive `vn_quote_2020-12_2024-09` (bid/ask sizes from 2021-07-01; book rows from the 2025-10 backup dumps, timestamps offset from the trade tables by tens of ms). File `<prefix>_<x>.<ext>` holds rows of archive table `<x>`.
- **Extracted on:** 2026-11-24 with `scripts/rivf26_extract.py` (pyarrow 26.0.1; writer settings fixed in `WRITER`).
- **Total size:** 5,380 bytes (5.3 KiB) in 4 files.

## Why this window is minimal

One ticker (DIG, S2's instrument) over S2's own window [2022-09-05, 2022-11-15), and only the three daily fields that identify a floor-close day: close, floor and the session high (`max`, to tell a full-day lock from a close at the floor). Nothing outside the window S2 trades.

## Files

| File | Rows | Bytes | sha256 |
|---|---:|---:|---|
| `quote_close.parquet` | 51 | 1,392 | `7391550bfcdf8f22b5e5c4e8a11b87276d95b8a94194f3ccf7cb0c9d8c6ac25c` |
| `quote_floor.parquet` | 51 | 1,399 | `041174772861f466429ab69eaab583e2089b34f7ed0ac9114152f6f44595d493` |
| `quote_max.parquet` | 51 | 1,389 | `4c1b15f7a0a74c211e8f5c0ddf29cf21445a72fc6d1f1c11b898edecdeab0973` |
| `quote_ticker.parquet` | 0 | 1,200 | `796d6fb0c68535dab1b391ac1112c2df2052462484d960d10e97122b881679ef` |

## Contents (tickers, ranges, fields, query)

### `quote_close.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.close WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `DIG`: [2022-09-05, 2022-11-15)

### `quote_floor.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.floor WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `DIG`: [2022-09-05, 2022-11-15)

### `quote_max.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.max WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `DIG`: [2022-09-05, 2022-11-15)

### `quote_ticker.parquet`
- Fields: `tickersymbol, exchangeid, lastupdated, instrumenttype, startdate, expdate`
- Query: `quote.ticker WHERE tickersymbol = ANY(<tickers>)`
- Tickers: none (the file is required to exist, or was looked for, but no row was read).
