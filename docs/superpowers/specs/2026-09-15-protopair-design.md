# ProtoPair — the cross-market pair capstone (Phase 3) — design

**Date:** 2026-09-15 · **Status:** design draft, pre-implementation ·
**Repo:** new `proto/ProtoPair` (9-step) + `plutus` hub (shared seam, registry).

Companion to `docs/superpowers/specs/2026-09-08-plutus-strategy-experiments-design.md`
(the four-strategy intensity-spectrum design, of which this is **Phase 3, the
capstone — point 4, "all axes + settlement asymmetry"**),
`docs/superpowers/specs/2026-09-14-protogrid-design.md` (Phase 1, whose tick
band-lock and T+2 work ProtoPair inherits and cites),
`docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md` (the band-lock
book tier), and `docs/reference/tables/experiments_registry.md` (where its results
land). The concrete mechanics template is `validation/scenarios/pair-trade.py`
(the J4 basket-vs-future scenario). Decisions doc:
`scratchpad/protogrid/phase3-pair-decisions.md` (the 12 brainstorm questions +
recommended defaults; ★ items appear here as `DECISION-PENDING`).

**Binding framing (from memory `rivf26-fidelity-not-pnl`, non-negotiable):**
ProtoPair is an execution-fidelity **DEMONSTRATOR, not an alpha strategy**. The
headline is the naive↔faithful execution gap; **P&L is not reported** (Tier-2 at
most). The **proceed gate is activity + credibility, not Sharpe/HPR**;
**optimization is B-style** (cost-driven structural params kept, no P&L tuning);
**settlement asymmetry is the capstone headline**.

---

## 1. Motivation and role

The experiment upgrade contrasts each strategy's **naive backtest** against the
**faithful Plutus market** on the *same signals*, and measures the gap as a
function of execution intensity: SB (null anchor) → Grid → MM → **Pair**.

SmartBeta established the null point (faithful≈naive; band-lock no-fills 0 at
daily resolution). ProtoGrid added the equity tick demonstrator (admission,
fill/queue, T+2 recycling). MM added the derivatives demonstrator (dated margin,
maker queue, KRX cutover). **ProtoPair is the capstone: the only strategy that
lives in two markets at once**, and so the only one that exercises the axis no
single-venue strategy can — **settlement asymmetry**.

The two legs settle on **different clocks in segregated pools**: the equity leg
on HSX settles **T+2** in the securities pool; the futures leg on HNXDS settles
**daily variation margin in cash** in the derivatives pool. A profit on one leg
is not spendable to fund the other until its own cycle clears. A "market-neutral"
pair is therefore **not capital-neutral in time**. A naive single-ledger
backtest nets both legs' cash same-day and **never sees the gap** — which is
exactly the point. On top of that, ProtoPair inherits every lower-intensity axis:
equity admission (tick grid, 100-lot, band), the futures margin ladder
(call→cure→forced-close), T+2 recycling, and — uniquely — the **no-short-sale
asymmetry** that makes only one side of the basis trade executable, and the
**band-lock that breaks the hedge** (a locked equity constituent doesn't just
miss a fill, it desyncs the leg while the future keeps moving).

ProtoPair is a **pure plutus consumer** (two venues, two pools, dated margin, T+2
and settlement are all config-reachable axes Plutus already surfaces — the
template drives them today) **except the continuous→dated-contract roll**, which
has no plutus support and is strategy-side glue (§3e).

## 2. Thesis and pre-registered hypothesis

> VN30F1M and the VN30 basket are cointegrated; the **basis mean-reverts**; a
> desk trades the spread on the **executable (no-short) side** — long the basket,
> short the future when the future is rich — and the T+2/daily-VM settlement
> asymmetry, the no-short opportunity-set truncation, and the dated margin ladder
> decide what a real two-pool account can actually hold.

**Proceed gate — pre-registered before the in-sample run. NOT a P&L gate**
(ProtoPair is a demonstrator; per `rivf26-fidelity-not-pnl` the P&L kill from the
9-step alpha template does not fit and is not used as a stop). The gate is:

