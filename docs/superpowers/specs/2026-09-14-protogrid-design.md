# ProtoGrid — the equity grid demonstrator (Phase 1) — design

**Date:** 2026-09-14 · **Status:** design approved, pre-implementation ·
**Repo:** new `proto/ProtoGrid` (9-step) + `plutus` hub (shared seam, registry).

Companion to `docs/superpowers/specs/2026-09-08-plutus-strategy-experiments-design.md`
(the four-strategy intensity-spectrum design, of which this is **Phase 1**),
`docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md` (the band-lock
fillability model ProtoGrid is the first strategy to exercise at tick resolution),
and `docs/reference/tables/experiments_registry.md` (where its results land).

---

## 1. Motivation and role

The experiment upgrade contrasts each strategy's **naive backtest** against the
**faithful Plutus market** on the *same signals*, and measures the gap as a
function of execution intensity: SB (null anchor) → **Grid** → MM → Pair.

SmartBeta established the null point: a monthly, close-price rebalance on liquid
names barely diverges (faithful Sharpe −0.51 vs naive −0.35; band-lock no-fills
0 — the band effect never fires at daily resolution on liquid names, per the
Increment-2 audit). ProtoGrid is the **equity demonstrator**: a resting-limit
ladder at **tick resolution** that exercises the three effects SB cannot —
**admission** (a fixed ladder against a sliding daily band), **fill/queue** (many
resting rungs matched on the real tape and book, where band lock can finally be a
*proven* no-fill), and **T+2 recycling** (sell proceeds locked two days, so a
buy-back rung cannot self-fund). It is the first strategy for which the
Increment-2 band-lock book tier and the T+2 settlement model bite.

## 2. Thesis and pre-registered hypothesis

> Liquid VN30 equities oscillate enough, day to day, that a **cost-aware
> buy-low/sell-high limit grid** harvests the chop after real fees and sell tax.

**Falsifiable, pre-registered before the in-sample run, judged on the naive arm**
(the developer's default — so the strategy is a genuine alpha-seeker, not
loss-by-construction; the paper then measures the naive→faithful delta on top):

- **Kill if** in-sample **net Sharpe ≤ 0**, **or** net HPR ≤ 0, **or** fewer than
  **300 completed buy→sell round-trips**.
- A kill means these names do not oscillate harvestably at this spacing →
  reselect tickers (§5 criterion) or abandon Grid; it does **not** mean the
  faithful arm is allowed to be worse — that gap is the finding, not a failure.

This is set in `docs/hypothesis.md` at 9-step step 1, with the assumed costs
(§3) recorded as part of the pre-registration.

## 3. The grid mechanic

### 3a. Anchor and re-anchor
The logical ladder is **re-anchored monthly to the month-open reference price**
and held **fixed between re-anchors**. HOSE's daily band is `reference ± 7%`
where the reference is the prior session's close, so within a month the band
**slides** over the fixed ladder as the prior-close drifts. Monthly matches
SmartBeta's cadence, giving Grid-vs-SB a clean same-clock comparison and ~45
re-anchor episodes over the window.

### 3b. Spacing Δ (per ticker, from the *assumed* cost)
Spacing is in **absolute price-points**, not percent. Δ is the **smallest whole
number of tick-grid steps** (at the anchor price) whose net profit, after the
**naive developer's assumed static round-trip cost**, clears ~2× that cost — i.e.
`Δ ≥ 3 × assumed_round_trip_cost(anchor_price)`, snapped up to the tick grid, and
fixed for the month. The assumed round-trip cost is the flat estimate a developer
without a faithful simulator would use: brokerage ≈ 0.15% per side + 0.1% sell
tax ≈ **~0.4% round-trip** (recorded as a pre-registered assumption).

**Δ is a signal parameter shared by both arms** (same signals, swap the backend).
The naive arm both *sets* Δ from this assumed cost and *charges* it; the faithful
arm trades the identical Δ but applies **real dated VN charges** — exposing
round-trips that clear the assumed margin but not the real one. This is the grid's
Tier-2 cost-fidelity lever.

### 3c. Ladder and inventory model (classic paired grid, start flat)
- **8 buy rungs** below the anchor: `anchor−Δ, anchor−2Δ, …, anchor−8Δ`. With a
  cost-driven Δ (~1–1.6% for a mid-priced name) the span reaches ~±10–13%, so the
  outer 1–3 rungs sit **below the −7% floor at anchor** and become placeable only
  as the band slides down — the admission demonstration.
- **Start flat.** A filled buy at rung *k* places a **sell one step up** (at its
  fill price + Δ), realizing Δ gross per completed pair. When price falls back to
  *k*, the grid attempts to **re-buy** — and here the faithful arm stalls if the
  earlier sell's proceeds are still locked T+2, while the naive arm re-buys
  instantly. That divergence is the T+2 demonstration.
