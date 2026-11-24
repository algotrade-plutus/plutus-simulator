# T2 group C: derivatives-margin rows on DB data, and fact-check F1

RIVF'26 camera-ready, handoff task T2. This reruns the two derivatives-margin groups of
`docs/reference/tables/t4_measured_results.md` on a slice extracted from the Algotrade DB, and
resolves fact-check **F1**. `t4_measured_results.md` is not edited.

## Data

| | |
|---|---|
| Slice | `rivf26/data/t2-futures-margin/` (working folder, not committed) with `DATA-MANIFEST.md` |
| Source | Algotrade DB, `--source db`, tables `quote.close` and `quote.futurecontractcode` |
| Request | `docs/reference/tables/t2/futures_margin_request.json` (replay: `scripts/rivf26_extract.py declared --source db --experiment t2-futures-margin --request <it>`) |
| `quote_close.parquet` | 401 rows, 3,903 bytes, sha256 `a046b87dd4ebb8a1fb37e47f5e77af29f8b5b981df492f0f25ab4dd8a85a1979` |
| `quote_futurecontractcode.parquet` | 414 rows, 2,670 bytes, sha256 `b181273a32e319a0f5e64b2b0b261af2750ef084752d7fde5fa3db7acaaa0e91` |
| Determinism | replayed into a second directory: byte-identical |

**Population (every row below):** long one VN30F front-month contract (`futurecode = 'VN30F1M'`) at each
session close, 20 contracts VN30F2106 .. VN30F2301, 401 front-month closes, **N = 381 entries**.
**Window:** 2021-06-01 .. 2022-12-30 (the DB's `futurecontractcode` starts 2021-06-01; the old corpus
ended 2022-12-30). Each contract is extracted only over its front-month days. Prices are stored in
thousands of đồng; the scripts apply the 100,000đ/point multiplier, so all amounts are real đồng.

Regenerate:

```
PYTHONPATH=src:. python measurements/t2_futures_margin.py <slice-root>
```

It calls the same functions with the same arguments as
`reproduce_measurements.measure_exchange_margin` (Wilson 95% CIs as there).

## Rule edition: derivatives margin (dated regime split)

`measurements/regime_split.py`. Requirement read at entry, same book under both editions; 0 refused.

| Result | Assumption set | Old value | New value (DB) | CI | N | Population / window |
|---|---|---|---|---|---|---|
| mean margin requirement | pre-KRX IM+VM (dated VSD IM) | 17,692,385đ | **17,692,385đ** | none (a mean over a fixed book, no sampling) | 381 | as above |
| mean margin requirement | post-KRX scenario grid (SSI mirror, TCBS 5,000đ MF) | 22,995,748đ (+30.0%) | **22,995,748đ (+30.0%)** | none | 381 | as above |

Ratio of means +29.98%; mean of per-position ratios 1.300. Both round to +30.0%.

## Funding level: margin-call incidence (account model)

`measurements/margin_incidence_account.py`: the real `DerivativesAccount`, dated VSD IM, daily VM cash
settlement, deposit 1.42× the opening requirement (`BEST_JOINT_FIT`), broker buffer 0.05.

| Result | Hold | Old value [95% CI] | New value (DB) [95% Wilson CI] | k / N | Population / window |
|---|---|---|---|---|---|
| margin-call incidence | 5 | 6.30% [4.27, 9.20] | **6.30% [4.27, 9.20]** | 24 / 381 | as above |
| forced-close incidence | 5 | 1.84% [0.89, 3.74] | **1.84% [0.89, 3.74]** | 7 / 381 | as above |
| margin-call incidence | 10 | 11.55% [8.72, 15.15] | **11.55% [8.72, 15.15]** | 44 / 381 | as above |
| forced-close incidence | 10 | 8.66% [6.23, 11.91] | **8.66% [6.23, 11.91]** | 33 / 381 | as above |
| margin-call incidence | 20 | 13.12% [10.10, 16.89] | **13.12% [10.10, 16.89]** | 50 / 381 | as above |
| forced-close incidence | 20 | 9.71% [7.13, 13.10] | **9.71% [7.13, 13.10]** | 37 / 381 | as above |

All six rates and both regime-split means reproduce exactly on DB data. The Wilson intervals treat the 381 entries as
independent; they are overlapping windows on 401 closes (`margin-model-adjudication.md` §"The
denominator"), so the intervals are too narrow. That caveat is unchanged from the old table.

## F1: which number belongs to which claim

The paper puts the **30.0%** next to the 13% → 17% IM step. On the same 381-entry book:

| Claim | Comparison | Mean requirement | Change |
|---|---|---|---|
| (1) **Regime split** (KRX cutover, 2025-05-05) | pre-KRX dated IM (371 entries at 13%, 10 at 17%) → post-KRX scenario grid (SSI mirror: risk 17%, basis 0.87%; TCBS minimum 5,000đ/contract) | 17,692,385đ → 22,995,748đ | **+30.0%** (+29.98%) |
| (2) **13% → 17% IM step alone** (VSD, 2022-12-15) | every entry at a flat 13% → every entry at a flat 17% | 17,584,984đ → 22,995,748đ | **+30.8%** (+30.77%, i.e. 17/13 − 1, for any book) |

- **+30.0% is the regime split.** It belongs to the KRX-cutover / dated-rule-editions claim.
- **+30.8% is the 13% → 17% step.** It belongs to the IM-hike claim and matches J18's single-position +30.8%.
  On a long-only one-contract book the step is linear in notional, so the book does not change it.

What the decomposition also shows (reported, not acted on): on this book the post-KRX grid equals a flat
17% IM to the đồng (grid vs flat 17%: +0.00%). A single leg has no spread charge, and the 5,000đ minimum
never binds (the risk term alone averages 22,995,748đ per contract). So the +30.0% "regime split" is almost
entirely the 13% → 17% step. It is diluted to 30.0% only because 10 of the 381 entries already sit at 17%.
Against the pre-KRX rule actually in force on the eve of the cutover (17% since 2022-12-15), the KRX grid
adds nothing on a one-contract book. The paper should not present +30.0% as an effect of the KRX cutover
without that qualification. Whether to restate it is the owner's decision.

## Not assessed

- The `funding_sweep` block (1.2 / 1.42 / 1.6 / 2.0 at hold 10) that `reproduce_measurements` also
  prints. It is not a T4 row.
- The legacy per-position path (`margin_incidence.py`, 29 / 48 / 56) and `measure_peak_requirement`.
  They read the same two files and the slice supports them, but they are not T4 rows.
- Any book other than the 2021-06 .. 2022-12 front-month one, e.g. a post-cutover book. The task was to
  rerun the old book, not to choose a new one.