- **Credibility pre-check:** the in-sample basis is a *credible* mean-reverting
  vehicle — Engle-Granger / ADF stationarity on the daily basis at p < ~0.10, or
  a finite estimated half-life within the window.
- **Activity threshold:** the naive in-sample run generates **≥ ~20 completed
  pair round-trips** *and* hundreds of leg-level order events (fills + refusals +
  margin/settlement events), enough to exercise the execution axes the faithful
  contrast measures.

`DECISION-PENDING: exact activity numbers` — a pair is chunky (multi-day holds →
far fewer round-trips than Grid's 300, but each round-trip is ~60 equity + a few
futures order events, so the large-n Tier-1 backbone is ample). Numbers are fixed
at 9-step step 1 in `docs/hypothesis.md`, with the assumed costs (§3c) recorded as
part of the pre-registration, and are not loosened after seeing the result. P&L is
computed and reported truthfully as Tier-2 (§7), never as the headline or a gate.

## 3. The pair mechanic

### 3a. Basket construction and re-constitution
The long leg is an **equal-lot VN30 proxy basket** on HSX, read from
`quote_vn30.parquet` (the corpus carries the semi-annual review snapshots). Equal
*lots* is not equal weight, let alone the free-float cap weighting HOSE
publishes — the corpus has **no shares-outstanding data**, so the real weights are
not derivable (template documents R²≈0.98 to the index, ~5pp drift). The basket is
**re-constituted at each semi-annual VN30 review** (data-driven from the parquet),
not frozen: a 2022–2025 window crosses ~6 reviews and a frozen snapshot would
drift materially. The re-constitution turnover is itself extra T+2/admission
events. Nothing here claims the basket *hedges* the index; it claims the two legs
route, fund and charge correctly — a different, checkable question.

### 3b. Hedge ratio — `DECISION-PENDING: static IS-fitted β vs rolling`
Recommended default (spec written on it): a **static hedge ratio fitted once on
the in-sample window** (notional-match, or OLS of basket vs future returns), held
fixed out-of-sample, then **snapped to whole lots and whole contracts** for
execution. The snap is a fidelity axis, not a rounding convenience: the pair
cannot be lot-matched below three board lots of each name (template: 30×300 sh ≈
411.75M vs 4×98.5M ≈ 394M notional → a 1.045 ratio; one lot of each name is 1.39
contracts). Nothing in the codebase computes a hedge ratio today (the template
hard-codes 1.045). A **rolling-OLS / cointegration β** is the rejected
alternative — it adds look-ahead machinery and reads as P&L-chasing, which the
fidelity framing forbids; if the owner wants it, this section and the sizing
(§6) revise.

### 3c. The basis signal — `DECISION-PENDING: z-score entry/exit rule`
Recommended default (spec written on it): the signal is the **rolling z-score of
the basis**, `basis = VN30F1M_close − VN30INDEX_close`,
`z = (basis − mean_L) / std_L` over a lookback **L ≈ 60 sessions**. The index
level (`VN30`) is read from the same source the session reads, so strategy and
exchange cannot disagree about the market; it is a *level, not an instrument*, and
is never itself submitted (the basket is its executable proxy).

- **Entry:** when `z ≥ +z_in` (the future is rich vs the basket), enter the
  executable leg — long basket, short future — sized by §3b.
- **Exit:** when `z ≤ z_out` (basis reverts toward 0), or on a roll/expiry
  boundary (§3e), close both legs.
- **`z_in` is cost-driven, not Sharpe-tuned** (B-style): set so the expected
  reversion clears the modelled round-trip cost. The **assumed round-trip cost**
  (dated VN brokerage per side + sell tax on the equity leg, per-contract futures
  fees) is a signal parameter **shared by both arms** — the naive arm both sets
  `z_in` from it and charges it; the faithful arm trades the identical `z_in` but
  applies **real dated VN charges** (§4b). The template's entries are hardcoded
  dates (a fidelity unit test, not a rule); this live systematic rule is net-new
  strategy work and is what generates the activity the gate (§2) requires.