- Total inventory per grid is bounded by the funded rung count (§6).
- **Continuous across re-anchors (start flat once, at the run's start).** A
  monthly re-anchor recomputes only the *buy-rung price levels* for new buys around
  the new month-open; **held inventory and its paired sell orders persist** at their
  original levels — the grid is not force-flattened each month. (Decision point for
  review: the alternative is independent monthly episodes that liquidate residual
  inventory at each month-end — cleaner episodes and a regular month-boundary T+2
  hit, more directly SB-comparable, but less grid-realistic and higher turnover.
  The continuous rule is the default here; confirm or switch at review.)

### 3d. Admission dynamics this produces (the point of tick + fixed ladder)
- **BAND_LIMIT:** a buy rung priced below today's floor is an illegal price — the
  faithful arm cannot place it; it becomes placeable only when the sliding band
  reaches it. The naive arm places every rung always.
- **BAND_LOCK (fill-time, Increment 2):** on a limit-down day a placed buy rung at
  the floor rests but may not fill; at **tick resolution the book tier (B1–B3)
  observes the offer side directly**, so a genuine trắng-bên-mua rung is a
  **proven no-fill** — the effect that was ~empty at SB's daily resolution.
- **TICK_GRID / ROUND_LOT:** rungs snap to the dated tick grid and sizes to the
  100-share lot in the faithful arm; the naive arm uses raw prices and share
  counts.

## 4. The two arms

Both read the **same frozen tick slice** (§5) and run the **same grid signal
logic** through the `ExecutionBackend` interface built in Phase 0; only the
backend differs.

### 4a. Naive engine (ProtoGrid's own backtester — the developer default)
Newly written in the ProtoGrid repo (there is no prior engine to reuse, unlike
SB). It is the honest developer default and must reproduce its own committed
baseline (`plutus check` green under it): fills the **full ladder on any touch**,
**no** band clip, **no** lock, **no** tick-snap, **unlimited** queue/liquidity
(instant fill at the rung price), **instant cash** (no T+2), and the **static
assumed round-trip cost** of §3b.

### 4b. Faithful (`PlutusBackend` over `ExchangeSession` + `TickSource`)
The Phase-0 adapter, pointed at the tick source: the full admission gauntlet
(TICK_GRID → ROUND_LOT → BAND_LIMIT → FOREIGN_ROOM → SESSION_SEMANTICS, with
BAND_LOCK now a **fill-time** book/OHLC-graded decision), fills under the chosen
`FillPolicy` against the real tape + book (queue ambiguity → INDETERMINATE),
**T+2 settlement ON with sale-advance OFF** (so the T+2 stall is visible; a
sale-advance variant is optional, to show it mitigates), and **real dated VN
charges**. Headline policy = **`soft`** (comparable to SB); the **`soft` /
`hard` / `probabilistic` spread** is reported as a Tier-1 measure (this is where
`compare_policies` earns its place — tick resolution makes the divergence real).

## 5. Data and resolution

- **Tick resolution**, from the equity tick corpus (`stock_quote_12.2020-09.2024`
  / the archive `TickSource` reads), 2021-01 → 2024-09 (corpus end).
- **3 VN30 tickers**, selected by a **stated, reproducible criterion** computed
  from the corpus over the window: high **liquidity** (median daily matched
  volume — so the tick book is dense enough for the book tier), high **realized
  volatility** (so rungs trigger often), and **range-boundedness / mean-reversion**
  (high daily-range-to-net-drift ratio — so a grid, not a trend-follower, is the
  right tool). The three names emerge at 9-step step 2 and are recorded with their
  criterion values; the criterion, not the names, is the pre-registered choice.
- **Frozen slice shipped with the code**: the selected tickers' tick data for the
  window, converted to parquet, committed (small) or Drive-hosted (large, proto
  pattern) — the *sole* input to **both** arms, so the delta is purely execution.
- **IS = 2021-01 → 2023-08, OOS = 2023-09 → 2024-09** (~70/30 chronological). The
  split is fixed once, at step 2, and OOS is sealed until step 6.

## 6. Capital and sizing

**2 B VND** total, split equally across the 3 grids (~667 M each). Per-rung buy
notional ≈ `capital_per_grid ÷ 8 rungs` (~83 M), floored to a **100-share lot** at
the rung price, so every buy rung on a grid is fundable if the price walks all the
way down. Prices are in thousands of đồng; cash in đồng (`PRICE_SCALE = 1000`), as
in SB.

## 7. What ProtoGrid measures

- **Tier-1 (sign-free, large-n — the headline):** orders refused by cause
  (BAND_LIMIT out-of-band rungs; fill-time BAND_LOCK; TICK_GRID snap adjustments;
  ROUND_LOT), fill-policy divergence + indeterminate/FEL profile across
  soft/hard/probabilistic, and **T+2 stalls** — buy-backs the faithful arm could
  not self-fund on the day the naive arm did. The grid generates thousands of
  order events, exactly the large-n backbone the paper wants.
- **Tier-2 (punchline):** net realized P&L / Sharpe / MDD, naive vs faithful —
  including the cost-gap round-trips that cleared the assumed Δ margin but not the
  real dated charges.
- **Attribution:** which mechanism (admission / fill policy / queue / T+2 / cost)
  drove the gap, from the frozen diagnostic + Plutus provenance.
- **Spectrum point:** Grid's naive→faithful divergence, expected ≫ SB's ≈0, is
  the second point on the intensity-spectrum figure.

## 8. Repo layout and build order

New `proto/ProtoGrid`, scaffolded via the `9-step:*` skills and shaped like
ProtoSmartBeta (`src/proto_grid/`, `parameter/`, `tests/`, `pyproject.toml`,
`.plutus/` manifest):

1. **step 1 — hypothesis** (§2): thesis, kill criteria, assumed costs → `docs/hypothesis.md`.
2. **step 2 — data**: selection criterion → the 3 tickers; freeze the tick slice; fix the IS/OOS split.
3. **step 3 — rules**: the grid signal logic (anchor/re-anchor, Δ, paired-grid inventory) in one shared `strategy.py` both arms import.
4. **step 4 — in-sample**: the naive engine on IS; assert the kill criteria; instrument the metric bundle.
5. **step 5 — optimization**: sweep Δ-margin and rung-count on IS only, pick a stable region.
6. **step 6 — out-of-sample**: naive on OOS; realism audit.
7. **the seam**: `ExecutionBackend` + `PlutusBackend` (reuse Phase 0), a naive/faithful runner (like SB's `null_anchor.py`), both arms over the frozen slice → results into `experiments_registry.md`.

`plutus check` stays green under the naive backend (the behaviour-preserving gate
that keeps the naive number a real anchor). `proto/ProtoGrid` adds `plutus` as a
path/git dependency.

## 9. Open items and risks

- **Tick-run cost.** Three tickers × ~3.75 years of tick data is a heavy slice and
  slow runs. Mitigation: the frozen slice is per-ticker and only the selected 3;
  if runs are intractable, fall back to a focused tick window for the fill/book
  Tier-1 while keeping a daily pass for headline P&L (the hybrid the resolution
  question set aside — a documented fallback, not the plan).
- **Book density at tick.** The book tier needs a non-sparse offer ladder; the
  liquidity criterion (§5) is what protects it, but verify the selected names
  actually carry a dense enough `quote_askprice`/`quote_bidprice` ladder (sizes
  are 0-row corpus-wide, so the tier reads prices only — a known limit).
- **Range-boundedness is not guaranteed** over 2021 (bull) → 2022 (crash) → 2023–24
  (recovery); the monthly re-anchor is what keeps the ladder near price through
  the trend, but if a name trends hard within a month the grid stalls (few
  round-trips) — the kill criterion catches this.
- **Δ from assumed vs real cost** must stay a shared signal parameter (set from the
  assumed cost), or the naive-vs-faithful contrast stops being purely execution.
- **Behaviour-preserving gate** must hold for the newly written naive engine, or
  the naive anchor loses credibility.

## 10. Acceptance criteria

1. `proto/ProtoGrid` exists as a 9-step repo (hypothesis with kill criteria, data
   with the selection criterion + IS/OOS split, shared `strategy.py`, naive engine,
   `.plutus/` manifest); `plutus check` green under the naive backend.
2. The grid signal logic runs through the `ExecutionBackend` seam; naive and
   faithful arms read one identical frozen tick slice.
3. In-sample naive run is evaluated against the pre-registered kill criteria
   (net Sharpe > 0, net HPR > 0, ≥ 300 round-trips) before OOS is unsealed.
4. Faithful arm runs at tick resolution under `soft` (headline) with the
   `soft/hard/probabilistic` spread reported; T+2 on, sale-advance off.
5. Tier-1 (refusals by cause, fill-policy divergence, T+2 stalls), Tier-2 (net
   P&L/Sharpe/MDD naive vs faithful), and attribution emit into
   `experiments_registry.md` with provenance and a regenerating command.
6. The experiment reproduces from the shipped frozen slice with no live source.
7. Grid's divergence point is added to the intensity-spectrum data (SB → Grid).
