# ProtoGrid (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `proto/ProtoGrid` — a tick-resolution, cost-aware buy-low/sell-high equity grid — as a 9-step strategy repo, and run its naive engine against the faithful Plutus market on one frozen tick slice, emitting the second point (SB → Grid) of the intensity-spectrum into the experiments registry.

**Architecture:** Hand-build the repo mirroring the sibling `proto/ProtoSmartBeta` (a `.plutus/manifest.yaml` + `plutus_verify` instrumentation + `src/` layout — SB uses **no** interactive 9-step skills and has no `.9step/`, so neither does Grid; the standalone `9-step:assess-realism` skill supplies the realism gate). One shared `strategy.py` produces the grid signals; the naive backtester (`backtest.py`) and the faithful runner (`experiments/grid_anchor.py`, mirroring SB's `null_anchor.py`) both consume them through the Phase-0 `ExecutionBackend`/`PlutusBackend` seam, reading the identical frozen slice. The faithful arm constructs a `TickSource` by hand and passes it via `PlutusBackend.from_config(cfg, source=...)` at `resolution:"tick"`.

**Tech Stack:** Python 3.12, uv + hatchling, DuckDB/pandas/pyarrow (data), `plutus` (path dep, editable), `plutus_verify`, pytest.

## Global Constraints

- **New repo `proto/ProtoGrid`**, branch `rivf-2026` (create it; matches the other proto repos). `plutus` stays on `rivf-2026`. Per-task local commits; do **not** push/PR (owner finalizes later).
- **Same signals, two backends.** `strategy.py` runs once against the `ExecutionBackend` interface; naive vs faithful is a backend swap. Both arms read the **one frozen tick slice** — identical file in, so the delta is purely execution.
- **Behaviour-preserving naive anchor.** The naive engine reproduces its own committed baseline; `plutus check` green under it.
- **Δ is a shared signal parameter set from the *assumed* static cost** (~0.4% round-trip), not the real dated charges — or the naive-vs-faithful contrast stops being purely execution. The faithful arm applies real dated VN charges on top.
- **Continuous grid** (confirmed): held inventory + paired sells persist across monthly re-anchors; start flat once. Classic paired grid: a buy at rung *k* places a sell at fill+Δ.
- **Ladder:** 8 buy rungs below the month-open anchor at spacing Δ (per ticker, cost-driven, tick-snapped). Re-anchor monthly to the month-open reference.
- **Capital 2 B VND**, split equally across 3 grids; per-rung buy notional = capital/grid ÷ 8, floored to a 100-share lot. Prices in thousands of đồng, cash in đồng (`PRICE_SCALE = 1000`).
- **Tick resolution.** Faithful policy headline = `soft` (uncapped). At tick resolution synthesized intervals carry `volume=None` and `open/high/low=None`, so only the **book tier** of band lock applies and `hard`/`probabilistic` degrade to INDETERMINATE (report honestly; do not treat as a bug).
- **Pre-registered kill criteria** (IS, naive arm, set before the IS run): net Sharpe ≤ 0 **or** net HPR ≤ 0 **or** < 300 completed round-trips → falsified.
- **IS = 2021-01 → 2023-08, OOS = 2023-09 → 2024-09.** OOS sealed until Task 8.
- **Data roots:** tick archive `$STOCK_QUOTE_CSV` (has `quote_matched.csv`, `quote_askprice.csv`, `quote_bidprice.csv`); daily band corpus `$HERMES_PARQUET`.
- **Attribution** on every commit:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure (new repo `proto/ProtoGrid`, mirroring ProtoSmartBeta)

| Path | Responsibility |
|---|---|
| `pyproject.toml` | package `proto-grid`, hatchling, `algotrade-plutus = {path="../../plutus", editable=true}`, console scripts `pg-*`. |
| `src/proto_grid/strategy.py` | **Pure** grid logic both arms import: anchor, Δ, ladder, `PairedGrid` state machine. |
| `src/proto_grid/config/config.py` | loads `.env` + `parameter/*.json` into module dicts (mirror SB). |
| `src/proto_grid/backtest.py` | the **naive** grid engine + `pg-backtest`; `pv.step("in_sample_backtest")`. |
| `src/proto_grid/optimize.py` | IS-only sweep of Δ-margin × rung-count → stable region; `pg-optimize`. |
| `src/proto_grid/evaluate.py` | OOS rerun with optimized params; `pv.step("out_of_sample_backtest")`; `pg-evaluate`. |
| `src/proto_grid/metrics/metric.py` | Sharpe/HPR/MDD + round-trip count (mirror SB's `Metric`). |
| `src/proto_grid/experiments/select_tickers.py` | the ticker-selection criterion → `parameter/tickers.json` + `docs/data.md`. |
| `src/proto_grid/experiments/extract_tick.py` | freeze the tick slice (3 tickers × window) + the daily band slice. |
| `src/proto_grid/experiments/grid_anchor.py` | the naive-vs-faithful runner (mirror SB `null_anchor.py`); Tier-1/Tier-2. |
| `parameter/{backtesting,optimization,optimized,tickers}.json` | externalized params. |
| `docs/hypothesis.md`, `docs/data.md` | 9-step step-1/step-2 artifacts. |
| `.plutus/manifest.yaml` | steps + expected + `nine_step_coverage` (mirror SB). |
| `tests/` | unit tests (strategy, metrics, selection) + regression baselines. |
| `data/tick/`, `data/band/` | frozen slices (git-ignored if large → Drive; small committed). |
| **`plutus`**: `docs/reference/tables/experiments_registry.md` | the Grid results block (Task 10). |

---

## Task 1: Scaffold the repo

**Files:** Create `proto/ProtoGrid/{pyproject.toml, README.md, .gitignore, src/proto_grid/__init__.py, src/proto_grid/config/config.py, docs/hypothesis.md}`; `git init` on branch `rivf-2026`.

**Interfaces:** Produces an installable `proto_grid` package importing `plutus`.

- [ ] **Step 1: Copy the SB scaffold shape.** Read `proto/ProtoSmartBeta/pyproject.toml` and replicate it for `proto-grid`: hatchling build, `requires-python=">=3.12"`, `dependencies=["algotrade-plutus", "duckdb", "pandas", "pyarrow", "pytz", "numpy", "plutus-verify"]`, `[tool.uv.sources] algotrade-plutus = {path="../../plutus", editable=true}` (+ `plutus-verify` wired the same way SB wires it — check SB's source block), `[tool.hatch.build.targets.wheel] packages=["src/proto_grid"]`, and console scripts `pg-select-tickers`, `pg-extract`, `pg-backtest`, `pg-optimize`, `pg-evaluate` pointing at the modules below.

- [ ] **Step 2: Write `docs/hypothesis.md`** — the pre-registered step-1 artifact: the thesis (§2 of the design), the falsifiable kill criteria (IS net Sharpe ≤ 0 or net HPR ≤ 0 or < 300 round-trips), and the assumed costs (brokerage 0.15%/side + 0.1% sell tax ≈ 0.4% round-trip) recorded as pre-registration. Copy the relevant prose from `plutus/docs/superpowers/specs/2026-09-14-protogrid-design.md` §2–§3.

- [ ] **Step 3: Package skeleton + `config/config.py`** mirroring SB (load `.env` for any DB creds — not needed for Phase 1 since data is frozen, but keep the shape; load `parameter/*.json`). `.gitignore` includes `.venv/`, `data/` (large slices), `__pycache__/`.

- [ ] **Step 4: Create the venv and verify install.**
Run:
```bash
cd proto/ProtoGrid && uv venv && uv pip install -e ../../plutus --no-deps && uv pip install duckdb pandas pyarrow pytz numpy && uv pip install -e .
python -c "import proto_grid, plutus; from plutus.execution import PlutusBackend; from plutus.market.adapters.tick import TickSource; print('ok')"
```
Expected: `ok`.

- [ ] **Step 5: Commit.**
```bash
git add -A && git commit -m "Scaffold ProtoGrid repo (mirrors ProtoSmartBeta shape)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Ticker selection by criterion

**Files:** Create `src/proto_grid/experiments/select_tickers.py`, `tests/test_select_tickers.py`; writes `parameter/tickers.json` + `docs/data.md`.

**Interfaces:**
- Consumes: the daily band corpus (`$HERMES_PARQUET`) via DuckDB; the VN30 constituent list (from `quote_vn30`/the corpus, or a hardcoded 2021–2024 VN30 set if the corpus lacks it — check `plutus.market.adapters.datahub` / the corpus for a VN30 table).
- Produces: `rank_tickers(frame) -> list[dict]` and a `main()` that writes `parameter/tickers.json` = `{"tickers": ["AAA","BBB","CCC"], "criteria": {...}}`.

- [ ] **Step 1: Write the failing test for the ranking function.**
```python
# tests/test_select_tickers.py
import pandas as pd
from proto_grid.experiments.select_tickers import score_ticker

def test_score_prefers_liquid_volatile_rangebound():
    # a liquid, volatile, mean-reverting series scores above a thin trending one
    import numpy as np
    dates = pd.date_range("2021-01-01", periods=250, freq="B")
    osc = 20 + np.sin(np.arange(250) / 5)          # oscillates, no drift
    trend = np.linspace(20, 60, 250)               # pure trend
    liquid = score_ticker(pd.DataFrame({"close": osc, "volume": [1e6]*250}))
    thin   = score_ticker(pd.DataFrame({"close": trend, "volume": [1e3]*250}))
    assert liquid["liquidity"] > thin["liquidity"]
    assert liquid["range_boundedness"] > thin["range_boundedness"]
```

- [ ] **Step 2: Run it — fails** (`score_ticker` undefined). `pytest tests/test_select_tickers.py -q`.

- [ ] **Step 3: Implement `score_ticker` + `rank_tickers`.**
```python
import numpy as np, pandas as pd

def score_ticker(df: pd.DataFrame) -> dict:
    """Liquidity, realized vol, and range-boundedness for one ticker's daily frame.

    range_boundedness = sum(|daily returns|) / |net return| — high when price
    oscillates without net drift (a grid's edge), low for a pure trend.
    """
    close = df["close"].astype(float).to_numpy()
    rets = np.diff(close) / close[:-1]
    liquidity = float(np.median(df["volume"].astype(float)))
    realized_vol = float(np.std(rets, ddof=1)) if len(rets) > 1 else 0.0
    net = abs(close[-1] / close[0] - 1.0) if close[0] else 0.0
    churn = float(np.sum(np.abs(rets)))
    range_boundedness = churn / net if net > 1e-6 else churn * 1e3
    return {"liquidity": liquidity, "realized_vol": realized_vol,
            "range_boundedness": range_boundedness}

def rank_tickers(scores: dict[str, dict], top: int = 3) -> list[str]:
    """Rank by the product of percentile ranks across the three axes; take `top`."""
    import pandas as pd
    s = pd.DataFrame(scores).T
    pct = s.rank(pct=True)
    combined = (pct["liquidity"] * pct["realized_vol"] * pct["range_boundedness"])
    return list(combined.sort_values(ascending=False).head(top).index)
```
`main()` queries each VN30 name's daily close+volume over 2021-01..2024-09 from the corpus, scores, ranks, and writes `parameter/tickers.json` + a `docs/data.md` table of the chosen 3 with their criterion values.

- [ ] **Step 4: Run the test — passes.** Then run `pg-select-tickers` against the real corpus; record the 3 tickers + values in `docs/data.md`.
Run: `pytest tests/test_select_tickers.py -q` (PASS), then `PLUTUS_DATA_ROOT=$HERMES_PARQUET python -m proto_grid.experiments.select_tickers`.
Expected: `parameter/tickers.json` written with 3 liquid/volatile/range-bound VN30 names.

- [ ] **Step 5: Commit** (`git add -A && git commit -m "Select 3 grid tickers by liquidity×vol×range-boundedness criterion ..."` + trailer).

---

## Task 3: Grid strategy core (`strategy.py`)

**Files:** Create `src/proto_grid/strategy.py`, `tests/test_strategy.py`.

**Interfaces:**
- Consumes: a tick size function (from `plutus.core.constant` / the venue spec — reuse `plutus`'s dated tick grid, e.g. `HSX.tick_size_function`, so rungs snap to the real grid) and the assumed cost rate.
- Produces (the shared API both arms call):
  - `grid_step(anchor_price: Decimal, assumed_cost_rate: Decimal, tick_size_fn, margin: int = 3) -> Decimal` — Δ.
  - `buy_rungs(anchor: Decimal, delta: Decimal, n: int = 8) -> list[Decimal]`.
  - `class PairedGrid` — the continuous paired-grid state machine: `.reanchor(anchor)`, `.on_price(ts, price) -> list[Order]` (emits buy/sell orders as rungs are crossed), `.on_fill(order_id, side, qty, price)` (buy fill → arm a sell at fill+Δ; sell fill → free the paired slot), `.open_orders`, `.inventory`.

- [ ] **Step 1: Write failing tests for the pure functions.**
```python
# tests/test_strategy.py
from decimal import Decimal
from proto_grid.strategy import grid_step, buy_rungs

def _tick(_price):            # HSX 10k-50k band = 0.05 (thousands)
    return Decimal("0.05")

def test_grid_step_clears_margin_over_cost_and_snaps_to_tick():
    # price 24.2, assumed round-trip 0.4% -> cost ~0.0968; margin 3x -> >=0.29;
    # snapped up to a 0.05 tick multiple -> 0.30
    d = grid_step(Decimal("24.2"), Decimal("0.004"), _tick, margin=3)
    assert d == Decimal("0.30")
    assert (d / Decimal("0.05")) % 1 == 0          # whole tick multiple

def test_buy_rungs_are_below_anchor_evenly_spaced():
    rungs = buy_rungs(Decimal("24.2"), Decimal("0.30"), n=8)
    assert rungs == [Decimal("23.90"), Decimal("23.60"), Decimal("23.30"),
                     Decimal("23.00"), Decimal("22.70"), Decimal("22.40"),
                     Decimal("22.10"), Decimal("21.80")]
```

- [ ] **Step 2: Run — fails.** `pytest tests/test_strategy.py -q`.

- [ ] **Step 3: Implement the pure functions.**
```python
from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR

def grid_step(anchor_price, assumed_cost_rate, tick_size_fn, margin=3):
    """Smallest whole-tick step whose gross clears `margin` x the round-trip cost.

    round_trip_cost (price points) = anchor_price * assumed_cost_rate. Delta must
    be >= margin * that, snapped UP to a whole multiple of the tick size at the
    anchor price, so net = Delta - cost >= (margin-1) x cost.
    """
    cost = anchor_price * assumed_cost_rate
    raw = cost * Decimal(margin)
    tick = tick_size_fn(anchor_price)
    steps = (raw / tick).to_integral_value(rounding=ROUND_CEILING)
    return steps * tick

def buy_rungs(anchor, delta, n=8):
    """n rung prices below the anchor: anchor-delta ... anchor-n*delta."""
    return [anchor - delta * Decimal(k) for k in range(1, n + 1)]
```

- [ ] **Step 4: Write + run the `PairedGrid` state-machine tests** (continuous, start-flat, paired): a buy fill arms a sell at fill+Δ; a subsequent price touch of that sell emits a sell order; after the sell fills, a re-touch of the buy rung re-emits the buy; a re-anchor recomputes buy rungs but leaves armed sells + inventory intact. Assert order emission and inventory transitions on a scripted price path. (Full test code: script a price series and assert the emitted `Order` list + `.inventory` after each `on_price`/`on_fill`.)

- [ ] **Step 5: Implement `PairedGrid`** to pass. Key rules: emit a buy `Order` (LIMIT at rung price) the first time price ≤ a buy rung with no live order/inventory at that rung; on a buy fill, arm+emit a sell LIMIT at fill+Δ; on a sell fill, free the rung; `reanchor(anchor)` recomputes `buy_rungs` for *new* buys only (armed sells + inventory persist). Order sizing is the caller's (backend) job — `strategy.py` emits intent (ticker, side, price, and the per-rung share qty passed in at construction).

- [ ] **Step 6: Run all strategy tests — green.** `pytest tests/test_strategy.py -q`.

- [ ] **Step 7: Commit** (strategy + tests, trailer).

---

## Task 4: Freeze the data slices

**Files:** Create `src/proto_grid/experiments/extract_tick.py`, `tests/test_slice_smoke.py`; writes `data/tick/{quote_matched,quote_askprice,quote_bidprice}.csv` and `data/band/*.parquet`.

**Interfaces:**
- Consumes: `parameter/tickers.json` (the 3 tickers), the tick archive + daily corpus roots (Global Constraints).
- Produces: a frozen tick archive dir (`data/tick/`) readable by `TickSource(archive_root="data/tick", band_source=...)`, and a daily band slice (`data/band/`) readable by `DataHubSource.for_root("data/band")`.

- [ ] **Step 1: Implement `extract_tick.py`.** For each of `quote_matched`, `quote_askprice`, `quote_bidprice`: DuckDB `COPY (SELECT * FROM read_csv_auto('<archive>/<t>.csv') WHERE tickersymbol IN (...) AND datetime >= '2021-01-01' AND datetime < '2024-10-01') TO 'data/tick/<t>.csv'`. For the band slice, reuse SB's `extract_market.py` approach (filter the daily `quote_*` tables — close/ceiling/floor/ref/dailyvolume/open/max/min — to the 3 tickers × window → `data/band/*.parquet`). Keep the exact table/column names SB used (read `proto/ProtoSmartBeta/src/proto_smart_beta/experiments/extract_market.py` for the daily table list + parquet write).

- [ ] **Step 2: Run the extract.** `python -m proto_grid.experiments.extract_tick`. Note the resulting `data/tick/` size — if > ~100 MB, mark it for Drive (proto pattern) in `.gitignore` + `docs/data.md`; else it may be committed.

- [ ] **Step 3: Smoke test the slice reads.**
```python
# tests/test_slice_smoke.py
from datetime import datetime
from plutus.market.adapters.tick import TickSource
from plutus.market.adapters.datahub import DataHubSource

def test_tick_slice_yields_states_with_a_book():
    band = DataHubSource.for_root("data/band")
    src = TickSource("data/tick", band_source=band)
    import json; t = json.load(open("parameter/tickers.json"))["tickers"][0]
    states = list(src.states(t, datetime(2021,1,4), datetime(2021,1,8)))
    assert states, "no tick states in the frozen slice"
    assert any(s.book and (s.book.asks or s.book.bids) for s in states), \
        "the frozen slice carries no ask/bid ladder — the book tier needs it"
```
Run: `pytest tests/test_slice_smoke.py -q` (PASS — confirms the book tier will have input, the Task-of-record for Grid's payoff).

- [ ] **Step 4: Fix the IS/OOS split** as constants in `config/config.py` (`IS = (2021-01-04, 2023-08-31)`, `OOS = (2023-09-01, 2024-09-30)`).

- [ ] **Step 5: Commit** (extractor + smoke test + split constants; data via Drive or committed per size).

---

## Task 5: Naive engine + in-sample backtest

**Files:** Create `src/proto_grid/backtest.py`, `src/proto_grid/metrics/metric.py`, `tests/test_metric.py`.

**Interfaces:**
- Consumes: `strategy.py` (signals), the frozen tick slice, `parameter/backtesting.json` (capital 2e9, 3 grids, n_rungs 8, assumed_cost_rate 0.004, margin 3).
- Produces: `GridBacktest.run(is_data=True) -> dict` with `sharpe/hpr/mdd/round_trips/fills`; a `pv.step("in_sample_backtest")` block.

- [ ] **Step 1: Metric tests + impl** (mirror SB's `metrics/metric.py`): Sharpe (annualized, daily returns), HPR, MDD, and a `round_trips` counter. TDD one test asserting Sharpe/HPR/MDD on a known equity series.

- [ ] **Step 2: Implement the naive engine.** Iterate the tick slice per ticker; feed prices to `PairedGrid.on_price`; **naive fills**: any emitted buy/sell LIMIT fills immediately at its rung price (full ladder on touch — no band clip, no lock, no tick-snap beyond the strategy's own snapping, unlimited size/queue, **instant cash** so a sell's proceeds fund the next buy same-tick), charged the **static assumed** round-trip cost. Split 2 B VND across 3 grids; per-rung qty = capital/grid ÷ 8 ÷ anchor_price, floored to 100. Build a daily equity curve → metrics. Wrap `main()` in `pv.step("in_sample_backtest")` with `r.metric("sharpe_ratio", ...)`, `hpr`, `mdd`, `round_trips`, and chart artifacts (mirror SB).

- [ ] **Step 3: Run IS.** `pg-backtest` (or `python -m proto_grid.backtest`) on the IS slice. Record `result/backtest/` metrics.

- [ ] **Step 4: Regression baseline test** — assert the naive IS metrics equal the just-recorded values (the behaviour-preserving anchor), mirroring SB's `test_regression_baseline.py`.

- [ ] **Step 5: Commit.**

---

## Task 6: Kill-criteria gate

**Files:** Create `tests/test_kill_criteria.py`.

- [ ] **Step 1: Write the gate test** asserting the IS naive run meets the pre-registered criteria:
```python
def test_in_sample_clears_pre_registered_kill_criteria():
    from proto_grid.backtest import GridBacktest
    r = GridBacktest().run(is_data=True)
    assert r["sharpe"] > 0, "kill: IS net Sharpe <= 0"
    assert r["hpr"] > 0, "kill: IS net HPR <= 0"
    assert r["round_trips"] >= 300, f'kill: only {r["round_trips"]} round-trips'
```
- [ ] **Step 2: Run it.** If it **fails**, the hypothesis is falsified for these tickers → **STOP and escalate** (re-run Task 2 selection with a different criterion weighting, or report the kill to the owner). Do not weaken the thresholds — they are pre-registered.
- [ ] **Step 3: Commit** (on pass) with the IS metrics in the message.

---

## Task 7: Optimization (IS-only, stable region)

**Files:** Create `src/proto_grid/optimize.py`; writes `parameter/optimized.json`.

- [ ] **Step 1: Implement the sweep** over Δ-margin ∈ {2,3,4} × n_rungs ∈ {6,8,10} on the **IS slice only**; record each cell's IS Sharpe/round-trips to a CSV. Pick a **stable region** (a cell whose neighbours are all similar — not the single max-Sharpe spike; mirror SB's optimize discipline). Write the chosen `{margin, n_rungs}` to `parameter/optimized.json`.
- [ ] **Step 2: Run it**; record the grid + the chosen stable cell in `docs/data.md`.
- [ ] **Step 3: Commit.**

---

## Task 8: Out-of-sample backtest + realism audit

**Files:** Create `src/proto_grid/evaluate.py`; `tests/test_oos_regression.py`.

- [ ] **Step 1: Implement `evaluate.py`** — rerun the **same** naive engine on the **OOS** slice with `parameter/optimized.json`, wrapped in `pv.step("out_of_sample_backtest")` (mirror SB's `evaluate.py`). Surface IS→OOS degradation.
- [ ] **Step 2: Run OOS**; record metrics; add an OOS regression baseline test.
- [ ] **Step 3: Realism audit.** Invoke the standalone **`9-step:assess-realism`** skill on `proto/ProtoGrid` (it needs no `.9step/` state). Record the band + any remediation in `docs/data.md`. Address any hard-credibility failure (zero cost / no OOS split / < 300 trades) before proceeding — the design already builds these in, so this should pass.
- [ ] **Step 4: Commit.**

---

## Task 9: Faithful arm + naive-vs-faithful runner

**Files:** Create `src/proto_grid/experiments/grid_anchor.py`, `tests/test_grid_anchor_smoke.py`.

**Interfaces:**
- Consumes: `strategy.py`, the frozen slice, `PlutusBackend` (`from plutus.execution import PlutusBackend`), `TickSource`, `DataHubSource`.
- Produces: `run_grid_anchor() -> {"naive": {...}, "faithful": {...}}` mirroring SB's `run_null_anchor`, with Tier-1 counts.

- [ ] **Step 1: Build the faithful backend** (the tick wiring the recon pinned down):
```python
from plutus.market.adapters.tick import TickSource
from plutus.market.adapters.datahub import DataHubSource
from plutus.execution import PlutusBackend

band = DataHubSource.for_root("data/band")
tick = TickSource("data/tick", band_source=band)          # 2 args — build by hand
cfg = {
    "period": {"start": str(span_start), "end": str(span_end)},
    "resolution": "tick",                                   # legal; PlutusBackend is resolution-agnostic
    "exchange_rules": {"venues": ["HSX"]},
    "accounts": {"securities": {"initial_cash": 2_000_000_000, "account_no": "SEC-GRID"}},
    "fill_policy": {"kind": "soft"},                        # headline; uncapped -> fills without volume
    "data": {"adapter": "plutus.market.adapters.tick.TickSource", "root": "data/tick"},
    # NB: data.adapter cannot build TickSource (2 ctor args) — the source= kwarg is authoritative:
}
backend = PlutusBackend.from_config(cfg, source=tick)
```

- [ ] **Step 2: Replay the same `strategy.py` signals through both arms** (naive engine from Task 5; faithful via `backend.submit`/`advance_to`), reading the identical slice. Advance tick-by-tick (or per trading day, submitting the day's grid orders then `advance_to` end-of-day). **T+2 on, sale-advance off** (do not enable `advance_sale_proceeds`), so a re-buy after a sell stalls on locked cash in the faithful arm.

- [ ] **Step 3: Count Tier-1** (mirror + extend SB's `null_anchor` counters):
  - **Refusals by cause** at submit: `Rejected` acks tallied by `ack.rule.name` (BAND_LIMIT out-of-band rungs, TICK_GRID, ROUND_LOT). Split `is_indeterminate` into a separate counter.
  - **Fill-time band-lock no-fills**: the Accepted-but-never-filled-on-a-band-edge-day classifier from SB's `null_anchor.py` (`source.state_at(...).locked_side is side`), adapted to tick (check per submitted rung).
  - **T+2 stalls**: buy-back rungs the naive arm funded same-day but the faithful arm could not (compare the two arms' fill sets per rung/day).
  - **Fill-policy spread** (honest at tick): rerun the faithful arm under `hard` and `probabilistic` and report their outcomes; **expect them dominated by no-volume INDETERMINATE** at tick resolution (record the indeterminate rate — itself the finding that the conservative policies cannot act without depth data).
- [ ] **Step 4: Tier-2** — net P&L/Sharpe/MDD, naive vs faithful, from each arm's equity curve (P&L in the runner's harness, per the design; Plutus reports only fills/cash/margin).
- [ ] **Step 5: Run it**, capture the JSON. Smoke test asserts the result shape + that the faithful arm produced fills and at least one BAND_LIMIT refusal (the admission effect firing).
- [ ] **Step 6: Commit.**

---

## Task 10: Registry, manifest, and `plutus check`

**Files:** Modify `plutus/docs/reference/tables/experiments_registry.md`; create `proto/ProtoGrid/.plutus/manifest.yaml`.

- [ ] **Step 1: Registry (in `plutus`).** Add a **Grid** block after the SB block in `experiments_registry.md`, same discipline: the naive-vs-faithful metric table, the Tier-1 paragraph (refusals by cause, T+2 stalls, fill-policy spread + the tick no-volume caveat, fill-time band-lock — expected non-zero here, unlike SB, because tick + book tier), Tier-2, and the two regenerate commands (`pg-extract`; `python -m proto_grid.experiments.grid_anchor`). Add Grid as the second spectrum point (SB → Grid).
- [ ] **Step 2: `.plutus/manifest.yaml` (in ProtoGrid)** mirroring SB's (schema 2.0): `env`, `data_sources`, `steps` (`data_preparation` → the extract; `in_sample_backtest`; `optimization` (artifact_check); `out_of_sample_backtest`), `expected` (per-step metric tolerances), `nine_step_coverage` (steps 1–6 present, 7 absent). Copy SB's structure and adapt the step commands/metrics.
- [ ] **Step 3: `plutus check` green under the naive backend.**
Run: `cd proto/ProtoGrid && plutus check`
Expected: exit 0 (all steps reproduce within tolerance).
- [ ] **Step 4: Commit** (both repos: ProtoGrid manifest; plutus registry).

---

## Self-review checklist (run before execution)
- **Spec coverage:** §1 role → Tasks 9-10 (spectrum point); §2 hypothesis/kill → Tasks 2,6; §3 mechanic → Task 3; §4 two arms → Tasks 5,9; §5 data/resolution → Tasks 2,4; §6 sizing → Tasks 5,9; §7 measures → Tasks 9-10; §8 build order → all; §9 risks → below; §10 acceptance → all.
- **Known risks carried from the design + recon:** tick-run cost (Task 4 flags Drive fallback); book density (Task 4 smoke test gates it); `volume=None` at tick → degenerate hard/prob policies (Task 9 handles honestly); Δ from assumed (not real) cost (Global Constraint); behaviour-preserving naive anchor (Tasks 5,6).

## Open decision for the executor to confirm with the owner
- **Frozen tick-slice hosting**: if `data/tick/` is large (> ~100 MB), it ships via Drive (SB pattern) rather than committed — confirm the Drive location when Task 4 measures the size.
