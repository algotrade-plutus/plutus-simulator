# T8.6 -- Policy-surface counts: broker fields and enforced rule versions

*Source: `measurements/t8_counts.py` (run `PYTHONPATH=src python measurements/t8_counts.py`). Generated on
`rivf26`; everything under "Output" is its output verbatim. Reviewer item: R2 m5 ("some broker rules are
weakly sourced or unsourced").*

## Summary for the paper

**Broker fields: 244 confirmed.** The 244 are every `FieldCoverage` entry of the 18 shipped profiles in
`src/plutus/market/session/broker_profile.py`: 14 firms, plus PLUTUS_DEFAULT (a synthesis of the pool),
plus 3 vintages or variants (SSI_FOREIGN, SSI_2025_09, Pinetree_2024). So "244 fields from fourteen firms"
is slightly loose: 17 of the 244 belong to PLUTUS_DEFAULT and 44 to the three extra vintages.

- **Published by the firm: 110** (105 `PUBLISHED`, plus 5 `PUBLISHED_STALE`, which were published but mirror
  a VSDC table that has since moved). This is the code's own `BrokerProfile.published_fields()`.
- **Supplied by us: 0 as shipped.** `FILLED_FROM_DEFAULT` (`supplied_fields()`) is set only when a caller
  opts in with `get_profile(firm, fill_from=PLUTUS_DEFAULT)`. In that case **11** fields are supplied
  (MBS 5, KIS 3, VPS 3, the firms that delegate their ladder numbers).
- **Ours by inference: 21** (`INFERRED`): PLUTUS_DEFAULT's 17 median-of-the-pool values, and 4 derived from
  a firm's own arithmetic (SSI x3 vintages, SHS).
- **Not published, recorded as such: 113.** 74 `UNPUBLISHED`, 22 `DELEGATED`, 8 `INAPPLICABLE`,
  5 `CONTRADICTORY`, 3 `DISCLAIMED`, 1 `PUBLISHED_ILLUSTRATIVE` (a teaching number, not the firm's rate).

So the paper's binary "published vs supplied" is really three-way: **110 published, 21 ours, 113 recorded
as not published** (0 supplied as shipped, 11 if filled from PLUTUS_DEFAULT). Counting by firm only (the 14
firms, without PLUTUS_DEFAULT and the 3 vintages): 183 fields, 88 published.

**Enforced rule versions: the code has 114, not 97.** The runtime rulebook
(`rulebook._build_tables('vn-2020-2026')`, which is what `Rulebook.at(ts)` resolves against) holds
**114 dated rows over 93 keys in 12 rule families**; 106 are distinct (8 rows are the same row shared by
several keys). Grade histogram over the 114:

| Grade | Rows | Share |
|---|---:|---:|
| HIGH | 87 | 76% |
| MEDIUM | 11 | 10% |
| LOW | 9 | 8% |
| UNVERIFIED | 7 | 6% |

By status: 100 `KNOWN`, 3 `NOT_APPLICABLE` (a sourced "no such rule"), **11 `UNKNOWN`** (an absence
recorded as data). The paper's "eleven record an absence as data" and "twelve rule families" are confirmed.
"Most are graded high confidence and only a handful medium, low or unverified" should become "87 of 114
(76%) are high confidence; 27 are medium, low or unverified, 10 of them rows that record an absence".
Among the 100 `KNOWN` rows: 83 HIGH, 10 MEDIUM, 7 LOW, 0 UNVERIFIED.

**Where 97 came from.** Commit `fd7a031` (2026-08-30, `docs/reference/PAPER-COMPENDIUM.md` section 2a)
says "84 cited + 13 unsourced = 97". Those are source-text grep counts over `rulebook.py`, reproduced below:
84 occurrences of `confidence=Confidence.` and 13 of `_unsourced(`. That is not a count of rule versions:
the 13 includes `_unsourced`'s own definition and a docstring mention (11 real calls), and the 84 counts
every explicit grade argument once per call site -- on `_interval` calls, on 4 of the `_unsourced` calls
(so those are counted twice) and on direct `RuleCitation`s -- while several call sites sit inside loops
over venues or keys and produce several rows. `rulebook.py` has changed one
line since `fd7a031` (a path in a docstring), so the difference is the counting method, not new rows. The
runtime count is the one to quote. The derived totals change with it: "341 encoded in the engine" (97 + 244)
becomes **358** (114 + 244).

**Caveat on the rule-version count.** Three rule families delegate their values to a dated function rather
than storing one row per step: the initial margin rate (one row citing `margin.VSD_INITIAL_MARGIN`, which
holds 3 dated steps: 10% / 13% / 17%), the round lot (`core.constant.get_trading_unit`, which carries the
HOSE 10 -> 100 step), and the HSX banded tick grid. Those steps are enforced but counted inside one row each.

## Output

## Broker fields

18 shipped profiles = 14 firms + PLUTUS_DEFAULT (a synthesis) + 3 vintages/variants (SSI_FOREIGN, SSI_2025_09, Pinetree_2024).

| Profile | Fields | Published | Supplied (as shipped) | Inferred | Not published by the firm | Supplied if `fill_from=PLUTUS_DEFAULT` |
|---|---:|---:|---:|---:|---:|---:|
| PLUTUS_DEFAULT | 17 | 0 | 0 | 17 | 0 | 0 |
| TCBS | 17 | 12 | 0 | 0 | 5 | 0 |
| SSI | 16 | 9 | 0 | 1 | 6 | 0 |
| SSI_FOREIGN | 16 | 9 | 0 | 1 | 6 | 0 |
| SSI_2025_09 | 16 | 8 | 0 | 1 | 7 | 0 |
| VNDIRECT | 13 | 9 | 0 | 0 | 4 | 0 |
| FPTS | 14 | 12 | 0 | 0 | 2 | 0 |
| SHS | 15 | 10 | 0 | 1 | 4 | 0 |
| Vietcap | 12 | 7 | 0 | 0 | 5 | 0 |
| HSC | 13 | 10 | 0 | 0 | 3 | 0 |
| MBS | 14 | 4 | 0 | 0 | 10 | 5 |
| KIS | 12 | 4 | 0 | 0 | 8 | 3 |
| VPS | 13 | 3 | 0 | 0 | 10 | 3 |
| Pinetree | 12 | 5 | 0 | 0 | 7 | 0 |
| Pinetree_2024 | 12 | 5 | 0 | 0 | 7 | 0 |
| DNSE | 10 | 1 | 0 | 0 | 9 | 0 |
| VCBS | 11 | 1 | 0 | 0 | 10 | 0 |
| ACBS | 11 | 1 | 0 | 0 | 10 | 0 |
| **Total** | **244** | **110** | **0** | **21** | **113** | **11** |

Coverage status over all fields:

| Status | Fields |
|---|---:|
| PUBLISHED | 105 |
| PUBLISHED_ILLUSTRATIVE | 1 |
| PUBLISHED_STALE | 5 |
| DELEGATED | 22 |
| UNPUBLISHED | 74 |
| DISCLAIMED | 3 |
| INAPPLICABLE | 8 |
| CONTRADICTORY | 5 |
| INFERRED | 21 |
| FILLED_FROM_DEFAULT | 0 |
| **Total** | **244** |

## Enforced rule versions (runtime rulebook tables)

| Rule family | Keys | Rows | Distinct rows | HIGH | MEDIUM | LOW | UNVERIFIED | KNOWN | NOT_APPLICABLE | UNKNOWN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| `trading_unit` | 5 | 5 | 2 | 5 | 0 | 0 | 0 | 4 | 1 | 0 |
| `daily_trading_limit` | 8 | 11 | 11 | 7 | 0 | 3 | 1 | 8 | 1 | 2 |
| `widened_trading_limit` | 7 | 7 | 6 | 6 | 0 | 1 | 0 | 6 | 0 | 1 |
| `tick_size` | 12 | 14 | 14 | 7 | 5 | 0 | 2 | 12 | 0 | 2 |
| `session_schedule` | 4 | 7 | 7 | 3 | 3 | 1 | 0 | 7 | 0 | 0 |
| `legal_order_types` | 29 | 30 | 30 | 28 | 1 | 0 | 1 | 29 | 0 | 1 |
| `settlement` | 5 | 8 | 4 | 8 | 0 | 0 | 0 | 7 | 1 | 0 |
| `initial_margin_rate` | 2 | 2 | 2 | 1 | 0 | 1 | 0 | 1 | 0 | 1 |
| `margin_model` | 1 | 2 | 2 | 1 | 1 | 0 | 0 | 1 | 0 | 1 |
| `position_limit` | 6 | 6 | 6 | 3 | 0 | 3 | 0 | 6 | 0 | 0 |
| `max_order_size` | 4 | 5 | 5 | 2 | 0 | 0 | 3 | 2 | 0 | 3 |
| `charge` | 10 | 17 | 17 | 16 | 1 | 0 | 0 | 17 | 0 | 0 |
| **Total (12 families)** | **93** | **114** | **106** | **87** | **11** | **9** | **7** | **100** | **3** | **11** |

Grade histogram over distinct rows (a row shared by several keys counted once): HIGH 79, MEDIUM 11, LOW 9, UNVERIFIED 7 (total 106).

Grade by status (all rows):

| Status | HIGH | MEDIUM | LOW | UNVERIFIED | Total |
|---|---:|---:|---:|---:|---:|
| KNOWN | 83 | 10 | 7 | 0 | 100 |
| NOT_APPLICABLE | 3 | 0 | 0 | 0 | 3 |
| UNKNOWN | 1 | 1 | 2 | 7 | 11 |

## Source-text counts (how the paper's 97 was obtained)

| Pattern in `rulebook.py` | Occurrences |
|---|---:|
| `confidence=Confidence.` | 84 |
| `_unsourced(` | 13 |
| `_interval(` | 78 |
| `confidence=Confidence.` + `_unsourced(` | 97 |
