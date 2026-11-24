# E1, published statistics (owner decision 2026-11-24: statistics only, at a checkable grain)

Regenerate: `PYTHONPATH=src:. python measurements/e1_publish.py --data-root <t2-e1 slice> --out docs/reference/tables/t2/e1_published`.
The slice itself is not published; anyone with access to the Algotrade database can rebuild it with
`measurements/e1_regenerate.py` (selection rule: `SELECTION_SQL` there).

| File | Grain | Rows |
|---|---|---:|
| `by_month_intent.csv` | month × intent | 60 |
| `by_ticker_intent.csv` | ticker × intent | 1,955 |
| `totals.json` | the run | 1 |

Both tables come from the same run as the headline and **sum to it exactly** (484,949 decisions, 332,549
agreed = 68.57%). The script asserts that before writing.

- `agreed`: the three policies are indistinguishable on the decision (same outcome, quantity and price). This is
  the headline's definition, which is stricter than "same outcome".
- `<policy>_fill / _no_fill / _indeterminate`: outcome counts per policy.
- `qty_soft / qty_hard` (month table only): filled shares summed over all tickers that month.

What these do **not** carry: prices, volumes, or per-ticker quantities (a filled quantity is min(order, 10% of
the day's volume), so per ticker it would leak volume). The outcome counts are still market-derived. For
example, `soft_fill` for `limit_buy_at_floor` in the ticker table is how many 2022 sessions that ticker's low
reached its floor.
