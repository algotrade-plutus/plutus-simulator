# BAND_LOCK as an evidence-graded fillability check — design

**Date:** 2026-09-10 · **Status:** design in progress (Section 1 approved; Sections 2–4 pending).
**Approach:** A — a dedicated `BandLockResolver` consulted in the fill phase (chosen over folding lock logic into each `FillPolicy`).

## Why this change

Today BAND_LOCK is **admission rule #4** in `EquityExchange.admits()` ([equity.py:104](../../../src/plutus/market/exchanges/equity.py)) and **hard-refuses** a marketable order into a locked band. That is **incorrect per Vietnamese market regulation**: a legal-priced buy at the ceiling on a limit-up day is a *valid order* — it rests in the queue and simply may not fill. Rejecting it at admission also violates the paper's own §IV philosophy ("*when the data cannot establish whether a resting order filled, that is an event on the order and the order stays resting rather than becoming terminal*").

Additionally the daily lock **detection over-asserts ~10×**: it infers a lock from `close == ceiling` alone, but on the SB universe in 2022, of 12,415 proxy buy-locks only 3,856 (31%) were true full-session locks; 8,559 **traded through** the band (a buyer clearly *could* have obtained shares) and 2,430 ATO-only locks were **missed**.

## Decided requirements (confirmed with the owner)

1. **BAND_LOCK moves out of admission into fill determination.** Admission keeps only **BAND_LIMIT** (a price beyond the band is a genuine rule — you cannot place it). A band-locked order is **Accepted and rests**; the fill step decides its fate as an *event*, never an admission rejection.
2. **Fill policies (hard / soft / probabilistic) apply in the auctions (ATO / ATC) too**, not only continuous. Normally auctions fill at the published open/close; in the locked-at-the-band edge case the policy decides.
3. **The lock is FEL-graded** (`PROVEN` / `ASSUMED` / `UNEVIDENCED`), resolved by a **best-available-evidence ladder**: observed ask/bid book where the tick feed is dense → daily OHLC + volume → otherwise INDETERMINATE. (Volume signal ladder: tick/matched where present → `quote_dailyvolume` → UNKNOWN.)
4. **Audit at the end:** after implementation, show the owner concrete ticker-day cases running through the ladder for a final correctness check.

---

## Section 1 — The `BandLockResolver` contract and FEL mapping  *(APPROVED)*

**What it does.** A pure function of `(order, MarketState)` — no session state — that answers *"would this order have obtained shares at ≤ its limit (buy) / ≥ its limit (sell) this phase?"* and returns a `FillDecision` already graded by FEL. Being pure, every row below is an isolated unit test (and the end-of-implementation audit).

**When it engages (precondition).** Only when the order must transact **at the locked band edge**:
- a **BUY** that is marketable into the ceiling — a market/ATO/ATC buy, or a limit buy priced **≥ ceiling**;
- a **SELL** that is marketable into the floor — a market/ATO/ATC sell, or a limit sell priced **≤ floor**.

A limit buy priced **below** the ceiling, or a limit sell **above** the floor, is **never a lock question** — it fills iff the session traded to it (`low ≤ limit` for a buy, `high ≥ limit` for a sell), the ordinary fill path. The resolver returns "not applicable" and the normal fill logic runs.

### 1a. BUY into a limit-**up** (ceiling) situation  *(reconciled 2026-09-14 for option B — see note after 1b)*

| # | Evidence tier | Condition | Outcome | FEL |
|---|---|---|---|---|
| B1 | Observed ask book (dense tick) | an ask rests **below** the ceiling | **FILL** at ≤ ceiling | `PROVEN` (TICK_BOOK) |
| B2 | Observed ask book | all asks ≥ ceiling (or none), bid at ceiling, **volume > 0** | **policy decides** | `ASSUMED` |
| B3 | Observed ask book | …same, **volume == 0 or absent** | **NO-FILL** (trắng bên bán) | `PROVEN` |
| B4 | Daily OHLC + volume | session traded below the cap (`low < ceiling`) | **FILL** at ≤ ceiling | `PROVEN` |
| B5 | Daily OHLC + volume | bar collapsed on the cap (`open==high==low==close==ceiling`), **volume == 0 or absent** | **NO-FILL** | `PROVEN` |
| B6 | Daily OHLC + volume | bar collapsed on the cap, **volume > 0** | **policy decides** | `ASSUMED` |
| B7 | Daily OHLC, absent | the phase-appropriate instant itself is absent (no `low`/`open`/`close` to test against the cap) | **INDETERMINATE** | `UNEVIDENCED` |

