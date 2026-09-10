# Experiments registry — naive vs faithful, per strategy

The single source the RIVF'26 paper quotes for the strategy-driven experiments
(the naive-vs-faithful contrast on real strategies, framed as an
execution-intensity spectrum). Each strategy runs the **same signals** through
its own naive engine and through the faithful Plutus market; the gap is the
finding. Every row carries the modelling choices it was measured under and the
command that regenerates it. See
`docs/superpowers/specs/2026-09-08-plutus-strategy-experiments-design.md`.

> **Read the gap, not a single arm.** The point of each block is that the two
> arms *differ*, and by how much relative to the strategy's execution intensity.
> P&L is a Tier-2 consequence, computed by the caller's harness; Plutus reports
> only fills / cash / margin.

---

## SB — SmartBeta (equity, monthly P/E-DY rebalance) · the null anchor

Low execution intensity (monthly, close-price, cash equity), so the faithful
run should land *close* to the naive — the calibration point of the spectrum.
Out-of-sample window 2022-01-04 → 2024-02-07 (525 trading days, 25 rebalances).

**Modelling choices (faithful arm).** Capital **25,000,000,000đ** (the naive
25M × 1000, because SmartBeta's prices are quoted in thousands of đồng);
`soft` fill policy; orders as **LIMIT at the day's close**; the **sale advance**
(*ứng trước tiền bán*) enabled at `daily_rate 0.0003` so the monthly
full-liquidation rebalance self-funds same-day; real 100-share lots and price
bands; weekday-only settlement calendar (Tết approximation). Both arms read one
identical frozen parquet slice (`data/market/`, the OOS universe's daily tables).

| Metric | naive (published) | faithful (Plutus) | Δ |
|---|--:|--:|--:|
| Sharpe (annualised) | **−0.3497** | **−0.5543** | −0.205 |
| HPR | −3.17% | −9.61% | −6.44 pp |
| Max drawdown | −46.04% | −46.25% | −0.21 pp |

**Tier-1 (sign-free, faithful arm).** 2,187 fills over the run; refusals: **45
BAND_LOCK** (a rebalance order into a limit-up/-down name the exchange would not
admit) and **0 INSUFFICIENT_CASH**; **0 indeterminate** (daily OHLC decides every
fill). The band-lock refusals are the *only* simulator-specific effect; the rest
of the gap is the sale-advance fee + lot-granularity + fill-at-close-vs-prev-close
timing — all of which are cheaply modelable in the naive engine too, which is why
SB stays the null anchor: a faithful simulator adds little here **beyond**
frictions a careful naive backtest could also add. The **max drawdown is
essentially unchanged**, i.e. the risk profile is the same; only the return level
and Sharpe move.

**Provenance / regenerate:**
```bash
cd proto/ProtoSmartBeta            # branch rivf-2026
python -m proto_smart_beta.experiments.extract_market      # freeze the daily slice
python -m proto_smart_beta.experiments.null_anchor         # naive vs faithful
```
Naive numbers reproduce the committed `.plutus/expected/` baseline exactly
(`tests/test_regression_baseline.py`).

---

## Grid · MM · Pair — pending (Phases 1–3)

The equity grid (ProtoGrid), the futures market-maker (ProtoMarketMaker) and the
cross-market pair (ProtoPair) are the high-intensity end of the spectrum; their
rows land as each phase completes. The synthetic corroborators (population E1,
the 381-book E2 re-dating, the equity-admission lag) are retained in
`t4_measured_results.md` and quoted as large-n backbone when page room allows.
