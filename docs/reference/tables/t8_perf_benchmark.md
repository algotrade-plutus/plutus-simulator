# T8.3 performance benchmark

## Machine

| | |
|---|---|
| CPU | Apple M6 (12 physical / 12 logical cores) |
| Memory | 24.0 GB |
| OS | macOS-27.0.1-arm64-arm-64bit-Mach-O |
| Power | AC Power |
| Python | 3.15.2 (DuckDB 2.0.1, pyarrow 26.0.1, pandas 3.1.1) |
| plutus-simulator | `b06d36c` (src dirty: False) |
| Run date | 2026-11-25 |

## Results

**10 runs, each a separate process.** Values are the median across runs; min–max and the coefficient of variation (CV) show the spread. 1-min load average at the start of each run: 1.69–4.61.

| Measure | Median | Min – max | CV |
|---|---:|---:|---:|
| Rulebook build + first `at()` (cold) | 0.18 ms | 0.18 – 0.55 | 49.71% |
| `Rulebook.at(ts)` (warm) | 3,911,183 / s | 3,857,222 – 4,000,087 | 1.06% |
| Daily: `submit` (admission) | 5,574 orders / s | 5,494 – 5,642 | 0.83% |
| Daily: fill evaluation (`advance_to`) | 13,086 orders / s | 12,830 – 13,210 | 0.87% |
| Tick maker, optimistic queue | 3,220 orders / s | 3,048 – 3,231 | 1.64% |
| Tick maker, conservative queue | 4,824 orders / s | 4,570 – 4,840 | 2.07% |
| E1 wall time (484,949 decisions × 3 policies) | 7.18 s | 7.06 – 7.27 | 0.96% |
| E1 peak RSS | 285.6 MB | 285.0 – 287.5 | 0.28% |

Per-rule `RuleSet.resolve` latency (µs; median of the per-run medians, worst max over all runs):

| Rule | Keys | Calls per run | Median | Max | Raised (unresolved) |
|---|---:|---:|---:|---:|---:|
| charge | 10.0 | 500.0 | 1.62 | 8.63 | 0.0 |
| daily_trading_limit | 8.0 | 400.0 | 2.27 | 19.33 | 0.0 |
| initial_margin_rate | 2.0 | 100.0 | 1.58 | 15.21 | 0.0 |
| legal_order_types | 29.0 | 1450.0 | 2.25 | 138.88 | 0.0 |
| margin_model | 1.0 | 50.0 | 1.29 | 3.37 | 0.0 |
| max_order_size | 4.0 | 200.0 | 1.58 | 17.42 | 0.0 |
| position_limit | 6.0 | 300.0 | 2.25 | 5.87 | 0.0 |
| session_schedule | 4.0 | 200.0 | 1.63 | 3.08 | 0.0 |
| settlement | 5.0 | 250.0 | 1.62 | 24.5 | 0.0 |
| tick_size | 12.0 | 600.0 | 3.645 | 69.54 | 0.0 |
| trading_unit | 5.0 | 250.0 | 2.31 | 33.75 | 0.0 |
| widened_trading_limit | 7.0 | 350.0 | 2.31 | 14.5 | 0.0 |

Workloads: rulebook 200,000 `at()` calls and 50 `resolve` calls per key; daily 5,000 FPT orders on the shipped daily fixture; tick an S8/S9-style maker requoting every 15 s on the shipped FPT 2022-11-09 book and tape (1762.0 orders); E1 the full 2022 population (484,949.0 decisions).

Regenerate: `PYTHONPATH=src:. python measurements/perf_benchmark_repeat.py --runs 10 --e1-root <t2-e1 slice> --log <log file>` on an otherwise idle machine. Each run's own output is in `docs/reference/tables/t8_perf_runs/`.