### 1b. SELL into a limit-**down** (floor) situation  *(the exact mirror)*

| # | Evidence tier | Condition | Outcome | FEL |
|---|---|---|---|---|
| S1 | Observed bid book (dense tick) | a bid rests **above** the floor | **FILL** at ≥ floor | `PROVEN` (TICK_BOOK) |
| S2 | Observed bid book | all bids ≤ floor (or none), ask at floor, **volume > 0** | **policy decides** | `ASSUMED` |
| S3 | Observed bid book | …same, **volume == 0 or absent** | **NO-FILL** (trắng bên mua) | `PROVEN` |
| S4 | Daily OHLC + volume | session traded above the floor (`high > floor`) | **FILL** at ≥ floor | `PROVEN` |
| S5 | Daily OHLC + volume | bar collapsed on the floor (`open==high==low==close==floor`), **volume == 0 or absent** | **NO-FILL** | `PROVEN` |
| S6 | Daily OHLC + volume | bar collapsed on the floor, **volume > 0** | **policy decides** | `ASSUMED` |
| S7 | Daily OHLC, absent | the phase-appropriate instant itself is absent (no `high`/`open`/`close` to test against the floor) | **INDETERMINATE** | `UNEVIDENCED` |

**Option B reconciliation (owner decision, 2026-09-11).** Rows B3/S3 and B5/S5 above read "volume == 0 or absent" because the shipped resolver treats a **zero or absent** `quote_dailyvolume` identically as the no-trade fact, not as two different things: the corpus never stores a literal `volume == 0` row (confirmed in the §4d audit: `MIN(quantity)=1` over 2,562,664 rows) — a day with nothing matched is simply **absent** from the table. The owner's call was that this is not evidence-starvation: once the bar has already collapsed to the edge (`open==high==low==close==band`, or the book is entirely at/past it), the collapse *is* the evidence that nothing moved the price, so an absent volume row on that bar is the no-trade fact itself, not ignorance about it — hence `NO_FILL`, not `INDETERMINATE`. `INDETERMINATE` (rows B7/S7) is reserved for a narrower failure than "volume unknown": it now fires only when the **phase-appropriate instant itself** is absent — no `low`/`high` for a continuous order, no `open` for an ATO, no `close` for an ATC — i.e. there is no price at all to test against the edge, before volume ever enters the question.

### 1c. How the `ASSUMED` tier (B2/B6, S2/S6) resolves — the policy floor

The resolver hands the `ASSUMED` rows to the **active `FillPolicy`**, reusing the existing policy-as-floor semantics unchanged ([evidence_level.py](../../../src/plutus/market/session/evidence_level.py) — "*a fill policy is a rule for the lowest FEL it acts on*"):

| Policy | Behaviour on an `ASSUMED` band-lock |
|---|---|
| `hard` | **INDETERMINATE** — refuses to assume it was in the matched set |
| `soft` | **FILL** at the band edge — assumes favourable queue position |
| `probabilistic` | **FILL with probability *p*** (seeded) — the modelled middle |

The two `PROVEN` ends (fill / no-fill) and `UNEVIDENCED` are policy-independent — the data settles them, so every policy returns the same outcome there. Only the genuine assumption (matching happened, but was *your* order in it?) is policy-dependent.

### 1d. Properties this guarantees

- **Symmetry:** buy-into-ceiling and sell-into-floor are mirror images (tables 1a/1b), so the model has no directional bias.
- **Phase-agnostic core, phase-specific evidence:** the same resolver serves continuous and auction fills, but *which instant's* price is tested against the band differs by phase (§3c). Rows B4–B6 / S4–S6 above are the **continuous / marketable** reading (whole-session `low`/`high` and the full collapse). An **ATO / ATC** order instead tests the open / close specifically — so an **ATC buy on a Case-B day** (traded through mid-day, closed at the cap) *is* a lock question for the ATC, even though a **continuous** buy the same day fills (`low < ceiling`). The two are not in conflict; they apply to different order types.
- **Output type is the existing `FillDecision`** with its FEL grade — no new result type, and it flows through `indeterminate_report()` / the FEL distribution the paper already reports.
- **A definite miss is `PROVEN`, not a failure** (B3/B5, S3/S5): the data settled "no fill" as firmly as it settles a fill — consistent with `fill_evidence_level()`'s existing treatment of NO_FILL as PROVEN.

