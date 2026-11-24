# Phase 0 — Execution seam + PlutusBackend + SB null-anchor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the naive-vs-faithful experiment architecture end-to-end on the simplest strategy (ProtoSmartBeta, the null anchor): a generic `PlutusBackend` adapter over `ExchangeSession`, ProtoSmartBeta refactored behind an execution seam so the *same signals* run against its own naive engine and against Plutus over one identical frozen parquet slice, and the first null-anchor comparison written to a results registry.

**Architecture:** A generic `plutus.execution.PlutusBackend` wraps `ExchangeSession` (the reusable adapter every strategy will use). ProtoSmartBeta on branch `rivf-2026` gets an `ExecutionBackend` seam at `rebalancing()` L267/268: signal+sizing stays strategy-side, execution moves behind the seam. `NaiveExecution` wraps the existing engine (behaviour-preserving — `psb-backtest` must still reproduce the published Sharpe); `PlutusExecution` drives the same targets through `PlutusBackend`. A runner steps both over frozen parquet and records Tier-1 (admission/fill) + Tier-2 (P&L) + attribution into the registry.

**Tech Stack:** Python 3.12+, uv, pandas, pyarrow, duckdb, pytz; Plutus imported as a path dependency; pytest.

## Global Constraints

- **Python ≥ 3.12** everywhere (`margin_lending.py` breaks on 3.11). A bare 3.12 venv with `duckdb pandas pyarrow pytz pytest` suffices.
- **Behaviour-preserving refactor gate:** after every ProtoSmartBeta change, `psb-backtest` and `psb-evaluate` must still reproduce the published metrics within **relative tolerance 0.05** (IS Sharpe `1.2971`, OOS Sharpe `-0.3497`; full table in Task 4). This is the regression gate; a drift means the refactor changed the strategy.
- **Identical frozen parquet:** both backends read the *same* frozen parquet slice; the naive loader is refactored to parquet so there is no CSV seam. CSV→parquet conversion must be **value-lossless** — in particular cast `vnindex.return`/`ac_return` to `float` before writing (they currently round-trip through float64; storing `Decimal`/object changes the metrics).
- **Price scale:** corpus prices are in **thousands of đồng** (`74.0` == 74,000đ); cash/deposits are in đồng. Multiply share price by `1000` for notional. Constant name: `PRICE_SCALE = 1000`.
- **Plutus API invariants:** use `OrderType.MARKET_WITH_LEFTOVER_AS_LIMIT` (MTL) for marketable orders, never `OrderType.MARKET`. `InstrumentSpec.exchange_code` is a `str` (`'HSX'`), not `.venue`. `advance_to()` is monotone and its returned event list is destructive/single-consumer — keep it, don't re-`poll()`. Two `advance_to` per day: a morning mark, submit, then a close mark **past 14:45**. A limit order with no band or into an UNKNOWN-evidence lock returns `Rejected(verdict=INDETERMINATE)`, not a fill — track REJECTED and INDETERMINATE separately.
- **Do not commit secrets.** algotradeDB creds live only in gitignored `.env`.

---

## File Structure

**plutus repo (branch `rivf-2026`):**
- Create `src/plutus/execution/__init__.py` — exports `PlutusBackend`.
- Create `src/plutus/execution/backend.py` — `PlutusBackend` (the reusable `ExchangeSession` facade).
- Create `tests/execution/test_plutus_backend.py` — unit tests (fixture smoke + corpus-gated J1 replica).
- Create `docs/reference/tables/experiments_registry.md` — the results registry (Task 9).

**ProtoSmartBeta repo (branch `rivf-2026`):**
- Modify `pyproject.toml` — add `plutus` path dependency.
- Modify `src/proto_smart_beta/backtest.py` — parquet I/O (Task 3), the execution seam (Task 5).
- Create `src/proto_smart_beta/execution.py` — `ExecutionBackend` protocol, `NaiveExecution`, `PlutusExecution`.
- Create `src/proto_smart_beta/experiments/__init__.py` and `src/proto_smart_beta/experiments/null_anchor.py` — the naive-vs-faithful runner (Task 8).
- Create `tests/test_execution_seam.py`, `tests/test_null_anchor.py`.
- Modify `.plutus/manifest.yaml` — repoint data outputs to `.parquet` (Task 3).

---

### Task 1: `PlutusBackend` — the reusable ExchangeSession facade (plutus repo)

**Files:**
- Create: `<plutus>/src/plutus/execution/__init__.py`
- Create: `<plutus>/src/plutus/execution/backend.py`
- Test: `<plutus>/tests/execution/test_plutus_backend.py`