### 3d. The no-short-sale direction asymmetry (a headline structural finding)
There is **no operational stock short-selling in Vietnam**. When `z ≤ −z_in` (the
future is *cheap*), the textbook trade is long-future / short-basket — which does
not exist here: the equity short is refused (`UNSETTLED_HOLDING` / naked-short,
template `run_venue_rules`). So **only the future-rich side is executable**; the
mirror side is **sat out**, and the *count of refused/forgone mirror-side
signals* is reported as a Tier-1 opportunity-set-asymmetry measure (a rule
shaping the opportunity set, not a defect). The naive arm, which allows shorting,
takes both sides — and that divergence in *which signals even become trades* is
part of the gap.

### 3e. The continuous→dated-contract roll (the sole strategy-side glue)
Plutus has no roll support and the template never rolls. ProtoPair defines the
roll itself, **data-driven from `futurecontractcode_full.parquet`** (date →
`VN30F1M` → dated contract, e.g. `VN30F2106`): when the mapping's front-month
dated contract changes, that is a roll date. The strategy **closes the expiring
dated contract on its last session and opens the new front month next session**,
staying in F1M throughout (no pre-roll into F2M — the front-month basis stays
clean). This lives in the shared strategy module (§4) as pure glue over the
mapping, not in Plutus. **Optionally**, one roll may be carried to expiry to
strike the **CLOSE_PROXY** settlement (the futures daily `settlement` column is
NaN in the staged data → unusable → Plutus's `SettlementResolver` substitutes the
futures close, `SettlementSource.CLOSE_PROXY`, `substituted=True`): the template's
citable gap is **972.78 published (VSD final) vs 972.5 proxy** = 0.28 pt × 4 ×
100,000 = 112,000đ on a 4-lot short — a real, on-disk-oracle fidelity finding
incurred only by a leg carried to maturity.

### 3f. The settlement-asymmetry mechanic — `DECISION-PENDING: funding policy` (THE HEADLINE)
Two segregated pools under **one session, two venues** (`venues=['HSX','HNXDS']`,
routing per `(ticker, ts)`; the pool follows the venue and neither leg knows the
other exists):

- **Securities pool (equity leg):** sale proceeds settle **T+2**; a sold
  constituent's cash is not spendable until it clears (`SETTLEMENT_CREDIT`, and
  `Holding.sellable` gates re-use).
- **Derivatives pool (futures leg):** **daily variation margin settles in cash**
  from the deposit each session (`VARIATION_SETTLEMENT`); the mark moves the
  deposit day by day, not in one lump at close-out.

Because the pools are segregated, **an equity profit cannot meet a futures VM
call until it has settled T+2** — the capital-neutral-in-time failure. The
strategy funds the futures leg **on demand** and **abandons the pair rather than
half-filling it**: the first futures order into an empty deposit is refused, the
strategy reads `funded_in_aggregate` off the refusal and **transfers cash between
pools** to a target; if the pair cannot be funded even in aggregate, the equity
orders accepted moments earlier are **cancelled** (a naked basket is a different
trade). Recommended headline **funding policy: settled-cash-only (sale-advance
OFF)** so the stall is visible; a **sale-advance ON variant** shows it mitigates;
**"can't cure → forced-close is the finding"** is the third outcome. Mirrors
Grid's "T+2 on, sale-advance off."

The margin ladder on the futures leg is the template's, dated:
`IM = rate × |net| × 100,000 × price`, **rate 0.13 → 0.17 @ 2022-12-15**;
warning 0.80 / call 0.90 / forced-close 1.00; daily VM cash settlement;
call → cure-by-deadline → forced-close if unanswered.

## 4. The two arms