---

## Section 2 — `MarketState` / adapter evidence enrichment  *(APPROVED; reconciled 2026-09-14 — see note)*

The resolver derives the lock from **raw facts**, so adapters supply *facts, not verdicts* — the intelligence lives in one place. This section originally proposed that `MarketState` gain additive `Optional` fields (backward-compatible on the frozen dataclass) to carry them:

> **Reconciliation (2026-09-14, Increment 2 shipped).** That proposal was not implemented, and did not need to be. By the time Increment 2 landed, `MarketInterval` ([session/types.py](../../../src/plutus/market/session/types.py)) already had its own `open`/`high`/`low`/`close`/`volume`/`book` fields — added independently, for the participation-cap seam — and `DataHubSource.interval()` ([adapters/datahub.py](../../../src/plutus/market/adapters/datahub.py)) already populated them (`_ohlc()` for open/high/low, the `quote_dailyvolume` join for volume; commit `e1450de`, 2026-08-30, predating this design). `band_lock_decision(order, interval)` ([session/fills.py](../../../src/plutus/market/session/fills.py)) reads them off the **interval** it is handed, never off `MarketState`. `MarketInterval`'s own docstring says why its `state` field is carried whole rather than unpacked: "the band, the lock and its evidence, the session phase and the foreign room all live there already, and copying them here would create a second copy that can drift." Adding open/high/low/volume onto `MarketState` too, as first proposed below, would have created exactly that second, driftable copy. `locked_side` / `lock_evidence` (including `LockEvidence.BAR_PROXY`) stay on `MarketState` exactly as the table below describes — `derivatives.py`'s `_exit_blocked` (an unrelated stop-loss exit-block check) and the `tick.py`/`datahub.py` adapter tests still read them — the resolver simply never consults either field. Net: **no change to `MarketState`, `datahub.py`, `tick.py`, or `derivatives.py`**; acceptance criterion 4 below ("`MarketState` carries open/high/low/volume") is satisfied via `MarketInterval` instead — see the annotation there. The table and the "Adapters" note below are corrected in place to say so; nothing else about this section's reasoning changes.

| Field | Source | Role |
|---|---|---|
| `open` *(on `MarketInterval`, not `MarketState`)* | `quote_open` | part of the full collapse test |
| `high` *(on `MarketInterval`)* | `quote_max` (session high) | traded-through test for a **sell** (`high > floor`) |
| `low` *(on `MarketInterval`)* | `quote_min` (session low) | traded-through test for a **buy** (`low < ceiling`) |
| `volume` *(on `MarketInterval`)* | `quote_dailyvolume` | splits `PROVEN no-fill` from `ASSUMED` at a collapsed edge (see §1 for the exact zero-or-absent boundary) |
| `book` *(present, on `MarketState`; `MarketInterval.book` also carries a tick-resolution copy)* | tick ask/bid ladder | the dense-book tier (B1–B3 / S1–S3) |
| `ceiling`, `floor` *(present, on `MarketState`, read via `interval.state`)* | bands | the band edges the order transacts against |
| `last` (**close**) *(present, on `MarketState`, read via `interval.state`; also `MarketInterval.close`)* | `quote_close` | the **fill-price reference** for a filled outcome, and the price a "at-close" order carries |

**Close is retained** (`last`) and used as the fill price; open/high/low/volume are the interval's own fields, not new `MarketState` fields. Note the collapse test `open==high==low==close==band` reduces to `high==low==band` (the range collapsed to a point implies open/close pinned there), so close isn't required to *detect* the collapse — but it stays as the fill-price reference.

**Adapters, as shipped:** `datahub.py`'s `DataHubSource.interval()` fetches open/high/low via `_ohlc()` (originally added for the F2 fix, commit `e1450de`) and the `quote_dailyvolume` join, and writes them onto the returned `MarketInterval` — no new data, only the container this section originally proposed for `MarketState`. `tick.py` continues to supply `book` on `MarketState`; the resolver reads `interval.book` first and falls back to `interval.state.book` (`fills.band_lock_decision`), so either adapter's placement works.