**Interfaces:**
- Consumes: `plutus.market.session.ExchangeSession` (`from_config`, `build`, `submit`, `advance_to`, `cash`, `holdings`, `positions`, `margin`, `indeterminate_report`); `plutus.market.protocol.Order`; `plutus.market.adapters.datahub.DataHubSource`; result types `Accepted`, `Rejected`, `Event` from `plutus.market.session`.
- Produces: `PlutusBackend` with methods `from_config(config: dict, *, source=None) -> PlutusBackend`, `submit(order: Order) -> Accepted|Rejected`, `advance_to(ts: datetime) -> list[Event]`, `fills(events) -> list[Event]` (staticmethod), `cash() -> Cash`, `holdings(ticker) -> Holding`, `positions() -> dict`, `margin() -> MarginView`, `indeterminate_report()`. Attribute `.session`.

- [ ] **Step 1: Write the failing test**

```python
# tests/execution/test_plutus_backend.py
import os
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest

from plutus.execution import PlutusBackend
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side
from plutus.market.session import Accepted

FIXTURES = str(Path(__file__).resolve().parents[1].parent / "strategies" / "fixtures" / "parquet")

BASE_CONFIG = {
    "period": {"start": "2022-11-09", "end": "2022-11-15"},
    "resolution": "1d",
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 200_000_000, "account_no": "SEC-P0"}},
    "fill_policy": {"kind": "soft"},
    "data": {"adapter": "plutus.market.adapters.datahub.DataHubSource", "root": FIXTURES},
}

def test_backend_builds_and_submits_over_fixtures():
    backend = PlutusBackend.from_config(BASE_CONFIG)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("74.0")))
    # A real answer either way — never an exception, never None.
    assert ack is not None
    events = backend.advance_to(datetime(2022, 11, 9, 15, 0))
    assert isinstance(events, list)
    # cash read-model is reachable
    assert backend.cash().settled_balance <= Decimal("200000000")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd <plutus> && PYTHONPATH=src python -m pytest tests/execution/test_plutus_backend.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'plutus.execution'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/plutus/execution/__init__.py
"""Execution adapters: drive a Plutus market from an external strategy.

The paper's claim in code — a strategy pairs Plutus (the counterparty) with
its own signal/portfolio tooling. ``PlutusBackend`` is the thin, reusable
facade over :class:`ExchangeSession` that every reference strategy drives.
"""
from plutus.execution.backend import PlutusBackend

__all__ = ["PlutusBackend"]
```

```python
# src/plutus/execution/backend.py
from __future__ import annotations

import json
import tempfile
from datetime import datetime
from typing import List, Mapping, Optional, Union

from plutus.market.session import ExchangeSession, Accepted, Rejected, Event
from plutus.market.protocol import Order


def _kind(event: Event) -> str:
    return getattr(getattr(event, "kind", None), "value", getattr(event, "kind", ""))


class PlutusBackend:
    """A reusable execution backend: submit orders and read account truth
    against a Plutus :class:`ExchangeSession`.

    This is deliberately thin — it adds a dict-config convenience builder, a
    ``fills`` helper, and a stable surface strategies code against, and holds
    no strategy logic of its own. Construct with :meth:`from_config`, or wrap
    an already-built session directly.
    """

    def __init__(self, session: ExchangeSession) -> None:
        self.session = session

    @classmethod
    def from_config(cls, config: Mapping, *, source=None) -> "PlutusBackend":
        """Build from a config dict, exactly the public ``from_config`` path —
        the dict is written to a temp JSON and loaded, no privileged injection.
        Pass ``source`` to share one :class:`DataHubSource` with a signal feed.
        """
        cfg = json.loads(json.dumps(config))  # deep copy; never mutate caller's
        with tempfile.NamedTemporaryFile(
            "w", suffix=".json", delete=False, encoding="utf-8"
        ) as handle:
            json.dump(cfg, handle)
            path = handle.name
        if source is not None:
            return cls(ExchangeSession.from_config(path, source=source))
        return cls(ExchangeSession.from_config(path))

    # -- operations --------------------------------------------------------
    def submit(self, order: Order) -> Union[Accepted, Rejected]:
        return self.session.submit(order)

    def advance_to(self, ts: datetime) -> List[Event]:
        return self.session.advance_to(ts)

    @staticmethod
    def fills(events) -> List[Event]:
        """The FILLED / PARTIALLY_FILLED events in an event list."""
        return [e for e in events if _kind(e) in ("filled", "partially_filled")]

    # -- read models -------------------------------------------------------
    def cash(self):
        return self.session.cash()

    def holdings(self, ticker: str):
        return self.session.holdings(ticker)

    def positions(self):
        return self.session.positions()

    def margin(self):
        return self.session.margin()

    def indeterminate_report(self):
        return self.session.indeterminate_report()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd <plutus> && PYTHONPATH=src python -m pytest tests/execution/test_plutus_backend.py -v`
