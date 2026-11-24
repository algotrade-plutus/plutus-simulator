# RIVF'26 camera-ready: shared brief for the strategy-rebuild sessions (T4–T7)

Written 2026-11-24 by the coordinating session (`local_417b07d0-d6bd-4073-85a5-7db2a12f4219`, working in
`plutus-simulator` on `rivf26`). Read this, then `docs/HANDOFF-2026-11-24-camera-ready.md` in the main
`plutus-simulator` checkout (untracked; read it from `<plutus-simulator>/docs/`),
then `docs/rivf26/T0-audit.md`. The handoff's "Owner decisions" are settled; don't reopen them.

## Your repo, your branch, your limits

- You work **only** in your proto repo under `<proto>/`, on branch **`rivf26`**
  (already created). **Local commits only. Never push.**
- **Do not edit `plutus-simulator`.** It is your engine dependency (install it editable from
  `<plutus-simulator>`) and the coordinating session is changing it in parallel
  (T2). If you need an engine change or hit an engine bug, `SendMessage` the coordinating session (id above)
  with the evidence and keep going on what you can. Record the `plutus-simulator` commit hash you ran
  against in every `result/*.json`.
- Python: there is no `uv` on this machine and no system Python ≥3.12 except Homebrew
  `/opt/homebrew/bin/python3.15`. Make your own `.venv` in your repo (gitignored) with it.
- The handoff's conventions (§4) are binding: pure-signal `strategy.py`, naive `backtest.py`, faithful arm via
  `plutus.execution.PlutusBackend`, runner `experiments/<name>_anchor.py` → `result/<name>_anchor/<window>.json`
  with `naive`, `faithful` and `tier1` blocks, a naive regression test and a faithful smoke test, real đồng,
  README with hypothesis / modelling choices / windows-and-why-minimal / regenerate command / manifest pointer.
- Acceptance (§6): report f/n fills and HPR n→f per window. **If a criterion fails, report it. Don't tune
  to pass.** The owner decides.

## Data: two sources, one tool

Extract with the coordinating repo's tool, run with its venv:

```
<plutus-simulator>/.venv/bin/python \
  <plutus-simulator>/scripts/rivf26_extract.py \
  declared --source {db|archive} --experiment <name> --files ... --tickers ... --start ... --end ... [--max-depth N]
```

(`log` mode records exactly what a pytest run reads; `declared --request request.json` replays a hand-written
per-day request. See the script's docstring.) Slices go to `$RIVF26_DATA/<name>/`
with a `DATA-MANIFEST.md`. Fill in its "Why this window is minimal" section yourself. Then copy exactly what you
need into your repo's `data/` (old layout: `data/market/`, `data/tick/`, `data/band/`, `data/l2/`).

| Source | Covers | Use for |
|---|---|---|
| `--source db`: remote Algotrade Postgres (read-only; creds read at runtime from `$CRED_DIR`, never printed or copied) | daily + tick to today; **bid/ask sizes only from 2023-01-03** | anything daily; any tick/book from 2023 on |
| `--source archive`: local parquet `$VN_QUOTE_ARCHIVE` | 2020-12 → 2024-09; **bid/ask sizes from 2021-07-01** | book/queue work before 2023 |

DB table `quote.<x>` ↔ file `quote_<x>.parquet` (same columns), so no engine change is needed. Facts learned
the hard way today:

- Tick tables carry an **end-of-day row stamped `00:00:00`** of that day. Exclude it from intraday
  cumulative-volume maths, and in multi-day slices don't let the *next* day's 00:00 row leak in.
- In the DB/archive the trade (`total`) and its price (`matched`) share a timestamp. The old dev extract
  stamped the price ~70 µs later, so old pinned maker-fill numbers can move (J32/J33 did). That is data,
  not a bug.
- Archive book rows (source `D`) are offset from the trade tables by tens of ms. Join with as-of, never
  equality.
- Book prices must be `decimal128(20,6)` as the adapters expect; the tool does this for you.
- Prices are in **thousands of đồng** in the data. Convert to real đồng and record it in the README.

## Data publication (hard rule)

Minimal slices only: the (ticker, date, field) set your experiment actually reads, long enough for the
strategy to run properly. Each slice gets a manifest with sha256 and sizes. Flag anything over a few MB. The
owner signs off before anything is pushed. **Don't rely on any dataset LICENSE file for permission.**
Never put credentials, host names or local paths in committed files.

## Known engine behaviour that will affect you (don't work around it silently; report it)

1. **Band-edge orders on book/tick sessions come back INDETERMINATE.** `fills.band_lock_decision` runs before
   the book walk and reads daily OHLC, which a `BookSessionSource` tick interval doesn't carry. A market order,
   or a limit at the ceiling or floor, gets `missing: book, low|high`. 12 hidden `test_book_walk.py` tests
   (they skip without `PLUTUS_DEPTH_ROOT`) record this. Not fixed yet.
2. **Locked books look like "ghosts".** The depth data has no deletion records, so at a lock the vanished side
   keeps its last (auction) quotes. The book reads as crossed, or stale, and the book walk refuses it.
3. **The conservative queue can't decide *taker* sweeps** (`ConservativeQueue(prints=None)`): every one is
   INDETERMINATE. The *maker* arm uses the sized tape and works. Wiring the tape in for takers was approved by
   the owner. The coordinating session will do it in `plutus-simulator`. **MM:** say what you need and report
   numbers both before and after it lands.
4. **The soft policy labels every market-order fill `TRADED_THROUGH`**, even on a day pinned at the band
   edge. Fill outcomes are right; only the evidence label is wrong. Owner decision pending. Don't depend on
   the label for market orders.
5. `hard` never fills market orders (by design: depth unobservable at daily resolution).

## Reporting back

When done (or blocked), your final message should say, one line per item: done / partial / not done; commit
hashes; per window the f/n fills, HPR n→f and the Tier-1 counters; the slice names, sizes and sha256s;
which §6 criteria pass or fail; and anything **not assessed and why**.
