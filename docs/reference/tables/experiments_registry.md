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
| Sharpe (annualised) | **−0.3497** | **−0.5093** | −0.160 |
| HPR | −3.17% | −8.39% | −5.22 pp |
| Max drawdown | −46.04% | −46.35% | −0.31 pp |

**Tier-1 (sign-free, faithful arm).** 2,257 fills over the run; refusals
**`{}`** and indeterminates **`{}`** — band lock is graded at fill time, not
admission, so it never appears as a `refusals` entry (see the Increment 2 note
below for the mechanism); the fee-buffered LIMIT-at-close sizing still leaves
no `INSUFFICIENT_CASH`, unchanged from before. **Band-lock no-fills: 0** —
every `Accepted` order this run submitted into a
close-at-the-band day resolved to a fill under the `soft` policy's floor. With
the band-lock channel measured at zero, the entire faithful/naive gap is the
sale-advance fee + lot-granularity + fill-at-close-vs-prev-close timing — all of
which are cheaply modelable in the naive engine too, which is why SB stays the
null anchor: a faithful simulator adds little here **beyond** frictions a
careful naive backtest could also add. The **max drawdown is essentially
unchanged** (−46.35% vs −46.04%), i.e. the risk profile is materially the same;
only the return level and Sharpe move — **up toward naive** relative to
Increment 1 (see below).

**Provenance / regenerate:**
```bash
cd proto/ProtoSmartBeta            # branch rivf-2026
python -m proto_smart_beta.experiments.extract_market      # freeze the daily slice
python -m proto_smart_beta.experiments.null_anchor         # naive vs faithful
```
Naive numbers reproduce the committed `.plutus/expected/` baseline exactly
(`tests/test_regression_baseline.py`).

**Increment 2 note.** Increment 1 moved BAND_LOCK to fill time but kept
Increment 0's evidence: a single `close==band` bar-proxy that could not tell a
genuine full-session lock from a bar that merely *closed* at the edge after
trading through it earlier in the session — every one of those was graded
`NO_FILL`, a ~10x over-assertion left unfixed until now. Increment 2 replaces it
with the full daily evidence ladder (OHLC + volume, phase-aware): a bar that
traded through the edge before closing there **fills** (the over-assertion
fix — most of the population); a bar that collapsed to the edge but still
recorded volume passes through to the active fill policy's floor, which for
`soft` **fills at the edge**; only a bar that collapsed to the edge with
**zero** recorded volume (*trắng bên bán/mua*, a genuine full-session lock) is
graded **`NO_FILL`**.

Regenerating under Increment 2: faithful Sharpe moves from **−0.5543**
(Increment 1) to **−0.5093** (measured) — up toward naive's **−0.3497**,
shrinking the gap from −0.2046 to −0.1596, the direction the fix predicts.
Total fills rose from 2,187 to **2,257**.

The runner's Tier-1 tally is recounted to match: since a fill-time `NO_FILL`
leaves the order **resting with no event of its own** (`REST` is the one
silent transition — it cannot be read off `advance_to`'s event stream),
`null_anchor.py`'s `_faithful` now classifies it post hoc instead — an
`Accepted` order marketable into a close-at-the-band day
(`DataHubSource.state_at(ticker, day).locked_side` matching the order's side)
that never turns up in a fill event over its rebalance window is a band-lock
no-fill. Of the **49** such candidates this run touched (the fresh count under
this classifier — not directly comparable to Increment 1's **45**, which was
measured under the older admission-time-rejection regime; accepting rather
than rejecting those orders changes downstream cash and holdings, so which
later orders even get submitted diverges too), **all 49 resolved to fills**:
**band-lock no-fills: 45 → 0**. Under the `soft` policy every collapsed-but-
traded bar fills at the edge, and this OOS window contains no ticker-day that
both collapsed to the band **and** recorded zero volume — the residual
true-lock population is empirically empty here, not assumed away.

---

## Grid · MM · Pair — pending (Phases 1–3)

The equity grid (ProtoGrid), the futures market-maker (ProtoMarketMaker) and the
cross-market pair (ProtoPair) are the high-intensity end of the spectrum; their
rows land as each phase completes. The synthetic corroborators (population E1,
the 381-book E2 re-dating, the equity-admission lag) are retained in
`t4_measured_results.md` and quoted as large-n backbone when page room allows.
