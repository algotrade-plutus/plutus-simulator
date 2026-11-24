# DATA-MANIFEST: scenarios-book

- **Reproduces:** Book/tape J-scenarios (scenarios/test_j{13,21,28-36}): run with no corpus (RIVF'26 T3). HPG tape deliberately absent: J35 tests a ticker the tape does not cover.
- **Extraction mode:** `declared`
- **Command:** `rivf26_extract.py declared --source archive --experiment scenarios-book --force --reproduces Book/tape J-scenarios (scenarios/test_j{13,21,28-36}): run with no corpus (RIVF'26 T3). HPG tape deliberately absent: J35 tests a ticker the tape does not cover. --request request.json`
- **Source:** Algotrade Vietnam market dataset, local parquet archive `vn_quote_2020-12_2024-09` (bid/ask sizes from 2021-07-01; book rows from the 2025-10 backup dumps, timestamps offset from the trade tables by tens of ms). File `<prefix>_<x>.<ext>` holds rows of archive table `<x>`.
- **Extracted on:** 2026-11-24 with `scripts/rivf26_extract.py` (pyarrow 26.0.1; writer settings fixed in `WRITER`).
- **Total size:** 182,287 bytes (178.0 KiB) in 12 files.

## Why this window is minimal

Logged, not chosen: the book and tape the 11 intraday J-scenarios (J13, J21, J28-J36) read, which is FPT and HPG on 2022-11-09, plus the two daily band rows they price against. Book sizes before 2023 exist only in the archive, hence the source. One deliberate removal: HPG's tape (`local_quote_matched`/`total`) is excluded from the request, because J35 tests a ticker the tape does not cover and HPG is that ticker.

## Files

| File | Rows | Bytes | sha256 |
|---|---:|---:|---|
| `local_quote_askprice.parquet` | 925 | 4,390 | `b69646a1a0dc842a5b0751a2e6875f7e18307af7877e3439312cb3c87859959e` |
| `local_quote_asksize.parquet` | 8,757 | 64,999 | `ff68d36cc6d55d66b1ad938e723fa9309c4dd3047477e5fc654a269e26553e2a` |
| `local_quote_bidprice.parquet` | 963 | 4,564 | `67d230f954fe22bca4e1d9b05adcbbab3eb31cf10fac0dbca0c776493da302f1` |
| `local_quote_bidsize.parquet` | 10,651 | 82,345 | `9164ef0cb07b696f2397d85246ea3334db2aead761a14c030378c03f0cdf7750` |
| `local_quote_matched.parquet` | 584 | 4,440 | `d039e0bf46d51e0dddd2781d63597adf5767b7128b65befda7b54f124ecbfd6d` |
| `local_quote_total.parquet` | 1,570 | 14,467 | `cc5deda5d6c087c348be306d73b0b7cbcaad5276c4627ffff6049d0cc94f57fb` |
| `quote_ceil.parquet` | 2 | 1,064 | `6db85b53be81ff933642e4d4d42f2a967ba000b9d93e0f7b6a118a9604c66fc2` |
| `quote_close.parquet` | 2 | 1,064 | `4ee836e9bf22c3622278045582f93a9af77658082358cb8a6cd3b9c239dc4ca8` |
| `quote_dailyvolume.parquet` | 2 | 1,090 | `c94f323805948f0254be1732525f5604c0667effc1a67fa165fe67b574b73d6f` |
| `quote_floor.parquet` | 2 | 1,064 | `e46be2425f5d4c4f8b8e81328e1c5ed310749bc727bdc7adc9de8429be50e4ce` |
| `quote_reference.parquet` | 2 | 1,064 | `12fa3fc59ee06684551f74bf01f0bd3b9b1751bad35245a53c412e314b2b9293` |
| `quote_ticker.parquet` | 2 | 1,736 | `b6aa43b9c6df52a73807d4a63fcabe6b442b9e08daed84cc2670db053a2efd3b` |

## Contents (tickers, ranges, fields, query)

### `local_quote_askprice.parquet`
- Fields: `datetime, tickersymbol, price, depth`
- Query: `quote.askprice WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi> AND depth BETWEEN 1 AND 3`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `local_quote_asksize.parquet`
- Fields: `datetime, tickersymbol, quantity, depth`
- Query: `quote.asksize WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi> AND depth BETWEEN 1 AND 3`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `local_quote_bidprice.parquet`
- Fields: `datetime, tickersymbol, price, depth`
- Query: `quote.bidprice WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi> AND depth BETWEEN 1 AND 3`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `local_quote_bidsize.parquet`
- Fields: `datetime, tickersymbol, quantity, depth`
- Query: `quote.bidsize WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi> AND depth BETWEEN 1 AND 3`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `local_quote_matched.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.matched WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `FPT`: [2022-11-09, 2022-11-10)

### `local_quote_total.parquet`
- Fields: `datetime, tickersymbol, quantity`
- Query: `quote.total WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- Note: the DB has no `local_quote_*` tables. This file carries `quote.*` rows under the `local_quote` name because its consumer reads that prefix. The old corpus's `local_quote_*` came from a second observer, so values can differ from it.
- `FPT`: [2022-11-09, 2022-11-10)

### `quote_ceil.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.ceil WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `quote_close.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.close WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `quote_dailyvolume.parquet`
- Fields: `datetime, tickersymbol, quantity`
- Query: `quote.dailyvolume WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `quote_floor.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.floor WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `quote_reference.parquet`
- Fields: `datetime, tickersymbol, price`
- Query: `quote.reference WHERE tickersymbol = <t> AND datetime >= <lo> AND datetime < <hi>`, once per (ticker, interval) below
- `FPT`: [2022-11-09, 2022-11-10)
- `HPG`: [2022-11-09, 2022-11-10)

### `quote_ticker.parquet`
- Fields: `tickersymbol, exchangeid, lastupdated, instrumenttype, startdate, expdate`
- Query: `quote.ticker WHERE tickersymbol = ANY(<tickers>)`
- `FPT`: ticker-master row
- `HPG`: ticker-master row
