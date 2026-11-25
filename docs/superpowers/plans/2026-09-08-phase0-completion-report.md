# Phase 0 — completion report (2026-09-08)

Implements `docs/superpowers/plans/2026-09-08-phase0-execution-seam-sb-null-anchor.md`.
Status: **COMPLETE — all of Tasks 1–9 landed and verified.** The two modeling
decisions below were confirmed by the user (faithful capital = 25B đồng; sale
advance enabled so SB stays the null anchor), and the null-anchor result landed
— see **Update (2026-09-10)** at the foot. All work is on branch `rivf-2026` in
each repo.

## What landed (green, committed)

| # | Deliverable | Repo · commit | Evidence |
|---|---|---|---|
| 1 | **`PlutusBackend`** — reusable `ExchangeSession` facade (`src/plutus/execution/`) | plutus · `189d05c` | 2 tests pass on the shipped fixtures; submits the FPT buy and **fills at 74.0** (J1 case), reads `cash()`/`holdings()` |
| 2 | ProtoSmartBeta on `rivf-2026` + Plutus editable path dep | ProtoSmartBeta · `29eaeb0` | `from plutus.execution import PlutusBackend` works inside the proto venv |
| 3 | **Parquet data layer** (4 I/O sites repointed; `return`/`ac_return` cast to float) | ProtoSmartBeta · `e5c4b96` | **behaviour-preserving: IS `1.2971462146128898` and OOS `-0.3497436972790686` reproduce bit-for-bit** |
| 4 | Regression gate as a test (`tests/test_regression_baseline.py`) | (same) | 2 tests pass — the exact-reproduction gate |
| 5 | **Signal seam** `Backtesting.select_qualified` (pure P/E∩DY) | ProtoSmartBeta · `5c6289d` | baseline still reproduces exactly after extraction |
| 6 | **Market-slice extractor** + frozen slice (`data/market/`, 16 MB, 9 daily tables) | (same) | extracts the 1693-ticker OOS universe in ~2 s; `DataHubSource.for_root` reads it |

The reusable half of the architecture — the Plutus-facing adapter and the
behaviour-preserving, parquet-backed, seam-ready strategy — is proven. Every
regression gate is green and exact, so the naive anchor stays a real, verified,
published number.

## Why the null-anchor number (Tasks 7–9) is paused — two findings, not bugs

Inspecting the naive engine's actual state (43 positions of 5,000–101,800
shares on "25M" capital, asset curve 25,000,000 → 24,207,282) surfaced two real
modeling facts that decide the faithful run rather than following from it:

1. **Scale reconciliation (×1000).** SmartBeta's prices are in *thousands of
   đồng* (close ≈ 75 == 75,000đ) but its accounting treats them as raw đồng, so
   a 7,700-share position is booked at ~577k, not ~577M. A faithful Plutus run
   in real đồng — real 100-share lots, real bands — must therefore use
   **capital = 25M × 1000 = 25B đồng**, or the portfolio cannot be built at all
   (25M đồng buys ~3 lots total). *Decision:* run the faithful arm at 25B đồng
   (the defensible reading) — confirm before it becomes the published anchor.

2. **SmartBeta is not a clean "null" on the T+2 axis.** Its rule is *"liquidate
   all holdings, then buy the new selection"* on the same rebalance day. Naively
   that self-funds; faithfully the sale proceeds are **unsettled for T+2** and
   cannot fund the same-day repurchase (unless the strategy uses the sale
   advance, *ứng trước tiền bán*, which its naive engine does not). So even the
   intended null anchor has a genuine, monthly-recurring capital gap. *Decision:*
   model the rebalance faithfully (accept the T+2 gap as a finding — SmartBeta
   moves off the null point), and/or add the sale-advance to recover it. Either
   is a paper-relevant result; the choice shapes the number.

Both are exactly the "naive assumptions distort the result" effects the paper
exists to measure — but a headline number should be produced under a stated,
user-confirmed choice, not guessed in the last mile. Forcing an unverified
number now would risk publishing a wrong anchor.

## Recommended next steps

1. **Confirm the two decisions above** (faithful capital = 25B đồng; how to treat
   the monthly T+2 liquidation — accept the gap and/or model the sale advance).
2. **Finish Tasks 7–9** under that choice: `PlutusExecution` (drive the shared
   `select_qualified` signal through `PlutusBackend` over `data/market`),
   the null-anchor runner (naive vs faithful Sharpe/HPR/MDD, computed
   scale-invariantly so units cancel, + Tier-1 refusals/indeterminates/fills by
   rule), and the `experiments_registry.md` row.
3. **Re-ship the SmartBeta parquet slice to Drive** and re-green containerized
   `plutus check` (the local exact-reproduction gate already stands in for it).
4. Then Phase 1 (ProtoGrid), Phase 2 (MM + KRX), Phase 3 (ProtoPair) per the
   design spec.

## Notes / caveats recorded

- `data/` and `data/market/` are untracked (repo ships data via Drive); the
  frozen parquet slices exist locally and regenerate from `extract_market` +
  the committed signal parquet.
- Plutus is installed editable `--no-deps` into the proto venv (+ `pytz duckdb
  pyarrow`); a full `uv sync` of the path dep is deferred so Plutus's heavy
  optional deps (redis, …) are not pulled.
- The buy-leg `sell_fee` quirk and the two divergent budget formulas were
  preserved (not "fixed") so the baseline stays exact.

## Update (2026-09-10) — null-anchor landed (Tasks 7–9)

Both decisions confirmed. Verified: naive SmartBeta charges **no** advance/
interest/T+2 logic (only the flat 0.035% fee), so it implicitly assumes a free
instant sale advance. The faithful arm therefore enables the sale advance
(`broker_profile.advance_sale_proceeds`, `daily_rate 0.0003`) at 25B đồng, with
LIMIT-at-close orders over the frozen daily slice.

**Result (OOS 2022–2024, 525 days, 25 rebalances):**

| Metric | naive | faithful | Δ |
|---|--:|--:|--:|
| Sharpe | −0.3497 | −0.5543 | −0.205 |
| HPR | −3.17% | −9.61% | −6.44 pp |
| Max drawdown | −46.04% | −46.25% | −0.21 pp |

Tier-1: 2,187 fills; refusals **45 BAND_LOCK only** (0 INSUFFICIENT_CASH after
switching MTL→LIMIT-at-close), **0 indeterminate**. The **drawdown is unchanged**
— same risk profile; only the return level moves, and the movable part is mostly
frictions (advance fee, lot granularity, fill timing) a naive backtest could also
add. SB is the null anchor. Committed: ProtoSmartBeta `3280d39`
(`experiments/null_anchor.py`, `tests/test_null_anchor.py`), plutus `1c1e3c9`
(`docs/reference/tables/experiments_registry.md`). Regenerate: `python -m
proto_smart_beta.experiments.{extract_market,null_anchor}`.

**Next:** Phase 1 (ProtoGrid, the high-intensity equity demonstrator), then MM
(+ KRX), then ProtoPair. Follow-up: re-ship the SB parquet slice to Drive and
re-green containerized `plutus check`.