Expected: PASS. (If the fixtures lack FPT for that date, the submit still returns a real `Accepted`/`Rejected`; adjust the asserted ticker to one present in `strategies/fixtures/parquet` — list it with `ls`.)

- [ ] **Step 5: Add the corpus-gated J1 replica test**

```python
@pytest.mark.skipif(not os.environ.get("PLUTUS_DATA_ROOT"),
                    reason="needs the full corpus")
def test_j1_buy_fills_at_limit_over_corpus():
    cfg = dict(BASE_CONFIG, data={"adapter": BASE_CONFIG["data"]["adapter"],
                                  "root": os.environ["PLUTUS_DATA_ROOT"]})
    backend = PlutusBackend.from_config(cfg)
    ack = backend.submit(Order(ticker="FPT", side=Side.BUY, quantity=1000,
                               order_type=OrderType.LIMIT, limit_price=Decimal("74.0")))
    assert isinstance(ack, Accepted)
    fills = PlutusBackend.fills(backend.advance_to(datetime(2022, 11, 9, 13, 0)))
    assert fills and fills[0].price == Decimal("74.0") and fills[0].quantity == 1000
```

Run: `cd <plutus> && PYTHONPATH=src PLUTUS_DATA_ROOT=$HERMES_PARQUET python -m pytest tests/execution/test_plutus_backend.py -v`
Expected: both PASS (the J1 replica confirms real fills against the corpus).

- [ ] **Step 6: Commit**

```bash
cd <plutus>
git add src/plutus/execution tests/execution
git commit -m "Add PlutusBackend: reusable ExchangeSession facade for strategy execution

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Branch ProtoSmartBeta to `rivf-2026` and add the Plutus path dependency

**Files:**
- Modify: `<proto>/ProtoSmartBeta/pyproject.toml`

**Interfaces:**
- Produces: importable `plutus` inside the ProtoSmartBeta env; branch `rivf-2026`.

- [ ] **Step 1: Branch**

```bash
cd <proto>/ProtoSmartBeta
git checkout -b rivf-2026
```

- [ ] **Step 2: Add plutus as a path dependency**

In `pyproject.toml`, add to `[project].dependencies` the entry `"plutus"`, and add a uv source table:

```toml
[tool.uv.sources]
plutus = { path = "<plutus>", editable = true }
```

- [ ] **Step 3: Sync and verify the import**

Run:
```bash
cd <proto>/ProtoSmartBeta && uv sync && \
uv run python -c "from plutus.execution import PlutusBackend; print('ok')"
```
Expected: prints `ok`.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "Depend on Plutus (path) for the faithful execution backend

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Refactor ProtoSmartBeta's data layer to parquet (behaviour-preserving)

**Files:**
- Modify: `<proto>/ProtoSmartBeta/src/proto_smart_beta/backtest.py` (4 I/O sites: L126, L396 write; L406, L419 read)
- Modify: `.plutus/manifest.yaml` (step `outputs`, `data_sources.raw.expected_layout`: `.csv` → `.parquet`)
- Test: `<proto>/ProtoSmartBeta/tests/test_parquet_roundtrip.py`

**Interfaces:**
- Produces: `data/{is,os}/{pe_dps,vnindex}.parquet`; `psb-backtest`/`psb-evaluate` read parquet; metrics unchanged.

- [ ] **Step 1: Write the failing test (value-lossless round-trip)**

```python
# tests/test_parquet_roundtrip.py
from decimal import Decimal
import pandas as pd

def test_vnindex_return_survives_parquet_as_float(tmp_path):
    # The current CSV path parses `return` as float64 then re-wraps Decimal(str(x)).
    # Parquet must reproduce that: store float, read float.
    df = pd.DataFrame({"date": ["2019-01-03"],
                       "return": [Decimal("-0.01517241379310344827586206897")]})
    df["return"] = df["return"].astype(float)          # the cast the loader must apply
    p = tmp_path / "vnindex.parquet"
    df.to_parquet(p, index=False)
    back = pd.read_parquet(p)
    assert back["return"].dtype == float
    assert back["return"].iloc[0] == float(Decimal("-0.01517241379310344827586206897"))
```

- [ ] **Step 2: Run it to confirm it passes as a spec of intent** (this pins the behaviour; it needs no source change).

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_parquet_roundtrip.py -v`
Expected: PASS.

