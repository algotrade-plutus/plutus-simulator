# ProtoMarketMaker (Phase 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor `proto/ProtoMarketMaker` (the VN30F1M/F2M inventory-skewed futures market-maker) so the **same quoting signal** runs against its own naive engine OR the faithful `PlutusBackend`, then run naive-vs-faithful over redated IS/OOS windows and emit the third point (SB → Grid → **MM**) of the execution-intensity spectrum into the experiments registry.

**Architecture:** Mirror the Phase-0 SmartBeta refactor task-for-task. Extract the pure quoting seam `quote(price, inventory, step) -> (bid, ask)` into a new `strategy.py` that both arms import; the requote **cadence** (15s / on-fill) is replicated in each arm — the naive engine keeps its loop, the faithful driver replays the same cadence against `PlutusBackend.advance_to` + **cancel/resubmit** (plutus refuses `amend` on a derivatives order, so requoting is cancel-and-replace). The faithful arm drives a `BookSessionSource` (daily bands + instrument from a `DataHubSource`, the L2 book from a `DepthSource`, the sized tape from a `TapeSource`) at TICK resolution under a `book_walk` + ConservativeQueue fill policy, an **account-level derivatives deposit** with dated VSD initial margin and real margin calls/forced-close, across the **KRX cutover** (2025-05-05) in OOS. One small shared plutus change: add `cancel`/`amend` pass-throughs to `PlutusBackend`.

**Tech Stack:** Python 3.12, uv + hatchling, DuckDB/pandas/pyarrow (data), `plutus` (`algotrade-plutus`, editable path dep), `plutus_verify`, pytest, psycopg2 (algotradeDB extract only).

## Global Constraints

