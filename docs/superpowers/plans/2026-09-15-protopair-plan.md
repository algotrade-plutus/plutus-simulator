# ProtoPair (Phase 3 — the cross-market capstone) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `proto/ProtoPair` — a daily-resolution VN30-basket-vs-VN30F1M cross-market pair — as a 9-step strategy repo, run its naive single-ledger engine against the faithful two-venue Plutus market on one frozen daily slice, and emit the **top** point of the execution-intensity spectrum (SB → Grid → MM → **Pair**) into the experiments registry, with **settlement asymmetry** (equity T+2 securities pool vs futures daily-VM derivatives pool) as the Tier-1 headline.

**Architecture:** Hand-build the repo mirroring the sibling `proto/ProtoGrid` and `proto/ProtoSmartBeta` (a `.plutus/manifest.yaml` + `plutus_verify` instrumentation + `src/` layout; **no** `.9step/`). One plutus-free `strategy.py` (+ `basket.py`, `hedge.py`, `roll.py`) produces the pair signal; the **naive** single-ledger backtester (`backtest.py`) and the **faithful** two-venue arm (`faithful/coordinator.py` driven by `experiments/pair_anchor.py`, mirroring SB's `null_anchor.py`) both consume it through the `plutus.execution.PlutusBackend` facade over a `venues=['HSX','HNXDS']` `ExchangeSession`, reading the identical frozen daily slice. The pair is a **pure plutus consumer except** the continuous→dated-contract roll and the caller-side funding-on-demand/abandon glue that keeps the two legs atomic (Plutus has no notion of a "pair").

**Tech Stack:** Python 3.12, uv + hatchling, DuckDB/pandas/pyarrow/numpy (data), `plutus` (editable path dep), `plutus_verify`, pytest.

## Global Constraints

- **New repo `proto/ProtoPair`** at absolute path `<proto>/ProtoPair` (sibling of `plutus`; the `proto/` shorthand in the spec resolves here). Branch `rivf-2026` (create it; matches the other proto repos). `plutus` stays on `rivf-2026`. Per-task local commits; do **not** push/PR (owner finalizes later). **Do not commit this plan file.**
- **Same signals, two backends.** `strategy.py` + `basket.py` + `hedge.py` + `roll.py` run once; naive vs faithful is a backend swap. Both arms read the **one frozen daily slice** (`data/market/`) — identical files in, so the delta is purely execution.
- **Behaviour-preserving naive anchor.** The naive engine reproduces its own committed baseline; `plutus check` green under it.
- **Proceed gate = ACTIVITY + credibility, NOT P&L** (binding, per memory `rivf26-fidelity-not-pnl`). No Sharpe/HPR stop-gate anywhere. (a) **Credibility pre-check:** the IS basis is a credible mean-reverting vehicle — Engle-Granger / ADF stationarity at p < ~0.10 **or** a finite estimated half-life within the IS window. (b) **Activity threshold:** the naive IS run generates **≥ ~20 completed pair round-trips** *and* hundreds of leg-level order events. Exact numbers pre-registered in `docs/hypothesis.md` at Task 1, never loosened after seeing the result. `DECISION-PENDING (spec §2): exact activity numbers` — plan on 20 round-trips + 300 leg order events; keep the numbers in one config constant so a revision touches one line.
- **Optimization is B-style** (cost-driven `z_in` + hedge sizing swept for the artifact, representative cell picked, ACTIVITY reported — **no P&L objective**, no rolling-β or lookback-L Sharpe tuner).
- **Signal:** rolling **z-score of the basis**, `basis = VN30F1M_close − VN30INDEX_close`, `z = (basis − mean_L) / std_L`, lookback **L = 60** sessions. Enter the **executable** leg (long basket, short future) when `z ≥ +z_in`; exit when `z ≤ z_out` (revert toward 0) **or** on a roll/expiry boundary. `z_in` cost-driven (covers the modelled round-trip cost), **not** Sharpe-tuned. `DECISION-PENDING (spec §3c)`.
- **Hedge ratio:** **static IS-fitted β** (OLS of basket returns vs future returns on IS), held fixed OOS, then **snapped to whole lots (basket) / whole contracts (future)**. **Not rolling.** `DECISION-PENDING (spec §3b)`.
- **Direction asymmetry:** only long-basket / short-future is executable (no operational stock short-sale in Vietnam → `UNSETTLED_HOLDING`/naked-short refusal on HSX). The mirror signal (`z ≤ −z_in`) is **sat out**; the count of forgone mirror-side signals is a Tier-1 opportunity-set-asymmetry measure.
- **Settlement asymmetry = the Tier-1 HEADLINE.** Two segregated pools under one session, two venues: securities pool (equity leg) settles **T+2**; derivatives pool (futures leg) settles **daily variation margin in cash**. Headline funding policy **settled-cash-only (sale-advance OFF)** so the stall is visible; ship a **sale-advance ON variant**; "can't cure → forced-close is the finding" is the third outcome. The **funding-on-demand / abandon-if-unfundable** glue is **caller-side** (Plutus has no "pair" concept).
- **Margin ladder (futures leg):** `IM = rate × |net| × 100,000 × price`, **rate 0.13 → 0.17 @ 2022-12-15**; warning 0.80 / call 0.90 / forced-close 1.00; daily VM cash settlement; call → cure-by-deadline → forced-close if unanswered. (Template `LADDER`/`BROKER_PROFILE`, `validation/scenarios/pair-trade.py:377-421`.)
- **Roll:** strategy-side glue, **data-driven** from `futurecontractcode_full.parquet` (columns `date, futurecode, contract`; VN30F1M → dated contract). Close the expiring dated contract on its last session, open the new front month next session; **no pre-roll into F2M**. **Optional:** carry one roll to expiry to strike the **CLOSE_PROXY** settlement (staged `settlement` column is NaN → `SettlementSource.CLOSE_PROXY`, `substituted=True`; template gap 972.78 published vs 972.5 proxy = 112,000đ on a 4-lot short).
- **Windows:** **IS = 2022-01-01 → 2023-12-31, OOS = 2024-01-01 → 2025-06-30** (`DECISION-PENDING spec §5/Q7`). Crosses **KRX 2025-05-05** (labeled dated-edition demo); spans **IM 0.13→0.17 @ 2022-12-15**. OOS sealed until Task 12. **Daily resolution** (`DECISION-PENDING spec §5/Q8`; the optional tick sub-window is an isolated later extension — see end of plan).
- **Capital (two configs, mirror template DEPOSIT_A vs DEPOSIT_B):** **Comfortable** (both pools funded; futures leg never leaves `ok` on entry — isolates the pure T+2/segregation gap) and **Thin deposit** (derivatives deposit sized to breach → exercise the dated ladder). Basket ≈ 400M đồng, thin deposit ≈ 60M đồng; **derivatives deposit opens at 0** — every đồng arrives by explicit `transfer`. `PRICE_SCALE = 1000` (prices in thousands of đồng, cash in đồng); futures multiplier 100,000 đồng/point. `DECISION-PENDING (spec §6): exact đồng figures` — confirm before the faithful run (as SB/MM did).
- **Data roots:**
  - Futures daily + roll: `$ALGOTRADEDB_SLICE/vn30f1m_vn30f2m_daily.parquet` (cols `date, futurecode, contract, open, high, low, close, reference, ceiling, floor, volume, open_interest, settlement`; `settlement` NaN; 2021-06 → 2026-09) and `$ALGOTRADEDB_SLICE/futurecontractcode_full.parquet` (cols `date, futurecode, contract`).
  - Equity daily ≤ **2024-09-26**: `$STOCK_QUOTE_CSV/` (CSV; `quote_close.csv`/`quote_ceil.csv`/`quote_floor.csv`/`quote_reference.csv`/`quote_open.csv`/`quote_high.csv`/`quote_low.csv`/`quote_max.csv`/`quote_min.csv`/`quote_dailyvolume.csv`/`quote_settlementprice.csv`/`quote_oi.csv`, each `datetime, tickersymbol, price`).
  - VN30 membership snapshots: `$HERMES_PARQUET/quote_vn30.parquet` (`datetime, tickersymbol`) — **coverage ends 2022-08-01**; later review snapshots come from the algotradeDB freeze (Task 8).
  - **Post-2024-09-26 equity daily + VN30 membership post-2022-08** via a **read-only algotradeDB freeze** (cred `$CRED_DIR/algotradeDB-readonly.json` — **NEVER commit**; gitignored; convert selectively fields × tickers × dates, never the whole corpus). Both arms then read one frozen slice.
- **plutus is an editable path dep** `algotrade-plutus = {path="../../plutus", editable=true}`.
- **Attribution** on every commit:
  ```
  Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>
  ```

---

## File Structure (new repo `proto/ProtoPair`, mirroring ProtoGrid/ProtoSmartBeta)

| Path | Responsibility |
|---|---|
| `pyproject.toml` | package `proto-pair`, hatchling, `algotrade-plutus = {path="../../plutus", editable=true}`, console scripts `pp-*`. |
| `src/proto_pair/strategy.py` | **Pure** pair signal both arms import: `basis()`, `rolling_z()`, `PairSignal` (ENTER/EXIT/SIT_OUT/HOLD), no-short direction filter, roll-boundary exit, `forgone_mirror`. |
| `src/proto_pair/basket.py` | VN30 basket construction + semi-annual re-constitution from `quote_vn30` snapshots (equal-lot proxy). |
| `src/proto_pair/hedge.py` | `fit_beta()` (IS OLS) + `snap_hedge()` → whole `(shares_per_name, contracts)`. |
| `src/proto_pair/roll.py` | `load_roll_map()`, `roll_dates()`, `front_month()` from `futurecontractcode_full.parquet`. |
| `src/proto_pair/credibility.py` | basis stationarity (ADF) / half-life pre-check — the credibility half of the proceed gate. |
| `src/proto_pair/config/config.py` | loads `.env` + `parameter/*.json` into module dicts (mirror SB/Grid). |
| `src/proto_pair/backtest.py` | the **naive** single-ledger engine + `pp-backtest`; `pv.step("in_sample_backtest")`. |
| `src/proto_pair/optimize.py` | **B-style** IS-only sweep of `z_in` × hedge base-lots → representative cell; `pp-optimize`. |
| `src/proto_pair/evaluate.py` | OOS naive rerun with optimized params; `pv.step("out_of_sample_backtest")`; `pp-evaluate`. |
| `src/proto_pair/metrics/metric.py` | activity counters (round-trips, leg order events) + Tier-2 P&L (Sharpe/HPR/MDD) — mirror SB's `Metric`. |
| `src/proto_pair/faithful/coordinator.py` | the **funding-on-demand/abandon** `PairCoordinator` over the two-venue `PlutusBackend` (keeps legs atomic). |
| `src/proto_pair/experiments/extract_slice.py` | freeze the daily slice (futures wide→long by dated contract + equity basket + `VN30` index + roll map) → `data/market/`; `pp-extract`. |
| `src/proto_pair/experiments/freeze_algotradedb.py` | the read-only algotradeDB freeze for post-2024-09-26 equity + VN30 membership; `pp-freeze-db`. |
| `src/proto_pair/experiments/pair_anchor.py` | the naive-vs-faithful runner (mirror SB `null_anchor.py`); settlement-asymmetry **Tier-1** + Tier-2; `pp-anchor`. |
| `parameter/{backtesting,optimization,optimized,basket,hedge}.json` | externalized params. |
| `docs/hypothesis.md`, `docs/data.md` | 9-step step-1/step-2 artifacts. |
| `.plutus/manifest.yaml` | steps + expected + `nine_step_coverage` (mirror SB). |
| `tests/` | unit tests (strategy, basket, hedge, roll, credibility, metric, coordinator) + smoke + regression baselines. |
| `data/market/` | frozen daily slice (git-ignored if large → Drive; small committed). |
| **`plutus`**: `src/plutus/execution/backend.py` | expose `transfer`/`cancel`/`charges` passthroughs (Task 2). |
| **`plutus`**: `docs/reference/tables/experiments_registry.md` | the Pair results block (Task 15). |

---

## Task 1: Scaffold the repo

**Files:**
- Create: `proto/ProtoPair/{pyproject.toml, README.md, .gitignore, .env.example, src/proto_pair/__init__.py, src/proto_pair/config/__init__.py, src/proto_pair/config/config.py, docs/hypothesis.md}`
- `git init` on branch `rivf-2026`.

**Interfaces:**
- Produces: an installable `proto_pair` package importing `plutus`; `config.BACKTESTING_CONFIG`, `config.GATE` dicts read from `parameter/*.json`.

- [ ] **Step 1: Copy the SB/Grid scaffold shape.** Read `proto/ProtoGrid/pyproject.toml` and replicate it for `proto-pair`: hatchling, `requires-python=">=3.12"`, `dependencies=["python-dotenv>=1.0","matplotlib>=3.9","algotrade-plutus","duckdb>=1.0","pandas>=2.2","pyarrow>=12.0","pytz","numpy>=2.0"]`, `[dependency-groups] dev=["pytest>=8","pylint>=3.3"]`, `[tool.uv.sources] algotrade-plutus = {path="../../plutus", editable=true}`, `[tool.hatch.build.targets.wheel] packages=["src/proto_pair"]`. Console scripts:
```toml
[project.scripts]
pp-extract   = "proto_pair.experiments.extract_slice:main"
pp-freeze-db = "proto_pair.experiments.freeze_algotradedb:main"
pp-backtest  = "proto_pair.backtest:main"
pp-optimize  = "proto_pair.optimize:main"
pp-evaluate  = "proto_pair.evaluate:main"
pp-anchor    = "proto_pair.experiments.pair_anchor:main"
```
Reuse SB's `plutus-verify` bootstrap note verbatim (it is NOT a project dependency — bootstrapped into an isolated `.plutus-venv/` from the release wheel; copy the comment block from `proto/ProtoGrid/pyproject.toml:38-46`).

- [ ] **Step 2: Write `docs/hypothesis.md`** — the pre-registered step-1 artifact. Copy the thesis prose from `plutus/docs/superpowers/specs/2026-09-15-protopair-design.md` §2, and record, as pre-registration:
  - The **cointegration thesis** (VN30F1M and the VN30 basket are cointegrated; the basis mean-reverts; trade the executable no-short side).
  - The **proceed gate — ACTIVITY + credibility, explicitly NOT a P&L kill**: (a) IS basis stationary (ADF p < 0.10) or finite half-life; (b) ≥ 20 completed pair round-trips **and** ≥ 300 leg-level order events. State plainly: "No Sharpe/HPR stop-gate is used (fidelity demonstrator, per `rivf26-fidelity-not-pnl`)."
  - The **assumed round-trip cost** (shared signal parameter, §3c): equity leg brokerage 0.15%/side + 0.1% sell tax; futures per-contract fees (HNXDS). Record the exact numbers so both arms set `z_in` from them and the naive arm charges them.

- [ ] **Step 3: Package skeleton + `config/config.py`** mirroring SB/Grid: load `.env` (for the algotradeDB cred path — see `.env.example`) and `parameter/*.json` into module dicts `BACKTESTING_CONFIG`, `OPTIMIZATION_CONFIG`, `GATE`. Create `.env.example` with `ALGOTRADEDB_CRED=$CRED_DIR/algotradeDB-readonly.json` (path only, never the secret). `.gitignore` includes `.venv/`, `.plutus-venv/`, `data/`, `__pycache__/`, `.env`, `*.cred.json`, and the cred filename.

- [ ] **Step 4: Create the venv and verify install + the two-venue session builds.**
Run:
```bash
cd proto/ProtoPair && uv venv && uv pip install -e ../../plutus --no-deps \
  && uv pip install duckdb pandas pyarrow pytz numpy matplotlib python-dotenv && uv pip install -e .
python -c "
import proto_pair, plutus
from plutus.execution import PlutusBackend
from plutus.market.session.types import Pool, Venue
cfg = {'period':{'start':'2022-10-21','end':'2022-10-24'},'resolution':'1d',
       'exchange_rules':{'venues':['HSX','HNXDS'],'rulebook':'vn-2020-2026','pins':[]},
       'accounts':{'securities':{'initial_cash':'600000000'},'derivatives':{'initial_deposit':'0'}},
       'fill_policy':{'kind':'soft'},'data':{}}
print('Pool',Pool.SECURITIES.value,Pool.DERIVATIVES.value,'Venue',Venue.HSX.value,Venue.HNXDS.value)
print('ok')
"
```
Expected: `Pool securities derivatives Venue HSX HNXDS` then `ok`. (This proves the two-venue account shape and the `Pool`/`Venue` enums the funding glue needs are importable. The session is not run here — a `source` is not yet wired.)

- [ ] **Step 5: Commit.**
```bash
git add -A && git commit -m "Scaffold ProtoPair repo (mirrors ProtoGrid/ProtoSmartBeta shape)

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: Expose `transfer`/`cancel`/`charges` on `PlutusBackend` (plutus-side)

**Files:**
- Modify: `plutus/src/plutus/execution/backend.py`
- Test: `plutus/tests/execution/test_backend_passthroughs.py` (create; check `plutus/tests/` for the existing execution test dir and place beside it)

**Interfaces:**
- Consumes: `ExchangeSession.transfer(source: Pool, destination: Pool, amount: Decimal) -> Union[Transferred, Rejected]` (`exchange.py:1904`), `ExchangeSession.cancel(order_id) -> Union[Cancelled, Rejected]` (`exchange.py:1612`), `ExchangeSession.charges() -> Tuple[Charge, ...]` (`exchange.py:1888`).
- Produces: `PlutusBackend.transfer(...)`, `PlutusBackend.cancel(...)`, `PlutusBackend.charges()` — thin passthroughs the funding-on-demand/abandon loop (Task 13) and the Tier-1 fee reads (Task 14) call. This is the **only** plutus-side change; it surfaces methods that already exist on the session onto the shared facade so ProtoPair stays a pure consumer of the facade (backend.py's own contract: "strategies never import the session type").

> **Why this task exists.** `PlutusBackend` currently exposes only `submit/advance_to/fills/cash/holdings/positions/margin/indeterminate_report` (`backend.py:54-79`) — **not** `transfer`/`cancel`/`charges`. The pair-trade template drives `transfer`/`cancel` through the validation harness `ctx`, not through this facade. The funding-on-demand/abandon loop needs both. This is the spec §8 "confirm the seam exposes `transfer` + `cancel`" made concrete: they exist on `ExchangeSession`, so this is a 3-method passthrough, not new margin/pool logic.

- [ ] **Step 1: Write the failing test.**
```python
# plutus/tests/execution/test_backend_passthroughs.py
from plutus.execution import PlutusBackend

def test_backend_exposes_funding_loop_methods():
    for name in ("transfer", "cancel", "charges"):
        assert hasattr(PlutusBackend, name), f"PlutusBackend missing {name}"

def test_passthroughs_delegate_to_session():
    calls = {}
    class FakeSession:
        def transfer(self, s, d, a): calls["transfer"] = (s, d, a); return "T"
        def cancel(self, oid):        calls["cancel"] = oid; return "C"
        def charges(self):            calls["charges"] = True; return ()
    b = PlutusBackend(FakeSession())
    assert b.transfer("SEC", "DER", 5) == "T" and calls["transfer"] == ("SEC", "DER", 5)
    assert b.cancel("O-1") == "C" and calls["cancel"] == "O-1"
    assert b.charges() == () and calls["charges"] is True
```

- [ ] **Step 2: Run — fails.** `cd plutus && python -m pytest tests/execution/test_backend_passthroughs.py -q`. Expected: FAIL (`PlutusBackend missing transfer`).

- [ ] **Step 3: Add the passthroughs** to `PlutusBackend` (after `indeterminate_report`, `backend.py:79`):
```python
    # -- pool + order operations the pair coordinator needs -----------------
    def transfer(self, source, destination, amount):
        """Move cash between the two segregated pools (securities <-> derivatives).
        Delegates to ExchangeSession.transfer; returns Transferred or Rejected."""
        return self.session.transfer(source, destination, amount)

    def cancel(self, order_id):
        """Cancel a resting order. Delegates to ExchangeSession.cancel;
        returns Cancelled (has .cancelled_quantity) or Rejected."""
        return self.session.cancel(order_id)

    def charges(self):
        """Every Charge levied so far, per venue/pool/base — the Tier-1 fee read."""
        return self.session.charges()
```

- [ ] **Step 4: Run — passes.** `cd plutus && python -m pytest tests/execution/test_backend_passthroughs.py -q`. Expected: 2 passed. Then run the existing execution suite to confirm no regression: `python -m pytest tests/execution -q`. Expected: all pass.

- [ ] **Step 5: Commit** (in the `plutus` repo, on `rivf-2026`):
```bash
cd plutus && git add src/plutus/execution/backend.py tests/execution/test_backend_passthroughs.py
git commit -m "Expose transfer/cancel/charges passthroughs on PlutusBackend for the pair funding loop

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: Basket construction + semi-annual re-constitution

**Files:**
- Create: `src/proto_pair/basket.py`, `tests/test_basket.py`
- Writes: `parameter/basket.json`, a basket section in `docs/data.md`

**Interfaces:**
- Consumes: `quote_vn30` membership snapshots (`datetime, tickersymbol`) — hermes-parquet ≤2022-08-01, extended by the algotradeDB freeze (Task 8); a DuckDB connection.
- Produces:
  - `constituents_on(review_snapshots: dict[date, tuple[str, ...]], day: date) -> tuple[str, ...]` — the VN30 membership in force on `day` (the most recent review at or before `day`).
  - `load_review_snapshots(vn30_frame) -> dict[date, tuple[str, ...]]` — group the membership table into `{review_date: (tickers...)}`.
  - `equal_lot_notional(prices: dict[str, Decimal], lots_per_name: int, price_scale: int = 1000) -> Decimal` — basket notional in đồng for `lots_per_name` board lots (100 shares) of each name.

- [ ] **Step 1: Write failing tests.**
```python
# tests/test_basket.py
from datetime import date
from decimal import Decimal
from proto_pair.basket import constituents_on, equal_lot_notional

SNAPS = {date(2022, 2, 1): ("A", "B", "C"), date(2022, 8, 1): ("A", "B", "D")}

def test_constituents_use_the_review_in_force():
    assert constituents_on(SNAPS, date(2022, 6, 30)) == ("A", "B", "C")   # Feb review
    assert constituents_on(SNAPS, date(2022, 9, 1)) == ("A", "B", "D")    # Aug review
    assert constituents_on(SNAPS, date(2022, 1, 1)) == ("A", "B", "C")    # before first -> earliest

def test_equal_lot_notional_is_lots_times_100_times_sum_prices_times_scale():
    prices = {"A": Decimal("20"), "B": Decimal("30")}   # thousands of dong
    # 3 lots each: 3*100*(20+30)*1000 = 15,000,000 dong
    assert equal_lot_notional(prices, lots_per_name=3) == Decimal("15000000")
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_basket.py -q`.

- [ ] **Step 3: Implement `basket.py`.**
```python
"""VN30 equal-lot proxy basket, re-constituted at each semi-annual review.

Equal *lots* is not equal weight, let alone HOSE's free-float cap weighting --
the corpus has no shares-outstanding, so the real weights are not derivable
(template R^2~0.98, ~5pp drift). The claim is routing/funding/charging fidelity,
not index tracking. See spec 2026-09-15-protopair-design.md S3a.
"""
from __future__ import annotations
from datetime import date
from decimal import Decimal
from typing import Dict, Mapping, Tuple


def load_review_snapshots(vn30_frame) -> Dict[date, Tuple[str, ...]]:
    """Group a `datetime, tickersymbol` membership table into
    {review_date: (tickers...)}. Each distinct datetime is one review snapshot.
    `vn30_frame` is a pandas DataFrame."""
    out: Dict[date, Tuple[str, ...]] = {}
    for dt, grp in vn30_frame.groupby("datetime"):
        d = dt.date() if hasattr(dt, "date") else dt
        out[d] = tuple(sorted(grp["tickersymbol"].astype(str)))
    return out


def constituents_on(review_snapshots: Mapping[date, Tuple[str, ...]],
                    day: date) -> Tuple[str, ...]:
    """The membership in force on `day`: the latest review at or before `day`,
    or the earliest review if `day` precedes them all (start-of-window guard)."""
    reviews = sorted(review_snapshots)
    if not reviews:
        raise ValueError("no VN30 review snapshots loaded")
    chosen = reviews[0]
    for r in reviews:
        if r <= day:
            chosen = r
        else:
            break
    return review_snapshots[chosen]


def equal_lot_notional(prices: Mapping[str, Decimal], lots_per_name: int,
                       price_scale: int = 1000) -> Decimal:
    """Basket notional in dong for `lots_per_name` board lots (100 shares) of
    each priced name. Prices are in thousands of dong (price_scale=1000)."""
    total = sum((Decimal(p) for p in prices.values()), Decimal("0"))
    return Decimal(lots_per_name) * Decimal(100) * total * Decimal(price_scale)
```

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_basket.py -q`. Then write `parameter/basket.json` = `{"lots_per_name": 3, "price_scale": 1000, "reconstitute": "semi_annual_review"}` and note in `docs/data.md` that the basket is re-constituted at each review (data-driven, not frozen); flag the `quote_vn30` coverage gap (ends 2022-08-01 → later reviews from the Task 8 freeze) as a dependency.

- [ ] **Step 5: Commit** (`basket.py` + test + `parameter/basket.json` + `docs/data.md`, trailer).

---

## Task 4: Basis z-score signal + no-short direction filter (`strategy.py`)

**Files:**
- Create: `src/proto_pair/strategy.py`, `tests/test_strategy.py`

**Interfaces:**
- Consumes: nothing from plutus (pure module, no I/O — like `proto/ProtoGrid/src/proto_grid/strategy.py`).
- Produces (the shared API both arms call):
  - `basis(future_close: Decimal, index_close: Decimal) -> Decimal`.
  - `rolling_z(history: Sequence[Decimal], lookback: int) -> Optional[Decimal]` — z of the **last** element vs the trailing `lookback`; `None` while warming up or if std == 0.
  - `class Action(str, Enum)`: `ENTER`, `EXIT`, `SIT_OUT`, `HOLD`.
  - `@dataclass(frozen=True) PairDecision`: `action: Action`, `day: date`, `z: Optional[Decimal]`, `reason: str`.
  - `class PairSignal`: `__init__(self, lookback=60, z_in=Decimal("1.5"), z_out=Decimal("0.5"))`; `update(self, day, future_close, index_close, is_roll_boundary=False) -> PairDecision`; attributes `in_position: bool`, `forgone_mirror: int`.

- [ ] **Step 1: Write failing tests.**
```python
# tests/test_strategy.py
from datetime import date
from decimal import Decimal
from proto_pair.strategy import basis, rolling_z, PairSignal, Action

def test_basis_is_future_minus_index():
    assert basis(Decimal("1000.5"), Decimal("1025.0")) == Decimal("-24.5")

def test_rolling_z_warms_up_then_scores():
    hist = [Decimal(x) for x in range(10)]          # 0..9
    assert rolling_z(hist, lookback=20) is None      # not enough history
    z = rolling_z(hist, lookback=10)                 # last=9, mean=4.5
    assert z is not None and z > 0                   # 9 is above the window mean

def _feed(sig, values, start=date(2022, 1, 3)):
    from datetime import timedelta
    out = []
    for i, (f, ix) in enumerate(values):
        out.append(sig.update(start + timedelta(days=i), Decimal(f), Decimal(ix)))
    return out

def test_enters_executable_side_when_future_rich():
    sig = PairSignal(lookback=5, z_in=Decimal("1.0"), z_out=Decimal("0.3"))
    # flat basis then a rich spike (future >> index) -> z high -> ENTER
    vals = [("100", "100")] * 5 + [("130", "100")]
    dec = _feed(sig, vals)[-1]
    assert dec.action is Action.ENTER and sig.in_position

def test_sits_out_the_mirror_side_and_counts_it():
    sig = PairSignal(lookback=5, z_in=Decimal("1.0"), z_out=Decimal("0.3"))
    vals = [("100", "100")] * 5 + [("70", "100")]   # future cheap -> mirror -> not executable
    dec = _feed(sig, vals)[-1]
    assert dec.action is Action.SIT_OUT and not sig.in_position and sig.forgone_mirror == 1

def test_roll_boundary_forces_exit_when_in_position():
    sig = PairSignal(lookback=5, z_in=Decimal("1.0"), z_out=Decimal("0.3"))
    _feed(sig, [("100", "100")] * 5 + [("130", "100")])
    dec = sig.update(date(2022, 2, 1), Decimal("125"), Decimal("100"), is_roll_boundary=True)
    assert dec.action is Action.EXIT and not sig.in_position
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_strategy.py -q`.

- [ ] **Step 3: Implement `strategy.py`.**
```python
"""Pure cross-market pair signal shared by ProtoPair's naive engine (Task 10)
and faithful arm (Task 13/14). No plutus import, no I/O -- mirrors
proto/ProtoGrid/src/proto_grid/strategy.py.

Signal: rolling z-score of basis = VN30F1M_close - VN30INDEX_close (lookback 60).
Enter the *executable* leg (long basket / short future) when z >= +z_in; exit
when z <= z_out (revert toward 0) or on a roll/expiry boundary. The mirror side
(z <= -z_in, future cheap) is not executable in Vietnam (no stock short-sale)
and is SAT OUT -- counted, not traded. See spec S3c/S3d.
"""
from __future__ import annotations
from collections import deque
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from enum import Enum
from statistics import fmean, pstdev
from typing import Optional, Sequence

__all__ = ["basis", "rolling_z", "Action", "PairDecision", "PairSignal"]


def basis(future_close: Decimal, index_close: Decimal) -> Decimal:
    """The trade's signal input: front-month future minus the index level."""
    return Decimal(future_close) - Decimal(index_close)


def rolling_z(history: Sequence[Decimal], lookback: int) -> Optional[Decimal]:
    """z-score of the last element vs the trailing `lookback` values.

    Returns None while warming up (fewer than `lookback` points) or when the
    window has zero dispersion (std == 0 -> z undefined). Uses population std
    over the window, matching a fixed-lookback normalisation.
    """
    if len(history) < lookback:
        return None
    window = [float(x) for x in list(history)[-lookback:]]
    sd = pstdev(window)
    if sd == 0:
        return None
    return Decimal(str((window[-1] - fmean(window)) / sd))


class Action(str, Enum):
    ENTER = "ENTER"        # long basket, short future (executable side)
    EXIT = "EXIT"          # close both legs
    SIT_OUT = "SIT_OUT"    # mirror signal fired but not executable (counted)
    HOLD = "HOLD"


@dataclass(frozen=True)
class PairDecision:
    action: Action
    day: date
    z: Optional[Decimal]
    reason: str


class PairSignal:
    """The systematic entry/exit rule. Stateful across sessions: it holds the
    rolling basis history and whether a pair is currently open. `z_in` is
    cost-driven (set so expected reversion clears the modelled round-trip cost,
    spec S3c), NOT Sharpe-tuned. Emits a decision; the arm turns ENTER/EXIT into
    sized leg orders (hedge.py) -- this class never sizes or submits.
    """

    def __init__(self, lookback: int = 60, z_in: Decimal = Decimal("1.5"),
                 z_out: Decimal = Decimal("0.5")) -> None:
        self.lookback = lookback
        self.z_in = Decimal(z_in)
        self.z_out = Decimal(z_out)
        self._history: deque = deque(maxlen=lookback)
        self.in_position = False
        self.forgone_mirror = 0

    def update(self, day: date, future_close: Decimal, index_close: Decimal,
               is_roll_boundary: bool = False) -> PairDecision:
        b = basis(future_close, index_close)
        self._history.append(b)
        z = rolling_z(self._history, self.lookback)

        if self.in_position:
            if is_roll_boundary:
                self.in_position = False
                return PairDecision(Action.EXIT, day, z, "roll/expiry boundary")
            if z is not None and z <= self.z_out:
                self.in_position = False
                return PairDecision(Action.EXIT, day, z, "basis reverted")
            return PairDecision(Action.HOLD, day, z, "in position")

        if z is None:
            return PairDecision(Action.HOLD, day, z, "warming up")
        if z >= self.z_in:                       # future rich -> executable
            self.in_position = True
            return PairDecision(Action.ENTER, day, z, "future rich vs basket")
        if z <= -self.z_in:                      # future cheap -> mirror, not executable
            self.forgone_mirror += 1
            return PairDecision(Action.SIT_OUT, day, z, "no-short: mirror side forgone")
        return PairDecision(Action.HOLD, day, z, "no signal")
```

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_strategy.py -q`. Expected: 5 passed.

- [ ] **Step 5: Commit** (`strategy.py` + test, trailer).

---

## Task 5: IS-fitted hedge ratio + lot/contract snap (`hedge.py`)

**Files:**
- Create: `src/proto_pair/hedge.py`, `tests/test_hedge.py`
- Writes: `parameter/hedge.json` (populated in Task 10/11 once IS data is frozen)

**Interfaces:**
- Consumes: IS basket-return and future-return series (built by the naive engine from the frozen slice).
- Produces:
  - `fit_beta(basket_returns: Sequence[float], future_returns: Sequence[float]) -> Decimal` — OLS slope (cov/var), the static IS hedge ratio.
  - `snap_hedge(beta: Decimal, basket_notional_per_lot: Decimal, future_notional_per_contract: Decimal, max_lots: int = 8) -> tuple[int, int]` — the whole `(lots_per_name, contracts)` whose basket:future notional ratio best matches `beta` (the fidelity snap; the pair cannot lot-match below ~3 lots, template `SHARES_PER_NAME=300`/`CONTRACTS=4` → 1.045).

- [ ] **Step 1: Write failing tests.**
```python
# tests/test_hedge.py
from decimal import Decimal
from proto_pair.hedge import fit_beta, snap_hedge

def test_fit_beta_recovers_a_known_slope():
    fut = [0.01, -0.02, 0.03, -0.01, 0.02]
    bas = [0.02 * x for x in fut]                 # basket moves 2x the future
    assert abs(float(fit_beta(bas, fut)) - 0.02) < 1e-9

def test_snap_matches_the_template_pairing():
    # basket ~137.25M/lot-per-name-set, future ~98.5M/contract, beta ~1.0
    # 3 lots -> 411.75M vs 4 contracts -> 394M is the closest whole pairing (1.045)
    lots, contracts = snap_hedge(Decimal("1.0"), Decimal("137250000"),
                                 Decimal("98500000"), max_lots=8)
    assert (lots, contracts) == (3, 4)
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_hedge.py -q`.

- [ ] **Step 3: Implement `hedge.py`.**
```python
"""Static IS-fitted hedge ratio, snapped to whole lots/contracts.

Fit beta ONCE on the in-sample window (OLS of basket vs future returns), hold it
fixed out-of-sample, then snap to whole board lots (basket) and whole contracts
(future). The snap is a fidelity axis, not a rounding convenience -- the pair
cannot be lot-matched below ~3 lots of each name (spec S3b). NOT rolling: a
rolling/cointegration beta adds look-ahead and reads as P&L-chasing, which the
fidelity framing forbids.
"""
from __future__ import annotations
from decimal import Decimal
from typing import Sequence, Tuple


def fit_beta(basket_returns: Sequence[float],
             future_returns: Sequence[float]) -> Decimal:
    """OLS slope of basket returns on future returns: cov / var. The static
    IS hedge ratio. Raises if the series differ in length or the future has
    zero variance (a degenerate IS window the caller must not hedge against)."""
    if len(basket_returns) != len(future_returns):
        raise ValueError("basket/future return series length mismatch")
    n = len(future_returns)
    if n < 2:
        raise ValueError("need >=2 return observations to fit beta")
    fmean = sum(future_returns) / n
    bmean = sum(basket_returns) / n
    var = sum((f - fmean) ** 2 for f in future_returns)
    if var == 0:
        raise ValueError("future returns have zero variance; beta undefined")
    cov = sum((b - bmean) * (f - fmean)
              for b, f in zip(basket_returns, future_returns))
    return Decimal(str(cov / var))


def snap_hedge(beta: Decimal, basket_notional_per_lot: Decimal,
               future_notional_per_contract: Decimal,
               max_lots: int = 8) -> Tuple[int, int]:
    """The whole (lots_per_name, contracts) whose basket:future notional ratio
    best matches `beta`.

    Target: lots * basket_notional_per_lot ~= beta * contracts * future_notional.
    Searches lots in 1..max_lots and, for each, the integer contracts nearest
    the notional match, and keeps the pair with the smallest relative mismatch.
    Both legs >= 1 (a pair needs both). `basket_notional_per_lot` is the notional
    of ONE board lot of EACH name (the whole 30-name set at 1 lot apiece).
    """
    beta = Decimal(beta)
    best: Tuple[int, int] = (1, 1)
    best_err = None
    for lots in range(1, max_lots + 1):
        basket_notional = Decimal(lots) * basket_notional_per_lot
        target_future = basket_notional / (beta * future_notional_per_contract)
        contracts = max(1, int(target_future.to_integral_value(rounding="ROUND_HALF_UP")))
        got = beta * Decimal(contracts) * future_notional_per_contract
        err = abs(got - basket_notional) / basket_notional
        if best_err is None or err < best_err:
            best_err, best = err, (lots, contracts)
    return best
```

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_hedge.py -q`. Expected: 2 passed.

- [ ] **Step 5: Commit** (`hedge.py` + test, trailer).

---

## Task 6: Continuous→dated-contract roll (`roll.py`)

**Files:**
- Create: `src/proto_pair/roll.py`, `tests/test_roll.py`

**Interfaces:**
- Consumes: `futurecontractcode_full.parquet` (`date, futurecode, contract`), a DuckDB connection.
- Produces:
  - `load_roll_map(parquet_path, futurecode="VN30F1M", con=None) -> dict[date, str]` — `{session_date: dated_contract}` for the front month.
  - `roll_dates(roll_map) -> list[date]` — the **last** session of each dated contract (the session on which the strategy closes the expiring contract).
  - `front_month(roll_map, day) -> str` — the dated contract in force on `day`.
  - `is_roll_boundary(roll_map, day) -> bool` — True iff `day` is the last session before the front-month contract changes.

- [ ] **Step 1: Write failing tests.**
```python
# tests/test_roll.py
from datetime import date
from proto_pair.roll import roll_dates, front_month, is_roll_boundary

RMAP = {
    date(2022, 1, 18): "VN30F2201", date(2022, 1, 19): "VN30F2201",  # last F2201
    date(2022, 1, 20): "VN30F2202", date(2022, 1, 21): "VN30F2202",
}

def test_front_month_reads_the_mapping():
    assert front_month(RMAP, date(2022, 1, 19)) == "VN30F2201"
    assert front_month(RMAP, date(2022, 1, 20)) == "VN30F2202"

def test_roll_dates_are_the_last_session_of_each_contract():
    assert roll_dates(RMAP) == [date(2022, 1, 19), date(2022, 1, 21)]

def test_is_roll_boundary_flags_the_last_session_before_a_change():
    assert is_roll_boundary(RMAP, date(2022, 1, 19)) is True   # F2201 -> F2202 next
    assert is_roll_boundary(RMAP, date(2022, 1, 18)) is False
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_roll.py -q`.

- [ ] **Step 3: Implement `roll.py`.**
```python
"""The continuous->dated-contract roll -- the SOLE strategy-side glue Plutus
does not provide (spec S3e). Data-driven off futurecontractcode_full.parquet:
when the front-month (VN30F1M) dated contract changes, the prior session is a
roll date. The strategy closes the expiring dated contract on its last session
and opens the new front month next session (stays in F1M throughout; no pre-roll
into F2M). Kept isolated and auditable here, never inside plutus.
"""
from __future__ import annotations
from datetime import date
from typing import Dict, List, Mapping, Optional


def load_roll_map(parquet_path: str, futurecode: str = "VN30F1M",
                  con=None) -> Dict[date, str]:
    """{session_date: dated_contract} for the front month, from the mapping
    parquet. `con` is an optional duckdb connection (one is created if None)."""
    import duckdb
    owns = con is None
    con = con or duckdb.connect()
    try:
        rows = con.execute(
            "SELECT date, contract FROM read_parquet(?) "
            "WHERE futurecode = ? ORDER BY date", [parquet_path, futurecode]
        ).fetchall()
    finally:
        if owns:
            con.close()
    out: Dict[date, str] = {}
    for d, contract in rows:
        out[d.date() if hasattr(d, "date") else d] = str(contract)
    return out


def front_month(roll_map: Mapping[date, str], day: date) -> str:
    """The dated contract in force on `day` (exact session lookup)."""
    return roll_map[day]


def roll_dates(roll_map: Mapping[date, str]) -> List[date]:
    """The last session of each dated contract, in date order -- the sessions
    on which the strategy closes the expiring leg."""
    days = sorted(roll_map)
    out: List[date] = []
    for i, d in enumerate(days):
        is_last = (i == len(days) - 1) or (roll_map[days[i + 1]] != roll_map[d])
        if is_last:
            out.append(d)
    return out


def is_roll_boundary(roll_map: Mapping[date, str], day: date) -> bool:
    """True iff `day` is the last session before the front-month contract
    changes (the next session carries a different dated contract)."""
    days = sorted(roll_map)
    try:
        i = days.index(day)
    except ValueError:
        return False
    if i == len(days) - 1:
        return False
    return roll_map[days[i + 1]] != roll_map[day]
```

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_roll.py -q`. Expected: 3 passed.

- [ ] **Step 5: Commit** (`roll.py` + test, trailer).

---

## Task 7: Freeze the daily slice (available sources)

**Files:**
- Create: `src/proto_pair/experiments/__init__.py`, `src/proto_pair/experiments/extract_slice.py`, `tests/test_slice_smoke.py`
- Writes: `data/market/` (a `DataHubSource`-readable corpus of `quote_*.parquet` long tables) + `data/market/futurecontractcode_full.parquet`; IS/OOS split constants in `config/config.py`.

**Interfaces:**
- Consumes: the staged futures wide parquet + roll mapping; `stock_quote_12.2020-09.2024` equity CSVs (≤2024-09-26); `quote_vn30.parquet` (≤2022-08-01); `parameter/basket.json`.
- Produces: `data/market/` readable via `DataHubSource.for_root("data/market")`, serving equity basket names, the `VN30` index level, and the **dated** futures contracts (tickersymbol = dated code e.g. `VN30F2206`); the roll mapping copied in for `roll.py`.

> **The transform.** `DataHubSource` expects long `quote_*.parquet` tables (`datetime, tickersymbol, price`). The staged futures parquet is **wide** (`date, futurecode, contract, open, high, low, close, reference, ceiling, floor, volume, open_interest, settlement`). The extract must **melt** the futures wide table into long `quote_close`/`quote_ceil`/`quote_floor`/`quote_reference`/`quote_open`/`quote_high`/`quote_low`/`quote_dailyvolume`/`quote_oi` rows keyed on `tickersymbol = contract` (the dated code), UNION the equity `quote_*` slices (basket names ∪ the `VN30` index level) filtered to the window, and write one table per field into `data/market/`. Reuse SB's `experiments/extract_market.py` for the equity daily-table list + the parquet-write idiom (`proto/ProtoSmartBeta/src/proto_smart_beta/experiments/extract_market.py`).

- [ ] **Step 1: Fix the IS/OOS split constants** in `config/config.py`:
```python
from datetime import date
IS = (date(2022, 1, 1), date(2023, 12, 31))
OOS = (date(2024, 1, 1), date(2025, 6, 30))
EQUITY_CORPUS_END = date(2024, 9, 26)   # stock_quote_12.2020-09.2024 coverage end
KRX_CUTOVER = date(2025, 5, 5)
IM_RATE_CHANGE = date(2022, 12, 15)     # 0.13 -> 0.17
```

- [ ] **Step 2: Implement `extract_slice.py`** with two functions and a `main()`:
  - `melt_futures(fut_parquet, out_dir, con)` — for each `(field_out, wide_col)` in `{"quote_close":"close","quote_ceil":"ceiling","quote_floor":"floor","quote_reference":"reference","quote_open":"open","quote_high":"high","quote_low":"low","quote_dailyvolume":"volume","quote_oi":"open_interest"}`, `COPY (SELECT date AS datetime, contract AS tickersymbol, <wide_col> AS price FROM read_parquet('<fut_parquet>') WHERE futurecode IN ('VN30F1M','VN30F2M') AND <wide_col> IS NOT NULL) TO '<out_dir>/<field_out>.parquet' (FORMAT PARQUET)`. (The dated `contract` is the served symbol, matching the template's `FUTURE='VN30F2211'`.)
  - `slice_equity(csv_root, out_dir, tickers, index_level, window, con)` — for each equity field table, `COPY (SELECT * FROM read_csv_auto('<csv_root>/<table>.csv') WHERE tickersymbol IN (<basket ∪ index_level>) AND datetime >= '<IS[0]>' AND datetime <= '<min(OOS[1], EQUITY_CORPUS_END)>') TO '<out_dir>/<table>.parquet'`. Then **append** the melted-futures rows into the same field tables where they share a field (close/ceil/floor/reference/open/high/low/dailyvolume) so one `quote_close.parquet` carries basket + index + futures rows. Copy `futurecontractcode_full.parquet` into `data/market/`.
  - `main()` reads `parameter/basket.json`, unions all review constituents across the window (so every name ever in the basket is frozen), sets `index_level="VN30"`, and runs both. Print the resulting `data/market/` size; if > ~100 MB mark it for Drive in `.gitignore` + `docs/data.md`, else commit it.

- [ ] **Step 3: Smoke test the slice reads.**
```python
# tests/test_slice_smoke.py
from datetime import date
import duckdb, os
ROOT = "data/market"

def test_slice_has_basket_index_and_dated_futures():
    con = duckdb.connect()
    close = f"{ROOT}/quote_close.parquet"
    assert os.path.exists(close), "extract not run"
    syms = {r[0] for r in con.execute(
        f"SELECT DISTINCT tickersymbol FROM read_parquet('{close}')").fetchall()}
    assert "VN30" in syms, "index level VN30 missing from the slice"
    assert any(s.startswith("VN30F2") for s in syms), "no dated futures contracts in the slice"
    assert len(syms) > 5, "basket names missing"

def test_futures_bands_present_for_admission():
    con = duckdb.connect()
    for field in ("quote_ceil", "quote_floor"):
        p = f"{ROOT}/{field}.parquet"
        n = con.execute(
            f"SELECT count(*) FROM read_parquet('{p}') WHERE tickersymbol LIKE 'VN30F2%'").fetchone()[0]
        assert n > 0, f"{field} has no futures rows -- admission BAND_LIMIT cannot fire"
```
Run: `python -m proto_pair.experiments.extract_slice` then `python -m pytest tests/test_slice_smoke.py -q`. Expected: PASS. (If `VN30` is absent from the equity `quote_close`, source the index level from the Task-8 freeze and note it in `docs/data.md` — see Open Questions.)

- [ ] **Step 4: Note the coverage boundary** in `docs/data.md`: this slice covers equity ≤ 2024-09-26 and full futures; the OOS tail (2024-09-27 → 2025-06-30) equity + VN30 membership post-2022-08 are added by Task 8.

- [ ] **Step 5: Commit** (extractor + smoke + split constants; data via Drive or committed per size; trailer).

---

## Task 8: algotradeDB freeze — post-2024-09-26 equity + VN30 membership (freeze-dependent, isolated)

**Files:**
- Create: `src/proto_pair/experiments/freeze_algotradedb.py`, `tests/test_freeze_db.py`
- Extends: `data/market/` with the OOS-tail equity rows + post-2022-08 VN30 review snapshots.

**Interfaces:**
- Consumes: the read-only algotradeDB (cred JSON at `$ALGOTRADEDB_CRED`, default `$CRED_DIR/algotradeDB-readonly.json`); `parameter/basket.json`.
- Produces: additional `quote_*.parquet` rows (2024-09-27 → 2025-06-30, basket ∪ `VN30` index) and `quote_vn30.parquet` review snapshots (2022-08 → 2025-06) merged into `data/market/`.

> **This is the one task blocked on the algotradeDB freeze.** Selective conversion only — fields × basket tickers × the OOS-tail date range, plus the VN30 membership review rows. **Never** convert the whole corpus; **never** commit the cred or raw DB dump. Reuse SB's DB access pattern: `proto/ProtoSmartBeta/src/proto_smart_beta/database/data_service.py` (`psycopg2.connect(**db_params)`) and `.../database/query.py` — this is "track-C's method" (the read-only psycopg2 path the MM/Pair DB phase uses). Load `db_params` from the cred JSON via `$ALGOTRADEDB_CRED`.

- [ ] **Step 1: Write the guard test** (runs without a DB; asserts the freeze is cred-gated and selective, never whole-corpus):
```python
# tests/test_freeze_db.py
import inspect
from proto_pair.experiments import freeze_algotradedb as fz

def test_freeze_is_cred_gated_and_windowed():
    src = inspect.getsource(fz)
    assert "ALGOTRADEDB_CRED" in src, "must read the cred path from env, never inline"
    assert "2024-09-27" in src or "EQUITY_CORPUS_END" in src, "must window to the OOS tail"
    # never a blanket SELECT * across the whole corpus
    assert "read_only" in src.lower() or "readonly" in src.lower()

def test_freeze_refuses_without_cred(monkeypatch):
    monkeypatch.delenv("ALGOTRADEDB_CRED", raising=False)
    import pytest
    with pytest.raises((RuntimeError, FileNotFoundError, KeyError)):
        fz.connect_params()
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_freeze_db.py -q`.

- [ ] **Step 3: Implement `freeze_algotradedb.py`.** `connect_params()` reads `$ALGOTRADEDB_CRED`, loads the JSON, returns a `db_params` dict (raise `RuntimeError` if the env var is unset). `freeze_equity_tail(tickers, begin, end, out_dir)` connects **read-only** (psycopg2, `options='-c default_transaction_read_only=on'`), selects only `(datetime, tickersymbol, price)` for the field tables × `tickers` × `[begin,end]`, writes one parquet per field, and merges into `data/market/`. `freeze_vn30_reviews(begin, end, out_dir)` selects the membership review snapshots into `quote_vn30.parquet`. `main()` runs both for `begin=EQUITY_CORPUS_END+1day`, `end=OOS[1]`. Keep every query windowed and ticker-scoped; log row counts, never dump the cred.

- [ ] **Step 4: Run the guard test — passes.** `python -m pytest tests/test_freeze_db.py -q`. Expected: 2 passed. **Then, when the owner authorizes the DB freeze**, run `ALGOTRADEDB_CRED=$CRED_DIR/algotradeDB-readonly.json python -m proto_pair.experiments.freeze_algotradedb` and re-run `tests/test_slice_smoke.py` to confirm the OOS tail now reads. Record the frozen row counts + date span in `docs/data.md`.

- [ ] **Step 5: Commit** (freezer + guard test; **no** cred, **no** raw data in the commit; trailer). Confirm `git status` shows no cred/`.env` staged.

---

## Task 9: Credibility pre-check (the credibility half of the proceed gate)

**Files:**
- Create: `src/proto_pair/credibility.py`, `tests/test_credibility.py`
- Writes: a credibility section in `docs/data.md`.

**Interfaces:**
- Consumes: the IS basis series (built from `data/market/` via `strategy.basis` over the IS window).
- Produces:
  - `half_life(basis_series: Sequence[float]) -> Optional[float]` — Ornstein-Uhlenbeck half-life from an AR(1) fit (`-ln(2)/ln(1+phi)`); `None` if non-mean-reverting (phi ≥ 0).
  - `adf_pvalue(basis_series: Sequence[float]) -> Optional[float]` — augmented Dickey-Fuller p-value if `statsmodels` is available, else `None` (half-life is the fallback).
  - `is_credible(basis_series, adf_max=0.10, max_half_life_days=90) -> tuple[bool, dict]` — the gate: stationary (ADF p < adf_max) **or** finite half-life ≤ `max_half_life_days`.

- [ ] **Step 1: Write failing tests.**
```python
# tests/test_credibility.py
import numpy as np
from proto_pair.credibility import half_life, is_credible

def test_half_life_finite_for_mean_reverting_series():
    rng = np.random.default_rng(0)
    x, series = 0.0, []
    for _ in range(500):
        x = 0.7 * x + rng.normal()      # strongly mean-reverting AR(1)
        series.append(x)
    hl = half_life(series)
    assert hl is not None and 0 < hl < 20

def test_random_walk_is_not_credible():
    rng = np.random.default_rng(1)
    walk = np.cumsum(rng.normal(size=500)).tolist()   # unit root
    ok, detail = is_credible(walk)
    assert ok is False and "half_life" in detail
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_credibility.py -q`.

- [ ] **Step 3: Implement `credibility.py`.**
```python
"""The credibility half of ProtoPair's proceed gate (spec S2): is the IS basis
a *credible* mean-reverting vehicle? NOT a P&L test. Stationary (ADF p<0.10) OR
a finite half-life within the window passes. statsmodels is optional; the AR(1)
half-life is the always-available fallback.
"""
from __future__ import annotations
import math
from typing import Dict, Optional, Sequence, Tuple


def half_life(basis_series: Sequence[float]) -> Optional[float]:
    """OU half-life from an AR(1) fit on the basis level: regress
    delta_x_t on x_{t-1}; phi = slope; half-life = -ln(2)/ln(1+phi). Returns
    None when phi >= 0 (no mean reversion) or the fit is degenerate."""
    x = [float(v) for v in basis_series]
    if len(x) < 3:
        return None
    lag = x[:-1]
    dx = [x[i] - x[i - 1] for i in range(1, len(x))]
    n = len(lag)
    lmean = sum(lag) / n
    dmean = sum(dx) / n
    var = sum((v - lmean) ** 2 for v in lag)
    if var == 0:
        return None
    phi = sum((lag[i] - lmean) * (dx[i] - dmean) for i in range(n)) / var
    if phi >= 0:
        return None
    return -math.log(2) / math.log(1 + phi)


def adf_pvalue(basis_series: Sequence[float]) -> Optional[float]:
    """ADF p-value if statsmodels is installed, else None."""
    try:
        from statsmodels.tsa.stattools import adfuller
    except Exception:
        return None
    return float(adfuller([float(v) for v in basis_series], autolag="AIC")[1])


def is_credible(basis_series: Sequence[float], adf_max: float = 0.10,
                max_half_life_days: float = 90.0) -> Tuple[bool, Dict]:
    """The gate: stationary (ADF p < adf_max) OR finite half-life
    <= max_half_life_days. Returns (passed, detail-with-both-measures)."""
    hl = half_life(basis_series)
    p = adf_pvalue(basis_series)
    hl_ok = hl is not None and 0 < hl <= max_half_life_days
    adf_ok = p is not None and p < adf_max
    return (hl_ok or adf_ok), {"half_life": hl, "adf_pvalue": p,
                               "hl_ok": hl_ok, "adf_ok": adf_ok}
```
(Add `statsmodels` to the `dev` dependency group so `adf_pvalue` is exercised in CI; it stays optional at runtime.)

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_credibility.py -q`. Expected: 2 passed. Then compute the real IS-basis credibility from `data/market/` and record `half_life` + `adf_pvalue` in `docs/data.md`. **If not credible, STOP and escalate to the owner** — the pair thesis is not supported for this window (do not weaken the thresholds).

- [ ] **Step 5: Commit** (`credibility.py` + test + `docs/data.md`, trailer).

---

## Task 10: Naive single-ledger engine + in-sample + activity gate

**Files:**
- Create: `src/proto_pair/backtest.py`, `src/proto_pair/metrics/__init__.py`, `src/proto_pair/metrics/metric.py`, `tests/test_metric.py`, `tests/test_activity_gate.py`
- Writes: `result/backtest/` (metrics + charts), `parameter/backtesting.json`, `parameter/hedge.json`.

**Interfaces:**
- Consumes: `strategy.PairSignal`, `hedge.fit_beta`/`snap_hedge`, `basket`, `roll`, the frozen slice, `parameter/backtesting.json` (capital, `lookback=60`, `z_in`, `z_out`, `assumed_cost_rate`, the two capital configs).
- Produces: `PairBacktest.run(is_data=True) -> dict` with `round_trips, leg_order_events, fills, forgone_mirror, sharpe, hpr, mdd`; a `pv.step("in_sample_backtest")` block.

> **Naive = the honest developer default (spec §4a):** one single ledger (both legs' cash netted same-day — no segregation, no T+2, no daily-VM clock), **shorting allowed on both sides** (so it takes the mirror side too — `SIT_OUT` becomes a real short-basket/long-future trade in the naive arm), static margin, frictionless fills on both legs (fill-at-close, unlimited liquidity), **no admission** (tick/lot/band), and the **static assumed round-trip cost** of §3c. Mirror SB's `backtest.py` for the `plutus_verify` `pv.step` wiring and chart artifacts.

- [ ] **Step 1: Metric tests + impl** (mirror SB's `metrics/metric.py`, `proto/ProtoSmartBeta/src/proto_smart_beta/metrics/metric.py`): `Metric` with `sharpe`, `hpr`, `maximum_drawdown` on a daily equity series, plus `round_trips` and `leg_order_events` counters. TDD one test asserting Sharpe/HPR/MDD on a known equity series (copy SB's known-series test).

- [ ] **Step 2: Implement the naive engine** in `backtest.py`. Iterate the frozen slice day-by-day over the IS window: read futures front-month close (via `roll.front_month`), the `VN30` index close, and basket constituent closes (via `basket.constituents_on`). Fit `beta` **once** on the IS returns (first pass) → `snap_hedge` → `(lots_per_name, contracts)` written to `parameter/hedge.json`. On `PairSignal.update`: `ENTER` → buy `lots_per_name` lots of each constituent + short `contracts` futures at close; `EXIT`/roll-boundary → close both; `SIT_OUT` → **the naive arm shorts the basket + longs the future** (it allows shorting). Net all cash same-day in one ledger; charge the static `assumed_cost_rate` round-trip. Build a daily equity curve → `Metric`. Count a **round-trip** as an ENTER→EXIT pair; count **leg order events** as every leg buy/sell/close submitted. Wrap `main()` in `pv.step("in_sample_backtest")` recording `r.metric("round_trips", ...)`, `r.metric("leg_order_events", ...)`, `r.metric("fills", ...)`, and Tier-2 `sharpe/hpr/mdd` (recorded, not gated), plus `hpr.svg`/`drawdown.svg` chart artifacts (mirror SB).

- [ ] **Step 3: Run IS.** `pp-backtest` (or `python -m proto_pair.backtest`) on the IS slice. Record `result/backtest/` metrics.

- [ ] **Step 4: Activity-gate test** (mirror Grid's kill-criteria gate shape, but ACTIVITY not P&L):
```python
# tests/test_activity_gate.py
from proto_pair.backtest import PairBacktest
from proto_pair.config.config import GATE   # {"min_round_trips":20,"min_leg_order_events":300}

def test_in_sample_clears_the_activity_gate():
    r = PairBacktest().run(is_data=True)
    assert r["round_trips"] >= GATE["min_round_trips"], \
        f'activity: only {r["round_trips"]} round-trips'
    assert r["leg_order_events"] >= GATE["min_leg_order_events"], \
        f'activity: only {r["leg_order_events"]} leg order events'
    # explicitly NOT a P&L gate: no assertion on sharpe/hpr here
```
If it **fails**, do **not** weaken the numbers — escalate: re-examine `z_in`/lookback (still cost-driven, not Sharpe-driven) or report the low-activity finding to the owner. (A pair is chunky; 20 round-trips × ~60 equity + a few futures events each is the large-n backbone.)

- [ ] **Step 5: Regression baseline test** — assert the naive IS metrics equal the just-recorded values (the behaviour-preserving anchor), mirroring `proto/ProtoSmartBeta/tests/test_regression_baseline.py`.

- [ ] **Step 6: Commit** (engine + metrics + gate + baseline + params, trailer).

---

## Task 11: B-style optimization (IS-only, ACTIVITY-reported)

**Files:**
- Create: `src/proto_pair/optimize.py`, `tests/test_optimize.py`
- Writes: `parameter/optimized.json`, `result/optimization/sweep.csv`.

**Interfaces:**
- Consumes: the naive engine (Task 10), `parameter/optimization.json` (the `z_in` grid + hedge `max_lots` grid).
- Produces: `sweep_is() -> list[dict]` (one row per cell) and a `main()` that writes `parameter/optimized.json`.

> **B-style, binding (spec §5/§6, decisions "Optimization"):** sweep the **cost-driven** structural params — `z_in ∈ {1.0, 1.5, 2.0}` and hedge `max_lots ∈ {3, 5, 8}` — on the **IS slice only**, report **ACTIVITY** (round-trips, fills, refusals-would-be, leg events) per cell, and pick a **representative** cell (a stable-neighbourhood cell, mirror SB's stable-region discipline), **never** the P&L-optimal one. **No Sharpe/HPR objective; no rolling-β or lookback-L tuner.**

- [ ] **Step 1: Write the test** asserting the sweep reports activity, not a P&L objective:
```python
# tests/test_optimize.py
from proto_pair.optimize import sweep_is
def test_sweep_reports_activity_not_pnl_objective():
    rows = sweep_is()
    assert rows and all("round_trips" in r and "z_in" in r for r in rows)
    # B-style: the artifact carries activity; it must NOT rank by sharpe
    assert all("objective_sharpe" not in r for r in rows)
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_optimize.py -q`.

- [ ] **Step 3: Implement the sweep** over `z_in × max_lots` on the **IS slice only**; record each cell's IS `round_trips`/`fills`/`leg_order_events` to `result/optimization/sweep.csv`. Pick a **representative** cell (neighbours similar in activity — not a spike). Write the chosen `{z_in, max_lots}` to `parameter/optimized.json`. Note in `docs/data.md`: the pick is representative and cost-justified, not P&L-optimal.

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_optimize.py -q`, then `pp-optimize`. Record the grid + chosen cell in `docs/data.md`.

- [ ] **Step 5: Commit** (optimizer + test + params, trailer).

---

## Task 12: Out-of-sample naive rerun + realism audit

**Files:**
- Create: `src/proto_pair/evaluate.py`, `tests/test_oos_regression.py`
- Writes: `result/evaluate/`.

**Interfaces:**
- Consumes: the naive engine, `parameter/optimized.json`, the OOS slice.
- Produces: `PairBacktest.run(is_data=False)` under optimized params; a `pv.step("out_of_sample_backtest")` block.

- [ ] **Step 1: Implement `evaluate.py`** — rerun the **same** naive engine on the **OOS** slice with `parameter/optimized.json`, wrapped in `pv.step("out_of_sample_backtest")` (mirror `proto/ProtoSmartBeta/src/proto_smart_beta/evaluate.py`). Surface IS→OOS activity (round-trips, forgone-mirror) and Tier-2 degradation. The OOS window crosses **KRX 2025-05-05** and depends on the Task-8 freeze for its post-2024-09 equity tail.

- [ ] **Step 2: Run OOS**; record metrics; add an OOS regression baseline test (assert the recorded OOS activity/metrics).

- [ ] **Step 3: Realism audit.** Invoke the standalone **`9-step:assess-realism`** skill on `proto/ProtoPair` (it needs no `.9step/` state). Record the band + any remediation in `docs/data.md`. Note the disclosed daily-resolution look-ahead (the 09:30 margin mark uses the same session's close — template finding 6) as a labeled limitation, not a defect.

- [ ] **Step 4: Commit** (evaluate + baseline + audit notes, trailer).

---

## Task 13: Faithful arm — two-venue wiring + funding-on-demand/abandon coordinator

**Files:**
- Create: `src/proto_pair/faithful/__init__.py`, `src/proto_pair/faithful/coordinator.py`, `tests/test_coordinator.py`

**Interfaces:**
- Consumes: `PlutusBackend` (Task 2's `transfer`/`cancel` + `submit`/`advance_to`/`cash`/`margin`/`positions`/`holdings`), `plutus.market.session.types.Pool`/`Venue`, `plutus.market.protocol.Order`, `plutus.core.order.OrderType`/`Side`, `plutus.market.session.Accepted`/`Rejected`.
- Produces:
  - `class EnterResult`: `filled: bool`, `abandoned: bool`, `transfers: list[tuple[str,str,Decimal]]`, `refusal_detail: Optional[dict]`.
  - `class PairCoordinator`: `__init__(self, backend, deposit_target: Decimal)`; `enter(self, day, basket_orders: list, future_order) -> EnterResult`; `exit(self, day, basket_orders, future_close_order) -> None`; `sweep_deposit(self) -> None`.

> **The novel glue (spec §3f).** Plutus has **no notion of a pair**; the two legs draw on two segregated pools. This coordinator keeps them **atomic**: submit the equity legs (HSX / securities pool) and the futures leg (HNXDS / derivatives pool); if the futures order is **refused** into an empty/short deposit, read `funded_in_aggregate` off the refusal, **transfer** securities→derivatives to the target, and resubmit; if the pair **cannot be funded even in aggregate**, **cancel** the equity legs accepted moments earlier (a naked basket is a different trade). Pattern ported from the template `PairTrade._enter`/`_fund`/`_abandon` (`validation/scenarios/pair-trade.py:520-556`), but driven through `PlutusBackend` instead of the validation `ctx`. Headline runs **settled-cash-only (sale-advance OFF)**; the sale-advance ON variant is a config flag on the session (`broker_profile.advance_sale_proceeds`), not a coordinator change.

- [ ] **Step 1: Write the failing test** with a fake backend (no plutus session needed — asserts the atomic-legs logic):
```python
# tests/test_coordinator.py
from decimal import Decimal
from proto_pair.faithful.coordinator import PairCoordinator, EnterResult

class FakeRejected:
    def __init__(self, funded, shortfall):
        self.rule = type("R", (), {"name": "INSUFFICIENT_DEPOSIT"})()
        self.detail = {"funded_in_aggregate": funded, "shortfall": Decimal(shortfall)}
    is_indeterminate = False
class FakeAccepted:
    def __init__(self, oid): self.order_id = oid; self.venue = "HNXDS"
class FakeTransferred:
    def __init__(self, amt): self.amount = Decimal(amt)
class FakeCancelled:
    def __init__(self, oid): self.cancelled_quantity = 1; self.order_id = oid

class FakeBackend:
    """Refuses the first futures submit, accepts after a transfer."""
    def __init__(self, fundable):
        self.fundable = fundable; self.submits = []; self.transfers = []; self.cancels = []
        self._future_tries = 0; self._deposit = Decimal("0")
    def submit(self, order):
        self.submits.append(order)
        if getattr(order, "_leg", None) == "future":
            self._future_tries += 1
            if self._future_tries == 1:
                return FakeRejected(self.fundable, "51000000")
            return FakeAccepted("F-1")
        return FakeAccepted(f"E-{len(self.submits)}")
    def transfer(self, s, d, amt):
        self.transfers.append((str(s), str(d), Decimal(amt))); self._deposit += Decimal(amt)
        return FakeTransferred(amt)
    def cancel(self, oid):
        self.cancels.append(oid); return FakeCancelled(oid)
    def margin(self):  return type("M", (), {"deposit_balance": self._deposit})()
    def live_basket_ids(self): return ["E-1", "E-2"]

def _orders():
    class O:
        def __init__(self, leg): self._leg = leg
    return [O("basket"), O("basket")], O("future")

def test_funds_on_demand_and_completes_the_pair():
    b = FakeBackend(fundable=True)
    coord = PairCoordinator(b, deposit_target=Decimal("60000000"))
    basket, fut = _orders()
    res = coord.enter("2022-10-21", basket, fut)
    assert res.filled and not res.abandoned
    assert b.transfers, "must fund the futures leg on demand via a transfer"
    assert b.transfers[0][0] == "securities" and b.transfers[0][1] == "derivatives"
    assert len(b.cancels) == 0

def test_abandons_the_pair_when_unfundable_in_aggregate():
    b = FakeBackend(fundable=False)
    coord = PairCoordinator(b, deposit_target=Decimal("60000000"))
    basket, fut = _orders()
    res = coord.enter("2022-10-21", basket, fut)
    assert res.abandoned and not res.filled
    assert set(b.cancels) == {"E-1", "E-2"}, "equity legs must be cancelled, not left naked"
```

- [ ] **Step 2: Run — fails.** `python -m pytest tests/test_coordinator.py -q`.

- [ ] **Step 3: Implement `coordinator.py`.**
```python
"""The caller-side pair coordinator: keeps two legs in two segregated pools
atomic. Plutus has no 'pair' concept -- funding-on-demand and abandon-if-
unfundable are the strategy's job (spec S3f). Ported from the template
PairTrade._enter/_fund/_abandon (validation/scenarios/pair-trade.py) onto the
PlutusBackend facade.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from decimal import Decimal
from typing import List, Optional, Tuple

from plutus.market.session.types import Pool


@dataclass
class EnterResult:
    filled: bool = False
    abandoned: bool = False
    transfers: List[Tuple[str, str, Decimal]] = field(default_factory=list)
    refusal_detail: Optional[dict] = None


def _is_accepted(outcome) -> bool:
    # Accepted acks carry an order_id/venue; Rejected carry .rule/.detail.
    return hasattr(outcome, "order_id") and not hasattr(outcome, "rule")


class PairCoordinator:
    """Submit both legs; fund the futures leg on demand; abandon rather than
    hold a naked basket. `backend` is a PlutusBackend (Task 2 surfaced
    transfer/cancel). `deposit_target` is the comfortable/thin config's target
    derivatives balance -- the coordinator transfers to a target, not to the
    printed shortfall (template finding 3: obeying the bare shortfall forces the
    account on the entry session)."""

    def __init__(self, backend, deposit_target: Decimal) -> None:
        self.backend = backend
        self.deposit_target = Decimal(deposit_target)

    def enter(self, day, basket_orders: List, future_order) -> EnterResult:
        res = EnterResult()
        # 1) equity legs first (securities pool)
        for order in basket_orders:
            self.backend.submit(order)
        # 2) futures leg (derivatives pool) -- refused into an empty deposit
        outcome = self.backend.submit(future_order)
        if _is_accepted(outcome):
            res.filled = True
            return res
        res.refusal_detail = dict(getattr(outcome, "detail", {}) or {})
        # 3) fund on demand, only if fundable in aggregate
        if res.refusal_detail.get("funded_in_aggregate"):
            need = self.deposit_target - self.backend.margin().deposit_balance
            if need > 0:
                moved = self.backend.transfer(Pool.SECURITIES, Pool.DERIVATIVES, need)
                if hasattr(moved, "amount"):
                    res.transfers.append((Pool.SECURITIES.value,
                                          Pool.DERIVATIVES.value, Decimal(moved.amount)))
                    again = self.backend.submit(future_order)
                    if _is_accepted(again):
                        res.filled = True
                        return res
        # 4) cannot complete -> abandon: cancel the equity legs (no naked basket)
        for oid in self.backend.live_basket_ids():
            self.backend.cancel(oid)
        res.abandoned = True
        return res

    def exit(self, day, basket_close_orders: List, future_close_order) -> None:
        for order in basket_close_orders:
            self.backend.submit(order)
        if future_close_order is not None:
            self.backend.submit(future_close_order)

    def sweep_deposit(self) -> None:
        """After the futures leg is flat, return the free deposit to securities
        (template PairTrade._sweep). Bounded by MarginView.free_deposit."""
        free = getattr(self.backend.margin(), "free_deposit", Decimal("0"))
        if free and free > 0:
            self.backend.transfer(Pool.DERIVATIVES, Pool.SECURITIES, free)
```
> **Note:** the runner (Task 14) provides `backend.live_basket_ids()` — a thin helper listing resting HSX order ids (filter `PlutusBackend`'s order view by `venue != HNXDS`, as the template's `_abandon` does at `pair-trade.py:488-495`). If exposing it cleanly is awkward, add it to the runner's backend wrapper rather than to `PlutusBackend` (keep the plutus change to Task 2's three methods).

- [ ] **Step 4: Run — passes.** `python -m pytest tests/test_coordinator.py -q`. Expected: 2 passed.

- [ ] **Step 5: Commit** (coordinator + test, trailer).

---

## Task 14: Naive-vs-faithful runner + settlement-asymmetry Tier-1 counters

**Files:**
- Create: `src/proto_pair/experiments/pair_anchor.py`, `tests/test_pair_anchor_smoke.py`

**Interfaces:**
- Consumes: `strategy.PairSignal`, `basket`, `hedge`, `roll`, the naive engine (Task 10), `PairCoordinator` (Task 13), `PlutusBackend`, `DataHubSource`.
- Produces: `run_pair_anchor(is_data=False) -> {"naive": {...}, "faithful": {...}}` (mirror SB's `run_null_anchor`), with the settlement-asymmetry **Tier-1** tally leading.

> **The faithful backend (two-venue).** Build exactly like SB's `_faithful` (`proto/ProtoSmartBeta/src/proto_smart_beta/experiments/null_anchor.py:73-90`) but with **two venues + a zero derivatives deposit**:
> ```python
> cfg = {
>   "period": {"start": str(span_start), "end": str(span_end)}, "resolution": "1d",
>   "exchange_rules": {"venues": ["HSX", "HNXDS"], "rulebook": "vn-2020-2026", "pins": []},
>   "accounts": {"securities": {"initial_cash": str(basket_notional)},
>                "derivatives": {"initial_deposit": "0"}},   # opens at zero; funded by transfer
>   "fill_policy": {"kind": "soft"},                          # headline; report soft/hard spread
>   "broker_profile": {  # ladder + two-venue commission + advance flag (template BROKER_PROFILE)
>     "name": "pair-desk", "warning_utilisation": "0.80",
>     "margin_call_utilisation": "0.90", "forced_close_utilisation": "1.00",
>     "commission": [{"venue": "HSX", "base": "trade_value", "rate": "0.0015"},
>                    {"venue": "HNXDS", "base": "per_contract", "amount": "5000"}],
>     "advance_sale_proceeds": {"enabled": False},            # headline: sale-advance OFF
>   },
>   "data": {},
> }
> backend = PlutusBackend.from_config(cfg, source=DataHubSource.for_root("data/market"))
> ```
> Advance the session per trading day (`advance_to(datetime.combine(day, CLOSE))`), submitting each day's ENTER/EXIT/roll leg orders through the `PairCoordinator`. **T+2 on, sale-advance off** (headline) so an equity profit cannot meet a futures VM call until it clears.

- [ ] **Step 1: Build the faithful arm** in `pair_anchor.py`: replay the **same** `PairSignal` decisions the naive engine produced, but route ENTER/EXIT through the `PairCoordinator`; size legs with `hedge` (`snap_hedge` from `parameter/optimized.json`/`parameter/hedge.json`), pick the futures dated symbol with `roll.front_month`, and close on `roll.is_roll_boundary`. Add the `backend.live_basket_ids()` helper here (Task 13 note).

- [ ] **Step 2: Count Tier-1 (settlement asymmetry leading)** — the headline tally, all read off fills/cash/margin (Plutus reports exactly this tier):
  - **Cross-pool transfers:** count + summed magnitude of every `PairCoordinator` securities→derivatives (and sweep-back) transfer.
  - **Funding-stall incidence:** entries where the futures leg was refused into locked cash and needed a transfer (a VM need the T+2-locked equity profit could not meet).
  - **`funded_in_aggregate` true/false + pair-abandonment** counts.
  - **Margin call / forced-close incidence** on the futures leg (thin config) — tally `margin_call`/`forced_liquidation` events from `advance_to`'s event stream (as the template `on_events` reads them).
  - **CLOSE_PROXY substitution** at any expiry-carried leg (`settlement_source == 'close_proxy'`, `substituted=True`).
  - **Orders refused by cause per venue:** `Rejected` acks tallied by `ack.rule.name`, split by venue — the no-short mirror-side count on HSX (`UNSETTLED_HOLDING`), equity `ROUND_LOT`/`TICK_GRID`/`BAND_LIMIT`, futures tick/`BAND_LIMIT`. Split `is_indeterminate` into its own counter (as SB does, `null_anchor.py:122`).
  - **Fill-policy divergence:** rerun the faithful arm under `hard` and report the `soft`/`hard` outcome spread + the indeterminate profile (honest at daily; expect the template's `hard`-arm INDETERMINATE behaviour, `pair-trade.py` finding 5).
  - **Opportunity-set asymmetry:** executable ENTER count vs `PairSignal.forgone_mirror` (the naive arm takes both sides; the faithful sits out the mirror).
- [ ] **Step 3: Tier-2 (consequence, not headline)** — net P&L/Sharpe/MDD, naive vs faithful, from each arm's daily equity curve (computed in the runner's harness; Plutus reports only fills/cash/margin). Frame as downstream effect; **may be omitted from the paper** (fidelity-not-pnl).
- [ ] **Step 4: Run it**, capture the JSON (`pp-anchor`). Smoke test asserts the result shape + that the faithful arm produced fills, at least one cross-pool transfer, and at least one no-short (`UNSETTLED_HOLDING`) refusal on the mirror side (the settlement-asymmetry + no-short effects firing):
```python
# tests/test_pair_anchor_smoke.py
from proto_pair.experiments.pair_anchor import run_pair_anchor
def test_faithful_arm_exercises_the_headline_axes():
    out = run_pair_anchor(is_data=False)
    f = out["faithful"]
    assert f["fills"] > 0
    assert f["cross_pool_transfers"]["count"] >= 1, "no segregation transfer -- headline not exercised"
    assert "opportunity_set" in f and "refusals_by_cause" in f
```
- [ ] **Step 5: Commit** (runner + smoke, trailer).

---

## Task 15: Registry, manifest, and `plutus check`

**Files:**
- Modify: `plutus/docs/reference/tables/experiments_registry.md`
- Create: `proto/ProtoPair/.plutus/manifest.yaml`

- [ ] **Step 1: Registry (in `plutus`).** Add a **Pair** block after the Grid block in `experiments_registry.md`, same discipline as the SB block: the modelling-choices paragraph (two venues `['HSX','HNXDS']`, two segregated pools, capital configs, `soft` headline + `soft`/`hard` spread, **T+2 on / sale-advance off** headline + the sale-advance variant, dated ladder 0.13→0.17, daily resolution, one frozen slice), the **Tier-1 settlement-asymmetry paragraph leading** (cross-pool transfers count+magnitude, funding stalls, `funded_in_aggregate`/abandonment, margin/forced-close, CLOSE_PROXY, no-short opportunity-set asymmetry, refusals by cause per venue, fill-policy divergence), Tier-2 (naive vs faithful, daily, framed as consequence / may be omitted), the attribution paragraph, and the **two regenerate commands** (`pp-extract`; `python -m proto_pair.experiments.pair_anchor`). Add Pair as the **top** spectrum point (SB → Grid → MM → **Pair**), and update the "Grid · MM · Pair — pending" note to mark Pair landed.

- [ ] **Step 2: `.plutus/manifest.yaml` (in ProtoPair)** mirroring SB's (schema 2.0; copy `proto/ProtoSmartBeta/.plutus/manifest.yaml` and adapt): `env` (uv, python 3.12), `data_sources` (the frozen slice via Drive if large; the algotradeDB freeze as a `raw` source with `satisfies: [data_preparation]` and a note that the cred is never committed), `steps` (`data_preparation` → `pp-extract` [+ `pp-freeze-db` for the OOS tail]; `in_sample_backtest` → `pp-backtest`; `optimization` → `pp-optimize`, `verification_mode: artifact_check`; `out_of_sample_backtest` → `pp-evaluate`), `expected` (**ACTIVITY metrics** with tolerances for `in_sample_backtest`: `round_trips`, `leg_order_events`, `fills` — the B-style gate; `optimization` as `artifact_check` on `parameter/optimized.json`; `out_of_sample_backtest` activity metrics; Tier-2 `sharpe/hpr/maximum_drawdown` recorded with loose tolerances, **not** framed as the gate), `nine_step_coverage` (steps 1–6 present, 7 absent).

- [ ] **Step 3: `plutus check` green under the naive backend.**
Run:
```bash
cd proto/ProtoPair && plutus check
```
Expected: exit 0 (all steps reproduce within tolerance). (Bootstrap the `.plutus-venv/` from the plutus-verify release wheel first, per SB's README "Reproducibility" section — the pyproject comment block from Task 1.)

- [ ] **Step 4: Commit** (both repos: ProtoPair manifest; plutus registry — two separate commits, each with the trailer). Do **not** push/PR.

---

## Self-review checklist (run before execution)

- **Spec coverage:** §1 role → Tasks 14–15 (top spectrum point); §2 hypothesis + activity/credibility gate → Tasks 1, 9, 10; §3a basket → Task 3; §3b hedge → Task 5; §3c z-score signal → Task 4; §3d no-short asymmetry → Tasks 4, 14; §3e roll → Task 6; §3f settlement asymmetry + funding-on-demand/abandon → Tasks 13, 14; §4a naive → Task 10; §4b faithful two-venue → Tasks 13, 14; §5 data/resolution + windows → Tasks 7, 8; §6 sizing (two configs) → Tasks 10, 14; §7 measures (Tier-1/Tier-2/attribution/spectrum) → Tasks 14, 15; §8 build order → all; §9 risks → below + Open Questions; §10 acceptance (1→8) → Tasks 1–2 (repo + green), 14 (two-venue arm), 9–10 (gate before OOS), 14 (soft headline + variants), 14–15 (Tier-1 leads + registry), 11 (B-style), 7 (reproduces from slice), 14–15 (top spectrum point).
- **DECISION-PENDING isolation:** signal (§3c, Task 4), hedge (§3b, Task 5), tick-vs-daily (§8/§5 — daily only; the tick sub-window is the isolated optional task below), window/KRX (§5, Task 7 constants), funding policy (§3f — a `broker_profile.advance_sale_proceeds` flag in Task 14, not code), activity numbers (§2, one `GATE` constant, Task 1), đồng figures (§6, `parameter/backtesting.json`, Task 10/14). Each is a single-file/single-constant revision — a flipped default reworks that task, not its neighbours.
- **Type consistency:** `PairSignal.update(...) -> PairDecision(action: Action, ...)` (Task 4) consumed by Tasks 10/14; `fit_beta(...)`/`snap_hedge(...) -> (int,int)` (Task 5) consumed by Tasks 10/14; `roll.front_month`/`is_roll_boundary` (Task 6) consumed by Tasks 10/14; `PlutusBackend.transfer/cancel/charges` (Task 2) consumed by Task 13; `PairCoordinator.enter -> EnterResult` (Task 13) consumed by Task 14. Names match across tasks.
- **Placeholder scan:** novel parts (strategy, hedge, roll, coordinator, credibility, backend passthroughs) carry complete code; boilerplate points at exact files (`null_anchor.py`, `extract_market.py`, SB `metric.py`/`backtest.py`/`evaluate.py`/`manifest.yaml`, `pair-trade.py` line ranges). No TBD/TODO.

## Known risks carried from the design + recon

- **`PlutusBackend` lacked `transfer`/`cancel`** — Task 2 surfaces them (they exist on `ExchangeSession`, `exchange.py:1904`/`1612`); the funding loop is blocked without it.
- **Equity corpus boundary:** `stock_quote_12.2020-09.2024` ends **2024-09-26** and `quote_vn30` ends **2022-08-01** — the OOS tail + later VN30 reviews depend on the **algotradeDB freeze** (Task 8, cred-gated, gitignored, never committed).
- **Basket ≠ index** (~5pp drift) — the claim is routing/funding/charging fidelity, stated in `docs/data.md` (Task 3), not hidden.
- **Roll is strategy-side, unsupported by plutus** — isolated in `roll.py` (Task 6), data-driven off the mapping table, auditable.
- **Behaviour-preserving naive anchor** — Tasks 10 (regression baseline) + 15 (`plutus check` green).
- **Same-day margin mark at daily resolution** (template finding 6) — disclosed look-ahead, labeled in Task 12/`docs/data.md`, not presented as intraday.
- **Corporate actions over multi-month holds** — relies on plutus's dated corporate-action/charge handling for 30 names (`corporate.py`, `vsdc_custody_equity`); verify coverage over the window (a `docs/data.md` risk note in Task 7), don't restrict the basket.

## Optional later task (isolated, non-core) — tick sub-window secondary arm

Per spec §5/§9 (`DECISION-PENDING Q8`), a secondary **tick-resolution** arm on the focused sub-window **2023-01 → 2024-09** (where futures L2 exists) may be added **only if** a futures tick/L2 freeze from algotradeDB is later done. It would reuse Tasks 4–6/10/13 unchanged and swap the faithful backend to `TickSource` at `resolution:"tick"` (Grid's Task-9 tick wiring), citing ProtoGrid's already-measured tick band-lock for the "band-lock desyncs the hedge" mechanism rather than re-measuring. **Keep it out of the core build** — it cannot cross KRX (tick equity ends 2024-09) and would block the capstone on a fresh freeze. This is a standalone add-on task, not a dependency of Tasks 1–15.

## Open questions for the executor to confirm with the owner

- **Frozen-slice hosting:** if `data/market/` is large (> ~100 MB), it ships via Drive (SB/Grid pattern) rather than committed — confirm the Drive location when Task 7 measures the size.
- **`VN30` index level presence:** Task 7's smoke test checks the `VN30` index level is a `tickersymbol` in the equity `quote_close` slice. If the named corpus does not carry it, source `VN30` daily closes from the Task-8 freeze (add it to `freeze_vn30_reviews`'s sibling query) — confirm the source.
- **Exact activity numbers, `z_in`/`z_out` defaults, and the two capital configs' đồng figures** — pre-registered in Task 1 / `parameter/*.json`; confirm before the faithful run (as SB/MM did).
- **algotradeDB freeze authorization** — Task 8 is gated on the owner running the read-only freeze with the cred; the guard tests pass without a DB, but the OOS tail (and thus the KRX-crossing demo) needs the freeze executed.
