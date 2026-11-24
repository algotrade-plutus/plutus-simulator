# T2 group B — daily population measurements on DB data

RIVF'26 camera-ready, handoff T2, group B. These are the "Signal timing — equity admission" and "Engine vs vendor"
rows of `t4_measured_results.md`, rerun from the Algotrade DB. That file is not edited here. All intervals are 95% Wilson
score intervals. Raw script outputs are in `hsx_daily/*.json`.

**Window:** the old corpus's banded span, daily bars **2021-02-05 → 2022-12-30**. The single exception is the
supplementary grid row, which keeps the *old grid* population (see below).

**Population:** each script's own selection, run unchanged on the slice. The slice holds every `quote.ticker` stock on
HSX/HNX/UPCOM with a close in the window: 1,736 tickers. `TWOTC` rows are a recent non-Vietnamese addition to the DB and
were never in the old corpus, so they are excluded.

## Results

| Row | Script | Population · window | Old | New — 95% CI | N (new) |
|---|---|---|---|---|---|
| blocked-entry rate, lag 0 (signal session; look-ahead) | `equity_admission.py` | stocks, **all three VN venues** (the script has no exchange filter) · 2021-02-05..2022-12-30 | **12.90%** [12.76, 13.05] — 25,464 / 197,337 | **13.16%** [13.01, 13.30] — 27,068 / 205,755 | 205,755 |
| blocked-entry rate, lag 1 (next tradeable session) | `equity_admission.py` | same | **5.84%** [5.74, 5.95] — 11,543 / 197,521 | **6.03%** [5.93, 6.14] — 12,425 / 205,958 | 205,958 |
| band agreement, engine `reconstruct_bands` vs vendor band | `band_conformance.py` | HSX stock (by **today's** ticker master) · 2021-02-05..2022-12-30 | **97.59%** [97.52, 97.66] — 4,324 / 179,784 disagree | **91.90%** [91.78, 92.03] — 14,769 / 182,367 disagree | 182,367 |
| tick-grid conformity, library rule vs flat-0.1 naive | `grid_conformity.py --start 2021-02-05 --end 2022-12-31` | HSX stock closes · 2021-02-05..2022-12-30 | (old was not measured on this window) | library **100.000%** [99.998, 100.000] — 0 off-grid; naive **72.94%** [72.74, 73.14] | 186,271 |
| tick-grid conformity (supplementary: old grid population) | `grid_conformity.py` | HSX stock closes · **2000-07-28..2022-12-30** (all history, as the old figure was) | **99.999%** vs naive **84.51%** (old plan: N = 1,086,518 HSX-stock closes) | library **99.9992%** [99.9984, 99.9996] — 9 off-grid; naive **85.38%** [85.31, 85.45] | 1,073,191 |

## What holds, and what moved

**Equity admission.** The essence holds. Lag 0 over-states the blocked rate about 2.2× relative to lag 1
(13.16% vs 6.03%; it was 12.90% vs 5.84%), and the two CIs are far apart. Both rates rise by about 0.2 pp, and N grows
4.3% (205,755 vs 197,337). That growth is **not decomposed**. The likely source is ticker-master membership and typing
(today's DB vs the old corpus), but this was not verified. Inverted-band rows excluded: 1,265 (old: 1,272 in all, 1,226 of them equity). Note that the T4 label
"HSX stocks" is inaccurate for this row: `equity_admission.py` filters on `instrumenttype = 'stock'` only, so both the
old and the new figure cover HSX + HNX + UPCOM stocks. The script's `all_instruments` lines equal the `stocks` lines
here because the slice holds stocks only; that variant is **not assessed**, and it is not a T4 row.

**Band agreement.** This row moved materially, from 97.59% to 91.90%. The cause is the population, not the engine:

- The reconstruction formula is still exact to the known residual. Only **2** HSX-stock disagreements (3 across all
  stocks) have the band width right (`disagree_same_width`), matching the old "2 of ~738k" claim.
- The extra misses come from **exchange-master drift**. The DB's `quote.ticker` stores each name's *latest* exchange.
  Names that traded on UPCOM (±15%) or HNX (±10%) in 2021–22 and moved to HSX since then are now scored against the
  HSX ±7% limit on every day of the window. Examples: BSR, VTP, MCH, ANT, SIP, ADP, KLB, NTC, PVP, VAB, VBB (469/469
  rows off-band each), plus partial-window movers ABR, ACG, CTR, PGV, GEE, VVS. 28 tickers have at least half of
  their rows off the ±7% band. They contribute 11,502 of the 14,769 disagreements on 12,205 rows.
- *Diagnostic only, not a headline:* dropping those 28 tickers gives **98.08%** [98.01, 98.14], 3,267 disagree on
  170,162 rows. That subset is selected *by outcome*, so it is not a comparable rate. It only locates the gap. The
  honest fix is a dated exchange history for the master, which neither the DB nor the engine has. `datahub.py` already
  warns that `exchange_code` is unreliable for historical by-exchange work.
- Other venues, for reference (not T4 rows): HNX stock 97.20%, UPCOM stock 72.76%, all stocks 81.88%. The low UPCOM
  figure is the special-limit-regime residual the script's docstring describes. 592 HSX-stock rows had no reference
  and were excluded, as the script does.

**Grid conformity.** The essence holds. On the old population (all HSX-stock history) the library rule gives
99.9992% vs 99.999% before. The 9 off-grid closes are the 2014–2015 two-decimal corpus defects the script's docstring
already names (C47, CCI, MCP, NLG, SVI); the old run had 13. The naive flat-0.1 grid is 85.38% vs 84.51%. On the
2021–22 window alone, the library rule is exact (0 of 186,271 off-grid) and the naive grid is much worse (72.94%),
because most 2021–22 HSX prices sit on the 0.05 or 0.01-tick bands.

## Reproduce

```
PY=<plutus-simulator venv python>
$PY scripts/rivf26_t2_hsx_daily_request.py --out request.json
$PY scripts/rivf26_extract.py declared --source db --experiment t2-hsx-daily --request request.json
$PY scripts/rivf26_t2_hsx_daily_request.py --grid-history --out grid.json
$PY scripts/rivf26_extract.py declared --source db --experiment t2-hsx-daily-grid-history --request grid.json
ROOT=<out-root>/t2-hsx-daily
PYTHONPATH=src:. $PY -m measurements.equity_admission --data-root $ROOT
PYTHONPATH=src:. $PY -m measurements.band_conformance --data-root $ROOT
PYTHONPATH=src:. $PY -m measurements.grid_conformity  --data-root $ROOT --start 2021-02-05 --end 2022-12-31
PYTHONPATH=src:. $PY -m measurements.grid_conformity  --data-root <out-root>/t2-hsx-daily-grid-history
```

Extracted 2026-11-24 from the DB (read-only), with `scripts/rivf26_extract.py` and pyarrow 26.0.1. The DB is live, so a
later extraction can differ if the vendor revises history or the ticker master changes. Check the sha256s below.

## Slices (not committed; publication is the owner's call)

`t2-hsx-daily`: 3,705,528 bytes (3.53 MiB), 1,736 tickers.

| File | Rows | Bytes | sha256 |
|---|---:|---:|---|
| `quote_ceil.parquet` | 765,679 | 934,588 | `d9abf9764bdccadc26298f924cbc2fba299be2cf7d2ea9640ce796cb31474510` |
| `quote_close.parquet` | 778,117 | 916,880 | `7b053c33e701f73c28394e4cc45c511ced9ba9287ff2b443acba9b5f0a152c92` |
| `quote_floor.parquet` | 765,678 | 918,730 | `6d027caf03b195dc15aeb771c59281993db216ecc407b66fb4508bb7a1cfe43a` |
| `quote_reference.parquet` | 763,933 | 927,597 | `7438cd875a091f11ad6a554acaf2e4ef069640c2b8b3956a8673007a7d06e14d` |
| `quote_ticker.parquet` | 1,736 | 7,733 | `4893db2004200ed559658b7bfa33a52318724536751b4f7cbdb8303bcc9d1e18` |
| `request.json` | | | `eb608a72fb86e4f0e6e43b778251bb3d8e376c5d960eb2862356e50d7bb9e9bc` |

`t2-hsx-daily-grid-history`: 2,770,872 bytes (2.64 MiB), 399 HSX-stock tickers.

| File | Rows | Bytes | sha256 |
|---|---:|---:|---|
| `quote_close.parquet` | 1,073,191 | 2,767,737 | `19c2d366d68310bfc78ae427f83a5a5b71f3a0f04de1126a8a3f03f8ac4aaba7` |
| `quote_ticker.parquet` | 399 | 3,135 | `97523aea1fb75251280b048c0c764c851fb20e2ba830f6ddc177eda3f12ff27d` |
| `request.json` | | | `1422fc0282b7a5564d2f1b4014c1ef3e6a92bcf6a849fb3e2d9bb95388e94dfd` |

## Not assessed

- The `all_instruments` variants of equity admission and grid conformity, and the `all instruments` band-ladder line:
  the slice holds stocks only. None of these is a T4 row.
- A historically correct HSX population for the band row. It would need a dated exchange history, which neither the
  DB nor the engine carries.
