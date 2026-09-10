# BAND_LOCK → fill-path fillability, Increment 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move BAND_LOCK out of admission into the continuous fill path as a shared, all-policy fill decision — the regulation correctness fix — with **no numeric behaviour change** (today's `close==band` bar-proxy evidence is kept; the OHLC/volume evidence ladder and auctions are Increment 2).

**Architecture:** Extract `BookWalkFillPolicy._lock_refusal` (which already mirrors admission's predicate) into a shared `band_lock_decision(order, interval)` in `fills.py`, call it as a pre-step in the shared `BaseFillPolicy._dispatch` before continuous routing (so Soft/Hard/Probabilistic all get it, un-gated from tick resolution), delete the admission BAND_LOCK block, and rewrite the assertions that expected a `Rejected(BAND_LOCK)` at admission to the new "Accepted + rests + no-fill/indeterminate event" contract.

**Tech Stack:** Python 3.12+, the Plutus `market/session` package, pytest. Run tests with the repo venv: `PYTHONPATH=src .venv/bin/python -m pytest`.

## Global Constraints

- **Scope = Increment 1 only:** continuous-phase LIMIT orders (the tested path). Pure ATO/ATC auction-into-lock and the OHLC/volume evidence ladder are **Increment 2** — do not build them here.
- **Behaviour-preserving on the numbers:** the resolver keeps admission's exact predicate (same side test, same marketability test, same `UNKNOWN`→INDETERMINATE / known→NO_FILL split reading `interval.state.*`). A band-locked order still does not fill; it now rests and receives a fill *event* instead of an admission rejection. The SB null-anchor should regenerate **~unchanged**.
- **BAND_LIMIT stays in admission** (equity.py:89–102) — the genuine "price beyond the band" rule.
- **FEL semantics preserved:** `no_fill` → PROVEN, `indeterminate` → UNEVIDENCED (from `evidence_level.fill_evidence_level`).
- **Reason strings must contain `BAND_LOCK`** so existing reason-substring assertions stay green.

---

## File Structure

- Modify `src/plutus/market/session/fills.py` — add `band_lock_decision(...)`; call it in `BaseFillPolicy._dispatch`.
- Modify `src/plutus/market/session/book_walk.py` — delete the now-redundant `_lock_refusal` and its call (the shared pre-step covers it).
- Modify `src/plutus/market/exchanges/equity.py` — delete the BAND_LOCK admission block + the now-unused `LockEvidence` import.
- New test `tests/market/session/test_band_lock_fill.py` — the resolver's unit cases.
- Rewrite assertions in `scenarios/test_j2_limit_up_lock.py`, `scenarios/test_j11_floor_lock_exit.py`, `scenarios/test_j10_naive_vs_plutus.py`, `tests/market/test_equity_admission.py`, `validation/test_equity-margin.py`.

---

### Task 1: The shared `band_lock_decision` fill step

**Files:**
- Modify: `src/plutus/market/session/fills.py` (add the function near `_dispatch`, ~line 400)
- Test: `tests/market/session/test_band_lock_fill.py`

**Interfaces:**
- Consumes: `OrderRecord`, `MarketInterval` (carries `interval.state.{locked_side, ceiling, floor, lock_evidence}`), `FillDecision`, `FillEvidence`, `LockEvidence`, `DataField`, `Side`.
- Produces: `band_lock_decision(order: OrderRecord, interval: MarketInterval) -> Optional[FillDecision]` — `no_fill` (known lock evidence, PROVEN), `indeterminate` (UNKNOWN evidence, UNEVIDENCED), or `None` (lock does not apply → ordinary fill path runs).

- [ ] **Step 1: Write the failing tests**

```python
# tests/market/session/test_band_lock_fill.py
from datetime import datetime
from decimal import Decimal

from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import FillOutcome, MarketInterval, OrderRecord, Order
from plutus.market.protocol import MarketState, LockEvidence, Resolution
from plutus.core.order import OrderType, Side
from plutus.market.session import Venue
from plutus.market.session.types import OrderState, TimeInForce


def _order(side, price):
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=datetime(2022, 11, 16),
        updated_at=datetime(2022, 11, 16), fills=(),
        order=Order(ticker="HPG", side=side, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=price))


def _interval(*, locked_side, ceiling, floor, evidence):
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=ceiling, floor=floor, last=ceiling,
                        locked_side=locked_side, lock_evidence=evidence)
    return MarketInterval(ticker="HPG", start=datetime(2022, 11, 16),
                          end=datetime(2022, 11, 17), resolution=Resolution.DAILY,
                          state=state, close=ceiling)


def test_buy_into_known_ceiling_lock_is_no_fill():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_unknown_lock_evidence_is_indeterminate():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.UNKNOWN))
    assert d is not None and d.outcome is FillOutcome.INDETERMINATE


def test_unlocked_side_returns_none():
    # a SELL on a buy-locked (limit-up) day is fillable — not our concern
    d = band_lock_decision(
        _order(Side.SELL, Decimal("13.35")),
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is None


def test_limit_below_ceiling_not_marketable_returns_none():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.00")),   # below the cap, not crossing the lock
        _interval(locked_side=Side.BUY, ceiling=Decimal("13.35"),
                  floor=Decimal("11.65"), evidence=LockEvidence.BAR_PROXY))
    assert d is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd /Users/dan/algotrade-research/plutus && PYTHONPATH=src .venv/bin/python -m pytest tests/market/session/test_band_lock_fill.py -v`
Expected: FAIL — `ImportError: cannot import name 'band_lock_decision'`.

- [ ] **Step 3: Implement the function** (port of `book_walk._lock_refusal`, reason carrying `BAND_LOCK`)

Add near `BaseFillPolicy._dispatch` (fills.py ~line 400), and to `__all__`:

```python
def band_lock_decision(order: OrderRecord,
                       interval: MarketInterval) -> Optional[FillDecision]:
    """BAND_LOCK as a fill decision — a fillability check, not an admission rule.

    The band being locked against the order's side means it rests but cannot
    cross the lock. Ported from ``BookWalkFillPolicy._lock_refusal`` so every
    policy shares one rule at fill time, reading ``interval.state``. Returns
    ``None`` when the lock does not apply (wrong side, or not marketable through
    the lock), so the ordinary price test runs.
    """
    state = interval.state
    if state.locked_side is None or order.order.side is not state.locked_side:
        return None
    price = order.order.limit_price
    marketable = price is None or (
        (order.order.side is Side.BUY and state.ceiling is not None
         and price >= state.ceiling)
        or (order.order.side is Side.SELL and state.floor is not None
            and price <= state.floor))
    if not marketable:
        return None
    if state.lock_evidence is LockEvidence.UNKNOWN:
        return FillDecision.indeterminate(
            f'BAND_LOCK: the band is reported locked against the '
            f'{order.order.side.value} side and this order is marketable '
            f'through it, but the lock rests on no book and no bar proxy, so '
            f'whether it would have filled cannot be established',
            [DataField.BOOK])
    bound = state.ceiling if order.order.side is Side.BUY else state.floor
    return FillDecision.no_fill(
        f'BAND_LOCK: the band is locked at {bound} against the '
        f'{order.order.side.value} side ({state.lock_evidence.value}) and this '
        f'order is marketable through it; it rests but cannot cross the lock')
```

Ensure the imports exist at the top of `fills.py`: `LockEvidence` and `Resolution` from `plutus.market.protocol`, `DataField` (already imported), `Side` (already imported via `core.order`). Add `'band_lock_decision'` to `__all__` (line ~156).

- [ ] **Step 4: Run to verify it passes**

Run: `cd /Users/dan/algotrade-research/plutus && PYTHONPATH=src .venv/bin/python -m pytest tests/market/session/test_band_lock_fill.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add src/plutus/market/session/fills.py tests/market/session/test_band_lock_fill.py
git commit -m "Add band_lock_decision: BAND_LOCK as a shared fill-path decision

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Wire the step into the shared continuous path; drop the book_walk duplicate

**Files:**
- Modify: `src/plutus/market/session/fills.py` (`BaseFillPolicy._dispatch`, ~line 448–455)
- Modify: `src/plutus/market/session/book_walk.py` (delete `_lock_refusal` (1763–1812) and its call (1574–1576))

**Interfaces:**
- Consumes: `band_lock_decision` (Task 1).
- Produces: every fill policy refuses a marketable-into-lock order at fill time via one shared pre-step.

- [ ] **Step 1: Add the pre-step in `_dispatch`**

In `fills.py` `_dispatch`, immediately after the `if phase not in MATCHING_PHASES: return FillDecision.no_fill(...)` block (~line 450) and before `if phase is SessionPhase.CONTINUOUS:`:

```python
        locked = band_lock_decision(order, interval)
        if locked is not None:
            return locked
```

This runs for continuous and continuous-LO-carried-into-auction (the LIMIT path); AUCTION_ONLY (ATO/ATC) orders are routed earlier and are out of scope for Increment 1.

- [ ] **Step 2: Delete the book_walk duplicate**

In `book_walk.py`, delete the `_lock_refusal` method (1763–1812) and its call site in `_continuous` (1574–1576: the `locked = self._lock_refusal(...)` / `if locked is not None: return locked` lines). The shared `_dispatch` pre-step now covers it for book-walk too (book-walk's `_continuous` is reached *through* `_dispatch`).

- [ ] **Step 3: Run the fill + book_walk suites**

Run: `cd /Users/dan/algotrade-research/plutus && PYTHONPATH=src .venv/bin/python -m pytest tests/market/session/test_fills.py tests/market/session/test_book_walk.py -v 2>&1 | tail -15`
Expected: PASS. In particular `test_book_walk.py::...` at line 891–892 still sees `NO_FILL` with `'BAND_LOCK' in decision.reason` (now sourced from the shared step). If that test asserted a tick-only precondition around the lock, adjust it to the shared path.

- [ ] **Step 4: Commit**

```bash
git add src/plutus/market/session/fills.py src/plutus/market/session/book_walk.py
git commit -m "Route band lock through the shared fill dispatch; drop book_walk duplicate

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Delete BAND_LOCK from admission

**Files:**
- Modify: `src/plutus/market/exchanges/equity.py` (delete lines 104–123; remove unused `LockEvidence` import at line 18)

**Interfaces:**
- Produces: `admits()` gauntlet = TICK_GRID → ROUND_LOT → BAND_LIMIT → FOREIGN_ROOM → SESSION_SEMANTICS. A marketable-into-lock order is now `ADMITTED` and rests.

- [ ] **Step 1: Delete the BAND_LOCK block**

Remove equity.py lines 104–123 (the entire `# --- 4. BAND_LOCK ...` block quoted in the design map). Remove `LockEvidence` from the import on line 18 if it is no longer referenced in the file (grep first: `grep -n LockEvidence src/plutus/market/exchanges/equity.py`).

- [ ] **Step 2: Confirm the order now rests and gets a fill-time no-fill (integration check)**

Run a quick integration probe over the fixtures (HPG 2022-11-16 closed at its ceiling):

```bash
cd /Users/dan/algotrade-research/plutus
PYTHONPATH=src PLUTUS_DATA_ROOT=strategies/fixtures/parquet .venv/bin/python - <<'PY'
from datetime import datetime
from decimal import Decimal
import sys; sys.path.insert(0, 'scenarios')
from _harness import build_session
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side
from plutus.market.session import Accepted
cfg = {"period": {"start": "2022-11-16", "end": "2022-11-18"}, "resolution": "1d",
       "exchange_rules": {"venues": ["HSX"]},
       "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-CHK"}},
       "fill_policy": {"kind": "hard"}}
s = build_session(cfg)
ack = s.submit(Order(ticker="HPG", side=Side.BUY, quantity=1000,
                     order_type=OrderType.LIMIT, limit_price=Decimal("13.35")))
print("admission:", type(ack).__name__)          # now Accepted (was Rejected(BAND_LOCK))
evs = s.advance_to(datetime(2022, 11, 16, 13, 0))
kinds = [getattr(e.kind, "value", e.kind) for e in evs]
print("events:", kinds)                          # no 'filled'; an 'indeterminate' or none
print("holdings:", s.holdings("HPG").total)      # 0 — did not fill
assert isinstance(ack, Accepted)
assert s.holdings("HPG").total == 0
print("OK: rests, does not fill")
PY
```
Expected: `admission: Accepted`, holdings 0, "OK". (Under `hard` the lock yields no fill; the order rests and expires at day end.)

- [ ] **Step 3: Commit**

```bash
git add src/plutus/market/exchanges/equity.py
git commit -m "Remove BAND_LOCK from admission (it is a fill-time fillability check)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Rewrite the scenario assertions (J2, J11, J10)

**Files:**
- Modify: `scenarios/test_j2_limit_up_lock.py`, `scenarios/test_j11_floor_lock_exit.py`, `scenarios/test_j10_naive_vs_plutus.py`

**Interfaces:** Consumes the new contract (Accepted + rests + no fill).

- [ ] **Step 1: Rewrite J2's BAND_LOCK assertion**

In `test_j2_limit_up_lock.py`, the buy-at-ceiling is now `Accepted`, rests, and does not fill. Replace the `at_ceiling` block (the `run_j2` submit + the Tier-2 assertion at line 105) so it: submits the buy (asserts `Accepted`), advances to `LOCK_DAY_AFTERNOON`, and asserts **no fill event for that order** and holdings stay 0. Keep the `above` (BAND_LIMIT) assertion at line 98 unchanged. Update the module docstring (lines 8–9, 33–38) to describe the new "admitted, rests, does not fill" behaviour. Concretely, the Tier-2 becomes:

```python
    assert isinstance(obs["at_ceiling"], Accepted), obs["at_ceiling"]
    fills = [e for e in obs["events"]
             if getattr(e.kind, "value", e.kind) == "filled"
             and e.order_id == obs["at_ceiling"].order_id]
    assert not fills, "a buy into a limit-up lock must not fill"
```

- [ ] **Step 2: Rewrite J11 (floor lock) symmetrically**

In `test_j11_floor_lock_exit.py`, the sell-at-floor (`sell_at_floor`) is now `Accepted` and does not fill. Replace the line-97 assertion the same way (assert `Accepted`, then no fill for that order after advancing). Keep the below-floor `BAND_LIMIT` assertion (line 103). Update docstring lines 10, 27.

- [ ] **Step 3: Rewrite J10**

In `test_j10_naive_vs_plutus.py`, line 100 asserts `plutus["stop"].rule.name == "BAND_LOCK"`. The stop (a marketable sell into a floor lock) is now `Accepted` + no fill. Change the assertion to assert the stop is `Accepted` and did not fill (holdings unchanged), and update the delta-vs-naive narrative (the "value proposition" delta is now "naive fills the stop, Plutus admits it but it does not fill" — the same economic point, one layer later).

- [ ] **Step 4: Run the three scenarios**

Run: `cd /Users/dan/algotrade-research/plutus && PYTHONPATH=src PLUTUS_DATA_ROOT=strategies/fixtures/parquet .venv/bin/python -m pytest scenarios/test_j2_limit_up_lock.py scenarios/test_j11_floor_lock_exit.py scenarios/test_j10_naive_vs_plutus.py -v 2>&1 | tail -12`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add scenarios/test_j2_limit_up_lock.py scenarios/test_j11_floor_lock_exit.py scenarios/test_j10_naive_vs_plutus.py
git commit -m "Rewrite J2/J10/J11 to the fill-time band-lock contract

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 5: Rewrite the unit / validation assertions

**Files:**
- Modify: `tests/market/test_equity_admission.py` (lines 191, 210, 220, 228–229, 237)
- Modify: `validation/test_equity-margin.py` (lines 713, 725)

**Interfaces:** Consumes the new contract.

- [ ] **Step 1: Move the equity-admission lock tests to the fill layer**

In `tests/market/test_equity_admission.py`, the three admission tests that assert a `BAND_LOCK` verdict on a real order — `test_buy_into_a_locked_ceiling_is_not_fillable` (191), `test_sell_into_a_locked_floor_is_not_fillable` (210), `test_unknown_lock_evidence_yields_indeterminate` (220), and `test_tick_book_evidence_is_honoured_the_same_way` (228–229) — now belong to `band_lock_decision`. Convert each to assert the **`FillDecision`** from `band_lock_decision(order, interval)` (as in Task 1's tests: `NO_FILL` for known evidence, `INDETERMINATE` for UNKNOWN) rather than an `Admissibility`. Delete `test_band_limit_precedes_band_lock` (237) — precedence is moot once BAND_LOCK leaves admission; add a one-line comment noting BAND_LIMIT is now the only band rule at admission. Keep the two ADMITTED tests (170 `test_price_exactly_at_ceiling_is_admissible`, 195 `test_sell_into_a_locked_ceiling_is_fine`) — they now assert the *correct* new admission behaviour (the order is admitted).

- [ ] **Step 2: Flip the forced-sale validation assertion**

In `validation/test_equity-margin.py`, lines 713 and 725 assert the forced *bán giải chấp* sell was refused **at admission** with `BAND_LOCK`. It is now refused at fill time. Change the assertions to expect the refusal as a fill-time no-fill on the resting forced-sale order (the sell is admitted, rests, and does not fill on the floor-locked day) — the economic outcome (the position cannot be liquidated) is unchanged; only the layer moves. If this file is not part of the standard suite (it lives under `validation/`, a scripts area), update it for accuracy but it need not gate the commit.

- [ ] **Step 3: Run the market unit suite**

Run: `cd /Users/dan/algotrade-research/plutus && PYTHONPATH=src PLUTUS_DATA_ROOT=strategies/fixtures/parquet .venv/bin/python -m pytest tests/market -q 2>&1 | tail -12`
Expected: PASS (the 1,646-test market suite green, with the lock tests now at the fill layer). `tests/market/test_verdicts.py` (enum-distinctness at 33, `Admissibility` unit at 61) stays green untouched — the `BAND_LOCK` enum member is retained.

- [ ] **Step 4: Commit**

```bash
git add tests/market/test_equity_admission.py validation/test_equity-margin.py
git commit -m "Move the band-lock unit/validation assertions to the fill layer

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Full suites green + regenerate the SB null-anchor

**Files:** none (verification), then a registry note.

- [ ] **Step 1: Run the three canonical suites**

Run each in its own process (scenarios and strategies each define a top-level `_harness`):
```bash
cd /Users/dan/algotrade-research/plutus
export PLUTUS_DATA_ROOT=strategies/fixtures/parquet
PYTHONPATH=src .venv/bin/python -m pytest tests/market -q 2>&1 | tail -3
PYTHONPATH=src .venv/bin/python -m pytest scenarios -q 2>&1 | tail -3
PYTHONPATH=src .venv/bin/python -m pytest strategies -q 2>&1 | tail -3
```
Expected: all green. Investigate any failure before proceeding — a failure here is a real behaviour change, not expected in Increment 1.

- [ ] **Step 2: Regenerate the SB null-anchor and confirm it is ~unchanged**

```bash
cd /Users/dan/algotrade-research/proto/ProtoSmartBeta
.venv/bin/python -m proto_smart_beta.experiments.null_anchor 2>&1 | tail -18
```
Expected: faithful Sharpe ≈ **−0.55** and **~45 BAND_LOCK-equivalent no-fills** as before — Increment 1 keeps the same `close==band` evidence, so the number should be materially unchanged. (Note: the refusals may now surface as fill-time no-fills; if the runner counted `Rejected(BAND_LOCK)` specifically, update its Tier-1 tally to count the fill-time no-fill/indeterminate instead. The Sharpe is what must stay ~−0.55.)

- [ ] **Step 3: Note the correctness fix in the registry**

Add a line under the SB block in `docs/reference/tables/experiments_registry.md` recording that BAND_LOCK is now enforced at fill time (Increment 1), numbers unchanged, and that Increment 2 (OHLC/volume evidence) is what will move the number toward naive.

- [ ] **Step 4: Commit**

```bash
cd /Users/dan/algotrade-research/plutus
git add docs/reference/tables/experiments_registry.md
git commit -m "Note Increment 1 (band lock now fill-time; numbers unchanged) in the registry

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review notes (author)

- **Spec coverage:** Increment 1 criteria from the spec — drop BAND_LOCK from admission (Task 3), a minimal resolver reusing `close==band` evidence in the continuous path (Tasks 1–2), scenarios re-greened (Tasks 4–5), suites green (Task 6). Criteria 4/5 (MarketState OHLC enrichment, ATO/ATC, full ladder) are explicitly **Increment 2**.
- **Deferred to Increment 2:** the OHLC-collapse + volume + book evidence ladder (rows B4–B7/S4–S7), phase-aware ATO/ATC instant selection, auction policy-awareness, the end-of-implementation audit, and the SB gap *shrinking* (Increment 1 holds it ~constant by design).
- **Watch:** `test_book_walk.py:892`'s reason-substring assertion (kept green by carrying `BAND_LOCK` in the shared reason); the SB runner's Tier-1 counter (may need to count fill-time no-fills instead of admission rejects); the `validation/` files are scripts, not gating suites.
