# T4, camera-ready: every measured number, old (hermes corpus) → new (Algotrade data)

Companion to `t4_measured_results.md` (the submission's values, left unchanged). Each row gives the old value, the
new value regenerated for the RIVF'26 camera-ready from Algotrade data (DB, or the local archive where book
sizes before 2023 are needed), its interval, the population and window, and where it is regenerated. Every new
value below was reproduced by the coordinating session from its slice before it was merged.
Engine: `plutus-simulator` `rivf26` (see each row's source for the commit).

**F5 convention:** a queue swing is always measured **relative to the optimistic arm**:
(optimistic − conservative) / optimistic. So "18.9%" means the conservative arm fills 18.9% less than the
optimistic one.

## Fill × resolution: the indeterminate rate (F2)
Source: `measurements/indeterminate_rate.py`, `docs/reference/tables/t2/indeterminate.md`. Population: FPT, HPG,
HTV, 2022-10-20..2022-11-30. Old: 66 instrument-days (the old extract was missing days); new: 90. Daily bars
from the DB; book and tape (with sizes) from the archive.

| Result | Old | New | N (new) | Note |
|---|---|---|---:|---|
| `hard`, daily bar | 35.8% [32.3, 39.4] | **32.6%** [29.7, 35.7] | 950 | all of it the resolution limit, as before |
| `book_walk` tick, optimistic | 85.6% [83.5, 87.4] | **10.1%** [8.7, 11.7] | 1,484 | sized book and tape now present |
| `book_walk` tick, conservative | 99.7% [99.3, 99.9] | **60.2%** [57.9, 62.6] | 1,650 | 78.2% before change 2 (`254aa1d`) |

**The finding changes direction:** with sized data, tick is *more* decidable than the bar (10.1% vs 32.6%).
What holds is the cause split: the resolution-limit cause appears only at the bar. `strategies/test_f2_*`
still asserts "bar < tick" and fails when given data; the owner decides its new wording.

## Fill policy: population divergence (E1)
Source: `measurements/fill_divergence.py`, `measurements/e1_regenerate.py`, `docs/reference/tables/t2/e1.md`;
published statistics in `t2/e1_published/`. Population: HSX stocks with ≥200 sessions in 2022.
Old: 385 tickers, 95,815 ticker-days, 477,537 decisions. New: 391 tickers, 97,269 ticker-days, 484,949 decisions.

| Result | Old | New (Wilson 95%) |
|---|---|---|
| Policies disagree | 31.6% | **31.43%** [31.30, 31.56]; ticker-cluster bootstrap [30.97, 31.84] |
| Market order | 95.5% | **95.44%** [95.30, 95.56] |
| Limit at close, buy / sell | 23.1% / 23.3% | **23.13%** / **23.52%** |
| Limit at floor / at ceiling | 9.9% / 6.0% | **9.15%** / **5.55%** |
| Filled shares, soft vs hard | 245.8M vs 128.5M (1.91×) | **247.4M vs 129.8M (1.91×)**; bootstrap [1.89, 1.92] |
| Undecided, hard / soft / probabilistic | 33.4% / 2.7% / 21.0% | **33.26% / 2.75% / 20.97%** |

## Fill policy: strategy divergence (F3, fill axis, S1)
Source: `strategies/test_f3_cross_policy.py` (shipped fixture, regenerated from the DB).

| Policy | Old | New |
|---|---|---|
| `soft` | −75.5%, 5 fills, 0% undecided | **−76.4%**, 5 fills, 0% undecided, 3 forced (was 2). Moved by the VM-baseline fix `64e826e` |
| `hard` | 0.0%, 0 fills, 50% undecided | 0.0%, 0 fills, 50% |
| `probabilistic` | 0.0%, 0 fills, 50% undecided | 0.0%, 0 fills, 50% |

## Queue assumption: maker fill (F3 queue axis, S8/S9)
Source: `strategies/test_s9_queue_sensitivity.py`, `test_f3_cross_policy.py`. FPT 2022-11-09.

| Queue | Old | New |
|---|---|---|
| optimistic | 152,600, 0% undecided | **152,600**, 0% |
| conservative | 123,700 (−18.9%), **16.7% undecided** | **123,700 (−18.9%)**, **0% undecided**: its taker walk now reads the sized tape (change 2, `254aa1d`) |
| probabilistic | 137,600, 0% undecided | **137,600**, 0% |

## Rule edition: derivatives margin (regime split, F1)
Source: `measurements/regime_split.py`, `measurements/t2_futures_margin.py`, `docs/reference/tables/t2/futures_margin.md`.
Book: 381 VN30F front-month entries, 2021-06-01..2022-12-30 (DB).

| Result | Old | New |
|---|---|---|
| Mean requirement, pre-KRX IM+VM | 17,692,385đ | **17,692,385đ** |
| Mean requirement, post-KRX grid | 22,995,748đ (+30.0%) | **22,995,748đ (+30.0%)** |
| The 13% → 17% IM step alone (F1) | (shown next to +30.0%, wrongly) | **+30.8%** (= 17/13 − 1) |

**F1 / paper:** +30.0% is the KRX regime split and +30.8% is the IM step. On this one-contract book the post-KRX
grid equals a flat 17% exactly, so against the 17% rule in force on the eve of the cutover, KRX adds 0%.

## Funding level: margin-call incidence
Source: `measurements/margin_incidence_account.py`. Same 381-entry book; funding 1.42×. Unchanged after `64e826e`.

| Hold | Call (old → new) | Forced (old → new) |
|---|---|---|
| 5 | 6.30% [4.27, 9.20] → **6.30%** | 1.84% [0.89, 3.74] → **1.84%** |
| 10 | 11.55% [8.72, 15.15] → **11.55%** | 8.66% [6.23, 11.91] → **8.66%** |
| 20 | 13.12% [10.10, 16.89] → **13.12%** | 9.71% [7.13, 13.10] → **9.71%** |

The 381 entries overlap in time, so these intervals are too narrow (unchanged caveat).

## Signal timing: equity admission
Source: `measurements/equity_admission.py`, `docs/reference/tables/t2/hsx_daily.md`. Window 2021-02-05..2022-12-30.
**Label correction:** the population is stocks on HSX, HNX and UPCOM, not "HSX stocks" (true of old and new).

| Result | Old | New |
|---|---|---|
| Blocked entry, lag 0 (look-ahead) | 12.90% [12.76, 13.05], 25,464 / 197,337 | **13.16%** [13.01, 13.30], 27,068 / 205,755 |
| Blocked entry, lag 1 (honest) | 5.84% [5.74, 5.95], 11,543 / 197,521 | **6.03%** [5.93, 6.14], 12,425 / 205,958 |

## Engine vs vendor
Source: `measurements/band_conformance.py`, `measurements/grid_conformity.py`, `t2/hsx_daily.md`.

| Result | Old | New |
|---|---|---|
| Band agreement, HSX stock | 97.59% [97.52, 97.66], 4,324 / 179,784 disagree | **91.90%** [91.78, 92.03], 14,769 / 182,367 disagree |
| Tick-grid conformity, HSX stock, all history | 99.999% vs naive 84.51% | **99.9992%** [99.9984, 99.9996] vs naive **85.38%** (1,073,191) |
| Tick-grid conformity, 2021–22 only | (not measured) | **100.000%** vs naive **72.94%** (186,271) |

**Band agreement drop:** this is not the engine. The DB ticker master records only each ticker's *current*
exchange, so 28 names that traded on UPCOM (±15%) or HNX (±10%) in 2021–22 and later moved to HSX are scored
against ±7%. Those 28 account for 11,502 of the 14,769 misses. The engine's formula is still exact: only 2 HSX
misses have the correct band width.

## Still to add
- **MarketMaker (Table II) and its attribution ladder:** pending the faithful-A reruns.
- Table II rows for SB, Pair and Grid are in their repos (`result/*_anchor/*.json`). They will be collected into
  `camera-ready-numbers.md` together with MM.
