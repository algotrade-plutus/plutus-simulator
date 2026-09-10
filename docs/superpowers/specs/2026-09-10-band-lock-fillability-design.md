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

### 1a. BUY into a limit-**up** (ceiling) situation

| # | Evidence tier | Condition | Outcome | FEL |
|---|---|---|---|---|
| B1 | Observed ask book (dense tick) | an ask rests **below** the ceiling | **FILL** at ≤ ceiling | `PROVEN` (TICK_BOOK) |
| B2 | Observed ask book | all asks ≥ ceiling (or none), bid at ceiling, **volume > 0** | **policy decides** | `ASSUMED` |
| B3 | Observed ask book | …same, **volume == 0** | **NO-FILL** (trắng bên bán) | `PROVEN` |
| B4 | Daily OHLC + volume | session traded below the cap (`low < ceiling`) | **FILL** at ≤ ceiling | `PROVEN` |
| B5 | Daily OHLC + volume | bar collapsed on the cap (`open==high==low==close==ceiling`), **volume == 0** | **NO-FILL** | `PROVEN` |
| B6 | Daily OHLC + volume | bar collapsed on the cap, **volume > 0** | **policy decides** | `ASSUMED` |
| B7 | Neither | book too sparse and no OHLC signal | **INDETERMINATE** | `UNEVIDENCED` |

### 1b. SELL into a limit-**down** (floor) situation  *(the exact mirror)*

| # | Evidence tier | Condition | Outcome | FEL |
|---|---|---|---|---|
| S1 | Observed bid book (dense tick) | a bid rests **above** the floor | **FILL** at ≥ floor | `PROVEN` (TICK_BOOK) |
| S2 | Observed bid book | all bids ≤ floor (or none), ask at floor, **volume > 0** | **policy decides** | `ASSUMED` |
| S3 | Observed bid book | …same, **volume == 0** | **NO-FILL** (trắng bên mua) | `PROVEN` |
| S4 | Daily OHLC + volume | session traded above the floor (`high > floor`) | **FILL** at ≥ floor | `PROVEN` |
| S5 | Daily OHLC + volume | bar collapsed on the floor (`open==high==low==close==floor`), **volume == 0** | **NO-FILL** | `PROVEN` |
| S6 | Daily OHLC + volume | bar collapsed on the floor, **volume > 0** | **policy decides** | `ASSUMED` |
| S7 | Neither | book too sparse and no OHLC signal | **INDETERMINATE** | `UNEVIDENCED` |

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

## Section 2 — `MarketState` / adapter evidence enrichment  *(APPROVED)*

The resolver derives the lock from **raw facts**, so adapters supply *facts, not verdicts* — the intelligence lives in one place. `MarketState` gains additive `Optional` fields (backward-compatible on the frozen dataclass):

| Field | Source | Role |
|---|---|---|
| `open` *(new)* | `quote_open` | part of the full collapse test |
| `high` *(new)* | `quote_max` (session high) | traded-through test for a **sell** (`high > floor`) |
| `low` *(new)* | `quote_min` (session low) | traded-through test for a **buy** (`low < ceiling`) |
| `volume` *(new)* | `quote_dailyvolume` | the `PROVEN no-fill` vs `ASSUMED` split (0 vs >0) |
| `book` *(present)* | tick ask/bid ladder | the dense-book tier (B1–B3 / S1–S3) |
| `ceiling`, `floor` *(present)* | bands | the band edges the order transacts against |
| `last` (**close**) *(present)* | `quote_close` | the **fill-price reference** for a filled outcome, and the price a "at-close" order carries |

**Close is retained** (`last`) and used as the fill price; only open/high/low/volume are new. Note the collapse test `open==high==low==close==band` reduces to `high==low==band` (the range collapsed to a point implies open/close pinned there), so close isn't required to *detect* the collapse — but it stays as the fill-price reference.

**Adapters:** `datahub.py` already *fetches* open/high/low via `_ohlc` (for the F2 fix) but discards them — now it writes them + `volume` into `MarketState` (no new data). `tick.py` already supplies `book`.

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

**(d) End-of-implementation audit (owner's request).** A script pulls concrete ticker-days for each rung — Case A (true lock, e.g. DAN 2022-01-04), Case B (traded through, DMN 2022-01-06), Case D (ATO-lock, NXT 2022-01-27), a dense-book example, and an UNKNOWN/data-gap example — and prints per case: raw evidence (band, OHLC, volume, book) → resolver tier + FEL → outcome, for the owner's sign-off.

**(e) Paper impact (small, improving):** §IV documents band-lock as an FEL-graded *fillability* outcome (not admission); the FEL distribution already reported now includes band-lock; "the band that **refuses the entry**" → "the band that **refuses the fill**"; threats-to-validity notes the daily-volume coarsening.

**(f) Sequencing.** Lands on plutus `rivf-2026` **before Phase 1 (ProtoGrid)** — a grid is a ladder of resting limit orders that hits band locks constantly, so Grid depends on correct band-lock fillability; fixing the core first means Grid measures a real effect, not an over-assertion artifact.

---

## Acceptance criteria

1. `BandLockResolver` exists as a pure `(order, MarketState) -> FillDecision|NotApplicable`, with all 14 rows unit-tested and the ASSUMED×3-policy behavior tested.
2. `admits()` no longer contains BAND_LOCK; a marketable order into a locked band is `Accepted` and rests.
3. Continuous fills route band-edge orders through the resolver; non-band orders are byte-for-byte unaffected (existing fill tests green).
4. `MarketState` carries open/high/low/volume; the daily adapter populates them.
5. ATO/ATC orders resolve against the phase-appropriate instant, and locked auctions are policy-aware.
6. J2/J11 (and any other BAND_LOCK-admission assertions) rewritten to the new contract and green; the market/scenario/strategy suites otherwise stay green.
7. SB null-anchor regenerated (faithful gap shrinks); `experiments_registry.md` updated with before/after.
8. The audit script prints the per-rung cases for owner sign-off.

**Increment split for the plan:** Increment 1 = criteria 1(minimal, close==band evidence only)+2+3+6 (the correctness fix). Increment 2 = criteria 1(full ladder)+4+5+7+8 (evidence ladder + auctions + audit).