- [ ] **Step 3: Repoint the 4 I/O sites**

At `backtest.py:126` (`df.to_csv(self.index_path)`) — before writing, ensure `df["return"]`/`df["ac_return"]` are `float`, then write parquet:
```python
df["return"] = df["return"].astype(float)
df["ac_return"] = df["ac_return"].astype(float)
df.to_parquet(self.index_path, index=False)
```
At `backtest.py:396` (`backtesting_data.to_csv(self.path)`):
```python
backtesting_data.to_parquet(self.path, index=False)
```
At `backtest.py:406` (`pd.read_csv(self.path)`):
```python
backtesting_data = pd.read_parquet(self.path)
```
At `backtest.py:419` (`pd.read_csv(self.index_path)`):
```python
self.vnindex_data = pd.read_parquet(self.index_path)
```
Then change the four path constants (in `config/config.py` or wherever `self.path`/`self.index_path` are set) from `pe_dps.csv`/`vnindex.csv` to `pe_dps.parquet`/`vnindex.parquet`. Keep the subsequent `pd.to_datetime(...).dt.date` and `Decimal(str(x))` lines unchanged — they work from parquet too.

- [ ] **Step 4: Regenerate the frozen slice and run the regression gate**

Regenerate the committed data as parquet. If a DB pull is unavailable, convert the existing shipped CSVs (`.plutus/cache/data/**` or `data/**`) in place:
```bash
cd <proto>/ProtoSmartBeta
uv run python - <<'PY'
import pandas as pd, glob, os
for csv in glob.glob("data/*/pe_dps.csv") + glob.glob("data/*/vnindex.csv"):
    df = pd.read_csv(csv)
    if "return" in df:      df["return"] = df["return"].astype(float)
    if "ac_return" in df:   df["ac_return"] = df["ac_return"].astype(float)
    df = df.loc[:, [c for c in df.columns if not c.startswith("Unnamed")]]
    df.to_parquet(csv.replace(".csv", ".parquet"), index=False)
    print("wrote", csv.replace(".csv", ".parquet"))
PY
uv run psb-backtest
```
Expected: `psb-backtest` prints IS metrics matching the baseline within rel-tol 0.05:

| Metric | IS baseline | OOS baseline |
|---|---|---|
| sharpe_ratio | 1.2971 | -0.3497 |
| information_ratio | 0.4716 | 0.7442 |
| sortino_ratio | 1.7298 | -0.4363 |
| maximum_drawdown | -0.2828 | -0.4604 |
| hpr (%) | 104.9 | -3.171 |
| annual_return (%) | 27.09 | -4.244 |

- [ ] **Step 5: Update the manifest and run `psb-evaluate`**

In `.plutus/manifest.yaml`, change the `data_preparation` step `outputs` and `data_sources.raw.expected_layout` from the four `data/**/*.csv` to `*.parquet`. Then:
```bash
uv run psb-evaluate
```
Expected: OOS metrics match the OOS column above within rel-tol 0.05.

- [ ] **Step 6: Commit**

```bash
git add src/proto_smart_beta tests/test_parquet_roundtrip.py .plutus/manifest.yaml data
git commit -m "Refactor the data layer to parquet (value-lossless; metrics unchanged)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 4: Verify the regression baseline is green after the parquet switch

**Files:** none (verification task).

- [ ] **Step 1: Run both backtests and diff against the baseline**

```bash
cd <proto>/ProtoSmartBeta
uv run psb-backtest && uv run psb-evaluate
```
Expected: every metric in the Task-3 table reproduces within rel-tol 0.05. If any drifts, the parquet conversion was not value-lossless (most likely `return`/`ac_return` stored as Decimal/object) — fix the cast and re-run. Do not proceed until green.

- [ ] **Step 2: (Optional, final gate) Full `plutus check`**

```bash
cd <proto>/ProtoSmartBeta
uv venv .plutus-venv && source .plutus-venv/bin/activate
uv pip install "plutus-verify[runner] @ https://github.com/algotrade-plutus/plutus-verify/releases/download/v0.5.1/plutus_verify-0.5.1-py3-none-any.whl"
plutus check .
```
Expected: exit `0`. (Needs Docker; if unavailable, the Step-1 local metric match is the working gate and `plutus check` is deferred to CI.)

---

### Task 5: Extract the `ExecutionBackend` seam + `NaiveExecution` (behaviour-preserving)

**Files:**
- Create: `<proto>/ProtoSmartBeta/src/proto_smart_beta/execution.py`
- Modify: `backtest.py` (`__init__` to accept an injected backend; `rebalancing()` L268-300 and `daily_update_asset()` L302-326 delegate to the backend)
- Test: `<proto>/ProtoSmartBeta/tests/test_execution_seam.py`

**Interfaces:**
- Consumes: the target-portfolio DataFrame produced by `rebalancing()` L258-267 (columns include `tickersymbol`, `qty`, `prev_close`, `close`).
- Produces: `ExecutionBackend` protocol with `rebalance_to(targets_df, group) -> Decimal` (returns new_asset), `mark(group) -> Decimal`, `holdings() -> dict[str,int]`, `cash() -> Decimal`, `total_value(group) -> Decimal`; and `NaiveExecution` implementing it by wrapping the existing `self.portfolio` engine. `Backtesting.__init__` gains `backend: ExecutionBackend | None = None` (defaults to `NaiveExecution`).

- [ ] **Step 1: Write the failing test — NaiveExecution reproduces the engine exactly**

```python
# tests/test_execution_seam.py
from proto_smart_beta.backtest import create_bt_instance

