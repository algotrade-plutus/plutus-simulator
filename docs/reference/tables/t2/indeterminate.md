# T2, group D: Fill × resolution, the indeterminate rate (F2), on current data

Camera-ready rerun of the first group of `docs/reference/tables/t4_measured_results.md` ("Fill × resolution —
the indeterminate rate (F2)"). That table is **not** edited here; this file is the new column.

- **Measurement:** `measurements/indeterminate_rate.py` (same probe, marks and arms as the paper: three resting
  buy limits per instrument-day, `buy@close ×1,000`, `buy@close ×30,000`, `buy@floor ×1,000`; BAR under `hard`,
  TICK under `book_walk` with the optimistic and the conservative queue).
- **Population (derived, book days × bar days):** **90 HSX instrument-days**, FPT 30 / HPG 30 / HTV 30,
  2022-10-20..2022-11-30. The old population was **66** days of the same three names and window: the old
  `hermes-dev-extract` book was missing days; the archive book covers every trading day.
- **Data:** daily bars from the Algotrade DB (`--source db`); the `local_quote` book **with sizes** and the sized
  tape from the local archive (`--source archive`), because the DB has no bid/ask sizes before 2023-01-03.
  Slices: `t2-indeterminate/daily` and `t2-indeterminate/book` (manifests with sha256 beside them; parquet not
  committed). Both come from one logged run (`log_run`), split by source.
- **Code:** "after change 2" = `rivf26` at `e528633` (the conservative queue reads the sized tape for taker
  sweeps, T0-audit §4e). "Before change 2" = `src/` of `f3958d1`, run with the same measurement script and
  slices. Change 2 touches only `src/plutus/market/session/book_walk.py` among the code this measurement runs.
- **CI:** 95% Wilson. **N** = fill evaluations (each live order, each mark that reaches the fill policy), so N
  differs between arms and between code versions: an order that fills earlier stops being evaluated.
- Raw outputs: `indeterminate_before_change2.json`, `indeterminate_after_change2.json` (this directory).

## The rows

| Row | Old (hermes, 66 days) | New, before change 2 (`f3958d1`) | New, after change 2 (`e528633`) |
|---|---|---|---|
| `hard`, daily bar | **35.8%** [32.3, 39.4] | **32.6%** [29.7, 35.7], 310 / 950 | **32.6%** [29.7, 35.7], 310 / 950 (unchanged) |
| `book_walk` tick, optimistic queue | **85.6%** [83.5, 87.4] | **10.1%** [8.7, 11.7], 150 / 1,484 | **10.1%** [8.7, 11.7], 150 / 1,484 (unchanged) |
| `book_walk` tick, conservative queue | **99.7%** [99.3, 99.9] | **78.2%** [76.3, 80.0], 1,544 / 1,974 | **60.2%** [57.9, 62.6], 994 / 1,650 |

## Cause split (resolution limit vs data ceiling)

Counts are evaluations naming each `DataField`. One evaluation can name more than one field (for example
`missing: book, low`), so the counts can sum to more than the indeterminate count.

| Row | Resolution limit (`fill_unobservable_at_resolution`) | Data ceiling, before change 2 | Data ceiling, after change 2 |
|---|---|---|---|
| `hard`, daily bar | **all of it**: 310 (32.6% of N) | none | none |
| tick, optimistic | 0 | book 48, low 48, volume 102 | same |
| tick, conservative | 0 | book_size 866, volume 630, book 48, low 48 | book_size 842, volume 104, book 48, low 48 |

## What moved, and why

1. **BAR, 35.8% → 32.6%.** Same kind (entirely the resolution limit; the `low` cause stays resolved). The CIs
   overlap. The difference is population (90 vs 66 days) and DB daily values.
2. **TICK optimistic, 85.6% → 10.1%.** The largest move, and it is **data, not code** (identical before and after
   change 2). The old extract lacked sized levels and the sized tape for most days; the archive book carries
   sizes from 2021-07-01 and the tape is sized, so the optimistic queue now decides most touches.
3. **TICK conservative, 99.7% → 78.2% (data) → 60.2% (change 2).** Data first: sizes remove most of the old
   ceiling. Change 2 then removes most of the `volume` cause (630 → 104): taker sweeps are now decided from the
   sized tape. What remains is mostly `book_size` (a resting buy at the close or floor with no displayed depth
   at that price, which the conservative queue refuses to size).
4. **The tick `book` + `low` pair (48 each, all tick arms, both code versions)** has the signature of the known
   engine gap #1 in `docs/rivf26/PARALLEL-BRIEF.md`: a limit at the floor on a book session goes through
   `band_lock_decision`, which reads a daily low the tick interval does not carry. Not verified per order here.
   `low` is a data-ceiling field in this classification; the resolution-limit count at tick stays 0.

**Classification still holds** (resolution limit only at BAR, structurally zero at TICK). **The magnitude story
inverts:** the paper's "the tick rate is higher than the bar's because this extract lacks the sized tape" is no
longer true on current data. Optimistic tick (10.1%) is now well **below** the bar (32.6%); conservative tick
(60.2%) is still above it.

## `strategies/test_f2_resolution_indeterminacy.py`

Now runnable against the slices (roots from `PLUTUS_F2_BAR_ROOT` / `PLUTUS_F2_TICK_ROOT`, falling back to
`PLUTUS_DATA_ROOT` / `PLUTUS_DEPTH_ROOT`; it skips with neither set). Assertions not changed. Result on the
slices (first 4 days per ticker, 12 instrument-days), at both code versions: **FAILS** at assertion (3),
`bar.rate < tick_opt.rate`: bar 34.1% (45/132) vs optimistic tick 0.0% (0/208). Assertions (1) and (2) pass
(bar entirely resolution-limit, no resolution-limit cause at tick). Assertion (4) is not reached; on this slice it
would also fail (`tick_opt.indeterminate > 0` is false, and after change 2 `volume` no longer appears in the
conservative arm: before `{volume 68, book_size 164}`, 84.1%; after `{book_size 158}`, 66.1%). The test encodes
the old, data-poor magnitudes. Rewriting it is an owner decision.

## Regenerate

```
PLUTUS_F2_BAR_ROOT=<rivf26-data>/t2-indeterminate/daily \
PLUTUS_F2_TICK_ROOT=<rivf26-data>/t2-indeterminate/book \
  .venv/bin/python measurements/indeterminate_rate.py --json out.json --png out.png
```

Re-extract: `scripts/rivf26_extract.py log --source archive --callable measurements.indeterminate_rate:log_run`
(repo root and `src` on `PYTHONPATH`), then replay the daily files of its `request.json` with `declared --source db`
and the `local_quote_*` files with `declared --source archive`.
