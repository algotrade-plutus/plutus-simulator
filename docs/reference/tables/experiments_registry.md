# Experiments registry — naive vs faithful, per strategy

The single source the RIVF'26 paper quotes for the strategy-driven experiments
(the naive-vs-faithful contrast on real strategies, framed as an
execution-intensity spectrum). Each strategy runs the **same signals** through
its own naive engine and through the faithful Plutus market; the gap is the
finding. Every row carries the modelling choices it was measured under and the
command that regenerates it. See
`docs/superpowers/specs/2026-09-08-plutus-strategy-experiments-design.md`.

> **Read the gap, not a single arm.** The point of each block is that the two
> arms *differ*, and by how much relative to the strategy's execution intensity.
> P&L is a Tier-2 consequence, computed by the caller's harness; Plutus reports
> only fills / cash / margin.

---

## SB — SmartBeta (equity, monthly P/E-DY rebalance) · the null anchor

Low execution intensity (monthly, close-price, cash equity), so the faithful
run should land *close* to the naive — the calibration point of the spectrum.
Out-of-sample window 2022-01-04 → 2024-02-07 (525 trading days, 25 rebalances).

**Modelling choices (faithful arm).** Capital **25,000,000,000đ** (the naive
25M × 1000, because SmartBeta's prices are quoted in thousands of đồng);
`soft` fill policy; orders as **LIMIT at the day's close**; the **sale advance**
(*ứng trước tiền bán*) enabled at `daily_rate 0.0003` so the monthly
full-liquidation rebalance self-funds same-day; real 100-share lots and price
bands; weekday-only settlement calendar (Tết approximation). Both arms read one
identical frozen parquet slice (`data/market/`, the OOS universe's daily tables).

| Metric | naive (published) | faithful (Plutus) | Δ |
|---|--:|--:|--:|
| Sharpe (annualised) | **−0.3497** | **−0.5093** | −0.160 |
| HPR | −3.17% | −8.39% | −5.22 pp |
| Max drawdown | −46.04% | −46.35% | −0.31 pp |

**Tier-1 (sign-free, faithful arm).** 2,257 fills over the run; refusals
**`{}`** and indeterminates **`{}`** — band lock is graded at fill time, not
admission, so it never appears as a `refusals` entry (see the Increment 2 note
below for the mechanism); the fee-buffered LIMIT-at-close sizing still leaves
no `INSUFFICIENT_CASH`, unchanged from before. **Band-lock no-fills: 0** —
every `Accepted` order this run submitted into a
close-at-the-band day resolved to a fill under the `soft` policy's floor. With
the band-lock channel measured at zero, the entire faithful/naive gap is the
sale-advance fee + lot-granularity + fill-at-close-vs-prev-close timing — all of
which are cheaply modelable in the naive engine too, which is why SB stays the
null anchor: a faithful simulator adds little here **beyond** frictions a
careful naive backtest could also add. The **max drawdown is essentially
unchanged** (−46.35% vs −46.04%), i.e. the risk profile is materially the same;
only the return level and Sharpe move — **up toward naive** relative to
Increment 1 (see below).

**Provenance / regenerate:**
```bash
cd proto/ProtoSmartBeta            # branch rivf-2026
python -m proto_smart_beta.experiments.extract_market      # freeze the daily slice
python -m proto_smart_beta.experiments.null_anchor         # naive vs faithful
```
Naive numbers reproduce the committed `.plutus/expected/` baseline exactly
(`tests/test_regression_baseline.py`).

**Increment 2 note.** Increment 1 moved BAND_LOCK to fill time but kept
Increment 0's evidence: a single `close==band` bar-proxy that could not tell a
genuine full-session lock from a bar that merely *closed* at the edge after
trading through it earlier in the session — every one of those was graded
`NO_FILL`, a ~10x over-assertion left unfixed until now. Increment 2 replaces it
with the full daily evidence ladder (OHLC + volume, phase-aware): a bar that
traded through the edge before closing there **fills** (the over-assertion
fix — most of the population); a bar that collapsed to the edge but still
recorded volume passes through to the active fill policy's floor, which for
`soft` **fills at the edge**; only a bar that collapsed to the edge with
**zero** recorded volume (*trắng bên bán/mua*, a genuine full-session lock) is
graded **`NO_FILL`**.

Regenerating under Increment 2: faithful Sharpe moves from **−0.5543**
(Increment 1) to **−0.5093** (measured) — up toward naive's **−0.3497**,
shrinking the gap from −0.2046 to −0.1596, the direction the fix predicts.
Total fills rose from 2,187 to **2,257**.

The runner's Tier-1 tally is recounted to match: since a fill-time `NO_FILL`
leaves the order **resting with no event of its own** (`REST` is the one
silent transition — it cannot be read off `advance_to`'s event stream),
`null_anchor.py`'s `_faithful` now classifies it post hoc instead — an
`Accepted` order marketable into a close-at-the-band day
(`DataHubSource.state_at(ticker, day).locked_side` matching the order's side)
that never turns up in a fill event over its rebalance window is a band-lock
no-fill. The runner now emits this candidate population as its own
`band_lock_candidates` output field, alongside `band_lock_no_fills` — so both
numbers below reproduce directly from the provenance command above, rather
than from the uncommitted scratch script Increment 2 was first measured with.
Of the **49** candidates this run touched (the fresh count under this
classifier — not directly comparable to Increment 1's **45**, which was
measured under the older admission-time-rejection regime; accepting rather
than rejecting those orders changes downstream cash and holdings, so which
later orders even get submitted diverges too), **all 49 resolved to fills**:
**band-lock no-fills: 45 → 0**. Under the `soft` policy every collapsed-but-
traded bar fills at the edge, and this OOS window contains no ticker-day that
both collapsed to the band **and** recorded zero volume — the residual
true-lock population is empirically empty here, not assumed away.

**Band-lock ladder audit (corpus-wide, owner-signed-off 2026-09-14).** SB's own
zero count is not a fluke of one OOS window: a full-corpus scan
(`measurements/band_lock_ladder_audit.py`, snapshot
`measurements/band_lock_ladder_audit_output.txt`) of every genuine
full-session collapse, 2021-02-05 → 2022-12-30, found **8,610 of 8,611
(99.99%)** buy-side candidates carry positive `quote_dailyvolume` →
**ASSUMED** (policy-dependent; `soft` fills at the edge); only **1** — PTG, a
dormant UPCOM penny stock — is a proven `NO_FILL`. So at **daily** resolution
band-lock is ASSUMED-dominant: the proven "band refuses the fill" is a
**tick-resolution** effect (the Grid/Pair book tier, B1–B3/S1–S3), not
something a daily, monthly-rebalance strategy like SB should ever expect to
hit — consistent with the `band_lock_no_fills: 0` measured above. See design
doc §4d/§4e
(`docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md`).

---

## Grid — ProtoGrid (equity, tick-resolution paired buy-low/sell-high grid) · the execution-fidelity demonstrator

The **second point** on the spectrum (SB → **Grid**), and the first with real
execution intensity: a cost-aware paired grid that rests LIMIT orders at every
rung and works them **tick-by-tick** on the continuous HOSE tape, re-anchored
each calendar month to that month's open reference price. Three liquid VN30
names (SSI, TCH, POW), capital **2,000,000,000đ**, 3 grids × 8 rungs, assumed
round-trip cost **0.4%**. In-sample window 2021-02-17 → 2023-08-31 (637 trading
days). ProtoGrid is an **execution-fidelity demonstrator**: Tier-1 (the
execution divergence) is the headline; P&L is Tier-2 and **de-emphasized** — see
`proto/ProtoGrid/docs/hypothesis.md`.

**Modelling choices (faithful arm).** The *same* grid signals as the naive arm,
replayed through `PlutusBackend` over the **identical** frozen tick slice:
`soft` fill policy; orders as **LIMIT at each rung price**; real 100-share HOSE
lots on the **dated tick grid** (`TICK_GRID` rejects a limit that is off-grid);
price bands (`BAND_LIMIT` at admission); the **tick book-tier band lock**
(`TICK_BOOK` evidence read from the resting ask/bid ladder — Grid's payoff over
SmartBeta's daily-bar proxy); and **T+2 settlement with the sale advance OFF**,
so a re-buy after a sell stalls on locked cash (`INSUFFICIENT_CASH`). Both arms
read one identical frozen slice (`data/tick/` matched ticks + `data/band/` daily
bands).

| Metric (Tier-2, de-emphasized) | naive | faithful (Plutus) | Δ |
|---|--:|--:|--:|
| Sharpe (annualised) | **−0.067** | **−0.319** | −0.253 |
| HPR | −19.0% | −34.2% | −15.2 pp |
| Max drawdown | −63.1% | −68.1% | −5.0 pp |

**Tier-1 (sign-free, the headline).** The same signals the naive engine fills
**1,457** times fill only **151** times through the faithful market — close to
an order-of-magnitude execution collapse, and the whole point of the row.
Refusals by cause (the admission gauntlet): **`BAND_LIMIT` 6,573** (+ **93**
graded *indeterminate* at submit), **`TICK_GRID` 2,409** (limit price off the
dated tick grid), **`INSUFFICIENT_CASH` 248** (buy-side, cash-constrained),
**`UNSETTLED_HOLDING` 67** (sell-side). The **248 `INSUFFICIENT_CASH`** are
overwhelmingly a **capital/charge-budget** constraint, not settlement: the grid
is sized to ~100% of the 2e9 account, so re-running with the sale advance ON
(proceeds credited T+1 rather than locked to T+2) drops them only **248 → 242**,
isolating **≈6 genuinely T+2-locked re-buys** (`t2_locked_rebuys: 6`). The
sell-side **`UNSETTLED_HOLDING` 67** is the T+2 hold on not-yet-settled shares
(≈unchanged, **67 → 66**, with the advance on). **Fill-time band-lock no-fills:
6 of 6** — every one of the run's six close-at-the-band candidates failed to
fill. This is **non-zero here, unlike SB's daily zero**: at Grid's **tick +
book tier** a genuine full-session lock is observable in the resting ask/bid
ladder, whereas SB's daily-bar proxy graded the same channel at zero — the
proven "band refuses the fill" is a **tick-resolution** effect (the Grid/Pair
book tier), consistent with SB's corpus-wide ladder audit. **Fill-policy spread**
(indeterminate rate): `soft` **0.0%** (151 fills / 708 evaluations), `hard`
**99.9%**, `probabilistic` **97.7%** — at tick resolution a bar carries **no
volume/OHLC**, so the conservative policies cannot establish *which* order filled
and collapse to `INDETERMINATE`; that rate **is** the finding, reported honestly
rather than papered over.

**Tier-2 (de-emphasized).** Net of the same assumed 0.4% round-trip cost,
Sharpe moves **−0.067 → −0.319** and HPR **−19.0% → −34.2%** as fidelity bites,
and max drawdown deepens **−63.1% → −68.1%**. Nothing is gated on this:
ProtoGrid demonstrates execution fidelity, not alpha (memory: fidelity, not P&L).

**Provenance / regenerate:**
```bash
cd proto/ProtoGrid                 # branch rivf-2026
pg-extract                         # freeze the tick + daily-band slice (Drive-hosted, ~168 MiB)
python -m proto_grid.experiments.grid_anchor   # naive vs faithful -> result/grid_anchor/is.json
```
The naive arm reproduces its committed baseline exactly
(`tests/test_regression_baseline.py`, `tests/test_oos_regression.py`, and
`plutus check` against `.plutus/manifest.yaml`); the faithful Tier-1 tallies
above are the `faithful` block of `result/grid_anchor/is.json` (the source of
truth — read, not re-derived).

---

## MM · Pair — pending (Phases 2–3)

The futures market-maker (ProtoMarketMaker) and the cross-market pair (ProtoPair)
are the high-intensity remainder of the spectrum; their rows land as each phase
completes. The synthetic corroborators (population E1, the 381-book E2 re-dating,
the equity-admission lag) are retained in `t4_measured_results.md` and quoted as
large-n backbone when page room allows.