Both read the **same frozen data slice** (§5) and run the **same pair signal
logic** through a plutus-free shared strategy module (mirroring ProtoGrid's
`strategy.py`: pure, no I/O, emits **order intents** — basket buys/sells, futures
sells/buys, a hedge-ratio sizer, the z-score signal, the roll — that each arm
turns into its own backend's orders). Only the backend differs.

### 4a. Naive engine (ProtoPair's own backtester — the developer default)
Newly written in the ProtoPair repo (no prior engine to reuse). The honest
developer default: **one single ledger** (both legs' cash netted **same-day** —
no segregation, no T+2, no daily-VM clock), **shorting allowed on both sides**
(so it takes the mirror side §3d), **static margin**, frictionless fills on both
legs (fill-at-close / on-touch, unlimited liquidity), **no admission**
(tick/lot/band), and the **static assumed round-trip cost** of §3c. It must
reproduce its own committed baseline (`plutus check` green under it — the
behaviour-preserving gate that keeps the naive number a real anchor).

### 4b. Faithful (`PlutusBackend` over a two-venue `ExchangeSession`)
The reusable `plutus.execution.PlutusBackend` facade over `ExchangeSession`
(built `venues=['HSX','HNXDS']`, initial deposit staged by explicit `transfer`,
per the template's `build_scenario`). It applies: the full **admission gauntlet**
per venue (equity ROUND_LOT/TICK_GRID/BAND_LIMIT; futures lot-1/0.1-tick/band —
each leg judged by *its own* venue's rules), **fills under the chosen `FillPolicy`**
(headline `soft`, comparable to SB/Grid; the `soft`/`hard` spread reported), the
**dated margin ladder** (§3f) with real call/forced-close, **T+2 settlement ON,
sale-advance OFF** (headline), the **no-short refusal** on the mirror side, the
**segregated-pool routing + funding-on-demand/abandon** (§3f), **real dated VN
charges** per venue schedule (HSX `trade_value`; HNXDS `per_contract` — two bases,
two pools), and **CLOSE_PROXY** at any leg carried to expiry (§3e).

## 5. Data and resolution — `DECISION-PENDING: tick vs daily`

Recommended default (spec written on it): **daily-primary**.

- **Futures leg:** `VN30F1M`/`VN30F2M` **daily** OHLC + band + open-interest,
  **already staged** (`$ALGOTRADEDB_SLICE/vn30f1m_vn30f2m_daily.parquet`,
  2021-06 → 2026-09; `settlement` column NaN → CLOSE_PROXY, §3e), plus the roll
  mapping (`futurecontractcode_full.parquet`).
- **Equity leg / basket:** VN30 membership from `quote_vn30.parquet`; daily
  constituent closes/bands from the equity corpus (`stock_quote_12.2020-09.2024`,
  ≤2024-09). **Post-2024-09 equity daily needs a windowed algotradeDB freeze**
  (the MM/Pair DB phase; read-only cred at
  `$CRED_DIR/algotradeDB-readonly.json` — **never commit**).
- **Index level:** `VN30` daily closes (signal input, §3c).
- **Window:** **IS = 2022-01-01 → 2023-12-31, OOS = 2024-01-01 → 2025-06-30**
  (`DECISION-PENDING: Q7`), fixed once at step 2, OOS sealed until step 6. The
  window spans **IM 0.13→0.17 @ 2022-12-15** and crosses **KRX 2025-05-05** as a
  labeled dated-edition demo.

**Why daily, and the tick trade-off.** The capstone headline — settlement
asymmetry — is **structural and fully daily-expressible** (segregated pools + T+2
vs daily-VM; the template demonstrates the whole thing at daily). Across-KRX is
**only feasible at daily**: the equity tick corpus ends 2024-09, so a tick pair
cannot reach 2025-05-05. The tick-resolution "**band-lock desyncs the hedge**"
mechanism is **cited from ProtoGrid's already-measured tick band-lock** rather
than blocking ProtoPair on a fresh **futures tick/L2 freeze** (not staged; futures
L2 sizes only ≥2023-01-03). An **optional secondary tick arm** on a focused
sub-window (2023-01 → 2024-09, where futures L2 exists) can be added *only if* that
freeze is later done. **Known daily limitation:** the 09:30 margin mark uses the
same session's close (template finding 6) — a disclosed same-day look-ahead,
acceptable and labeled for a demonstrator.

**Frozen slice shipped with the code** (parquet, the sole input to **both** arms,
so the delta is purely execution): the basket constituents' daily tables, the
`VN30` index, the futures daily + roll mapping, for the window. Large slices via
Drive (proto pattern), small committed in-repo.

## 6. Capital and sizing

Two configs (mirroring the template's DEPOSIT_A vs DEPOSIT_B):

- **Comfortable** (headline settlement-asymmetry run): both pools funded so the
  futures leg never leaves `ok` on entry — isolates the pure T+2/segregation gap
  (cross-pool transfers, funding stalls) without margin-ladder noise.
- **Thin deposit** (Tier-1 margin demonstrator): the derivatives deposit is sized
  to breach, so the dated ladder is **exercised** — call→cure→forced-close on the
  futures leg — while the equity profit is locked T+2 and cannot cure it.

Securities cash opens with the basket notional; the **derivatives deposit opens
at zero** and every đồng it holds arrives by an explicit `transfer`, making the
segregation audit total (template invariant). Scale ≈ template proportions
(basket ~400M, thin deposit ~60M) or up to a round figure; prices in thousands of
đồng, cash in đồng (`PRICE_SCALE = 1000`, as SB/Grid; futures multiplier 100,000
đồng/point). `DECISION-PENDING: exact đồng figures` — confirm before the faithful
run, as SB/MM did.

## 7. What ProtoPair measures

- **Tier-1 (sign-free, large-n — the headline), settlement asymmetry leading:**
  **cross-pool transfer count + magnitude** and **funding-stall incidence**
  (a futures VM call the equity leg's profit could not meet because it was locked
  T+2 — the naive arm nets it same-day); **`funded_in_aggregate` true/false** and
  **pair-abandonment** events; **margin call / forced-close incidence** on the
  futures leg (thin config); **CLOSE_PROXY substitution** at any expiry-carried
  leg; **orders refused by cause** per venue (no-short mirror-side count, equity
  ROUND_LOT/TICK_GRID/BAND_LIMIT, futures tick/band); **fill-policy divergence**
  (`soft` vs `hard`, indeterminate/FEL profile); and the **opportunity-set
  asymmetry** (executable vs forgone mirror-side signals). Plutus reports only
  fills / cash / margin — exactly this tier.
- **Tier-2 (consequence, not headline):** realized P&L / Sharpe / MDD, naive vs
  faithful, computed by the caller's harness at **daily** granularity, reported
  truthfully and framed as the downstream effect of the named mechanisms. **May be
  omitted from the paper entirely** (per fidelity-not-pnl).
- **Attribution:** which mechanism (settlement asymmetry / segregation / no-short
  / dated margin / admission / fill policy) drove the gap, from the frozen
  diagnostic + Plutus provenance.
- **Spectrum point:** ProtoPair's naive→faithful divergence is the **top** point
  of the intensity-spectrum figure (SB≈0 → Grid → MM → **Pair**), the capstone
  the whole design builds toward.

## 8. Repo layout and build order

New `proto/ProtoPair`, scaffolded via the `9-step:*` skills and shaped like
`ProtoGrid`/`ProtoSmartBeta` (`src/proto_pair/`, `parameter/`, `tests/`,
`pyproject.toml`, `.plutus/` manifest; `plutus` as an editable path dep on the
sibling repo; console scripts `pp-select` / `pp-extract` / `pp-backtest` /
`pp-optimize` / `pp-evaluate`, mirroring Grid's `pg-*`):

1. **step 1 — hypothesis** (§2): cointegration thesis, the **activity+credibility
   proceed gate** (explicitly *not* a P&L kill), assumed costs → `docs/hypothesis.md`.
2. **step 2 — data**: freeze the daily slice (basket + `VN30` + futures + roll
   mapping); the algotradeDB freeze for post-2024-09 equity; fix the IS/OOS split;
   run the credibility pre-check (basis stationarity/half-life) → `docs/data.md`.
3. **step 3 — rules**: the pair signal logic (basis z-score §3c, hedge sizer §3b,
   no-short direction filter §3d, the roll §3e, funding-on-demand/abandon §3f) in
   one shared plutus-free `strategy.py` both arms import.
4. **step 4 — in-sample**: the naive engine on IS; assert the **activity gate**
   (not a P&L kill); instrument the metric bundle.
5. **step 5 — optimization**: **B-style** — sweep `z_in` (cost-driven) and hedge
   sizing on IS only, pick a **representative** cell, report ACTIVITY not Sharpe.
6. **step 6 — out-of-sample**: naive on OOS; realism audit.
7. **the seam**: drive `PlutusBackend` over the two-venue `ExchangeSession`; a
   naive/faithful runner (like SB's `null_anchor.py`), both arms over the frozen
   slice → results into `experiments_registry.md`.

`plutus check` stays green under the naive backend (the behaviour-preserving
gate). ProtoPair adds `plutus` as a path/git dependency; the **only** plutus-side
consideration is confirming `PlutusBackend`/`ExchangeSession` expose the cross-pool
`transfer` + `cancel` the funding-on-demand/abandon loop needs (the template drives
them today, so this is a check, not new plutus work).

## 9. Open items and risks

- **★ Tick vs daily (§5) and the KRX window (§7) are entangled.** Daily buys
  across-KRX + the whole headline but forfeits a *fresh* tick band-lock-desyncs-hedge
  measurement (cited from Grid instead). A tick pair would need a futures tick/L2
  freeze and could not cross KRX. Owner call.
- **★ The signal rule (§3c) and hedge ratio (§3b) are net-new** with no codebase
  precedent; a wrong default is real strategy.py + sizing rework. Owner call.
- **algotradeDB freeze for post-2024-09 equity + the futures leg.** Read-only
  cred, gitignored, **never committed**; convert selectively (fields × tickers ×
  dates), never the whole corpus.
- **Corporate actions over a multi-month hold (§Q12).** Relies on plutus's dated
  corporate-action/charge handling for 30 names (`corporate.py`; the
  `vsdc_custody_equity` monthly custody fee, template finding 11); verify coverage
  over the window rather than restricting the basket.
- **Basket ≠ index.** The equal-lot proxy drifts ~5pp; the claim is routing /
  funding / charging fidelity, not tracking. State it, don't hide it.
- **Roll is strategy-side and unsupported by plutus** — the one place ProtoPair is
  not a pure consumer; keep it isolated in `strategy.py` and data-driven off the
  mapping table so it is auditable.
- **Behaviour-preserving gate** must hold for the newly written naive engine, or
  the naive anchor loses credibility.
- **Same-day margin mark at daily resolution** (template finding 6) — disclosed
  look-ahead; label it, don't present a 09:30-timestamped margin event as intraday.

## 10. Acceptance criteria

1. `proto/ProtoPair` exists as a 9-step repo (hypothesis with the **activity +
   credibility** proceed gate — not a P&L kill; data with the frozen slice, the
   credibility pre-check, and the IS/OOS split; shared plutus-free `strategy.py`;
   naive engine; `.plutus/` manifest); `plutus check` green under the naive backend.
2. The pair signal logic runs through `PlutusBackend` over a two-venue
   (`['HSX','HNXDS']`) `ExchangeSession`; naive and faithful arms read one
   identical frozen slice.
3. In-sample naive run is evaluated against the pre-registered **activity +
   credibility** gate before OOS is unsealed; **no Sharpe/HPR stop-gate** is used.
4. Faithful arm runs under `soft` (headline) with the `soft`/`hard` spread
   reported; **T+2 on, sale-advance off** (headline), with a sale-advance variant;
   dated margin ladder (0.13→0.17) exercised in the thin config.
5. **Settlement-asymmetry Tier-1 measures lead** (cross-pool transfers, funding
   stalls, `funded_in_aggregate`/abandonment, margin/forced-close, CLOSE_PROXY,
   no-short opportunity-set asymmetry, refusals by cause, fill-policy divergence);
   Tier-2 P&L (naive vs faithful, daily) reported truthfully as consequence or
   omitted; attribution emits into `experiments_registry.md` with provenance and a
   regenerating command.
6. Optimization is **B-style** (cost-driven `z_in` + hedge sizing swept for the
   artifact, representative cell picked, ACTIVITY reported — no P&L objective).
7. The experiment reproduces from the shipped frozen slice with no live source.
8. ProtoPair's divergence point is added to the intensity-spectrum data as the
   **top** point (SB → Grid → MM → **Pair**).
