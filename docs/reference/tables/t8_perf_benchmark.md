# T8.3 performance benchmark

Machine: Apple M6, 12 physical / 12 logical cores, 24.0 GB; macOS-27.0.1-arm64-arm-64bit-Mach-O; Python 3.15.2, DuckDB 2.0.1, pyarrow 26.0.1. plutus-simulator `8d46c56` (src dirty: False); load average at start (1.23, 2.17, 3.55).

| Measure | Value |
|---|---:|
| Rulebook build + first `at()` (cold) | 0.18 ms |
| `Rulebook.at(ts)` (warm) | 3,912,146.3 / s |
| Daily: `submit` (admission) | 5,545.2 orders / s |
| Daily: fill evaluation (`advance_to`) | 13,223.0 orders / s |
| Tick maker, optimistic queue (881 requotes, 1762 orders) | 3,211.0 orders / s (0.55 s) |
| Tick maker, conservative queue (881 requotes, 1762 orders) | 4,818.5 orders / s (0.37 s) |
| E1, 484,949 decisions × 3 policies | 7.14 s, peak RSS 285.8 MB |

Per-rule `RuleSet.resolve` latency (median / max, µs):

| Rule | Keys | Calls | Median | Max | Raised (unresolved) |
|---|---:|---:|---:|---:|---:|
| charge | 10 | 500 | 1.62 | 3.58 | 0 |
| daily_trading_limit | 8 | 400 | 2.25 | 4.04 | 0 |
| initial_margin_rate | 2 | 100 | 1.58 | 2.08 | 0 |
| legal_order_types | 29 | 1450 | 2.25 | 20.83 | 0 |
| margin_model | 1 | 50 | 1.29 | 2.79 | 0 |
| max_order_size | 4 | 200 | 1.58 | 7.0 | 0 |
| position_limit | 6 | 300 | 2.25 | 3.08 | 0 |
| session_schedule | 4 | 200 | 1.62 | 2.46 | 0 |
| settlement | 5 | 250 | 1.6 | 3.04 | 0 |
| tick_size | 12 | 600 | 3.62 | 6.08 | 0 |
| trading_unit | 5 | 250 | 2.25 | 20.42 | 0 |
| widened_trading_limit | 7 | 350 | 2.29 | 7.96 | 0 |

Regenerate: `PYTHONPATH=src:. python measurements/perf_benchmark.py --e1-root <t2-e1 slice> --json docs/reference/tables/t8_perf_benchmark.json --md docs/reference/tables/t8_perf_benchmark.md`
(per-stage progress goes to stderr). The E1 stage reran the full population and reproduced its headline
(484,949 decisions over 97,269 ticker-days; agreement 68.6%; undecided soft 2.7%, hard 33.3%, probabilistic 21.0%).