def test_naive_backend_reproduces_published_sharpe():
    bt = create_bt_instance(process_data=True, is_data=True)   # default NaiveExecution
    ann_sharpe = bt.run()  # run() returns annualized IS sharpe (backtest.py:462)
    assert abs(float(ann_sharpe) - 1.2971) / 1.2971 < 0.05
```

- [ ] **Step 2: Run to verify it fails** (the seam doesn't exist yet, or `run()` signature differs).

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_execution_seam.py -v`
Expected: FAIL (import/attribute error, or the test drives a not-yet-injected backend).

- [ ] **Step 3: Define the protocol and NaiveExecution**

```python
# src/proto_smart_beta/execution.py
from __future__ import annotations
from decimal import Decimal
from typing import Mapping, Protocol, runtime_checkable
import pandas as pd


@runtime_checkable
class ExecutionBackend(Protocol):
    """The seam between ProtoSmartBeta's signal and its execution.

    The strategy computes a target portfolio (tickers + lot-rounded qty) each
    rebalance day and hands it to :meth:`rebalance_to`; on other days it calls
    :meth:`mark`. Reads go through :meth:`holdings`/:meth:`cash`/:meth:`total_value`.
    ``NaiveExecution`` wraps the frictionless engine; ``PlutusExecution`` drives
    the faithful market. Same signals, swapped execution.
    """
    def rebalance_to(self, targets: pd.DataFrame, group: pd.DataFrame) -> Decimal: ...
    def mark(self, group: pd.DataFrame) -> Decimal: ...
    def holdings(self) -> Mapping[str, int]: ...
    def cash(self) -> Decimal: ...
    def total_value(self, group: pd.DataFrame) -> Decimal: ...
```

`NaiveExecution` moves the *bodies* of the existing methods verbatim (preserving every quirk, including the buy-leg `sell_fee` and the divergent budget formulas — see the map). It owns `portfolio` (dict with `"CASH"`), `old_price`, `suspended_stock`, `buy_fee`, `sell_fee`:

```python
class NaiveExecution:
    def __init__(self, initial_cash: Decimal, buy_fee: Decimal, sell_fee: Decimal):
        self.portfolio = {"CASH": initial_cash}
        self.old_price: dict = {}
        self.suspended_stock: set = set()
        self.buy_fee, self.sell_fee = buy_fee, sell_fee

    def rebalance_to(self, targets, group):
        # MOVE HERE the body of Backtesting.sell_stocks (backtest.py:173-242)
        # and the buy loop (backtest.py:268-300), operating on self.portfolio.
        # Return new_asset exactly as rebalancing() did.
        ...

    def mark(self, group):
        # MOVE HERE the body of daily_update_asset (backtest.py:302-326).
        ...

    def holdings(self):
        return {k: v for k, v in self.portfolio.items() if k != "CASH"}

    def cash(self):
        return self.portfolio["CASH"]

    def total_value(self, group):
        # MOVE HERE the body of total_asset (backtest.py:156-171).
        ...
```

- [ ] **Step 4: Inject the backend into `Backtesting`**

In `backtest.py` `Backtesting.__init__`, add `backend: ExecutionBackend | None = None`; store `self.backend = backend or NaiveExecution(self.initial_capital, self.buy_fee, self.sell_fee)`. In `rebalancing()` replace L268-300 with `new_asset = self.backend.rebalance_to(qualified_stocks, group)`; in `update_period_return`'s daily branch replace the `daily_update_asset(...)` call with `self.backend.mark(group)`; route holdings/cash/total_asset reads to `self.backend`. Keep L258-267 (signal+sizing) in `Backtesting`.

