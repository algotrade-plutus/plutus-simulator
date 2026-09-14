# BAND_LOCK Increment 2 — evidence ladder, phase-aware auctions, SB validation & audit — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade the equity band-lock fillability check from Increment 1's single `close==band` proxy to the full evidence-graded ladder — daily OHLC+volume, dense ask/bid book, phase-aware ATO/ATC — so a band-locked order fills when the session traded through the edge and only fails to fill on a proven full-session lock; then regenerate the SmartBeta null-anchor (the faithful gap must shrink) and print the owner's audit cases.

**Architecture:** `band_lock_decision(order, interval)` in `session/fills.py` stays a **pure, override-only** function returning `Optional[FillDecision]` — `None` (defer to the ordinary fill path), a definite `NO_FILL`, or an `INDETERMINATE`, **never a FILL** (fills are sized by the policy). It engages only when the order is *marketable into the band edge* on its side, picks the **tested instant by phase** (continuous → session extreme toward the order; ATO → open; ATC → close), consults the **dense book** where the interval carries one and otherwise the **daily OHLC+volume**, and grades: traded through the edge → passthrough (the policy fills); locked at the edge with zero volume → `NO_FILL` (*trắng bên bán/mua*); locked with volume > 0 → passthrough (the policy floor decides — soft fills, hard indeterminate, probabilistic draws); locked with volume unknown, or no signal at all → `INDETERMINATE`. No `MarketState`, adapter, or `derivatives.py` change: `MarketInterval` already carries and populates open/high/low/close/volume/book, and the adapters' `locked_side`/`BAR_PROXY` are still consumed by `derivatives.py` and the adapter tests.

**Tech Stack:** Python 3.12, pytest, DuckDB/pandas (proto data), Decimal financial precision. Two repos: `plutus` (hub, the resolver + tests + registry + audit) and its sibling `proto/ProtoSmartBeta` (the SB runner, branch `rivf-2026`).

## Global Constraints

- **Branch `rivf-2026`** in both repos. This is the long-lived paper-dev branch; **do not merge, push, PR, or run the finishing-a-development-branch skill** — the owner finalizes ("commit and push") later. Per-task local commits on `rivf-2026` are the SDD mechanism and are expected.
- **Override-only resolver.** `band_lock_decision(order, interval) -> Optional[FillDecision]` returns only `None` / `FillDecision.no_fill(...)` / `FillDecision.indeterminate(...)`. **It must never return `FillDecision.fill(...)`** — a fill is sized by the policy's `_sized_fill`, which the resolver has no access to.
- **Every band-lock reason string contains the literal `BAND_LOCK`** (scenarios and the audit grep for it).
- **Do not modify** `src/plutus/market/protocol.py` (`MarketState`), `src/plutus/market/adapters/datahub.py`, `src/plutus/market/adapters/tick.py`, or `src/plutus/market/exchanges/derivatives.py`. `locked_side`/`lock_evidence`/`BAR_PROXY` stay; the resolver simply stops depending on them.
- **Behaviour-preserving for non-band orders.** After every task, `python -m pytest tests/market -q` must be **0 failed** on the real corpus (the Increment-1 invariant was 1532 passed / 0 failed). Fixture-only minimal-corpus suites may differ; the real corpus is the gate.
- **Decimal everywhere** for prices/bands; `volume` is `Optional[int]`; corpus prices are in thousands of đồng (`PRICE_SCALE = 1000` in the SB runner).
- **Run tests from the `plutus` repo root**, environment: `source .venv/bin/activate && export PYTHONPATH=/Users/dan/algotrade-research/plutus/src` (or the installed package). Proto tests run from `proto/ProtoSmartBeta` with its own `.venv`.
- **Attribution** on every commit:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure

| File | Responsibility | Task |
|---|---|---|
| `src/plutus/market/session/fills.py` | Rewrite `band_lock_decision` (currently lines 549-581) to the phase-aware daily ladder; wire it into the `AUCTION_ONLY` branch of `BaseFillPolicy._dispatch` (currently lines 431-446); add small pure helpers next to it. | 1, 3 |
| `tests/market/session/test_band_lock_fill.py` | Replace the 6 Increment-1 unit tests with the daily-tier matrix (B4–B7, S4–S7) + phase (ATO/ATC/continuous) + marketability cases. | 1 |
| `tests/market/session/test_band_lock_book_tier.py` *(new)* | The dense-book rows B1–B3 / S1–S3. | 3 |
| `tests/market/session/test_band_lock_policy_floor.py` *(new)* | ASSUMED tier × 3 policies end-to-end through `.evaluate()`. | 4 |
| `scenarios/test_j2_limit_up_lock.py`, `test_j11_floor_lock_exit.py`, `test_j10_naive_vs_plutus.py` | Fixtures updated to a true full-session lock (collapse + zero volume) so they stay `NO_FILL`; J2 gains a traded-through variant that now fills. | 2 |
| `proto/ProtoSmartBeta/src/proto_smart_beta/experiments/null_anchor.py` | Tier-1 recount of fill-time band-lock no-fills (Accepted-but-unfilled on a band-edge day); regenerate. | 5 |
| `docs/reference/tables/experiments_registry.md` | SB row before/after: faithful Sharpe/HPR move toward naive; the reduced true-lock count. | 5 |
| `measurements/band_lock_ladder_audit.py` *(new)* | The owner sign-off audit: concrete ticker-days through the ladder, printing evidence → tier → FEL → outcome. | 6 |
| `docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md` | §2 reconciliation note (MarketInterval already carries OHLC → no MarketState change); mark Increment-2 acceptance criteria met; §4e paper-impact note. | 7 |

---

## Task 1: Phase-aware daily evidence ladder in `band_lock_decision` (override-only) + auction wiring

**Files:**
- Modify: `src/plutus/market/session/fills.py` — replace `band_lock_decision` (lines 549-581) and its section; edit `BaseFillPolicy._dispatch` `AUCTION_ONLY` branch (lines 431-446).
- Test: `tests/market/session/test_band_lock_fill.py` — replace the whole file.

**Interfaces:**
- Consumes: `MarketInterval` (`.state`, `.session`, `.open/.high/.low/.close/.volume/.book`, `.lacks`), `MarketState` (`.ceiling`, `.floor`), `OrderRecord` (`.order.side`, `.order.limit_price`), `Side`, `DataField`, `FillDecision.no_fill/.indeterminate`, `SessionPhase`.
- Produces: `band_lock_decision(order: OrderRecord, interval: MarketInterval) -> Optional[FillDecision]`, override-only. Task 3 will prepend a book branch; Task 4 relies on the volume>0 passthrough.

### Context the implementer needs

Current `_dispatch` (fills.py:401-467) calls `band_lock_decision` **only** at line 452, i.e. for **non-auction-only** orders once the phase is in `MATCHING_PHASES`. Auction-only orders (ATO/ATC time-in-force) return earlier at line 444 via `self._auction(...)` and are **never** band-lock-checked today. This task fixes both: rewrites the resolver, and adds a band-lock pre-step to the auction-only branch.