- **Two repos, branch `rivf-2026`.** `proto/ProtoMarketMaker` is on `main` today — create/checkout `rivf-2026` (Task 2). `plutus` is already on `rivf-2026`. Per-task **local commits only**; do **not** push/PR (owner finalizes). Do **not** commit at the very end either — leave the tree for controller review (this is a controller-reviewed plan; the final registry/manifest task commits locally like the rest).
- **Same signals, two backends.** `strategy.py:quote()` runs once against both arms; naive vs faithful is a backend/cadence swap over one identical frozen data slice, so the delta is purely execution.
- **Behaviour-preserving naive anchor.** After the parquet + seam refactor, the naive engine reproduces its **currently published** metrics exactly (Task 3 regression gate on the existing committed data), before any redating. `plutus check` stays green under the naive engine.
- **Window redating (CONFIRMED):** **IS = 2022-01-01 → 2023-12-31, OOS = 2024-01-01 → 2025-06-30.** IS spans the **13%→17% margin change (2022-12-15)** and the **displayed-size era (≥2023-01-03)**; OOS crosses **KRX (2025-05-05)** with a ~2-month post-KRX tail and is entirely queue-era. This **abandons MM's original published anchor** (IS Sharpe 0.95) — the naive anchor re-runs on the new windows (Task 5).
- **The pure seam** is `quote(price: Decimal, inventory: int, step: Decimal) -> tuple[Decimal, Decimal]` — the two inventory-skew lines lifted verbatim from `backtest.update_bid_ask`, quantized to the 0.1 grid with `ROUND_HALF_UP`. No state inside it.
- **Roll stays in the SIGNAL.** MM's existing F1→F2 roll (`move_f1_to_f2`, 3rd-Thursday via `get_expired_dates`) is a signal input computed once; both arms trade the dated contracts it picks. Faithful roll/settlement fidelity is not a Phase-2 axis.
- **The one plutus change:** add `cancel(order_id)` + `amend(...)` pass-throughs to `PlutusBackend` (the session already implements them — `exchange.py:1612` / `:1641`). `amend` **refuses derivatives orders** by design, so the MM faithful driver requotes by **cancel + resubmit**; the `amend` pass-through exists for the shared seam (equity strategies).
- **Faithful fill policy:** headline `book_walk` + **ConservativeQueue** where displayed sizes exist (**≥2023-01-03**); **OptimisticQueue** is the documented fallback before (no sizes). Sensitivity spread = `soft` (uncapped) + ProbabilisticQueue. The pre-2023-01-03 no-size span produces genuine INDETERMINATEs under conservative — **report the rate as a finding**, do not paper over.
- **Faithful margin:** account-level `accounts.derivatives.initial_deposit` → `DerivativesAccount`, **dated VSD IM** via the rulebook (`vsd_initial_margin`: 13% <2022-12-15, 17% ≥2022-12-15), real call/forced-close via the `advance_to` mark. **NOT** the legacy per-position path. Contract multiplier resolves to the real **100,000 đồng/point** (`resolve_contract_multiplier`, VN30F).
- **Capital / multiplier reconciliation (CONFIRMED):** `initial_deposit` = MM naive capital `5e5` × 1000 = **500,000,000 đồng (5e8)** — thousand-đồng convention (as SB 25M→25B). MM's naive multiplier `100`/pt = real `100,000`/pt ÷ 1000. Both arms report Sharpe/HPR/MDD **scale-invariantly** so they compare directly; any absolute-đồng figure from the naive arm is ×1000. **Owner confirms the exact đồng figure right before the faithful run** (default 5e8; bump toward 7–8e8 if day-1 utilisation is too high).
- **Optimization = B-style (CONFIRMED):** keep the **cost-driven** `step` floor (`step` must exceed fee+slippage — a structural floor, same role as Grid's Δ); **DROP the Optuna-Sharpe objective**. Keep the representative `step` (=3.1) or a light sweep with a representative pick; report **activity** (fills / round-trips), not Sharpe. The `pmm-optimize` step stays (manifest completeness) with a non-P&L objective.
- **Proceed gate = ACTIVITY-based, pre-registered, NOT P&L (CONFIRMED, per memory `rivf26-fidelity-not-pnl`):** naive arm produces **≥ 300 completed round-trips** (a non-trivial fill count); faithful arm **completes without an UNBOUNDED margin-liquidation cascade** (bounded forced-closes OK). **No Sharpe/HPR stop-gate.**
- **Tier-1 counters (headline, sign-free):** (1) **queue-fill divergence** (book_walk conservative vs naive fills, incl. the pre-2023 no-size INDETERMINATE rate + the optimistic/probabilistic spread), (2) **dated-margin effect** (13%/17% contract affordability + refusals + MARGIN_CALL / FORCED_LIQUIDATION incidence), (3) **KRX-crossing indeterminates** (post-2025-05-05 unsourced-rule INDETERMINATEs). **Tier-2 (de-emphasized):** net P&L / Sharpe / MDD naive vs faithful, DAILY granularity.
- **Data creds — NEVER commit.** The L2 + naive extracts read algotradeDB (the same DB MM already uses) via a gitignored `.env` populated from the read-only cred at `$CRED_DIR/algotradeDB-readonly.json`. Do not read, echo, or commit the cred; `.env` stays in `.gitignore`. Large frozen slices ship via Drive (proto pattern), git-ignored.
- **Attribution** on every commit:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure

| Path (repo) | Create/Modify | Responsibility |
|---|---|---|
| `plutus:src/plutus/execution/backend.py` | Modify | Add `cancel` / `amend` pass-throughs to `PlutusBackend`. |
| `plutus:tests/execution/test_plutus_backend.py` | Modify | Cover cancel (Cancelled) + equity amend (Amended). |
| `MM:pyproject.toml` | Modify | py≥3.12; add `algotrade-plutus` editable path dep + duckdb/pyarrow/pytz; add `pmm-extract-l2` + `pmm-anchor` scripts. |
| `MM:.gitignore` | Modify/Create | `.venv/`, `data/`, `.env`, `__pycache__/`. |
| `MM:src/proto_market_maker/strategy.py` | Create | **Pure** `quote(price, inventory, step) -> (bid, ask)` — the shared seam. |
| `MM:src/proto_market_maker/data_loader.py` | Modify | Write parquet beside CSV (I/O site 1); redated windows. |
| `MM:src/proto_market_maker/backtest.py` | Modify | `process_data` reads parquet (I/O site 2); `update_bid_ask` calls `strategy.quote`. |
| `MM:src/proto_market_maker/config/config.py` | Modify | Redated IS/OOS window constants. |
| `MM:src/proto_market_maker/optimize.py` | Modify | Cost-driven `step` floor + activity report; drop Optuna-Sharpe. |
| `MM:src/proto_market_maker/experiments/__init__.py` | Create | Package marker. |
| `MM:src/proto_market_maker/experiments/extract_l2.py` | Create | Freeze L2 depth 1-3 + tape + futures daily bands → parquet. |
| `MM:src/proto_market_maker/experiments/mm_anchor.py` | Create | Naive-vs-faithful runner (mirror SB `null_anchor.py`); Tier-1/Tier-2. |
| `MM:parameter/backtesting_parameter.json` | Modify | Redated windows. |
| `MM:parameter/optimization_parameter.json` | Modify | Cost-driven sweep range. |
| `MM:parameter/optimized_parameter.json` | Modify | Representative `step`. |
| `MM:tests/test_strategy.py` | Create | Pure-seam tests. |
| `MM:tests/test_regression_baseline.py` | Create | Behaviour-preserving naive gate (old windows, then re-blessed to new). |
| `MM:tests/test_mm_anchor.py` | Create | Faithful-arm shape + naive exactness + activity gate. |
| `MM:.plutus/manifest.yaml` | Modify | Redated windows, re-blessed `expected`, py 3.12, reframed optimization. |
| `plutus:docs/reference/tables/experiments_registry.md` | Modify | Add the **MM** block after SB (extend SB/Grid). |

**Reference files to copy boilerplate from** (do not reinvent): `proto/ProtoSmartBeta/pyproject.toml` (the `[tool.uv.sources]` block), `proto/ProtoSmartBeta/tests/test_regression_baseline.py`, `proto/ProtoSmartBeta/src/proto_smart_beta/experiments/{extract_market,null_anchor}.py`, `proto/ProtoSmartBeta/tests/test_null_anchor.py`, `proto/ProtoSmartBeta/.plutus/manifest.yaml`, and the **SB block** in `plutus/docs/reference/tables/experiments_registry.md`.

---

## Task 1: [plutus] Add `cancel` / `amend` pass-throughs to `PlutusBackend`

**Files:**
- Modify: `plutus/src/plutus/execution/backend.py`
- Test: `plutus/tests/execution/test_plutus_backend.py`

**Interfaces:**
- Consumes: `ExchangeSession.cancel(order_id) -> Cancelled | Rejected` (`exchange.py:1612`), `ExchangeSession.amend(order_id, *, quantity=None, limit_price=None) -> Amended | Rejected` (`exchange.py:1641`). `amend` **refuses derivatives orders** (`exchange.py:1680-1684`).
- Produces: `PlutusBackend.cancel(order_id)` and `PlutusBackend.amend(order_id, *, quantity=None, limit_price=None)` — the maker requote seam the MM faithful driver (Task 8) calls with `ack.order_id` from a prior `submit`.

- [ ] **Step 1: Write the failing tests.** Append to `plutus/tests/execution/test_plutus_backend.py` (reuses the existing `BASE_CONFIG` / FPT 2022-11-09 fixtures at close 74.0):

```python
from plutus.market.session import Cancelled, Amended

def test_backend_cancels_a_resting_order():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    # a buy LIMIT below the 74.0 close is not marketable, so it rests
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("60.0")))
    assert isinstance(ack, Accepted)
    out = backend.cancel(ack.order_id)
    assert isinstance(out, Cancelled)
    assert out.cancelled_quantity == 1000

def test_backend_amends_a_resting_equity_order():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("60.0")))
    out = backend.amend(ack.order_id, quantity=500)
    assert isinstance(out, Amended)
```

- [ ] **Step 2: Run — fails.** Run: `cd plutus && python -m pytest tests/execution/test_plutus_backend.py -q`
Expected: FAIL — `AttributeError: 'PlutusBackend' object has no attribute 'cancel'`.

- [ ] **Step 3: Implement the pass-throughs.** In `plutus/src/plutus/execution/backend.py`, extend the imports and add two methods after `submit`:

```python
# extend the existing session import line:
from plutus.market.session import (ExchangeSession, Accepted, Rejected, Event,
                                    Cancelled, Amended, OrderId)
# add at top-level imports:
from decimal import Decimal
from typing import Optional
```

```python
    def cancel(self, order_id: OrderId) -> Union[Cancelled, Rejected]:
        """Cancel a resting order — the maker requote / risk-pull seam.

        A derivatives requote is cancel-and-resubmit (not amend): the session
        refuses a derivatives ``amend`` so the margin requirement is re-run on a
        fresh submit. Feed ``ack.order_id`` from the order's ``submit`` Accepted.
        """
        return self.session.cancel(order_id)

    def amend(self, order_id: OrderId, *, quantity: Optional[int] = None,
              limit_price: Optional[Decimal] = None) -> Union[Amended, Rejected]:
        """Amend a resting order in place (equity strategies).

        Re-runs admission and funding. Refused for derivatives orders by the
        session — cancel and resubmit there.
        """
        return self.session.amend(order_id, quantity=quantity,
                                  limit_price=limit_price)
```

- [ ] **Step 4: Run — passes.** Run: `cd plutus && python -m pytest tests/execution/test_plutus_backend.py -q`
Expected: PASS (all tests in the file, including the two new ones).

- [ ] **Step 5: Commit (plutus repo).**
```bash
cd plutus && git add src/plutus/execution/backend.py tests/execution/test_plutus_backend.py
git commit -m "Add cancel/amend pass-throughs to PlutusBackend (maker requote seam)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: [MM] Branch, plutus dependency, Python 3.12

**Files:** Modify `MM/pyproject.toml`, `MM/.gitignore` (create if absent); `git checkout -b rivf-2026`.

**Interfaces:** Produces an installable `proto_market_maker` importing `plutus`.

- [ ] **Step 1: Branch.** Run: `cd proto/ProtoMarketMaker && git checkout -b rivf-2026`.

- [ ] **Step 2: Wire the plutus dep + deps + scripts.** Edit `pyproject.toml`: bump `requires-python = ">=3.12"`; add to `dependencies` (mirror SB's block verbatim — read `proto/ProtoSmartBeta/pyproject.toml`):
```toml
    "algotrade-plutus",
    "duckdb>=1.0",
    "pyarrow>=12.0",
    "pytz",
```
add the `[tool.uv.sources]` block (copy from SB, same relative path — MM sits at the same depth):
```toml
[tool.uv.sources]
algotrade-plutus = { path = "../../plutus", editable = true }
```
and add two console scripts under `[project.scripts]`:
```toml
pmm-extract-l2 = "proto_market_maker.experiments.extract_l2:main"
pmm-anchor     = "proto_market_maker.experiments.mm_anchor:main"
```

- [ ] **Step 3: `.gitignore`.** Ensure it contains `.venv/`, `data/`, `.env`, `__pycache__/`, `result/`.

- [ ] **Step 4: Create the venv and verify the import.**
Run:
```bash
cd proto/ProtoMarketMaker && uv venv && uv pip install -e ../../plutus --no-deps \
  && uv pip install duckdb pandas pyarrow pytz numpy matplotlib optuna psycopg2-binary python-dotenv \
  && uv pip install -e . --no-deps
python -c "import proto_market_maker, plutus; from plutus.execution import PlutusBackend; from plutus.market.adapters.book_session import BookSessionSource; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit.**
```bash
git add pyproject.toml .gitignore && git commit -m "MM on rivf-2026: add plutus editable dep, py3.12, experiment scripts

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: [MM] Parquet-refactor the 2 I/O sites + behaviour-preserving regression gate

**Files:** Modify `data_loader.py`, `backtest.py`; Create `tests/test_regression_baseline.py`.

**Interfaces:**
- I/O site 1 — `data_loader.loading_bid_ask(...)` currently ends `is_data.to_csv(...)`. Add a parallel `.to_parquet(...)` write at the same path stem.
- I/O site 2 — `backtest.Backtesting.process_data(evaluation=False)` currently `pd.read_csv(f"{prefix}VN30F1M_data.csv")` / `VN30F2M_data.csv`. Switch to parquet, preferring `.parquet` when present.
- Produces: byte-identical strategy behaviour — the regression test pins it.

- [ ] **Step 1: Write the regression baseline test first** (mirror SB `tests/test_regression_baseline.py`). It pins the **currently published** IS/OOS numbers (this proves the parquet swap is value-lossless — before any redating). Use the values from `.plutus/manifest.yaml`'s `expected` (IS `sharpe_ratio` 0.9516979860670635, HPR 0.29926; OOS `sharpe_ratio` 0.08150478711107652, HPR 0.0802). Assert exactly:

```python
# tests/test_regression_baseline.py
"""Behaviour-preserving regression gate for the RIVF'26 MM refactor.

The parquet data layer and the strategy-seam extraction must not change the
strategy: with the naive engine the backtest reproduces the published,
full-precision Sharpe/HPR *exactly*. Skips cleanly without the data slice.
"""
import os
from decimal import Decimal

import numpy as np
import pytest

from proto_market_maker.backtest import Backtesting

HAS_IS = os.path.exists("data/is/VN30F1M_data.parquet") or os.path.exists("data/is/VN30F1M_data.csv")
HAS_OS = os.path.exists("data/os/VN30F1M_data.parquet") or os.path.exists("data/os/VN30F1M_data.csv")

# The published anchor (parameter/optimized_parameter.json step=3.1 for OOS;
# backtest.main() runs IS at step 1.8). These are the values in .plutus/manifest.yaml.
IS_STEP = Decimal("1.8")
OS_STEP = Decimal("3.1")


def _run(evaluation, step):
    bt = Backtesting(capital=Decimal("5e5"), printable=False)
    bt.run(bt.process_data(evaluation=evaluation), step)
    sharpe = float(bt.metric.sharpe_ratio(risk_free_return=Decimal("0.00023")) * Decimal(np.sqrt(250)))
    return sharpe, float(bt.metric.hpr())


@pytest.mark.skipif(not HAS_IS, reason="needs the in-sample slice under data/is")
def test_in_sample_reproduces_published_exactly():
    sharpe, hpr = _run(evaluation=False, step=IS_STEP)
    assert sharpe == 0.9516979860670635
    assert round(hpr, 5) == 0.29926


@pytest.mark.skipif(not HAS_OS, reason="needs the out-of-sample slice under data/os")
def test_out_of_sample_reproduces_published_exactly():
    sharpe, hpr = _run(evaluation=True, step=OS_STEP)
    assert sharpe == 0.08150478711107652
    assert round(hpr, 4) == 0.0802
```

- [ ] **Step 2: Run it against the CURRENT committed CSVs (pre-refactor) to capture the true baseline.** Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_regression_baseline.py -q` (with the current CSV loader still in place). Expected: PASS (or, if a value differs, **correct the asserted literal to the printed full-precision value now** — the point is exact reproduction, so pin whatever the current engine actually emits, then keep it fixed through the refactor).

- [ ] **Step 3: Add the parquet write** (I/O site 1). In `data_loader.loading_bid_ask`, after the `is_data.to_csv(...)` call, add a parquet write to the same stem:
```python
        parquet_path = (
            f"data/os/{contract_type}_data.parquet" if validation
            else f"data/is/{contract_type}_data.parquet"
        )
        is_data.to_parquet(parquet_path, index=False)
```

- [ ] **Step 4: Switch the reader to parquet-preferring** (I/O site 2). In `backtest.Backtesting.process_data`, replace the two `pd.read_csv(f"{prefix_path}VN30F1M_data.csv")` / `..F2M..` reads with a helper that prefers parquet:
```python
    @staticmethod
    def _read(prefix_path, contract):
        pq = f"{prefix_path}{contract}_data.parquet"
        if os.path.exists(pq):
            return pd.read_parquet(pq)
        return pd.read_csv(f"{prefix_path}{contract}_data.csv")
```
and call `f1_data = Backtesting._read(prefix_path, "VN30F1M")` / `f2_data = Backtesting._read(prefix_path, "VN30F2M")`. Keep every downstream line (the `round_decimal`, `pd.to_datetime`, `merge`, `ffill`) exactly as-is — parquet round-trips the CSV dtypes, but the `round_decimal` calls re-Decimalize regardless, so precision is preserved. (`os` is already imported in `backtest.py`.)

- [ ] **Step 5: Generate the parquet slices from the committed CSVs** (no DB needed — a pure format swap of the existing data). Run a one-off in the scratchpad:
```bash
cd proto/ProtoMarketMaker && python - <<'PY'
import pandas as pd, os
for sub in ("is", "os"):
    for c in ("VN30F1M", "VN30F2M"):
        csv = f"data/{sub}/{c}_data.csv"
        if os.path.exists(csv):
            pd.read_csv(csv).to_parquet(f"data/{sub}/{c}_data.parquet", index=False)
            print("wrote", f"data/{sub}/{c}_data.parquet")
PY
```

- [ ] **Step 6: Run the regression gate against parquet — must still be exact.** Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_regression_baseline.py -q`
Expected: PASS (both tests) — the parquet read reproduces the CSV baseline bit-for-bit. If any assert fails, the parquet conversion lost precision (design §12 risk) — **stop and fix the conversion** (e.g. keep the price columns as strings in the parquet), do not weaken the assert.

- [ ] **Step 7: Commit.**
```bash
git add src/proto_market_maker/data_loader.py src/proto_market_maker/backtest.py tests/test_regression_baseline.py
git commit -m "Parquet-refactor the 2 MM I/O sites; behaviour-preserving regression gate (exact)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: [MM] Extract the pure quoting seam `strategy.quote`

**Files:** Create `src/proto_market_maker/strategy.py`, `tests/test_strategy.py`; Modify `backtest.py`.

**Interfaces:**
- Produces: `quote(price: Decimal, inventory: int, step: Decimal) -> tuple[Decimal, Decimal]` — the shared signal both arms import.
- Consumes: called by `backtest.update_bid_ask` (naive) and `experiments/mm_anchor.py` (faithful, Task 8).

- [ ] **Step 1: Write the failing seam tests.**
```python
# tests/test_strategy.py
from decimal import Decimal
from proto_market_maker.strategy import quote

def test_quote_flat_inventory_is_symmetric_step_around_price():
    bid, ask = quote(Decimal("1000.0"), 0, Decimal("3.1"))
    assert bid == Decimal("996.9")    # price - step
    assert ask == Decimal("1003.1")   # price + step

def test_quote_long_inventory_skews_bid_down_ask_unchanged():
    # inv +5: bid = 1000 - 3.1*(5*0.02+1) = 1000 - 3.41 = 996.59 -> 996.6;
    # ask uses min(5,0)=0 -> 1000 - 3.1*(0-1) = 1003.1
    bid, ask = quote(Decimal("1000.0"), 5, Decimal("3.1"))
    assert bid == Decimal("996.6")
    assert ask == Decimal("1003.1")

def test_quote_short_inventory_skews_ask_down_bid_unchanged():
    # inv -5: bid uses max(-5,0)=0 -> 996.9; ask = 1000 - 3.1*(-5*0.02-1) = 1000-3.1*(-1.1)=1003.41 -> 1003.4
    bid, ask = quote(Decimal("1000.0"), -5, Decimal("3.1"))
    assert bid == Decimal("996.9")
    assert ask == Decimal("1003.4")
```

- [ ] **Step 2: Run — fails.** Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_strategy.py -q`
Expected: FAIL — `ModuleNotFoundError: proto_market_maker.strategy`.

- [ ] **Step 3: Implement the pure seam** — lift the two lines from `update_bid_ask` **verbatim** (the float intermediate `*0.02+1` inside `Decimal(...)` is load-bearing for exact reproduction; do not "clean it up"):
```python
# src/proto_market_maker/strategy.py
"""The pure quoting seam: inventory-skewed two-sided quotes.

Extracted verbatim from ``backtest.update_bid_ask`` so the naive engine and the
faithful Plutus driver quote from the identical function. The requote *cadence*
(15s / on-fill) is NOT here — it is each arm's own loop. This function is pure:
``inventory`` and ``step`` are inputs, so both arms produce the same quote for
the same (price, inventory, step).

    bid = (price - step) - step * max(inventory, 0) * 0.02
    ask = (price + step) - step * min(inventory, 0) * 0.02

Both are quantized to the 0.1 grid with ROUND_HALF_UP, exactly as the inline
engine did.
"""
from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP


def quote(price: Decimal, inventory: int, step: Decimal) -> tuple[Decimal, Decimal]:
    bid = (price - step * Decimal(max(inventory, 0) * 0.02 + 1)).quantize(
        Decimal("0.0"), rounding=ROUND_HALF_UP)
    ask = (price - step * Decimal(min(inventory, 0) * 0.02 - 1)).quantize(
        Decimal("0.0"), rounding=ROUND_HALF_UP)
    return bid, ask
```

- [ ] **Step 4: Run — passes.** Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_strategy.py -q`
Expected: PASS.

- [ ] **Step 5: Route the naive engine through the seam.** In `backtest.py`, add `from proto_market_maker.strategy import quote` and replace the two identical bid/ask assignment blocks inside `update_bid_ask` (the `if ... old_timestamp` branch and the `elif matched != 0` branch) with:
```python
            self.bid_price, self.ask_price = quote(price, self.inventory, step)
```
Leave the cadence logic (`self.old_timestamp = timestamp`, the `timedelta(seconds=...)` guard, the `elif matched != 0`) untouched — that is the naive arm's cadence.

- [ ] **Step 6: Regression gate must still be exact.** Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_regression_baseline.py tests/test_strategy.py -q`
Expected: PASS — the seam extraction changed structure, not behaviour.

- [ ] **Step 7: Commit.**
```bash
git add src/proto_market_maker/strategy.py src/proto_market_maker/backtest.py tests/test_strategy.py
git commit -m "Extract pure quote() seam; naive engine routes through it (behaviour-preserving)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: [MM] Redate the windows, re-extract, re-run the naive anchor, re-bless

**Files:** Modify `config/config.py`, `parameter/backtesting_parameter.json`; regenerates `data/is|os/*.parquet`; updates `tests/test_regression_baseline.py`.

**Interfaces:**
- Consumes: algotradeDB via gitignored `.env` (populate from the read-only cred — see Global Constraints; never commit).
- Produces: the redated naive data slice + the **new-window naive anchor** (the published number the paper quotes).

- [ ] **Step 1: Redate the window params.** Set `parameter/backtesting_parameter.json` to the confirmed windows:
```json
{
    "is_from_date_str": "2022-01-01 00:00:00",
    "is_end_date_str": "2023-12-31 00:00:00",
    "os_from_date_str": "2024-01-01 00:00:00",
    "os_end_date_str": "2025-06-30 00:00:00",
    "fee": "0.4",
    "time": "15"
}
```

- [ ] **Step 2: Populate `.env` from the read-only cred** (do NOT read/echo/commit the file). Create `proto/ProtoMarketMaker/.env` with the five keys `config.py` reads (`HOST`, `PORT`, `DATABASE`, `USER_DB`, `PASSWORD`) filled from `$CRED_DIR/algotradeDB-readonly.json`. Confirm `.env` is git-ignored (Task 2 Step 3).

- [ ] **Step 3: Re-extract the naive data over the redated windows.** Run: `cd proto/ProtoMarketMaker && uv run pmm-load-data`
Expected: writes `data/is/VN30F1M_data.{csv,parquet}`, `data/is/VN30F2M_data.{csv,parquet}`, and the `data/os/...` pair, now spanning 2022-01-01..2023-12-31 (IS) and 2024-01-01..2025-06-30 (OOS). If the extract is heavy, note the slice size for Drive.

- [ ] **Step 4: Re-run the naive anchor and capture the new full-precision numbers.** Run: `cd proto/ProtoMarketMaker && uv run pmm-backtest` (IS) and `uv run pmm-evaluate` (OOS, uses `optimized_parameter.json`). Record the printed Sharpe/Sortino/MDD/HPR/monthly/annual for both windows.

- [ ] **Step 5: Re-bless the regression baseline to the NEW-window numbers.** Update the four asserted literals in `tests/test_regression_baseline.py` (Task 3) to the values just recorded — these are now the published anchor. Keep the exactness (`==` on the full-precision Sharpe). Re-run: `python -m pytest tests/test_regression_baseline.py -q` → PASS.

- [ ] **Step 6: Commit** (data via Drive/gitignored; params + test committed).
```bash
git add parameter/backtesting_parameter.json tests/test_regression_baseline.py src/proto_market_maker/config/config.py
git commit -m "Redate MM to IS 2022-2023 / OOS 2024-2025H1; re-run + re-bless naive anchor

New windows span the 13->17% margin change, the >=2023-01-03 size era, and the
KRX 2025-05-05 cutover (OOS). Abandons the original IS Sharpe 0.95 anchor.

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: [MM] Reframe optimization — cost-driven `step` floor, drop Optuna-Sharpe

**Files:** Modify `optimize.py`, `parameter/optimization_parameter.json`, `parameter/optimized_parameter.json`.

**Interfaces:**
- Produces: `parameter/optimized_parameter.json` = `{"step": <representative>}` chosen for a **cost floor**, not Sharpe; `optimize.main()` writes it and reports **activity** (fills / round-trips), not a Sharpe objective.

- [ ] **Step 1: Replace the Optuna-Sharpe objective with a cost-driven floor + representative pick.** Rewrite `optimize.main()` so it (a) computes the structural floor `step_min` = round-trip cost in price points (`2 × fee + assumed slippage`, i.e. `2 × Decimal(BACKTESTING_CONFIG["fee"]) + slippage_ticks × tick`, where `fee` is in the naive per-point convention and one tick is `0.1`), (b) sweeps `step ∈ {step_min ... upper}` on the **IS slice only** in 0.1 increments, (c) records **fills and completed round-trips** per cell to `result/optimization/optimization.log.csv`, and (d) writes the **representative** `step` (the existing 3.1 if it clears the floor and sits in a stable activity region, else the smallest cell that clears the floor with non-trivial activity) to `parameter/optimized_parameter.json`. Drop the `optuna` import and `TPESampler`. Concretely:

```python
"""Optimization: cost-driven step floor + representative pick (activity, not Sharpe).

Per fidelity-not-pnl, MM is an execution-fidelity demonstrator; `step` is chosen
so the captured spread exceeds fee+slippage (a structural floor, same role as
Grid's Delta), NOT to maximize Sharpe. We report activity (fills / round-trips).
"""
import json
from decimal import Decimal
import pandas as pd

from proto_market_maker.config.config import BACKTESTING_CONFIG, OPTIMIZATION_CONFIG
from proto_market_maker.backtest import Backtesting

TICK = Decimal("0.1")
SLIPPAGE_TICKS = Decimal("1")


def step_floor() -> Decimal:
    """Smallest step whose one-way move clears round-trip fee + slippage."""
    fee_pts = Decimal(BACKTESTING_CONFIG["fee"])          # per-contract, naive points
    return (Decimal("2") * fee_pts + SLIPPAGE_TICKS * TICK)


def main():
    data = Backtesting.process_data()
    lo = max(step_floor(), Decimal(str(OPTIMIZATION_CONFIG["step"][0])))
    hi = Decimal(str(OPTIMIZATION_CONFIG["step"][1]))
    rows = []
    s = lo
    while s <= hi:
        bt = Backtesting(capital=Decimal("5e5"), printable=False)
        bt.run(data, s)
        fills = sum(1 for _ in bt.transactions) if bt.transactions else 0
        rows.append({"step": float(s), "fills": fills,
                     "days": len(bt.daily_returns)})
        s += Decimal("0.1")
    df = pd.DataFrame(rows)
    df.to_csv("result/optimization/optimization.log.csv", index=False)
    # representative pick: keep 3.1 if it clears the floor, else smallest cell
    # that clears the floor with non-trivial activity.
    default = Decimal("3.1")
    chosen = default if default >= lo else Decimal(str(df.iloc[0]["step"]))
    with open("parameter/optimized_parameter.json", "w", encoding="utf-8") as f:
        json.dump({"step": float(chosen)}, f, indent=4)
    print(f"step floor={lo}; chosen step={chosen}; activity written to "
          f"result/optimization/optimization.log.csv")


if __name__ == "__main__":
    main()
```
(If `bt.transactions` is not populated by the naive engine, count fills from `bt.daily_inventory` turnover instead — the point is an **activity** figure per cell, not P&L.)

- [ ] **Step 2: Widen the sweep floor in params** if needed. Set `parameter/optimization_parameter.json` `"step": [<floor-ish lower>, 5]` (keep `random_seed`/`no_trials` keys harmless or remove them — they are no longer used). Ensure `optimized_parameter.json` = `{"step": 3.1}`.

- [ ] **Step 3: Run it.** Run: `cd proto/ProtoMarketMaker && mkdir -p result/optimization && uv run pmm-optimize`
Expected: prints the floor + chosen step; writes `result/optimization/optimization.log.csv` with a `fills` column per step; `parameter/optimized_parameter.json` = `{"step": 3.1}`.

- [ ] **Step 4: Commit.**
```bash
git add src/proto_market_maker/optimize.py parameter/optimization_parameter.json parameter/optimized_parameter.json
git commit -m "Reframe optimization to cost-driven step floor + activity (drop Optuna-Sharpe)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: [MM] Freeze the L2 depth + tape + futures daily-band slice

**Files:** Create `src/proto_market_maker/experiments/__init__.py`, `src/proto_market_maker/experiments/extract_l2.py`, `tests/test_l2_slice_smoke.py`; writes `data/faithful/l2/*.parquet` and `data/faithful/daily/*.parquet`.

**Interfaces:**
- Consumes: algotradeDB via `.env` (same cred as Task 5); the futurecode→dated-`tickersymbol` map in `quote.futurecontractcode`; the redated windows.
- Produces: an L2 slice readable by `DepthSource("data/faithful/l2")` + `TapeSource("data/faithful/l2")`, and a daily slice readable by `DataHubSource.for_root("data/faithful/daily")`, composed by `BookSessionSource.for_roots(price_root="data/faithful/daily", book_root="data/faithful/l2")` (Task 8).

**Schema the faithful arm requires** (measured from `plutus/src/plutus/market/adapters/depth.py` + `tape.py`):

| File (prefix `local_quote`) | Columns |
|---|---|
| `local_quote_bidprice.parquet` | `datetime, tickersymbol, depth, price` |
| `local_quote_askprice.parquet` | `datetime, tickersymbol, depth, price` |
| `local_quote_bidsize.parquet` | `datetime, tickersymbol, depth, quantity` |
| `local_quote_asksize.parquet` | `datetime, tickersymbol, depth, quantity` |
| `local_quote_matched.parquet` | `datetime, tickersymbol, price` |
| `local_quote_total.parquet` | `datetime, tickersymbol, quantity` (cumulative) |

`tickersymbol` is the **dated** contract (e.g. `VN30F2201`) that `quote.futurecontractcode` maps each `futurecode` (VN30F1M/F2M) to per date — so plutus routes it to HNXDS and dates its IM. Depth is 1-3; displayed **sizes only exist ≥ 2023-01-03** (bidsize/asksize will be empty before that — expected; Task 8 falls back to OptimisticQueue there).

- [ ] **Step 1: Implement `extract_l2.py`.** It extends MM's existing `database/query.py` pattern (the `quote.bidprice`/`askprice`/`futurecontractcode` join) to depths 1-3 + sizes + tape, and freezes parquet. Uses `psycopg2` and `config.db_params` (already wired). Novel code:

```python
"""Freeze the L2 book + sized tape + futures daily bands for the faithful arm.

Reads algotradeDB (the same DB pmm-load-data uses) and writes parquet in the
schema plutus's DepthSource / TapeSource / DataHubSource read. Depth 1-3;
displayed sizes exist only >= 2023-01-03 (empty before -> OptimisticQueue
fallback in mm_anchor). tickersymbol is the dated contract from
quote.futurecontractcode, so plutus routes it to HNXDS and dates its margin.

Run: python -m proto_market_maker.experiments.extract_l2
"""
from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path

import pandas as pd
import psycopg2

from proto_market_maker.config.config import db_params, BACKTESTING_CONFIG

OUT_L2 = Path("data/faithful/l2")
OUT_DAILY = Path("data/faithful/daily")
FUTURECODES = ("VN30F1M", "VN30F2M")
SESSION_HOURS = (
    "((EXTRACT(HOUR FROM {c}.datetime) >= 9 AND EXTRACT(HOUR FROM {c}.datetime) < 14) "
    "OR (EXTRACT(HOUR FROM {c}.datetime) = 14 AND EXTRACT(MINUTE FROM {c}.datetime) <= 45))"
)

# depth 1-3 price/size, parameterized by futurecode + window. `{val}` is the DB's
# value column: `price` for price tables, the size column for size tables aliased
# to `quantity` (CONFIRM the real algotradeDB size column name, e.g. `quantity`
# or `volume`, when wiring — alias it to `quantity`).
DEPTH_SQL = """
  select x.datetime, x.tickersymbol, x.depth, x.{val} as {out}
  from quote.{table} x
  join quote.futurecontractcode fc
    on date(x.datetime) = fc.datetime and fc.tickersymbol = x.tickersymbol
  where fc.futurecode = %s and x.depth between 1 and 3
    and x.datetime between %s and %s and """ + SESSION_HOURS.format(c="x") + """
  order by x.datetime, x.depth
"""
TAPE_SQL = """
  select x.datetime, x.tickersymbol, x.{val} as {out}
  from quote.{table} x
  join quote.futurecontractcode fc
    on date(x.datetime) = fc.datetime and fc.tickersymbol = x.tickersymbol
  where fc.futurecode = %s and x.datetime between %s and %s
    and """ + SESSION_HOURS.format(c="x") + """
  order by x.datetime
"""
CLOSE_SQL = """
  select c.datetime::date as datetime, c.tickersymbol, c.price
  from quote.close c
  join quote.futurecontractcode fc on c.datetime = fc.datetime and fc.tickersymbol = c.tickersymbol
  where fc.futurecode = %s and c.datetime between %s and %s
  order by c.datetime
"""


def _q(conn, sql, table, val, out, code, lo, hi):
    return pd.read_sql(sql.format(table=table, val=val, out=out), conn,
                       params=(code, lo, hi))


def main():
    OUT_L2.mkdir(parents=True, exist_ok=True)
    OUT_DAILY.mkdir(parents=True, exist_ok=True)
    lo, hi = "2022-01-01", "2025-06-30 23:59:59"     # both windows in one freeze
    conn = psycopg2.connect(**db_params)

    depth_specs = [("bidprice", "price", "price"), ("askprice", "price", "price"),
                   ("bidsize", "quantity", "quantity"), ("asksize", "quantity", "quantity")]
    for table, val, out in depth_specs:
        frames = [_q(conn, DEPTH_SQL, table, val, out, code, lo, hi) for code in FUTURECODES]
        df = pd.concat(frames, ignore_index=True).sort_values(["datetime", "depth"])
        df.to_parquet(OUT_L2 / f"local_quote_{table}.parquet", index=False)
        print(f"  local_quote_{table}: {len(df):,} rows")

    for table, val, out in [("matched", "price", "price"), ("total", "quantity", "quantity")]:
        frames = [_q(conn, TAPE_SQL, table, val, out, code, lo, hi) for code in FUTURECODES]
        df = pd.concat(frames, ignore_index=True).sort_values("datetime")
        df.to_parquet(OUT_L2 / f"local_quote_{table}.parquet", index=False)
        print(f"  local_quote_{table}: {len(df):,} rows")

    # daily band slice (DataHubSource schema): close from DB; reference = prev
    # close; ceiling/floor = reference * (1 +/- 0.07) (HNXDS daily limit, derived
    # -> record as derived in docs). Also the ticker master with venue + expiry.
    close = pd.concat([_q(conn, CLOSE_SQL, "close", "price", "price", code, lo, hi)
                       for code in FUTURECODES], ignore_index=True)
    close["datetime"] = pd.to_datetime(close["datetime"]).dt.date
    close.to_parquet(OUT_DAILY / "quote_close.parquet", index=False)
    ref = close.rename(columns={"price": "price"}).copy()
    for name, factor in (("quote_reference", Decimal("1")),
                         ("quote_ceil", Decimal("1.07")), ("quote_floor", Decimal("0.93"))):
        out = close.copy()
        out["price"] = (out["price"].astype(float) * float(factor)).round(1)
        out.to_parquet(OUT_DAILY / f"{name}.parquet", index=False)
    # ticker master — venue HNXDS + expiry per dated contract (from
    # futurecontractcode + 3rd-Thursday). CONFIRM DataHubSource's exact
    # quote_ticker columns (tickersymbol, exchange/venue, startdate, expdate)
    # against a working equity slice before writing.
    conn.close()
    print(f"wrote L2 -> {OUT_L2}, daily -> {OUT_DAILY}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run the extract.** Run: `cd proto/ProtoMarketMaker && uv run pmm-extract-l2`
Expected: prints row counts for all six `local_quote_*` tables + the daily tables. Note the `data/faithful/l2/` size; if > ~100 MB, mark it for **Drive** (proto pattern) in `.gitignore` + `docs/data.md`.

- [ ] **Step 3: Smoke-test the slice reads and serves a sized book (the queue axis' payoff).**
```python
# tests/test_l2_slice_smoke.py
import os
from datetime import datetime
import pytest

HAS = os.path.exists("data/faithful/l2/local_quote_bidprice.parquet")


@pytest.mark.skipif(not HAS, reason="needs the frozen L2 slice under data/faithful/l2")
def test_depth_source_serves_the_four_tables_and_a_ladder():
    from plutus.market.adapters.depth import DepthSource
    from plutus.market.adapters.tape import TapeSource
    src = DepthSource("data/faithful/l2", table_prefix="local_quote")
    assert set(src.tables) >= {"bidprice", "askprice"}, src.tables
    tickers = src.tickers()
    assert tickers, "no futures tickers in the frozen L2 slice"
    tape = TapeSource("data/faithful/l2", table_prefix="local_quote")
    assert tape.tickers(), "no tape (matched/total) rows in the slice"

@pytest.mark.skipif(not HAS, reason="needs the frozen L2 slice")
def test_sizes_present_in_queue_era_after_2023_01_03():
    from plutus.market.adapters.depth import DepthSource
    src = DepthSource("data/faithful/l2", table_prefix="local_quote")
    # 'bidsize' must resolve as a table for the conservative-queue era to exist
    assert "bidsize" in src.tables, \
        "no displayed sizes -> only the OptimisticQueue fallback is available"
```
Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_l2_slice_smoke.py -q`
Expected: PASS — confirms the book tier and the conservative-queue era have input. If `bidsize` is absent everywhere, the whole run falls back to optimistic (record that as a data finding).

- [ ] **Step 4: Commit** (extractor + smoke test; data via Drive/gitignored).
```bash
git add src/proto_market_maker/experiments/__init__.py src/proto_market_maker/experiments/extract_l2.py tests/test_l2_slice_smoke.py
git commit -m "Freeze VN30F1M/F2M L2 depth 1-3 + tape + daily bands for the faithful arm

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 8: [MM] Faithful arm — cadence, derivatives margin, book_walk conservative queue

**Files:** Create `src/proto_market_maker/experiments/mm_anchor.py` (the `_faithful` driver + wiring; the naive `_naive` wrapper; run assembled in Task 9).

**Interfaces:**
- Consumes: `strategy.quote`, the frozen slices (Task 7), `PlutusBackend` (+ its Task-1 `cancel`), `BookSessionSource`, `Order`/`OrderType`/`Side`.
- Produces: `_faithful(is_data: bool) -> dict` with keys `sharpe, hpr, mdd, fills, refusals, indeterminates, margin_calls, forced_liquidations, days, deposit_dong` (Tier-1 counters extended in Task 9); `_naive(is_data)` mirroring SB.

**Faithful wiring (the derivatives + book_walk seam):**
```python
from plutus.market.adapters.datahub import DataHubSource
from plutus.market.adapters.book_session import BookSessionSource
from plutus.execution import PlutusBackend

DEPOSIT_DONG = 500_000_000          # CONFIRM exact figure with owner before the run
MULT = 100_000                      # real VN30F multiplier (dong/point); naive uses 100
QUEUE_ERA_START = date(2023, 1, 3)  # displayed sizes exist from here

source = BookSessionSource.for_roots(price_root="data/faithful/daily",
                                     book_root="data/faithful/l2",
                                     table_prefix="local_quote")
cfg = {
    "period": {"start": "2022-01-01", "end": "2023-12-31"},   # IS; OOS for is_data=False
    "resolution": "tick",
    "exchange_rules": {"venues": ["HNXDS"]},
    "accounts": {"derivatives": {"initial_deposit": DEPOSIT_DONG, "account_no": "DER-MM"}},
    "fill_policy": {"kind": "book_walk", "queue": "conservative"},
    "data": {"adapter": "plutus.market.adapters.book_session.BookSessionSource",
             "root": "data/faithful/l2", "book_root": "data/faithful/l2"},
}
backend = PlutusBackend.from_config(cfg, source=source)
```

> **Futures-routing confirmation (do this first, it de-risks the task).** Submit one probe `Order(ticker=<a dated VN30F contract in the slice>, side=BUY, quantity=1, order_type=LIMIT, limit_price=<near touch>)` right after building `backend`. If it returns `Accepted` (or a *market-rule* `Rejected` such as `INSUFFICIENT_DEPOSIT`/`BAND_LIMIT`), routing works. If it returns `SESSION_SEMANTICS`/routing failure, the dated contract is not recognised as an HNXDS future from the slice alone — build the session with an explicit listing instead: `from plutus.market.session import ExchangeSession, VenueListing` (VenueListing lives in `plutus.market.session.rulebook`), `session = ExchangeSession.from_mapping(cfg, source=source, listings=[VenueListing(...)])`, then `backend = PlutusBackend(session)` (the constructor wraps a session directly). Record which path was needed in the module docstring.

- [ ] **Step 1: Implement `_naive`** — mirror SB's `null_anchor._naive`: run the existing `Backtesting` engine on the redated slice at the optimized `step`, return `{"sharpe","hpr","mdd","round_trips","fills"}`. Derive `round_trips`/`fills` from the naive engine's inventory turnover (count sign-consistent fill events over the run; a completed round-trip = a buy fill later closed by a sell fill).

- [ ] **Step 2: Implement the faithful driver cadence** (the hard part — replicate 15s/on-fill against `advance_to` + cancel/resubmit). Key rules: step the clock on the **15s grid** (matching the naive cadence — NOT every micro-tick, which bounds the loop); at each requote point read the **faithful inventory** from `backend.positions()` so `quote()` skews on real state; **cancel** the live bid/ask and **resubmit** 1-contract LIMITs; `advance_to(ts)` lets book_walk sweep the interval's prints against resting orders and runs the daily mark (margin calls / forced-close are automatic). Novel code:

```python
from collections import Counter
from datetime import date, datetime, timedelta
from decimal import Decimal

from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side
from plutus.market.session import Accepted, Rejected

def _kind(e):
    return getattr(getattr(e, "kind", None), "value", getattr(e, "kind", ""))

def _faithful(is_data: bool) -> dict:
    span_start, span_end, ticks = _load_faithful_inputs(is_data)   # 15s-gridded (ts, ticker, price)
    backend = _build_backend(is_data, span_start, span_end)        # the wiring above
    step = Decimal(str(_optimized_step()))

    live = {"bid": None, "ask": None}     # order_ids of the resting quotes
    last_requote = None
    fills = 0
    refusals, indeterminates = Counter(), Counter()
    margin_calls = forced = 0
    equity, eq_dates, prev_day = [], [], None

    def net_inventory() -> int:
        pos = backend.positions()                       # {ticker: ContractPosition}
        return sum(int(getattr(p, "net", getattr(p, "quantity", 0))) for p in pos.values())

    def cancel_live():
        for key in ("bid", "ask"):
            oid = live[key]
            if oid is not None:
                backend.cancel(oid)                     # Task-1 pass-through
                live[key] = None

    def place(side, price):
        ack = backend.submit(Order(ticker=ticker, side=side, quantity=1,
                                   order_type=OrderType.LIMIT, limit_price=price))
        if isinstance(ack, Rejected):
            (indeterminates if ack.is_indeterminate else refusals)[ack.rule.name] += 1
            return None
        return ack.order_id

    for ts, ticker, price in ticks:
        # requote at the 15s cadence or right after a fill (tracked below)
        if last_requote is None or ts >= last_requote + timedelta(seconds=15):
            inv = net_inventory()
            bid, ask = _quote(price, inv, step)         # strategy.quote
            cancel_live()
            live["bid"] = place(Side.BUY, bid)
            live["ask"] = place(Side.SELL, ask)
            last_requote = ts
        events = backend.advance_to(ts)
        for e in events:
            k = _kind(e)
            if k in ("filled", "partially_filled"):
                fills += 1
                last_requote = None                      # force an on-fill requote next tick
            elif k == "margin_call":
                margin_calls += 1
            elif k == "forced_liquidation":
                forced += 1
            elif k == "indeterminate":
                indeterminates[getattr(getattr(e, "cause", None), "name", "INDETERMINATE")] += 1
        # daily mark-to-market equity (Tier-2, DAILY granularity)
        day = ts.date()
        if prev_day is not None and day != prev_day:
            equity.append(_faithful_equity(backend, price)); eq_dates.append(prev_day)
        prev_day = day
    equity.append(_faithful_equity(backend, price)); eq_dates.append(prev_day)

    rets = [equity[i]/equity[i-1]-1.0 for i in range(1, len(equity)) if equity[i-1]]
    return {"sharpe": _sharpe(rets), "hpr": _hpr(equity), "mdd": _mdd(equity),
            "fills": fills, "refusals": dict(refusals), "indeterminates": dict(indeterminates),
            "margin_calls": margin_calls, "forced_liquidations": forced,
            "days": len(equity), "deposit_dong": DEPOSIT_DONG}
```
Provide the small helpers alongside: `_sharpe/_hpr/_mdd` copied verbatim from SB `null_anchor.py` (RF_DAILY `0.00023`, ×√250); `_quote` = `from proto_market_maker.strategy import quote`; `_optimized_step()` reads `parameter/optimized_parameter.json`; `_faithful_equity(backend, mark_price)` = `float(deposit balance) + net_inventory()*mark_price*MULT` (read the deposit balance from `backend.margin()` / `backend.positions()` marks — the account-level equity, in real đồng); `_load_faithful_inputs(is_data)` reads `local_quote_matched.parquet`, filters to the window + the active dated contract per date (via the futurecode roll), and **downsamples to the 15s grid** (last matched price per 15s bucket per ticker).

- [ ] **Step 3: Smoke-run the faithful driver on a short sub-window** (e.g. one queue-era month, 2024-02) to confirm it produces fills and margin behaviour without an unbounded loop. Run a scratch invocation of `_faithful` over the short window; assert `result["fills"] > 0` and the run terminates.
Expected: non-zero fills; `margin_calls`/`forced_liquidations` are finite; no exception. If routing fails, apply the `VenueListing` fallback from the confirmation note above.

- [ ] **Step 4: Commit** (driver only; the assembled runner + counters land in Task 9).
```bash
git add src/proto_market_maker/experiments/mm_anchor.py
git commit -m "Faithful MM driver: 15s/on-fill cadence via advance_to + cancel/resubmit; dated deposit + book_walk

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 9: [MM] Tier-1 counters, Tier-2 P&L, and the assembled runner

**Files:** Modify `src/proto_market_maker/experiments/mm_anchor.py`; Create `tests/test_mm_anchor.py`.

**Interfaces:**
- Produces: `run_mm_anchor(is_data=False) -> {"naive": {...}, "faithful": {...}, "queue_spread": {...}}` (mirror SB `run_null_anchor`), plus `main()` that prints JSON.

- [ ] **Step 1: Tier-1 counter 1 — queue-fill divergence.** In `run_mm_anchor`, after the headline conservative `_faithful` run, rerun the faithful arm's fill evaluation under **OptimisticQueue** and **ProbabilisticQueue** (change `cfg["fill_policy"]` to `{"kind":"book_walk","queue":"optimistic"}` and `{"kind":"book_walk","queue":"probabilistic","seed":2025}`) plus the `soft` uncapped policy, over the same window, and record the **fill-count spread** (`{"conservative": n, "optimistic": n, "probabilistic": n, "soft": n}`). The pre-2023-01-03 no-size span shows up as INDETERMINATEs under conservative — surface `faithful["indeterminates"]` and note that concentration as the "conservative queue cannot act without displayed sizes" finding. This is the ~19% maker-queue swing, measured.

- [ ] **Step 2: Tier-1 counter 2 — dated-margin effect.** Report, from the headline faithful run: `margin_calls`, `forced_liquidations`, and the **refusals by cause** (esp. the margin/deposit rule name for orders the dated IM refused). Add a small **affordability probe**: at one date **before** 2022-12-15 (13% IM) and one **after** (17% IM), compute the contracts the deposit affords (`floor(deposit / (price*MULT*rate))`) for both rates and record the pair — the E2 headline (same deposit affords fewer contracts post-2022-12-15). Put these in `faithful["dated_margin"]`.

- [ ] **Step 3: Tier-1 counter 3 — KRX-crossing indeterminates.** Split the OOS `faithful["indeterminates"]` by side of the KRX cutover (`< 2025-05-05` vs `≥`), and report the **post-KRX INDETERMINATE rate** (fills-attempted vs indeterminate) as `faithful["krx"] = {"pre": {...}, "post": {...}, "post_indeterminate_rate": r}`. Post-KRX unsourced rulebook fields legitimately resolve to INDETERMINATE — reporting the rate **is** the finding (do not pin them).

- [ ] **Step 4: Tier-2 — net P&L / Sharpe / MDD, naive vs faithful, DAILY.** The runner already has both daily equity curves. Reconcile units: the naive arm's absolute-đồng P&L is `×1000` (naive multiplier 100 → real 100,000); Sharpe/HPR/MDD are scale-invariant and compare directly. Emit `{"naive": {...}, "faithful": {...}}` at daily granularity, framed as Tier-2 consequence (de-emphasized).

- [ ] **Step 5: Assemble `run_mm_anchor` + `main`** (mirror SB `run_null_anchor` + `main`): call `_naive`, `_faithful`, the queue-spread reruns; return the merged dict; `main()` prints `json.dumps(out, indent=2, default=str)`.

- [ ] **Step 6: Write the anchor shape test** (mirror SB `tests/test_mm_anchor.py`, data-gated on the frozen slices):
```python
# tests/test_mm_anchor.py
import os
import pytest

HAS = (os.path.exists("data/faithful/l2/local_quote_bidprice.parquet")
       and os.path.exists("data/is/VN30F1M_data.parquet"))


@pytest.mark.skipif(not HAS, reason="needs the naive + faithful frozen slices")
def test_mm_anchor_shape_and_tier1_counters():
    from proto_market_maker.experiments.mm_anchor import run_mm_anchor
    out = run_mm_anchor(is_data=False)     # OOS crosses KRX
    naive, faithful = out["naive"], out["faithful"]
    assert {"sharpe", "hpr", "mdd"} <= naive.keys()
    assert {"fills", "refusals", "indeterminates", "margin_calls",
            "forced_liquidations", "dated_margin", "krx"} <= faithful.keys()
    assert faithful["fills"] > 0
    # Tier-1: the queue axis produced a measurable conservative-vs-optimistic spread
    assert out["queue_spread"]["conservative"] != out["queue_spread"]["optimistic"]
```

- [ ] **Step 7: Run the full anchor and capture JSON.** Run: `cd proto/ProtoMarketMaker && uv run pmm-anchor > result/mm_anchor.json` and `python -m pytest tests/test_mm_anchor.py -q`.
Expected: PASS; `result/mm_anchor.json` carries both arms + the queue spread + the three Tier-1 counters.

- [ ] **Step 8: Commit.**
```bash
git add src/proto_market_maker/experiments/mm_anchor.py tests/test_mm_anchor.py
git commit -m "MM Tier-1 counters (queue divergence, dated margin, KRX indeterminates) + Tier-2 + runner

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 10: [MM] Activity-based proceed gate (pre-registered, not P&L)

**Files:** Create `tests/test_proceed_gate.py`.

- [ ] **Step 1: Record the pre-registration** in the `mm_anchor.py` module docstring (written in Task 8): "Proceed gate (pre-registered, activity/credibility only, per fidelity-not-pnl): naive arm ≥ 300 completed round-trips; faithful arm completes without an unbounded margin-liquidation cascade. No Sharpe/HPR stop-gate."

- [ ] **Step 2: Write the gate test.**
```python
# tests/test_proceed_gate.py
import os
import pytest

HAS = (os.path.exists("data/faithful/l2/local_quote_bidprice.parquet")
       and os.path.exists("data/is/VN30F1M_data.parquet"))


@pytest.mark.skipif(not HAS, reason="needs the frozen slices")
def test_activity_gate_naive_roundtrips_and_faithful_bounded():
    from proto_market_maker.experiments.mm_anchor import run_mm_anchor
    out = run_mm_anchor(is_data=True)       # IS
    naive, faithful = out["naive"], out["faithful"]
    # naive: non-trivial activity (>= 300 completed round-trips)
    assert naive["round_trips"] >= 300, f'kill: only {naive["round_trips"]} round-trips'
    # faithful: bounded — forced liquidations are finite, not a runaway cascade.
    # Bound = at most one forced-close per trading day (a cascade is many-per-day).
    assert faithful["forced_liquidations"] <= faithful["days"], \
        "kill: unbounded margin-liquidation cascade"
```

- [ ] **Step 3: Run it.** Run: `cd proto/ProtoMarketMaker && python -m pytest tests/test_proceed_gate.py -q`
Expected: PASS. If the naive round-trip count is < 300, the strategy is not active enough on the redated IS window — **escalate to the owner** (do not weaken the pre-registered threshold; options are a different representative `step` from Task 6's activity sweep, or confirming the windows). If forced-liquidations run away, revisit `DEPOSIT_DONG` (bump toward 7–8e8 per the confirmed decision) — but only with owner confirmation of the exact figure.

- [ ] **Step 4: Commit.**
```bash
git add tests/test_proceed_gate.py
git commit -m "Pre-registered activity proceed gate (>=300 round-trips; bounded forced-close; no P&L gate)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 11: [plutus + MM] Registry row, manifest re-bless, `plutus check` green

**Files:** Modify `plutus/docs/reference/tables/experiments_registry.md`; Modify `proto/ProtoMarketMaker/.plutus/manifest.yaml`.

- [ ] **Step 1: Registry (plutus repo).** Replace the "Grid · MM · Pair — pending" paragraph's MM mention with a full **MM block** after the SB block in `experiments_registry.md`, same discipline as SB: the redated windows; the modelling choices (faithful arm — `initial_deposit` 5e8 đồng [note: owner-confirmed exact figure], dated VSD IM 13%/17%, `book_walk`+ConservativeQueue with the pre-2023-01-03 OptimisticQueue fallback, real multiplier 100,000 đồng/pt, KRX-crossing OOS); the **naive-vs-faithful** Tier-2 metric table (Sharpe/HPR/MDD, from `result/mm_anchor.json`); the **Tier-1 paragraph** (queue-fill divergence conservative-vs-optimistic-vs-probabilistic + the pre-2023 no-size INDETERMINATE rate; dated-margin affordability 13%→17% + margin-call/forced-close counts; post-KRX INDETERMINATE rate); and the regenerate commands. Place MM as the third spectrum point (SB ≈ null → Grid → **MM** highest, derivatives). Regenerate block:
```bash
cd proto/ProtoMarketMaker            # branch rivf-2026
uv run pmm-extract-l2                 # freeze the L2 + tape + daily slices
uv run pmm-anchor                     # naive vs faithful + Tier-1/Tier-2
```

- [ ] **Step 2: Manifest (MM repo).** Update `.plutus/manifest.yaml`: `env.python_version: '3.12'`; redate any window references; **re-bless `expected`** for `in_sample_backtest` + `out_of_sample_backtest` to the new-window naive numbers (Task 5 Step 4) — copy the six metric literals from the re-run, keeping `tolerance {kind: relative, value: 0.05}`; keep the `optimization` step as `artifact_check` (its objective is now activity, but it still writes `parameter/optimized_parameter.json`); leave `nine_step_coverage` as-is (step 3 can flip to `present: true` since `strategy.py` now exists — set `step_3_forming_set_of_rules: {present: true, section: "Forming Set of Rules"}`). Point the `data_collection` step's Drive URL/layout note at the redated slices.

- [ ] **Step 3: `plutus check` green under the naive engine.** Run: `cd proto/ProtoMarketMaker && plutus check`
Expected: exit 0 — IS + OOS reproduce the re-blessed `expected` within tolerance. (The faithful `pmm-anchor` is an **experiment**, not a `plutus check` step — the gate is the naive engine, exactly as SB.)

- [ ] **Step 4: Commit both repos.**
```bash
cd proto/ProtoMarketMaker && git add .plutus/manifest.yaml
git commit -m "Re-bless MM manifest on redated windows (py3.12); plutus check green under naive

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
cd ../../plutus && git add docs/reference/tables/experiments_registry.md
git commit -m "Registry: MM block (derivatives spectrum point) — queue/dated-margin/KRX Tier-1

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-review checklist (run before execution)

**Spec / confirmed-decision coverage:**
- Branch `rivf-2026` + `algotrade-plutus` editable dep + parquet 2 I/O sites + regression baseline → Tasks 2, 3.
- Pure quoting seam `quote(price, inventory, step)` + cadence replication → Tasks 4 (seam), 8 (faithful cadence via `advance_to` + cancel/resubmit).
- Redated windows IS 2022-01-01..2023-12-31 / OOS 2024-01-01..2025-06-30 (crosses KRX, spans 13→17% + ≥2023-01-03) → Task 5, Global Constraints.
- The one plutus change (`cancel`/`amend` on `PlutusBackend`) → Task 1. **amend refuses derivatives → MM requotes cancel/resubmit** (baked into Task 8).
- L2-depth freeze (depth 1-3 `quote.{bidprice,askprice,bidsize,asksize}` for VN30F1M/F2M from algotradeDB; sizes ≥2023-01-03) → Task 7 (+ tape + daily bands, the schema DepthSource/TapeSource/DataHubSource actually read).
- Faithful arm: `book_walk`+ConservativeQueue (OptimisticQueue fallback pre-2023-01-03), account-level derivatives margin (5e8 đồng, dated VSD IM, real call/forced-close), KRX crossing, multiplier reconciliation (100 ↔ 100,000) → Tasks 8, 9.
- Optimization B-style (cost-driven `step`, drop Optuna-Sharpe, activity report) → Task 6.
- Proceed gate ACTIVITY-based, no P&L → Task 10.
- Tier-1 counters (queue-fill divergence, dated-margin, KRX indeterminates) + Tier-2 → Task 9. Registry row extending SB/Grid → Task 11.
- Creds never committed (gitignored `.env` from the read-only JSON) → Tasks 2, 5, 7.

**Type / name consistency:** `quote()` signature identical across Tasks 4/8/9; `PlutusBackend.cancel(order_id)` (Task 1) fed `ack.order_id` (Task 8); `_faithful`/`_naive`/`run_mm_anchor` mirror SB's `_faithful`/`_naive`/`run_null_anchor`; event kinds (`filled`/`margin_call`/`forced_liquidation`/`indeterminate`) match `plutus.market.session.types.EventKind`; queue names (`conservative`/`optimistic`/`probabilistic`) match `book_walk.py`; config keys (`accounts.derivatives.initial_deposit`, `fill_policy.kind=book_walk`+`queue`, `venues=["HNXDS"]`) match `exchange.parse_config`.

**Known risks carried forward (from recon + code inspection):**
- **Futures routing** — VN30F dated contracts may need a `VenueListing` to route to HNXDS; Task 8's confirmation probe + the `ExchangeSession.from_mapping(..., listings=...)` + `PlutusBackend(session)` fallback handles it.
- **Tick-run cost** — the faithful loop is bounded to the 15s cadence grid (not micro-ticks); the L2 slice may need Drive (Task 7 Step 2).
- **Behaviour-preserving parquet** — Task 3 pins exact reproduction before any redating; if precision drifts, stop and fix the conversion, never weaken the assert.
- **Pre-2023 no sizes** — conservative queue → INDETERMINATE there; reported as a finding (Task 9), optimistic is the documented fallback.
- **Exact `initial_deposit`** — owner confirms the đồng figure before the faithful run (default 5e8; bump to 7–8e8 only on confirmation); the affordability/forced-close behaviour depends on it.

**Open questions for the owner (surface before the faithful run):**
1. Confirm the exact `initial_deposit` đồng figure (default 500,000,000; bump if day-1 utilisation too high).
2. Confirm the algotradeDB size-table value column name (`quote.bidsize`/`asksize` — `quantity` vs `volume`) so the L2 freeze SQL aliases it correctly (Task 7).

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-09-15-protomarketmaker-plan.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration.
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints.

Which approach?