- [ ] **Step 5: Run the seam test AND the regression gate**

Run:
```bash
cd <proto>/ProtoSmartBeta
uv run python -m pytest tests/test_execution_seam.py -v && uv run psb-backtest && uv run psb-evaluate
```
Expected: seam test PASSES and both backtests still reproduce the baseline within rel-tol 0.05. The extraction is behaviour-preserving or it is wrong.

- [ ] **Step 6: Commit**

```bash
git add src/proto_smart_beta tests/test_execution_seam.py
git commit -m "Extract the ExecutionBackend seam; NaiveExecution wraps the engine (behaviour-preserving)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 6: Freeze the Plutus market-data slice for SB's universe/dates

**Files:**
- Create: `<proto>/ProtoSmartBeta/src/proto_smart_beta/experiments/__init__.py` (empty)
- Create: `<proto>/ProtoSmartBeta/src/proto_smart_beta/experiments/extract_market.py`
- Create: `data/market/` (frozen `quote_*.parquet`)

**Interfaces:**
- Consumes: the equity CSV at `$STOCK_QUOTE_CSV/` (fields `quote_close`, `quote_ceil`, `quote_floor`, `quote_reference`, `quote_ticker`, `quote_open`, `quote_max`, `quote_min`, `quote_dailyvolume`); the SB universe (every `tickersymbol` appearing in `data/*/pe_dps.parquet`) and date span.
- Produces: `data/market/quote_*.parquet` in the DataHubSource schema (`datetime`, `tickersymbol`, and `price`/`quantity`), readable by `DataHubSource.for_root("data/market")`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_market_slice.py
from pathlib import Path
from plutus.market.adapters.datahub import DataHubSource

def test_market_slice_serves_states_for_the_universe():
    root = Path("data/market")
    assert (root / "quote_ticker.parquet").exists()
    src = DataHubSource.for_root(str(root))
    # a ticker/date known to be in SB's universe (fill in from pe_dps.parquet)
    from datetime import datetime
    st = src.state_at("FPT", datetime(2022, 6, 1, 15, 0))
    assert st is not None and st.last is not None
```

- [ ] **Step 2: Run to verify it fails** — `data/market` doesn't exist yet.

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_market_slice.py -v`
Expected: FAIL (missing `quote_ticker.parquet`).

- [ ] **Step 3: Write the extractor**

`extract_market.py` reads the SB universe + span from `data/*/pe_dps.parquet`, then for each needed `quote_*` CSV in `$STOCK_QUOTE_CSV/`, filters to `tickersymbol in universe AND datetime in span` and writes `data/market/quote_*.parquet` with the DataHubSource columns (`datetime`, `tickersymbol`, `price` — or `quantity` for volume; `exchangeid`/`instrumenttype` for `quote_ticker`). Convert the raw CSV `date`/value columns to the adapter's expected names. Selective by column and row so the slice is small. (If a needed field is missing from the equity CSV, pull it from algotradeDB via the proto `database/query.py` and write the same parquet — but for SB, price+band+ticker from the CSV suffice.)

- [ ] **Step 4: Run the extractor and the test**

Run:
```bash
cd <proto>/ProtoSmartBeta
uv run python -m proto_smart_beta.experiments.extract_market && \
uv run python -m pytest tests/test_market_slice.py -v
```
Expected: `data/market/quote_*.parquet` created; test PASSES.

- [ ] **Step 5: Commit** (ship the small slice; large slices go to Drive per the proto pattern).

```bash
git add src/proto_smart_beta/experiments tests/test_market_slice.py data/market
git commit -m "Freeze the Plutus market-data slice for SB's universe (shipped parquet)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 7: `PlutusExecution` — drive the same targets through PlutusBackend

**Files:**
- Modify: `src/proto_smart_beta/execution.py` (add `PlutusExecution`)
- Test: `tests/test_execution_seam.py` (add a Plutus-backed case)

**Interfaces:**
- Consumes: `plutus.execution.PlutusBackend`; `plutus.market.protocol.Order`; `plutus.core.order.OrderType, Side`; the frozen `data/market` slice.
- Produces: `PlutusExecution(config: dict, market_root: str)` implementing `ExecutionBackend`: `rebalance_to` computes per-ticker deltas vs current `holdings()`, submits sells then buys (MTL for marketable), advances the session to the day's close mark, and records refusals/indeterminates + fills; `mark` advances the clock; reads come from the session. Exposes `.refusals`, `.indeterminates`, `.fills_log` for Tier-1.

