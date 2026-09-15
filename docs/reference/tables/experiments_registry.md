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

## MM — ProtoMarketMaker (VN30 index futures, 15s-cadence two-sided quoting) · the derivatives market-maker

The **third point** on the spectrum (SB → Grid → **MM** → Pair), and the
highest-cadence strategy: a two-sided inventory-skewed quoter that requotes
both sides every **15 seconds** (or immediately on a fill), so the gap
between a naive fill model and a faithful one is where its edge lives or
dies. Both arms replay the **identical** pure signal `strategy.quote(price,
inventory, step)` at the optimized `step=3.1`; the ONLY difference is
execution. Redated windows: in-sample 2022-01-01 → 2023-12-31 (498 trading
days), out-of-sample 2024-01-01 → 2025-06-30 (**360 trading days, the
headline below** — the only MM window that crosses the **KRX matching-engine
cutover, 2025-05-05**). Like Grid and Pair, ProtoMarketMaker is an
**execution-fidelity demonstrator**: Tier-1 (the maker-side counters) is the
headline, P&L is Tier-2 and de-emphasized.

**Modelling choices (faithful arm).** Real đồng throughout: account-level
derivatives deposit **500,000,000đ** (`initial_deposit`, the same capital as
the naive engine's 5e5-thousand-đồng once units reconcile), the real VN30F
multiplier **100,000đ/index-point**, and the **dated VSD initial-margin**
ratio — **13% before 2022-12-15, 17% on/after** — reached through
`plutus.market.margin.vsd_initial_margin` per (contract, timestamp), not a
flat assumption. Fills are decided by a **`book_walk`** policy sweeping the
frozen depth ladder under the **`conservative`** queue (headline; the OOS
window starts inside the displayed-size era so the conservative sweep can
act), with a pre-2023-01-03 **`optimistic`**-queue fallback for windows that
start before displayed sizes exist. Both arms replay the same frozen
VN30F1M/F2M L2 depth + tape slice.

**Tier-1 (sign-free, the headline) — OOS, 360 trading days.** The
maker-queue axis is the first finding: replaying the *same* signal under
four queue policies swings fills **conservative 402 → probabilistic 560 →
optimistic 628 → soft (uncapped) 11,185** — a **35.99%**
conservative-vs-optimistic swing, with the `soft` upper bound sitting almost
an order of magnitude above the positioned queues. The conservative
headline's own indeterminate rate is **99.94%** — it can decide almost
nothing without displayed depth to sweep — and a dedicated pre-2023 probe
(one week wholly before the size era) shows why: forcing the conservative
queue there yields **100% INDETERMINATE** (zero fills, all `book_size`),
because the reconstructed ladder before 2023-01-03 carries no displayed
sizes at all. **Counter 2, the dated-margin affordability shift:** the same
500,000,000đ deposit affords **37 contracts** at the 13% VSD-IM rate and
**28** once it steps to 17% on 2022-12-15 — a **24% (9-contract)**
affordability cut at an unchanged price — with **zero** margin calls or
forced liquidations over the OOS run (**0/0**) and a peak margin utilisation
of **52.3%**. Both of those are **intraday-flat** results: the faithful arm
builds a fresh backend *per trading day* and flattens at each day's close
(the naive arm instead carries inventory overnight), so the `0/0` reflects
no *overnight* accumulation ever reaching a call, and the 52.3% peak reflects
**intraday inventory build-up** (multiple lots accumulating within a trend
session), not a near-flat book. **Counter 3, the KRX cutover (2025-05-05):**
post-cutover fills fall to **65** against **337** pre-cutover (the
post-cutover span is much shorter, not a decidability effect), and the
**fill-time** INDETERMINATE rate — `book_size`+`volume`+`book`
fill-evaluation events over fills-plus-that-sum, the rate that actually
reconciles with this split — reads **99.92%** post-cutover against **99.94%**
pre-, i.e. materially unchanged by the KRX matching-engine change; the
maker-side finding is dominated by queue positioning, not the cutover
itself. Submit-time `BAND_LIMIT` session rejections are a **separate**,
largely immaterial channel at this window's resolution — **1,530 events,
0.22%** of OOS submit attempts (larger in IS, 1,852, where it is likewise a
submit-time channel, not a fill-decidability one: quoting the *blended*
top-level indeterminate rate there, 0.7191, would overstate
fill-undecidability — the clean IS **fill-time** rate is **≈0.4830**,
matching `krx.pre_indeterminate_rate` exactly once `BAND_LIMIT` is
excluded). All indeterminate/refusal counts above are **fill-evaluation
events**, not orders — a resting order can be evaluated indeterminate and
re-evaluated again on a later tick. **Maker gap:** the naive engine fills
**910** times over the same OOS window against the faithful arm's **402** —
a **≈2.3×** gap between assuming every crossing order fills and faithfully
sweeping the reconstructed book. The naive arm's own OOS Sharpe/HPR
(**0.766/0.5675**) reproduce the published Task-5/6 anchor **exactly**
(`matches_published_oos_anchor: true`), so the Tier-1 counters above are
measured against a naive baseline that is itself pinned.

**Tier-2 (de-emphasized).**

| Metric (daily) | naive | faithful (Plutus) | Δ |
|---|--:|--:|--:|
| Sharpe (annualised) | **0.766** | **1.449** | +0.683 |
| HPR | 56.75% | 31.62% | −25.13 pp |
| Max drawdown | −13.12% | −1.43% | +11.69 pp |

Nothing is gated on this table — like Grid and Pair, ProtoMarketMaker
demonstrates execution fidelity, not alpha (fidelity, not P&L) — and here the
gap is a **doubly** unsafe P&L comparison to over-read: beyond the usual
naive-vs-faithful execution difference, the faithful arm is
**intraday-flat** while the naive arm **carries inventory overnight**, so
part of this Sharpe/HPR/MDD delta is a carry-vs-flat difference, not purely
an execution-fidelity effect. The Tier-1 counters above are unaffected (they
are per-fill decisions on the same replayed signal), which is why this table
stays Tier-2.

**Provenance / regenerate:**
```bash
cd proto/ProtoMarketMaker           # branch rivf-2026
uv run pmm-extract-l2               # freeze the VN30F1M/F2M L2 depth + tape slice
uv run pmm-anchor                   # naive vs faithful -> result/mm_anchor.json
```
The naive arm reproduces its committed baseline exactly
(`tests/test_regression_baseline.py` and `plutus check` against
`.plutus/manifest.yaml`); the pre-registered activity/credibility gate
(naive IS round-trips ≥ 300; faithful forced-liquidations bounded by days —
never a Sharpe/HPR stop-gate) is `tests/test_proceed_gate.py`. The Tier-1
tallies above are the `faithful` / `queue_spread` blocks of
`result/mm_anchor.json` (the source of truth — read, not re-derived).

---

## Pair — ProtoPair (cross-market VN30 basket vs `VN30F1M` future) · the settlement-asymmetry capstone

The **fourth and final point** on the spectrum (SB → Grid → MM → **Pair**),
and the only strategy that trades **two venues and two segregated pools at
once**: an equal-lot VN30 proxy basket (long, HSX) against the front-month
`VN30F1M` future (short, HNXDS). It is therefore the only point that
exercises **settlement asymmetry** — the equity leg settles **T+2**, the
futures leg settles **daily variation margin in cash**, and a naive
single-ledger backtest nets both same-day and never sees the gap. ProtoPair
inherits every lower-intensity axis the earlier phases established (equity
admission, the futures margin ladder, T+2 recycling) plus two axes unique to
it: the **no-short-sale asymmetry** (no operational stock short-selling in
Vietnam, so only the future-rich side of the basis is executable — the
mirror side is sat out and its forgone-signal count is itself a Tier-1
finding) and the **continuous→dated-contract roll**. In-sample window
2022-01-01 → 2023-12-31 (498 aligned trading days, 25 distinct dated
front-month contracts). Like ProtoGrid, ProtoPair is an **execution-fidelity
demonstrator**: settlement asymmetry (Tier-1) is the headline, P&L is Tier-2
and de-emphasized — see `proto/ProtoPair/docs/hypothesis.md`
(`rivf26-fidelity-not-pnl`).

**Modelling choices (faithful arm).** Two venues (`['HSX','HNXDS']`), two
segregated pools (securities / derivatives, no auto-transfer between them);
capital **600,000,000đ** with a **comfortable** deposit target
(**80,000,000đ**) as the headline and a **thin** deposit target
(**62,000,000đ**) run as a stress variant (same capital, tighter derivatives
buffer); `soft` fill policy as the headline, with a `hard` variant run for
comparison; **T+2 settlement ON, sale advance OFF** as the headline (a
T+2-locked equity sale cannot fund a same-session futures need), with a
sale-advance-ON variant run to isolate the effect; the real dated derivatives
PIT margin-ratio ladder (**0.13 → 0.17 on 2022-12-15**); daily resolution.
Both arms read one identical frozen daily slice (`data/market/`).

**Tier-1 (sign-free, the headline) — settlement asymmetry leads.** Of the
naive engine's 22 executable (long-basket/short-future) entries, **16 stall
on exit (72.7%)** — the equity legs bought to open cannot be sold again
until they clear T+2, holding the position open **758 name-days** longer
than the naive single ledger would (entry-side stalls: **0** — the
funding-on-demand coordinator absorbs the entry side; it is the exit/closing
sell of the equity leg where the pure T+2 hold bites). **Funding:** every
one of the 22 entries needs an on-demand transfer (the derivatives pool
opens at zero); all 22 are **`funded_in_aggregate`** and successfully funded
— **22 cross-pool transfers, Σ1,760,000,000đ** — with **21 sweep-backs**
(Σ1,701,303,129đ) returning the deposit to securities once each futures leg
flattens, one fewer than the transfer count because the 22nd cycle's futures
leg is still open at the window's end. **Abandonment is 0 at the headline**
(and 0 again under the thin deposit ladder — Σ1,364,000,000đ
transferred/Σ1,323,303,129đ swept back) — not because the abandon path is
unreachable, but because this IS window never happens to starve it: a
dedicated thin-book probe (2022-04-18, securities cash deliberately cut to
209,839,500đ against a 205,725,000đ basket notional) demonstrates the path
firing correctly once the shortfall (38,300,600đ) exceeds what the other
pool can cover (3,750,361đ available) — `funded_in_aggregate=False` →
**abandoned=True**, the 30 equity legs already placed are cancelled, no
naked basket left resting. **Margin call / forced liquidation: 0/0**, at
both the comfortable and the thin deposit target — the 2-contract
derivatives size never stresses the ladder in this window. **Expiry:** both
of the window's 2 dated-contract expiries needed a **`CLOSE_PROXY`**
substitution (2/2). **No-short opportunity-set asymmetry:** the executable
side fills **22/22 (100%)**; the mirror side (short-basket/long-future — 17
actual naive-engine mirror trades, out of 29 SIT_OUT signal-days the pure
signal registered) is refused **17/17 (100%)** — Vietnam's no operational
stock short-sale makes the mirror side structurally unexecutable, not merely
less profitable. **Refusals by cause:** essentially all land on HSX —
**`UNSETTLED_HOLDING` 459** (these are mirror-side HSX sells with no settled
deliverable — every leg of a mirror-side sell attempt lacks a *settled*
position to deliver, whether the name was never held at all or was simply
bought too recently to have cleared T+2 yet; not just never-held names) —
with nothing persisting on HNXDS (the 22 initial `INSUFFICIENT_DEPOSIT`
refusals there are all cured by the on-demand transfer above, so none
survive as a final refusal). **Fill-policy spread** (indeterminate rate):
`soft` **2.2%** (1,236 fills / 1,803 evaluations), `hard` **96.8%** (0
fills) — at daily resolution with no book, the conservative `hard` policy
cannot establish which side of an ambiguous bar actually traded and
collapses to `INDETERMINATE` almost every time, the same
tick/daily-resolution effect SB's and Grid's own fill-policy spreads already
surface.

**Attribution: the exit stall is a pure T+2 buy-side lag, not a cash-timing
artifact.** Toggling `advance_sale_proceeds` ON does **not** move the exit
stall count at all — 16 stalls with the advance off, 16 with it on. That is
expected, not a bug: the sale advance only accelerates *sale* proceeds
becoming available; the 16 stalls are **unsettled-*purchase*** stalls — the
equity legs bought to open the position have not yet cleared T+2 by the
time the signal says exit, and no amount of advancing *sale* proceeds
touches when a *purchase* settles. This isolates the finding to the pure
T+2 equity-settlement lag, independent of the funding-side sale-advance
policy Grid's own Tier-1 varies.

**Tier-2 (de-emphasized).** Naive Sharpe **+0.7183** → faithful **−0.7940**
(Δ ≈ −1.51); HPR **+3.50%** → **−3.16%** (Δ ≈ −6.66 pp); max drawdown
**2.32%** → **4.35%** (Δ ≈ +2.03 pp, roughly double). Nothing is gated on
this: like Grid, ProtoPair demonstrates settlement fidelity, not alpha
(memory: fidelity, not P&L) — and per `docs/hypothesis.md`'s
`rivf26-fidelity-not-pnl` framing, this row may be omitted from the paper
entirely.

**Provenance / regenerate:**
```bash
cd proto/ProtoPair                 # branch rivf-2026
pp-extract                          # freeze the daily slice (Drive-hosted; algotradeDB freeze folds in separately, pp-freeze-db)
python -m proto_pair.experiments.pair_anchor   # naive vs faithful -> result/pair_anchor/is.json
```
The naive arm reproduces its committed baseline exactly
(`tests/test_regression_baseline.py`, `tests/test_oos_regression.py`, and
`plutus check` against `.plutus/manifest.yaml`); the faithful Tier-1 tallies
above are the `faithful` block of `result/pair_anchor/is.json` (the source
of truth — read, not re-derived). The credibility pre-check underlying the
signal (IS basis ADF p ≈ 2.9507e-10, OU half-life ≈ 1.14 trading days) is
itself reproducible from a committed script: `pp-credibility` →
`result/credibility/is.json`.