**Availability (from the data probe), which the ladder degrades over gracefully:** daily OHLC+volume+bands are robust for **every** name → the daily tier always has its inputs; the tick **book is sparse for exactly the thin names that lock** → the book tier is often absent, so the resolver *falls to the daily tier*, not to UNKNOWN. UNKNOWN (B7/S7) is reserved for the genuinely dark case (no book **and** no OHLC — e.g. a data gap).

**Deliberate coarsening (surfaced in the audit):** `volume` is the *session-daily* figure, so "volume > 0" means *something* matched that day, not necessarily at the band; auction/price-specific volume is the dense-tier refinement, used where present (the Option-1 ladder).

## Section 3 — Admission drop + continuous & auction fill wiring  *(APPROVED)*

**(a) Admission drops BAND_LOCK.** `EquityExchange.admits()` gauntlet becomes TICK_GRID → ROUND_LOT → **BAND_LIMIT** → FOREIGN_ROOM → SESSION_SEMANTICS. A legal-priced order into a locked band is **Accepted and rests**. BAND_LIMIT (price beyond the band) stays.

**(b) The resolver is consulted in the fill phase.** `_evaluate_fills(ts)` ([exchange.py:1462](../../../src/plutus/market/session/exchange.py)) calls the fill policy per live order; the resolver slots in as a **pre-step**: order not at the band edge → "not applicable", ordinary fill path runs unchanged; at the band edge → the resolver's `FillDecision` is the outcome, deferring only `ASSUMED` to the policy. One integration point; non-band orders unaffected.

**(c) Phase decides which instant's collapse to test (the ATO/ATC answer):**

| Order / phase | Buy-side locked ⟺ (sell mirrors) | Rationale |
|---|---|---|
| **ATO** | `open == ceiling` **and** no ask-below / opening-volume evidence | an ATO only sees the opening auction — the *open* is its moment |
| **ATC** | `last(close) == ceiling` **and** no ask-below / closing-volume evidence | an ATC only sees the closing auction — the *close* is its moment |
| **Continuous / marketable** | `high == low == ceiling` (traded only at the cap all session) | a resting order had the whole session; locked only if the cap never lifted (`low < ceiling` ⇒ fills) |

So an ATO buy on a name that opened locked but fell (Case D) is correctly no-fill for the ATO, while a *continuous* buy the same day fills — the daily proxy conflated these.

**(d) Auction fills become policy-aware.** `auction_fill_price` ([fills.py:608](../../../src/plutus/market/session/fills.py)) still gives the published open/close for a clean cross (`PROVEN` fill); a **locked** auction routes through the resolver — `PROVEN no-fill` (no volume) or `ASSUMED` → policy (`hard` refuses, `soft` fills at the cap, `probabilistic` = p).

**Two-increment landing.** **Increment 1** — drop BAND_LOCK from admission + a minimal resolver reusing today's `close==band` evidence in the continuous path (pure correctness fix; order rests + no-fill/indeterminate event; scenarios re-greened). **Increment 2** — phase-aware collapse test + OHLC/volume/book evidence ladder + auction policy-awareness.

## Section 4 — Testing, re-runs, the audit, and sequencing  *(APPROVED)*

**(a) The resolver's purity makes verification exhaustive.** Each of the 14 rows (B1–B7, S1–S7) is one unit test against a hand-built `MarketState`, plus the `ASSUMED` tier × 3 policies (hard/soft/probabilistic floor behavior). This table *is* the test matrix and the audit's case set.

**(b) Scenario rewrites — the contract change is the audit.** J2 and J11 flip from `Rejected(BAND_LOCK)` at admission to **`Accepted` + rests + a fill *event*** (no-fill on a true full-session lock; fill if it traded through), keeping their QĐ 352 Điều 9 citations. Grep every test asserting BAND_LOCK-at-admission and update it; check the auction scenarios (J7/J14/S4) exercise the new ATO/ATC policy path.

**(c) Experiment re-runs — SB becomes a validation of the fix.** The SB null-anchor regenerates: most of its **45 BAND_LOCK refusals should become fills** (those names traded through), so the faithful arm moves **toward** naive — a shrinking gap is direct evidence the fix works. E1 regenerates if it touches band-lock. `experiments_registry.md` gets the before/after with a note.