- [ ] **Step 1: Write the failing test**

```python
def test_plutus_execution_runs_a_rebalance_over_the_slice():
    from proto_smart_beta.execution import PlutusExecution
    cfg = {
        "period": {"start": "2021-02-05", "end": "2022-12-30"},
        "resolution": "1d", "exchange_rules": {"venues": ["HSX"]},
        "accounts": {"securities": {"initial_cash": 25_000_000, "account_no": "SEC-SB"}},
        "fill_policy": {"kind": "soft"},
    }
    ex = PlutusExecution(cfg, market_root="data/market")
    assert ex.holdings() == {}          # starts flat
    assert ex.cash() > 0
```

- [ ] **Step 2: Run to verify it fails.**

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_execution_seam.py::test_plutus_execution_runs_a_rebalance_over_the_slice -v`
Expected: FAIL — `PlutusExecution` undefined.

- [ ] **Step 3: Implement PlutusExecution**

```python
# append to src/proto_smart_beta/execution.py
from datetime import datetime, time
from plutus.execution import PlutusBackend
from plutus.market.adapters.datahub import DataHubSource
from plutus.market.protocol import Order
from plutus.core.order import OrderType, Side
from plutus.market.session import Accepted, Rejected

CLOSE_MARK = time(15, 0)

class PlutusExecution:
    def __init__(self, config: dict, market_root: str):
        source = DataHubSource.for_root(market_root)
        cfg = dict(config, data={"adapter": "plutus.market.adapters.datahub.DataHubSource",
                                 "root": market_root})
        self.backend = PlutusBackend.from_config(cfg, source=source)
        self.refusals: list = []
        self.indeterminates: list = []
        self.fills_log: list = []

    def rebalance_to(self, targets, group):
        day = group["date"].iloc[0] if "date" in group else group.name
        # advance to a morning mark so today's bar is judged after submit
        self.backend.advance_to(datetime.combine(day, time(10, 0)))
        current = self.holdings()
        want = {r["tickersymbol"]: int(r["qty"]) for _, r in targets.iterrows()}
        # sells first (free settlement/cash), then buys
        for tk, held in current.items():
            tgt = want.get(tk, 0)
            if tgt < held:
                self._order(tk, Side.SELL, held - tgt)
        for tk, tgt in want.items():
            held = current.get(tk, 0)
            if tgt > held:
                self._order(tk, Side.BUY, tgt - held)
        events = self.backend.advance_to(datetime.combine(day, CLOSE_MARK))
        self.fills_log.extend(PlutusBackend.fills(events))
        return self.total_value(group)

    def _order(self, ticker, side, qty):
        ack = self.backend.submit(Order(ticker=ticker, side=side, quantity=int(qty),
                                        order_type=OrderType.MARKET_WITH_LEFTOVER_AS_LIMIT))
        if isinstance(ack, Rejected):
            (self.indeterminates if ack.is_indeterminate else self.refusals).append(
                (ticker, side, int(qty), ack.rule))

    def mark(self, group):
        day = group["date"].iloc[0] if "date" in group else group.name
        self.backend.advance_to(datetime.combine(day, CLOSE_MARK))
        return self.total_value(group)

    def holdings(self):
        out = {}
        # read every universe ticker's settled+unsettled position
        for tk in getattr(self, "_universe", ()):  # set by the runner
            h = self.backend.holdings(tk)
            q = int(getattr(h, "settled", 0) or 0) + sum(t.quantity for t in (h.unsettled or ()))
            if q:
                out[tk] = q
        return out

    def cash(self):
        c = self.backend.cash()
        return c.settled_balance + c.advanced

    def total_value(self, group):
        val = self.cash()
        prices = {r["tickersymbol"]: r for _, r in group.iterrows()} if hasattr(group, "iterrows") else {}
        for tk, q in self.holdings().items():
            row = prices.get(tk)
            if row is not None:
                val += Decimal(str(row["close"])) * q * Decimal(1000)  # PRICE_SCALE
        return val