The resolver's tested instant unifies by phase because the band is a hard bound (`high <= ceiling`, `low >= floor` always):
- **BUY** marketable into the **ceiling**: continuous tests `interval.low` (the session's best price toward a buyer); ATO tests `interval.open`; ATC tests `interval.close`. `instant < ceiling` ⟹ the session/cross traded **below** the cap ⟹ a buyer could obtain shares ⟹ passthrough. `instant == ceiling` ⟹ nothing traded below the cap ⟹ locked; volume splits it. (For continuous, `low == ceiling` implies `high == low == ceiling`, the full collapse.)
- **SELL** marketable into the **floor**: continuous tests `interval.high`; ATO `open`; ATC `close`. `instant > floor` ⟹ passthrough; `instant == floor` ⟹ locked.

- [ ] **Step 1: Replace the unit-test file with the daily-tier matrix (write the failing tests first)**

Replace the entire contents of `tests/market/session/test_band_lock_fill.py` with:

```python
"""Unit tests for `band_lock_decision`: the phase-aware daily evidence ladder.

`band_lock_decision` (session/fills.py) is the shared, override-only band-lock
rule every fill policy applies via `BaseFillPolicy._dispatch`. It is a pure
function of (order, interval): it returns `None` to defer to the ordinary fill
path, a definite `NO_FILL` on a proven full lock with zero volume, or an
`INDETERMINATE` where the marketable-into-the-edge order's fate cannot be
established. It never returns a FILL — a fill is sized by the policy.

Rows below are the daily OHLC+volume tier of the design's ladder
(docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md, tables 1a/1b):
B4/S4 traded-through -> passthrough; B5/S5 collapse+vol==0 -> NO_FILL;
B6/S6 collapse+vol>0 -> passthrough (the policy floor decides); B7/S7 no signal
-> INDETERMINATE; plus the phase instant (continuous low/high, ATO open, ATC
close) and the not-applicable (unmarketable / no band) cases.
"""

from datetime import datetime
from decimal import Decimal

from plutus.market.protocol import (MarketState, Order, OrderType, Resolution,
                                    SessionPhase, Side)
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (DataField, FillOutcome,
                                         MarketInterval, OrderRecord,
                                         OrderState, TimeInForce, Venue)

CEIL = Decimal("13.35")
FLOOR = Decimal("11.65")


def _order(side, price, order_type=OrderType.LIMIT):
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=(TimeInForce.AUCTION_ONLY
                       if order_type in (OrderType.AT_THE_OPENING,
                                         OrderType.AT_THE_CLOSE)
                       else TimeInForce.DAY),
        submitted_at=datetime(2022, 11, 16),
        updated_at=datetime(2022, 11, 16), fills=(),
        order=Order(ticker="HPG", side=side, quantity=1000,
                    order_type=order_type, limit_price=price))


def _interval(*, phase=SessionPhase.CONTINUOUS, ceiling=CEIL, floor=FLOOR,
              open=None, high=None, low=None, close=None, volume=None,
              missing=()):
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=ceiling, floor=floor, last=close,
                        session=phase)
    miss = set(missing)
    if volume is None:
        miss.add(DataField.VOLUME)
    return MarketInterval(
        ticker="HPG", start=datetime(2022, 11, 16),
        end=datetime(2022, 11, 17), resolution=Resolution.DAILY, state=state,
        open=open, high=high, low=low, close=close, volume=volume,
        missing=frozenset(miss))


# ---- BUY into the ceiling (limit-up), continuous ----------------------------

def test_b4_buy_traded_below_cap_is_passthrough():
    # session low is under the cap: a buyer could obtain shares -> ordinary path
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=Decimal("13.00"), close=CEIL, volume=5000))
    assert d is None


def test_b5_buy_full_collapse_zero_volume_is_no_fill():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b6_buy_collapse_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=7000))
    assert d is None


def test_b7_buy_collapse_volume_unknown_is_indeterminate_naming_volume():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=None))
    assert d is not None and d.outcome is FillOutcome.INDETERMINATE
    assert DataField.VOLUME in d.missing


def test_b7_buy_no_low_signal_is_indeterminate():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(high=None, low=None, close=CEIL, volume=0,
                  missing={DataField.LOW, DataField.HIGH, DataField.OPEN}))
    assert d is not None and d.outcome is FillOutcome.INDETERMINATE


# ---- SELL into the floor (limit-down), continuous ---------------------------

def test_s4_sell_traded_above_floor_is_passthrough():
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=Decimal("12.00"), low=FLOOR, close=FLOOR, volume=5000))
    assert d is None


def test_s5_sell_full_collapse_zero_volume_is_no_fill():
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=FLOOR, low=FLOOR, close=FLOOR, volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_s6_sell_collapse_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=FLOOR, low=FLOOR, close=FLOOR, volume=7000))
    assert d is None


# ---- phase: ATO tests the open, ATC tests the close (Case D) -----------------

def test_ato_buy_opened_locked_then_fell_is_no_fill_for_the_ato():
    # opened at the ceiling with no opening trade, even though it later fell:
    # the ATO only saw the opening auction.
    d = band_lock_decision(
        _order(Side.BUY, None, order_type=OrderType.AT_THE_OPENING),
        _interval(phase=SessionPhase.OPENING_AUCTION,
                  open=CEIL, high=CEIL, low=Decimal("13.00"),
                  close=Decimal("13.10"), volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL


def test_ato_buy_opened_below_cap_is_passthrough():
    d = band_lock_decision(
        _order(Side.BUY, None, order_type=OrderType.AT_THE_OPENING),
        _interval(phase=SessionPhase.OPENING_AUCTION,
                  open=Decimal("13.00"), high=CEIL, low=Decimal("13.00"),
                  close=CEIL, volume=5000))
    assert d is None


def test_atc_buy_closed_locked_zero_volume_is_no_fill():
    d = band_lock_decision(
        _order(Side.BUY, None, order_type=OrderType.AT_THE_CLOSE),
        _interval(phase=SessionPhase.CLOSING_AUCTION,
                  open=Decimal("13.00"), high=CEIL, low=Decimal("13.00"),
                  close=CEIL, volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL


# ---- not applicable: unmarketable / wrong-way / no band ---------------------

def test_limit_below_ceiling_is_not_marketable_returns_none():
    d = band_lock_decision(
        _order(Side.BUY, Decimal("13.00")),
        _interval(high=CEIL, low=CEIL, close=CEIL, volume=0))
    assert d is None


def test_sell_on_a_limit_up_day_is_not_a_lock_question_returns_none():
    # a SELL when only the ceiling is pinned (floor untouched) -> ordinary path
    d = band_lock_decision(
        _order(Side.SELL, FLOOR),
        _interval(high=CEIL, low=Decimal("13.00"), close=CEIL, volume=5000))
    assert d is None


def test_no_ceiling_band_returns_none():
    d = band_lock_decision(
        _order(Side.BUY, CEIL),
        _interval(ceiling=None, high=CEIL, low=CEIL, close=CEIL, volume=0))
    assert d is None
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `python -m pytest tests/market/session/test_band_lock_fill.py -q`
Expected: failures/errors — the current `band_lock_decision` reads `state.locked_side`/`lock_evidence` (unset here) and returns `None` for every case, so the `NO_FILL`/`INDETERMINATE` assertions fail. (Confirms the tests exercise the new contract, not the old.)

- [ ] **Step 3: Rewrite `band_lock_decision` and its helpers**

In `src/plutus/market/session/fills.py`, replace the whole `band_lock_decision` definition (lines 549-581, the block under the `# BAND_LOCK -- a fillability check` banner) with:

```python
def _band_edge(side: Side, state) -> Optional[Decimal]:
    """The band edge an order of ``side`` transacts against: ceiling for a
    buy, floor for a sell. ``None`` when that edge is absent for this state."""
    if side is Side.BUY:
        return state.ceiling
    if side is Side.SELL:
        return state.floor
    return None   # Side.CROSS is an integration bug; the caller validates it


def _marketable_into(order: OrderRecord, side: Side, edge: Decimal) -> bool:
    """Whether the order crosses the edge: a market order always, a limit only
    at or beyond it (buy >= ceiling, sell <= floor). A limit strictly inside
    the band is never a lock question -- it fills iff the session traded to it,
    which is the ordinary price test."""
    price = order.order.limit_price
    if price is None:
        return True
    return price >= edge if side is Side.BUY else price <= edge


def _lock_instant(side: Side, interval: MarketInterval
                  ) -> Tuple[Optional[Decimal], DataField]:
    """The price whose relation to the edge decides the lock, by phase.

    An ATO order only sees the opening auction (the open), an ATC only the
    closing auction (the close); a continuous order had the whole session, so
    it is locked only if the session extreme toward it never left the edge --
    the low for a buy, the high for a sell. Returns ``(None, field)`` when that
    price is absent, and the caller degrades to INDETERMINATE naming ``field``.
    """
    phase = interval.session
    if phase is SessionPhase.OPENING_AUCTION:
        return interval.open, DataField.OPEN
    if phase is SessionPhase.CLOSING_AUCTION:
        return interval.close, DataField.CLOSE
    if side is Side.BUY:
        return interval.low, DataField.LOW
    return interval.high, DataField.HIGH


def _phase_word(interval: MarketInterval) -> str:
    phase = interval.session
    if phase is SessionPhase.OPENING_AUCTION:
        return 'opening auction'
    if phase is SessionPhase.CLOSING_AUCTION:
        return 'closing auction'
    return 'session'


def band_lock_decision(order: OrderRecord,
                       interval: MarketInterval) -> Optional[FillDecision]:
    """BAND_LOCK as an evidence-graded fillability check -- not an admission rule.

    A pure, **override-only** function of ``(order, interval)``. It engages only
    when the order is marketable into the band edge on its side (a market order,
    or a limit at or beyond the edge). It then reads the phase-appropriate
    instant (``_lock_instant``) and the interval's volume, and returns:

    * ``None`` -- defer to the ordinary fill path -- when the edge was traded
      through (``instant`` past the edge, rows B4/S4), when the edge was merely
      matched at with volume present (rows B6/S6, the ASSUMED tier, where the
      active fill policy's floor decides -- soft fills, hard is INDETERMINATE,
      probabilistic draws), or when the lock does not apply at all;
    * ``NO_FILL`` -- a proven full lock: the instant sat on the edge and zero
      volume traded (*trắng bên bán/mua*, rows B5/S5);
    * ``INDETERMINATE`` -- the order is marketable into the edge but neither the
      book (Task 3) nor the bar can settle whether it filled: the instant is
      absent, or it sat on the edge with volume unknown (rows B7/S7).

    It **never returns a FILL**: a fill is sized by the policy's ``_sized_fill``,
    so both the traded-through fill and the assumed fill are passed through for
    the policy to size and grade. This is why Increment 1's ``close==band``
    proxy over-asserted ~10x -- it answered NO_FILL for every close-at-the-band
    bar, including the majority that had traded below the cap earlier in the
    session (design section, "Why this change").
    """
    side = order.order.side
    edge = _band_edge(side, interval.state)
    if edge is None or not _marketable_into(order, side, edge):
        return None

    instant, field = _lock_instant(side, interval)
    if instant is None:
        return FillDecision.indeterminate(
            f'BAND_LOCK: this {side.value} order is marketable into the '
            f'{"ceiling" if side is Side.BUY else "floor"} of {edge}, but the '
            f'{_phase_word(interval)} carries no price to test against it, so '
            f'whether it would have filled cannot be established',
            [DataField.BOOK, field])

    traded_through = instant < edge if side is Side.BUY else instant > edge
    if traded_through:
        return None   # rows B4/S4: the edge was crossed -> the policy fills

    # instant sits on the edge: a lock at the tested instant. Volume splits it.
    if interval.volume is None or interval.lacks(DataField.VOLUME):
        return FillDecision.indeterminate(
            f'BAND_LOCK: {side.value} into a {edge} lock at the '
            f'{_phase_word(interval)}, but with no observed volume a proven '
            f'no-fill cannot be told from a matched-at-the-edge assumption',
            [DataField.VOLUME])
    if interval.volume == 0:
        return FillDecision.no_fill(
            f'BAND_LOCK: {side.value} into a {edge} lock at the '
            f'{_phase_word(interval)} with zero volume (trắng bên '
            f'{"bán" if side is Side.BUY else "mua"}); it rests but nothing '
            f'traded, so it cannot cross the lock')
    return None   # rows B6/S6: volume > 0 -> ASSUMED -> the policy floor decides
```

Notes for the implementer:
- `Tuple` and `Optional` are already imported at fills.py:139-140; `DataField` at 146-149; `Side`, `SessionPhase` at 144-145. No new imports.
- Leave the section banner comment (`# BAND_LOCK -- a fillability check, not an admission rule`) above the helpers.

- [ ] **Step 4: Wire the resolver into the auction-only branch of `_dispatch`**

In `src/plutus/market/session/fills.py`, in `BaseFillPolicy._dispatch`, the `AUCTION_ONLY` branch currently (lines 444-446) ends:

```python
            return self._auction(order, interval, rules,
                                 already_filled=already_filled,
                                 instrument=instrument)
```

Insert the band-lock pre-step immediately before that `return`, so the branch reads:

```python
            locked = band_lock_decision(order, interval)
            if locked is not None:
                return locked
            return self._auction(order, interval, rules,
                                 already_filled=already_filled,
                                 instrument=instrument)
```

Leave the existing call at line 452 (the non-auction-only path) unchanged — the rewritten resolver keys off `interval.session`, so it correctly serves continuous, opening- and closing-auction phases there too.

- [ ] **Step 5: Run the band-lock unit tests to green**

Run: `python -m pytest tests/market/session/test_band_lock_fill.py -q`
Expected: all pass.

- [ ] **Step 6: Run the fill-policy and dispatch suites (no non-band regression yet)**

Run: `python -m pytest tests/market/session -q`
Expected: 0 failed. If a pre-existing fill test asserted the old `state.locked_side` path of `band_lock_decision`, migrate it to the new contract (it should be one of the cases in Step 1); do not weaken an unrelated assertion.

- [ ] **Step 7: Commit**

```bash
git add src/plutus/market/session/fills.py tests/market/session/test_band_lock_fill.py
git commit -m "Grade the band lock from OHLC/volume by phase, override-only

band_lock_decision now engages on marketability into the band edge, tests the
phase-appropriate instant (continuous low/high, ATO open, ATC close), and grades
from the interval's OHLC+volume: traded-through -> passthrough (policy fills),
collapse+zero-volume -> NO_FILL, collapse+volume -> passthrough (policy floor),
no signal -> INDETERMINATE. Wired into the auction-only dispatch branch too.
Replaces Increment 1's close==band proxy (which over-asserted ~10x).

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Re-green the Jx scenarios and prove behaviour-preserving

**Files:**
- Modify: `scenarios/test_j2_limit_up_lock.py`, `scenarios/test_j11_floor_lock_exit.py`, `scenarios/test_j10_naive_vs_plutus.py`.

**Interfaces:**
- Consumes: `band_lock_decision`'s new contract from Task 1 (collapse+vol==0 → NO_FILL; traded-through → fill).
- Produces: green `scenarios` + `tests/market` suites; a J2 traded-through variant that documents the fixed over-assertion.

### Context

J2/J11/J10 were migrated in Increment 1 to "Accepted + rests + no-fill". Their fixtures previously relied on the `close==band` proxy. Under Task 1 the outcome now depends on the **full bar**: a bar with `close==ceiling` but `low<ceiling` (or unknown volume) no longer produces a `NO_FILL`. The scenarios that intend a **true lock** must feed a collapsed, zero-volume bar; J2's own docstring already flags HPG 2022-11-16 as a *traded-through* day ("allowed some fills"), so it is the natural traded-through variant.

- [ ] **Step 1: Read the three scenarios and locate the band bar each asserts on**

Run: `sed -n '1,140p' scenarios/test_j2_limit_up_lock.py` (repeat for j11, j10). Identify whether each uses the live corpus via `ExchangeSession`/`DataHubSource` (J2 does — HPG 2022-11-16) or a hand-built interval.

- [ ] **Step 2: Make the "true lock" assertions rest on a collapsed zero-volume bar**

For each scenario that must remain `NO_FILL`:
- If it hand-builds the interval/state: set `open==high==low==close==ceiling` (buy lock) or `==floor` (sell lock) and `volume=0`.
- If it reads the live corpus: pick a ticker-day that is a genuine full-session lock, or assert the **new** truthful outcome. For J2 (HPG 2022-11-16, which traded through), split into two assertions:
  - the at-ceiling order on the **traded-through** day now **fills** (or is sized/indeterminate per the `soft` policy) — the corrected behaviour;
  - add a true-lock ticker-day (from the audit set, e.g. DAN 2022-01-04) asserting `NO_FILL` with `BAND_LOCK` in the reason.

Keep every QĐ 352 Điều 9 / rulebook citation comment intact; only the fixture bar and the expected outcome change.

- [ ] **Step 3: Run the scenarios**

Run: `python -m pytest scenarios/test_j2_limit_up_lock.py scenarios/test_j11_floor_lock_exit.py scenarios/test_j10_naive_vs_plutus.py -q`
Expected: all pass. Each must call `advance_to` past the lock day so the fill decision is actually evaluated (non-vacuous), as established in Increment 1.

- [ ] **Step 4: Full market + scenario regression (the behaviour-preserving gate)**

Run: `python -m pytest tests/market scenarios -q`
Expected: **0 failed** on the real corpus. Investigate any failure: a *non-band* fill/margin/admission test that moved is a real regression and must be fixed in code, not by editing the test; a *band* test that moved should match Task 1's contract.

- [ ] **Step 5: Commit**

```bash
git add scenarios/test_j2_limit_up_lock.py scenarios/test_j11_floor_lock_exit.py scenarios/test_j10_naive_vs_plutus.py
git commit -m "Re-green Jx band-lock scenarios on the full-bar contract

True-lock scenarios now rest on a collapsed zero-volume bar (NO_FILL); J2 gains
a traded-through variant showing the at-ceiling order now fills, the corrected
over-assertion. Full tests/market + scenarios green on the real corpus.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Dense ask/bid book tier (rows B1–B3 / S1–S3)

**Files:**
- Modify: `src/plutus/market/session/fills.py` — prepend a book branch inside `band_lock_decision`; add a `_band_lock_by_book` helper.
- Test: `tests/market/session/test_band_lock_book_tier.py` (new).

**Interfaces:**
- Consumes: `interval.book` (a `plutus.market.protocol.OrderBook` with `.asks`/`.bids` tuples of `BookLevel(price, size)`), falling back to `interval.state.book`.
- Produces: the book tier takes precedence over the OHLC tier when a relevant-side book is present; daily intervals (no book) are unaffected, so Tasks 1/2 numbers do not move.

### Context

At tick resolution the interval can carry a resting ladder. A dense ask book is authoritative for a buy-into-ceiling: an ask **below** the ceiling means a buyer can cross now (B1 fill → passthrough); all asks **at/above** the ceiling (or none) with volume means matched-at-the-edge (B2 → policy); with zero volume means *trắng bên bán* (B3 → NO_FILL). Sizes are always `None` on this corpus (`BookLevel.size`), so the tier reads **prices** only. The book branch runs before the OHLC branch and only when the relevant side of the book is non-empty; otherwise the resolver falls through to Task 1's OHLC tier.

- [ ] **Step 1: Write the failing book-tier tests**

Create `tests/market/session/test_band_lock_book_tier.py`:

```python
"""Dense ask/bid book tier of band_lock_decision (rows B1-B3 / S1-S3)."""
from datetime import datetime
from decimal import Decimal

from plutus.market.protocol import (BookLevel, MarketState, Order, OrderBook,
                                    OrderType, Resolution, SessionPhase, Side)
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (FillOutcome, MarketInterval,
                                         OrderRecord, OrderState, TimeInForce,
                                         Venue)

CEIL = Decimal("13.35")
FLOOR = Decimal("11.65")


def _order(side, price):
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=datetime(2022, 11, 16),
        updated_at=datetime(2022, 11, 16), fills=(),
        order=Order(ticker="HPG", side=side, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=price))


def _interval(*, asks=(), bids=(), volume=None):
    book = OrderBook(asks=tuple(BookLevel(price=p) for p in asks),
                     bids=tuple(BookLevel(price=p) for p in bids),
                     as_of=datetime(2022, 11, 16))
    state = MarketState(ticker="HPG", ts=datetime(2022, 11, 16),
                        ceiling=CEIL, floor=FLOOR, last=CEIL,
                        session=SessionPhase.CONTINUOUS, book=book)
    return MarketInterval(ticker="HPG", start=datetime(2022, 11, 16),
                          end=datetime(2022, 11, 17), resolution=Resolution.TICK,
                          state=state, close=CEIL, volume=volume, book=book)


def test_b1_ask_below_ceiling_is_passthrough():
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[Decimal("13.30")], volume=100))
    assert d is None


def test_b3_all_asks_at_or_above_ceiling_zero_volume_is_no_fill():
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[CEIL], bids=[CEIL], volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b3_locked_ladder_absent_volume_is_no_fill():
    # option B (2026-09-11): a locked ask ladder with no volume figure is still
    # trắng bên bán -- the empty offer side is the direct evidence.
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[CEIL], bids=[CEIL], volume=None))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
    assert "BAND_LOCK" in d.reason


def test_b2_asks_at_ceiling_with_volume_is_passthrough_to_policy():
    d = band_lock_decision(_order(Side.BUY, CEIL),
                           _interval(asks=[CEIL], bids=[CEIL], volume=200))
    assert d is None


def test_s1_bid_above_floor_is_passthrough():
    d = band_lock_decision(_order(Side.SELL, FLOOR),
                           _interval(bids=[Decimal("11.70")], volume=100))
    assert d is None


def test_s3_all_bids_at_or_below_floor_zero_volume_is_no_fill():
    d = band_lock_decision(_order(Side.SELL, FLOOR),
                           _interval(bids=[FLOOR], asks=[FLOOR], volume=0))
    assert d is not None and d.outcome is FillOutcome.NO_FILL
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/market/session/test_band_lock_book_tier.py -q`
Expected: `test_b1`/`test_s1` may already pass (a book with an ask below the ceiling — but Task 1's OHLC path sees `low`/`high` unset → INDETERMINATE, so `test_b1` currently fails with INDETERMINATE, not None). Confirms the book tier is needed.

- [ ] **Step 3: Add the book helper and prepend the book branch**

In `src/plutus/market/session/fills.py`, add next to the other band-lock helpers:

```python
def _band_lock_by_book(side: Side, edge: Decimal, book,
                       volume: Optional[int]) -> Optional[FillDecision]:
    """The dense-book tier (rows B1-B3 / S1-S3), or ``None`` to fall through.

    Prices only -- ``BookLevel.size`` is ``None`` on every corpus here. An ask
    below the ceiling (bid above the floor) means the order can cross now, a
    passthrough. Otherwise the offer side below the edge is empty: ``volume > 0``
    means the edge was still matched at (the ASSUMED tier the policy floor
    decides), while zero *or absent* volume is trắng bên bán -- a proven no-fill
    (option B, 2026-09-11: the empty offer ladder is the direct evidence, just
    as the OHLC collapse is at daily resolution). Returns ``None`` when the
    relevant side of the book is empty, so the caller falls to the OHLC tier.
    """
    levels = book.asks if side is Side.BUY else book.bids
    if not levels:
        return None
    crossable = (any(l.price < edge for l in levels) if side is Side.BUY
                 else any(l.price > edge for l in levels))
    if crossable:
        return _PASSTHROUGH   # B1/S1: an order can cross -> the policy fills
    if volume is not None and volume > 0:
        return _PASSTHROUGH   # B2/S2: matched at the edge -> the policy floor
    # B3/S3: locked ladder, nothing on offer below the edge, no trade recorded.
    return FillDecision.no_fill(
        f'BAND_LOCK: {side.value} into a {edge} lock; the resting '
        f'{"ask" if side is Side.BUY else "bid"} ladder is entirely at or '
        f'past the edge with no trade recorded (trắng bên '
        f'{"bán" if side is Side.BUY else "mua"})')
```

Add a module-level sentinel near the band-lock section (a distinct object so "passthrough decided by the book" is not confused with "book tier not applicable / `None`"):

```python
#: Sentinel: the book tier decided "defer to the ordinary path". Distinct from
#: ``None`` (book tier not applicable), so band_lock_decision can tell "the book
#: says pass through" from "no book -- try the OHLC tier".
_PASSTHROUGH = object()
```

Then, in `band_lock_decision`, immediately after the `_marketable_into` guard and before `instant, field = _lock_instant(...)`, insert:

```python
    book = interval.book if interval.book is not None else interval.state.book
    if book is not None:
        by_book = _band_lock_by_book(side, edge, book, interval.volume)
        if by_book is not None:
            return None if by_book is _PASSTHROUGH else by_book
```

- [ ] **Step 4: Run the book-tier and daily suites**

Run: `python -m pytest tests/market/session/test_band_lock_book_tier.py tests/market/session/test_band_lock_fill.py -q`
Expected: all pass. The daily tests still pass because they build intervals with `book=None`.

- [ ] **Step 5: Full market regression**

Run: `python -m pytest tests/market -q`
Expected: 0 failed. (Tick-resolution fill tests that carry a book may now route through the book tier; confirm any change matches B1-B3/S1-S3.)

- [ ] **Step 6: Commit**

```bash
git add src/plutus/market/session/fills.py tests/market/session/test_band_lock_book_tier.py
git commit -m "Add the dense ask/bid book tier to band_lock_decision (B1-B3/S1-S3)

Where the interval carries a resting ladder, an ask below the ceiling (bid above
the floor) is a crossable passthrough; an all-at-or-past-the-edge ladder with
zero volume is a proven no-fill, with volume the policy floor decides. Prices
only (sizes are None on this corpus). Daily intervals (no book) are unaffected.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: Policy-floor (ASSUMED tier) end-to-end tests

**Files:**
- Test: `tests/market/session/test_band_lock_policy_floor.py` (new). No production change expected.

**Interfaces:**
- Consumes: `SoftFillPolicy`, `HardFillPolicy`, `ProbabilisticFillPolicy` `.evaluate(order, interval, rules, ...)`, an `Exchange` (HSX rules) for the `rules` argument, `FillOutcome`.
- Produces: proof that a collapse+volume>0 band bar (which `band_lock_decision` passes through) is resolved by the policy floor exactly as the design's table 1c requires — soft fills at the edge, hard is INDETERMINATE, probabilistic draws.

### Context

Rows B6/S6 (and B2/S2) return `None` from the resolver, deferring to the ordinary continuous path. The design (§1c) requires that path to reproduce the policy-as-floor semantics: `soft` fills a touch at the edge, `hard` returns INDETERMINATE on a touch (`FILL_UNOBSERVABLE_AT_RESOLUTION`), `probabilistic` draws. This task proves the seam end-to-end so a future refactor cannot silently break it.

- [ ] **Step 1: Write the end-to-end policy-floor tests**

Create `tests/market/session/test_band_lock_policy_floor.py`. Build a real HSX `Exchange`, a collapsed-at-ceiling bar with `volume>0`, a `LIMIT` buy at the ceiling, and assert each policy's outcome through `.evaluate(...)`:

```python
"""The ASSUMED band-lock tier resolves through the fill policy floor (table 1c).

A collapse+volume>0 band bar is passed through by band_lock_decision, so the
active policy decides: soft fills at the edge, hard is INDETERMINATE (time
priority unrecoverable), probabilistic draws with its p.
"""
from datetime import datetime
from decimal import Decimal

from plutus.market.exchanges.equity import HSX_EXCHANGE
from plutus.market.protocol import (MarketState, Order, OrderType, Resolution,
                                    SessionPhase, Side)
from plutus.market.session.fills import (HardFillPolicy, ProbabilisticFillPolicy,
                                         SoftFillPolicy)
from plutus.market.session.types import (FillOutcome, MarketInterval,
                                         OrderRecord, OrderState, TimeInForce,
                                         Venue)

CEIL = Decimal("13.35")


def _order():
    return OrderRecord(
        order_id="o1", venue=Venue.HSX, state=OrderState.RESTING,
        time_in_force=TimeInForce.DAY, submitted_at=datetime(2022, 1, 4),
        updated_at=datetime(2022, 1, 4), fills=(),
        order=Order(ticker="HPG", side=Side.BUY, quantity=1000,
                    order_type=OrderType.LIMIT, limit_price=CEIL))


def _collapsed_bar():
    state = MarketState(ticker="HPG", ts=datetime(2022, 1, 4), ceiling=CEIL,
                        floor=Decimal("11.65"), last=CEIL,
                        session=SessionPhase.CONTINUOUS)
    return MarketInterval(ticker="HPG", start=datetime(2022, 1, 4),
                          end=datetime(2022, 1, 5), resolution=Resolution.DAILY,
                          state=state, open=CEIL, high=CEIL, low=CEIL,
                          close=CEIL, volume=7000)


def test_soft_fills_the_assumed_band_lock_at_the_edge():
    d = SoftFillPolicy().evaluate(_order(), _collapsed_bar(), HSX_EXCHANGE)
    assert d.outcome is FillOutcome.FILL and d.price == CEIL


def test_hard_is_indeterminate_on_the_assumed_band_lock():
    d = HardFillPolicy().evaluate(_order(), _collapsed_bar(), HSX_EXCHANGE)
    assert d.outcome is FillOutcome.INDETERMINATE


def test_probabilistic_draws_on_the_assumed_band_lock():
    # seed positional; max_participation keyword-required; p_touch=1 always fills
    pol = ProbabilisticFillPolicy(1, max_participation=None, p_touch=Decimal("1"))
    d = pol.evaluate(_order(), _collapsed_bar(), HSX_EXCHANGE)
    assert d.outcome is FillOutcome.FILL   # grade is MODELLED
```

`HSX_EXCHANGE` is the pre-built HSX `EquityExchange` instance the fill tests already use as the `rules` argument (`from plutus.market.exchanges.equity import HSX_EXCHANGE`). `ProbabilisticFillPolicy(seed, *, max_participation, p_touch=Decimal('0.5'), ...)` — `seed` positional-required, `max_participation` keyword-required.

- [ ] **Step 2: Run to green**

Run: `python -m pytest tests/market/session/test_band_lock_policy_floor.py -q`
Expected: all pass. If `hard` returns something other than INDETERMINATE, verify the bar is a *touch* (`high==low==ceiling==limit`, so the extreme toward the buy equals the limit) and that no participation-cap INDETERMINATE is masking the touch INDETERMINATE — either is an acceptable INDETERMINATE for the assertion, but document which in a comment.

- [ ] **Step 3: Commit**

```bash
git add tests/market/session/test_band_lock_policy_floor.py
git commit -m "Prove the ASSUMED band-lock tier resolves through the policy floor

End-to-end: a collapse+volume band bar passes through band_lock_decision and the
active policy decides -- soft fills at the edge, hard is INDETERMINATE, prob
draws (table 1c). Locks the seam so a refactor cannot silently break it.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: Regenerate the SmartBeta null-anchor + Tier-1 recount + registry before/after

**Files:**
- Modify: `proto/ProtoSmartBeta/src/proto_smart_beta/experiments/null_anchor.py` (branch `rivf-2026`).
- Modify: `docs/reference/tables/experiments_registry.md` (in `plutus`).

**Interfaces:**
- Consumes: `PlutusBackend` (`.submit`, `.advance_to`, `.cash`, `.holdings`, `PlutusBackend.fills(events)`), `DataHubSource.state_at(ticker, day)` (for the band-edge classification), the Task 1 resolver (behaviour change is automatic — no proto import change).
- Produces: the regenerated faithful numbers (gap toward naive), a Tier-1 count of fill-time band-lock no-fills, and the registry row's before/after.

### Context

The runner's `refusals`/`indeterminates` counters (`null_anchor.py:109-110`) only tally **`Rejected` acks at submit**. Since Increment 1, band-locked orders are `Accepted`, so they vanished from the counters. A definite fill-time band-lock `NO_FILL` leaves the order **RESTING and emits no event** (REST is the one silent transition), so it cannot be counted from `advance_to` events. Classify it instead: an order that was `Accepted`, produced **no fill** over its rebalance window, on a **band-edge day** (`state_at(...).locked_side is not None`) under the `soft` policy is a band-lock no-fill. Task 1's resolver makes the traded-through majority fill, so this count drops sharply from Increment 1's 45.

- [ ] **Step 1: Read the runner and confirm the fill-event/order-id surface**

Run (from `proto/ProtoSmartBeta`): `sed -n '90,160p' src/proto_smart_beta/experiments/null_anchor.py` and `python -c "from plutus.market.session.types import Fill; print([f.name for f in __import__('dataclasses').fields(Fill)])"` to confirm a fill event/`Fill` carries `order_id`. This is how "which Accepted orders filled" is known.

- [ ] **Step 2: Add a band-lock no-fill classifier to the faithful arm**

In `_faithful`, track submitted-order ids and their band-edge day, then after each rebalance window subtract the ids that appeared in a fill event. Concretely: give `submit(...)` a record of `(order_id, ticker, day, locked_side)` for each `Accepted` marketable order whose `source.state_at(ticker, day)` has `locked_side is not None`; after the rebalance `advance_to(... CLOSE_MARK)`, collect filled order ids from `PlutusBackend.fills(events)`; any recorded id **not** in the filled set is a fill-time band-lock no-fill. Accumulate into a `band_lock_no_fills` counter and return it alongside `fills`/`refusals`. Keep the change small and reversible; do not alter the sizing/advance logic.

- [ ] **Step 3: Regenerate the experiment**

Run (from `proto/ProtoSmartBeta`, branch `rivf-2026`, its `.venv` active):
```bash
python -m proto_smart_beta.experiments.extract_market      # refresh the frozen slice if needed
python -m proto_smart_beta.experiments.null_anchor > /tmp/sb_inc2.json
```
Expected shape: `naive.sharpe` unchanged at **−0.3497**; `faithful.sharpe` **moves up toward naive** from Increment 1's −0.5543 (most of the 45 band-locks were traded-through days that now fill); `faithful.band_lock_no_fills` a small residual (the genuine full-session locks). Record the actual numbers from the JSON — do not invent them.

- [ ] **Step 4: Run the SB regression test**

Run: `python -m pytest tests/test_regression_baseline.py -q`
Expected: the **naive** IS/OOS assertions still hold (naive is untouched). If a committed faithful expectation exists and moved, update it to the regenerated value with a one-line note that Increment 2 shrank the gap.

- [ ] **Step 5: Update the registry with before/after**

In `docs/reference/tables/experiments_registry.md`, in the SB block, update the metric table and Tier-1 paragraph to the regenerated numbers, and rewrite the "Increment 1 note" into an "Increment 2 note" recording: faithful Sharpe before (−0.5543) → after (measured); band-lock no-fills 45 → measured residual; the mechanism (traded-through days now fill, only full-session zero-volume locks remain no-fill). Keep the provenance/regenerate block's two commands.

- [ ] **Step 6: Commit (two repos)**

In `proto/ProtoSmartBeta`:
```bash
git add src/proto_smart_beta/experiments/null_anchor.py
git commit -m "Recount fill-time band-lock no-fills; regenerate under Increment 2

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```
In `plutus`:
```bash
git add docs/reference/tables/experiments_registry.md
git commit -m "Register the SB null-anchor before/after for band-lock Increment 2

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: The owner sign-off audit script

**Files:**
- Create: `measurements/band_lock_ladder_audit.py` (in `plutus`).

**Interfaces:**
- Consumes: `DataHubSource.for_root(root)`, `.interval(ticker, start, end)` / `.state_at(...)`, `band_lock_decision`, `Order`/`OrderRecord`.
- Produces: a printed table — per case: raw evidence (band, OHLC, volume, book) → resolver tier + FEL/outcome — for the owner's final correctness check (design §4d).

### Context

The design names concrete cases: **A** true lock (e.g. DAN 2022-01-04), **B** traded-through (DMN 2022-01-06), **D** ATO-lock (NXT 2022-01-27), a dense-book example (tick), and an UNKNOWN/data-gap example. The script must run against a data root that contains them — the SB frozen slice covers the OOS universe only, so default to the broader corpus root (the `stock_quote_12.2020-09.2024` parquet or the algotradeDB-derived slice); accept `--root`.

- [ ] **Step 1: Write the audit script**

Create `measurements/band_lock_ladder_audit.py` that, for each case `(ticker, day, side, order_type)`, builds the daily interval via `DataHubSource.interval`, constructs a marketable order at the edge, calls `band_lock_decision`, and prints: `ticker day | ceiling floor | O H L C vol | book? | -> outcome (reason)`. Parametrize the case list at the top so the owner can add rows. Skeleton:

```python
"""Band-lock ladder audit — concrete ticker-days through band_lock_decision.

Prints, per case, the raw evidence and the resolver's verdict, for the owner's
final correctness sign-off (design section 4d). Run:

    python measurements/band_lock_ladder_audit.py --root <corpus-or-slice-root>
"""
import argparse
from datetime import datetime, timedelta
from decimal import Decimal

from plutus.market.adapters.datahub import DataHubSource
from plutus.market.protocol import Order, OrderType, Side
from plutus.market.session.fills import band_lock_decision
from plutus.market.session.types import (OrderRecord, OrderState, TimeInForce,
                                         Venue)

CASES = [   # (label, ticker, YYYY-MM-DD, side, order_type)
    ("A true lock",     "DAN", "2022-01-04", Side.BUY,  OrderType.LIMIT),
    ("B traded-through","DMN", "2022-01-06", Side.BUY,  OrderType.LIMIT),
    ("D ATO lock",      "NXT", "2022-01-27", Side.BUY,  OrderType.AT_THE_OPENING),
]


def _order(ticker, day, side, order_type, edge):
    price = None if order_type in (OrderType.AT_THE_OPENING, OrderType.AT_THE_CLOSE) else edge
    tif = (TimeInForce.AUCTION_ONLY
           if order_type in (OrderType.AT_THE_OPENING, OrderType.AT_THE_CLOSE) else TimeInForce.DAY)
    return OrderRecord(order_id="audit", venue=Venue.HSX,
                       state=OrderState.RESTING, time_in_force=tif,
                       submitted_at=datetime.fromisoformat(day),
                       updated_at=datetime.fromisoformat(day), fills=(),
                       order=Order(ticker=ticker, side=side, quantity=1000,
                                   order_type=order_type, limit_price=price))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True)
    args = ap.parse_args()
    src = DataHubSource.for_root(args.root)
    for label, ticker, day, side, ot in CASES:
        d0 = datetime.fromisoformat(day)
        iv = src.interval(ticker, d0, d0 + timedelta(days=1))
        if iv is None:
            print(f"[{label}] {ticker} {day}: NO BAR in root")
            continue
        edge = iv.state.ceiling if side is Side.BUY else iv.state.floor
        decision = band_lock_decision(_order(ticker, day, side, ot, edge), iv)
        verdict = "PASSTHROUGH (policy fills)" if decision is None else (
            f"{decision.outcome.value}: {decision.reason}")
        print(f"[{label}] {ticker} {day} {side.value} {ot.value}")
        print(f"    band  ceil={iv.state.ceiling} floor={iv.state.floor}")
        print(f"    ohlc  O={iv.open} H={iv.high} L={iv.low} C={iv.close} "
              f"vol={iv.volume} book={'yes' if iv.book else 'no'}")
        print(f"    -->   {verdict}\n")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the audit and capture output**

Run: `python measurements/band_lock_ladder_audit.py --root <the corpus/slice root>`
Save the output to `/tmp/band_lock_audit.txt`. If a named ticker-day is absent from the chosen root, substitute a verified equivalent from the same period (a true full-session lock, a traded-through close-at-band day, an ATO-lock day) and note the substitution in a comment in `CASES`.

- [ ] **Step 3: Sanity-check each verdict against the raw evidence**

For each printed case confirm the verdict matches the ladder: A → `no_fill` (collapse, vol 0); B → `PASSTHROUGH` (low < ceiling); D → `no_fill` for the ATO (open == ceiling, no opening trade). A mismatch is a resolver bug — fix in Task 1's code and re-run, do not paper over it here.

- [ ] **Step 4: Commit**

```bash
git add measurements/band_lock_ladder_audit.py
git commit -m "Add the band-lock ladder audit for owner sign-off (design 4d)

Prints concrete ticker-days (true lock / traded-through / ATO lock) through
band_lock_decision with their raw evidence and verdict.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

> **Do not proceed past this task without surfacing the audit output to the owner** — the design explicitly requires the owner's sign-off on the ladder cases. The executing skill should pause here and present `/tmp/band_lock_audit.txt`.

---

## Task 7: Documentation reconciliation + audit-finding record

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md`.
- Create: `measurements/band_lock_ladder_audit_output.txt` (the committed snapshot of the audit run, so the finding is referenceable without a live corpus).
- Modify: `docs/reference/tables/experiments_registry.md` (a short cross-reference to the audit finding).

**Interfaces:** none (docs only). All the exact numbers below come from the Task 6 audit (`measurements/band_lock_ladder_audit.py`, owner-signed-off 2026-09-14); copy them verbatim.

- [ ] **Step 1: Reconcile §2 (no MarketState change)**

Add a dated note to Section 2 recording that Increment 2 did **not** add open/high/low/volume to `MarketState`: `MarketInterval` already carries and populates them (via `DataHubSource.interval` → `_ohlc` + the volume join), the resolver takes the interval, and the `MarketInterval` docstring warns against a second copy on the snapshot. `locked_side`/`lock_evidence`/`BAR_PROXY` stay on `MarketState` because `derivatives.py` and the adapter tests consume them; the resolver simply no longer depends on them.

- [ ] **Step 2: Reconcile the §1 ladder for the owner's option-B decision (2026-09-11)**

Update the §1a/§1b tables and §1c prose so they match the shipped resolver: the corpus never stores a literal `volume==0` (a no-trade day is an **absent** row), so **B5/S5 fire on collapse + zero-OR-absent volume → NO_FILL** (trắng bên bán); **B7/S7 (INDETERMINATE) now means the phase instant itself is absent** (no OHLC to test against the edge), not "volume unknown". Note this was the owner's option-B call: the OHLC collapse is the evidence, so an absent volume row on a collapsed bar is the no-trade fact, not ignorance.

- [ ] **Step 3: Record the audit finding in §4d (the whole point of the audit)**

Replace §4d's hypothetical case list with the **measured** result. Copy these verbatim from the Task 6 report:
- A full-corpus scan of genuine full-session collapses (`open==high==low==close==ceiling`, over 2021-02-05..2022-12-30): **8,611** buy-side candidates; **8,610 (99.99%)** carry positive `quote_dailyvolume` → the **ASSUMED** tier (passthrough → the policy floor decides), and **1 (0.01%)** has absent volume → the proven `NO_FILL`. Literal `volume==0`: **0** (confirmed `MIN(quantity)=1` over 2,562,664 rows).
- Sell-side floor collapses: 5,535 candidates, **183 absent-volume — all the same single ticker (PTG)**. ATO-only locks: 15,903 candidates, **1 absent — the same PTG day**.
- The one proven-`NO_FILL` name, **PTG** (2021-02-17 buy, 2021-05-28 sell), is a dormant UPCOM penny stock with almost no recorded trading — not a name squeezed to its limit by real pressure.
- The verified over-assertion fix: **DMN 2022-01-06** closed at its ceiling but traded up from 12.7 intraday (`low < ceiling`) → passthrough/fills (Increment 1's `close==band` proxy wrongly called it a lock).
- The daily-volume coarsening on the ATO instant: **NXT 2022-01-27** is a real ATO-lock candidate (`open==ceiling`) but its day volume (4,900) is positive because the price fell later, so the ATO test lands on ASSUMED/passthrough, not NO_FILL — the daily figure can't isolate the opening cross.
- The data-gap case: **CFPT2010 2021-02-17** (LOW absent) → INDETERMINATE.
- The design's originally-named DAN 2022-01-04 was **wrong** (UPCOM, volume 1800 → ASSUMED); it was replaced.
- Point §4d at the committed script `measurements/band_lock_ladder_audit.py` and the snapshot `measurements/band_lock_ladder_audit_output.txt` as the regenerable evidence. **No resolver bug was found; every verdict matches the §1 ladder.**

- [ ] **Step 4: Add the §4e paper-impact framing**

Rewrite §4e to the measured reality: at **daily** resolution a band lock is **ASSUMED-dominant** — it makes the fill *policy-dependent* (soft fills, hard is INDETERMINATE), and is a *proven* no-fill only with the tick/auction-volume evidence the daily corpus lacks (≈99.99% ASSUMED). So the "band **refuses the fill**" proven-no-fill demonstration is a **tick-resolution phenomenon for the Grid/Pair phases** (whose book tier B1-B3/S1-S3 can observe the empty offer side directly), not an SB one — consistent with SB's null-anchor `band_lock_no_fills = 0`. Keep: FEL distribution now includes fill-time band-lock; threats-to-validity notes the session-daily volume coarsening.

- [ ] **Step 5: Snapshot the audit output + cross-reference from the registry**

Save the Task 6 audit run to `measurements/band_lock_ladder_audit_output.txt` (regenerate it: `python measurements/band_lock_ladder_audit.py --root /Users/dan/dataset/hermes-parquet > measurements/band_lock_ladder_audit_output.txt`, or copy `/tmp/band_lock_audit.txt` if still present). In `experiments_registry.md`, add one line to the SB block (or a short "Band-lock audit" note) pointing to the script + snapshot and stating the headline (≈99.99% of real full-session locks are ASSUMED at daily resolution; the proven no-fill is a tick-resolution effect).

- [ ] **Step 6: Mark the Increment-2 acceptance criteria**

In the design doc's "Acceptance criteria" / "Increment split" section, annotate criteria 1(full ladder), 4, 5, 7, 8 with their landing task/commit; note criterion 4 is met via `MarketInterval` (not `MarketState`), and that criterion 8's audit is owner-signed-off with the finding recorded in §4d.

- [ ] **Step 7: Commit**

```bash
git add docs/superpowers/specs/2026-09-10-band-lock-fillability-design.md measurements/band_lock_ladder_audit_output.txt docs/reference/tables/experiments_registry.md
git commit -m "Reconcile the band-lock design with the Increment 2 implementation + audit

MarketInterval already carried OHLC/volume (no MarketState change); §1 ladder
updated for option B (collapse + zero-or-absent volume -> NO_FILL); §4d records
the measured audit finding (99.99% of real full-session locks are ASSUMED at
daily resolution, proven NO_FILL is a tick-resolution effect) with a committed
output snapshot; §4e reframed; criteria 1(full)/4/5/7/8 marked met.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Acceptance criteria (Increment 2)

1. `band_lock_decision` grades the full daily ladder (B4–B7 / S4–S7) phase-aware (continuous/ATO/ATC), override-only, with all rows unit-tested. *(Task 1)*
2. The dense book tier (B1–B3 / S1–S3) grades where a ladder is present; daily is unaffected. *(Task 3)*
3. The ASSUMED tier resolves through the policy floor (soft fill / hard indeterminate / prob draw), proven end-to-end. *(Task 4)*
4. `tests/market` + `scenarios` are **0 failed** on the real corpus; Jx scenarios re-greened on the full-bar contract. *(Tasks 1, 2)*
5. No change to `MarketState`, the adapters, or `derivatives.py`. *(all)*
6. SB null-anchor regenerated: faithful gap shrinks toward naive; runner recounts fill-time band-lock no-fills; registry before/after recorded. *(Task 5)*
7. The audit script prints the per-rung cases and the owner has signed off. *(Task 6)*
8. The design doc reconciles §2 and marks the Increment-2 criteria. *(Task 7)*