**(d) End-of-implementation audit — measured result (owner-signed-off 2026-09-14).** The committed script `measurements/band_lock_ladder_audit.py` and its output snapshot `measurements/band_lock_ladder_audit_output.txt` went beyond printing the handful of hypothetical cases this section originally named — they scanned the **full corpus** for every genuine full-session collapse and counted how the ladder actually resolves them:

- **Buy-side (ceiling) collapses**, `open==high==low==close==ceiling`, 2021-02-05..2022-12-30: **8,611** candidates. **8,610 (99.99%)** carry positive `quote_dailyvolume` → the **ASSUMED** tier (passthrough → the policy floor decides); **1 (0.01%)** has absent volume → the proven `NO_FILL`. Literal `volume == 0`: **0** across the corpus (confirmed `MIN(quantity)=1` over 2,562,664 rows) — the fact the §1 option-B reconciliation above is built on.
- **Sell-side (floor) collapses:** 5,535 candidates, **183 absent-volume — all the same single ticker, PTG**. **ATO-only locks** (`open==ceiling`): 15,903 candidates, **1 absent — the same PTG day**.
- The one proven-`NO_FILL` name, **PTG** (2021-02-17 buy, 2021-05-28 sell), is a dormant UPCOM penny stock with almost no recorded trading history — not a name squeezed to its limit by real buying/selling pressure. Both the continuous and ATO rungs resolve it to `NO_FILL`, exactly as the ladder predicts.
- **The over-assertion fix, verified:** DMN 2022-01-06 closed at its ceiling (`close==ceiling`) but traded up from 12.7 intraday (`low < ceiling`) — a genuine traded-through day. Increment 1's `close==band` proxy called this a lock; the shipped ladder correctly resolves it to passthrough (the policy fills).
- **The daily-volume coarsening, on the ATO instant:** NXT 2022-01-27 is a real ATO-lock candidate (`open==ceiling`), but its whole-day volume (4,900) is positive because the price fell later in continuous trading — the daily volume field cannot separate "the opening cross traded" from "the afternoon traded." The ATO test correctly lands on ASSUMED/passthrough per the ladder, not `NO_FILL` — the naive expectation that an ATO-lock candidate must be a no-fill is exactly what the audit corrects.
- **The data-gap case:** CFPT2010 2021-02-17 (an FPT covered warrant) closed at its ceiling but carries no session `LOW` at all → `INDETERMINATE`, the B7 rung.
- **The design's originally-named case was wrong.** This section originally named DAN 2022-01-04 as the true-lock example; the audit found DAN's real bar is a collapse on the UPCOM board with `volume=1800` (the `ASSUMED` tier), not a proven lock — verified independently twice (the Task 2 scenario-fixture work and this task's corpus scan). It has been replaced above by PTG, the corpus's only genuine proven no-fill.

**No resolver bug was found. Every verdict matches the §1 ladder exactly** — the audit's role turned out to be less "catch a bug" and more "measure how empty the `PROVEN` no-fill rung actually is on this corpus" (§4e).

**(e) Paper impact — reframed to the measured reality (2026-09-14).** At **daily** resolution a band lock is **ASSUMED-dominant, not proven-no-fill-dominant**: §4d's corpus scan puts ≈99.99% of real full-session collapses in the `ASSUMED` tier, where the fill is **policy-dependent** (`soft` fills at the edge, `hard` returns `INDETERMINATE`, `probabilistic` draws) rather than settled by the data. A *proven* band-lock no-fill at daily resolution is the empirically near-empty residual (1 name, PTG, out of 8,611 candidates) — establishing it takes the tick/auction-volume evidence the daily corpus mostly lacks, not just a collapsed bar.

So §IV's "the band that **refuses the fill**" demonstration is honestly a **tick-resolution phenomenon**, specific to the phases that carry a dense order book (Grid, Pair) whose B1–B3/S1–S3 book tier can observe the empty offer/bid side directly — **not an SB (daily, monthly-rebalance) finding**. This is consistent with, not contradicted by, the SB null-anchor's own measurement: `band_lock_no_fills = 0` out of 49 candidates the OOS run touched (`experiments_registry.md`, SB block, with a cross-reference to this audit) — under `soft`, every one of SB's daily band-lock candidates resolved to a fill, exactly as "daily ⟹ ASSUMED-dominant ⟹ soft fills" predicts.

What stands from the original framing: §IV documents band-lock as an FEL-graded *fillability* outcome, never an admission rejection — the ~10x admission-time over-assertion this design opened with ("Why this change") is fixed and quantified in §4d; the FEL distribution already reported now includes fill-time band-lock; "the band that refuses the **entry**" → "the band that refuses the **fill**" stands as the paper's framing shift; and threats-to-validity keeps the session-daily volume coarsening note — surfaced concretely by the NXT 2022-01-27 ATO case (§4d): the daily volume figure cannot isolate a single auction instant from the rest of the session, which is why the *proven* rung needs tick resolution to be more than a rounding error.

**(f) Sequencing.** Lands on plutus `rivf-2026` **before Phase 1 (ProtoGrid)** — a grid is a ladder of resting limit orders that hits band locks constantly, so Grid depends on correct band-lock fillability; fixing the core first means Grid measures a real effect, not an over-assertion artifact.

---

## Acceptance criteria

1. `BandLockResolver` exists as a pure `(order, MarketState) -> FillDecision|NotApplicable`, with all 14 rows unit-tested and the ASSUMED×3-policy behavior tested.

   **Met (full ladder), Increment 2 — 2026-09-14.** Shipped as `band_lock_decision(order: OrderRecord, interval: MarketInterval) -> Optional[FillDecision]` (`session/fills.py`) — the resolver takes the **interval**, not `MarketState` (see the §2 reconciliation); "NotApplicable" is `None`. All 14 rows are unit-tested across three commits: the daily tier B4–B7/S4–S7 (`c9c4c06`, amended for option B by `e57ee2c`), the dense-book tier B1–B3/S1–S3 (`c000312`, `2e97e2f`), and the `ASSUMED`×3-policy floor end-to-end (`64a5d00`).
2. `admits()` no longer contains BAND_LOCK; a marketable order into a locked band is `Accepted` and rests.
3. Continuous fills route band-edge orders through the resolver; non-band orders are byte-for-byte unaffected (existing fill tests green).
4. `MarketState` carries open/high/low/volume; the daily adapter populates them.

   **Met — via `MarketInterval`, not `MarketState`.** `MarketInterval` already carried and populated these fields before this design was written (`e1450de`, 2026-08-30, the F2/E1 blocker fix); Increment 2 built the resolver on that existing seam instead of duplicating the fields onto `MarketState`, which is unchanged. See the §2 reconciliation note.
5. ATO/ATC orders resolve against the phase-appropriate instant, and locked auctions are policy-aware.

   **Met, Increment 2 — `c9c4c06`.** Same commit as criterion 1: `_lock_instant` selects `open`/`close`/`low`/`high` by `interval.session`, and `BaseFillPolicy._dispatch`'s `AUCTION_ONLY` branch now calls `band_lock_decision` before `_auction(...)` — a locked auction gets the same per-policy (soft/hard/probabilistic) treatment that criterion 1's `ASSUMED`×3-policy tests (`64a5d00`) prove end-to-end for the continuous path.
6. J2/J11 (and any other BAND_LOCK-admission assertions) rewritten to the new contract and green; the market/scenario/strategy suites otherwise stay green.
7. SB null-anchor regenerated (faithful gap shrinks); `experiments_registry.md` updated with before/after.

   **Met, Increment 2 — 2026-09-14.** Registry updated in `plutus` (`e74c0f2`, addended by `da369ff`); the runner recount landed in the sibling `proto/ProtoSmartBeta` repo (`371e68b`, `b520187`). Faithful Sharpe moved from −0.5543 (Increment 1) to −0.5093, narrowing the gap to naive's −0.3497; fill-time band-lock no-fills went 45 → 0 (registry SB block, which this Task 7 commit also cross-references to the §4d audit).
8. The audit script prints the per-rung cases for owner sign-off.

   **Met, Increment 2 — `6bfdc53`, owner-signed-off 2026-09-14.** `measurements/band_lock_ladder_audit.py` (Task 6) prints per-case raw evidence → tier → outcome; the corpus-wide measurement it enabled is recorded in §4d above, with the run snapshotted at `measurements/band_lock_ladder_audit_output.txt` (this commit).

**Increment split for the plan:** Increment 1 = criteria 1(minimal, close==band evidence only)+2+3+6 (the correctness fix). Increment 2 = criteria 1(full ladder)+4+5+7+8 (evidence ladder + auctions + audit). **Increment 2 status (2026-09-14): all five closed** — see the per-criterion notes above; §4d/§4e carry the audit finding this closure rests on.