```

Note: `holdings()` needs the universe; the runner sets `ex._universe = tuple(all_tickers)` before stepping. (A later refinement can read holdings from the session's order/position log instead.)

- [ ] **Step 4: Run the test.**

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_execution_seam.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/proto_smart_beta/execution.py tests/test_execution_seam.py
git commit -m "Add PlutusExecution: drive SB targets through the faithful market

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 8: The null-anchor runner — same signals, both backends, into the registry

**Files:**
- Create: `src/proto_smart_beta/experiments/null_anchor.py`
- Test: `tests/test_null_anchor.py`

**Interfaces:**
- Consumes: `create_bt_instance`, `NaiveExecution`, `PlutusExecution`, the frozen signal + market parquet.
- Produces: `run_null_anchor() -> dict` with `{"naive": {sharpe, hpr, mdd}, "faithful": {sharpe, hpr, mdd}, "tier1": {refusals, indeterminates, fills, blocked_by_rule}}`; and a Markdown row appended to the registry.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_null_anchor.py
from proto_smart_beta.experiments.null_anchor import run_null_anchor

def test_null_anchor_produces_both_arms_and_tier1():
    out = run_null_anchor(is_data=True)
    assert set(out) >= {"naive", "faithful", "tier1"}
    assert abs(out["naive"]["sharpe"] - 1.2971) / 1.2971 < 0.05   # null-anchor: naive == published
    # SB is the null anchor: faithful should be CLOSE to naive (small, not zero, gap)
    assert "refusals" in out["tier1"] and "indeterminates" in out["tier1"]
```

- [ ] **Step 2: Run to verify it fails.**

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_null_anchor.py -v`
Expected: FAIL — module undefined.

- [ ] **Step 3: Implement the runner**

`run_null_anchor(is_data=True)` builds two `Backtesting` instances over the same frozen signal parquet — one with the default `NaiveExecution`, one with a `PlutusExecution(cfg, "data/market")` (set `ex._universe` to the full pe_dps universe) — runs each, and reads metrics from each `Metric`. For the faithful arm, also collect `ex.refusals`, `ex.indeterminates`, `len(ex.fills_log)`, and a `blocked_by_rule` Counter over `refusals`+`indeterminates`. Return the dict.

- [ ] **Step 4: Run the test.**

Run: `cd <proto>/ProtoSmartBeta && uv run python -m pytest tests/test_null_anchor.py -v`
Expected: PASS. (If the faithful arm diverges *far* from naive, that is a finding to investigate — SB should be near-null; a large gap means a data or wiring mismatch, not a real effect.)

- [ ] **Step 5: Commit**

```bash
git add src/proto_smart_beta/experiments/null_anchor.py tests/test_null_anchor.py
git commit -m "Add the SB null-anchor runner (naive vs faithful, Tier-1 + Tier-2)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 9: Write the SB null-anchor result into the results registry (plutus repo)

**Files:**
- Create: `<plutus>/docs/reference/tables/experiments_registry.md`

**Interfaces:**
- Consumes: the dict from `run_null_anchor`.
- Produces: the registry table with the SB row; the single source the paper prose quotes.

- [ ] **Step 1: Generate the numbers**

Run:
```bash
cd <proto>/ProtoSmartBeta
uv run python -c "import json; from proto_smart_beta.experiments.null_anchor import run_null_anchor; print(json.dumps(run_null_anchor(is_data=True), default=str, indent=2))"
```
Record the printed naive/faithful/tier1 values.

- [ ] **Step 2: Write the registry**

Create `experiments_registry.md` following the T4 discipline (every value carries its provenance and regenerating command). Header explains the naive-vs-faithful contrast and the execution-intensity spectrum; the first section is **SB — null anchor**, with a table: metric | naive (published) | faithful (Plutus) | Δ, plus a Tier-1 line (refusals, indeterminates, fills, blocked-by-rule). Note the regenerating command from Step 1 and the frozen-slice provenance.

- [ ] **Step 3: Commit**

```bash
cd <plutus>
git add docs/reference/tables/experiments_registry.md
git commit -m "Add the experiments results registry with the SB null-anchor row

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Self-Review notes (author)

- **Spec coverage:** ExecutionBackend seam (T5), PlutusBackend (T1), identical frozen parquet (T3+T6, both backends read parquet), behaviour-preserving gate (T4), null-anchor result + registry (T8+T9), branch layout (T2). Data-extraction pipeline is SB-scoped here (T6) and generalises in later phases. algotradeDB not needed for SB (equity CSV suffices) — deferred to MM/Pair phases.
- **Deferred to later phases (out of Phase 0):** ProtoGrid/ProtoPair 9-step repos, MM refactor, algotradeDB futures extraction, the intensity-spectrum figure, the frozen-diagnostic reuse of `fill_divergence.py`/`equity_admission.py` at scale.
- **Known soft spots to watch in implementation:** `PlutusExecution.holdings()` reading the universe (T7 note); `rebalancing()` returns `new_asset` whose exact composition the NaiveExecution must reproduce (T5 — verify against the L268-300 body); the frozen market slice's price consistency with `pe_dps` close (both algotradeDB-sourced; verify a few rows).
