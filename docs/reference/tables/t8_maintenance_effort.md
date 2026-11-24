# T8.5 -- Maintenance effort: rule data vs engine code per dated change

*Source: `measurements/maintenance_effort.py` (run `PYTHONPATH=src python measurements/maintenance_effort.py
--markdown`; without `--markdown` it also lists every counted line). Generated on `rivf26`; the tables below
are its output verbatim.*

## Read this first: what git history can and cannot show

**History is too entangled to measure "lines changed to add one dated change" from commit diffs.** No dated
change in this repository was added *after* the mechanism carrying it existed. `rulebook.py` has five commits
in all (`b737f6f` creates it with 464 lines; `7ee32b9` +1,913; `7b56e95` +327; `bc7f793` +150; `a95d59f` one
path line), and every dated row arrived inside one of those bulk commits together with the resolver, the
session and their tests. The dated series kept outside the rulebook (`margin.VSD_INITIAL_MARGIN`,
`core.constant.get_trading_unit`) arrived in `0d91323`, which fixed six unrelated defects at once (12 files,
+511/-72). A per-commit diff would therefore measure "build the mechanism and several other things", not the
cost of one dated change, and is not reported as if it were. The last table shows how large each contributing
commit was.

**What is shown instead: each change's footprint at `HEAD`, attributed to commits by `git blame`.** For each
change the script finds the source lines that encode it (anchored on its date or the constant naming it),
expands each hit to its syntactic unit with `ast`, and classifies it:

- **Rule data** -- the dated rows: value, dates, document, article, confidence grade and note (citation
  lines count as data).
- **Undated duplicate scalars** -- the same value copied elsewhere without a date (a default, a guard
  constant). Each is a line a future step must remember to touch.
- **Engine, change-specific** -- code (comments/docstrings excluded) that names the change: a branch on its
  date, or a call that switches on the edition.
- **Engine, per-family resolver** -- the lookup function the rule family needed the first time. Shared by
  every past and future step of that rule, so it is a one-off cost, not a per-change cost.
- **Tests** -- whole test functions that name the date or its constant.

## Findings

1. **VSD IM 13% -> 17% (2022-12-15) is data-only in the engine:** the step itself is one dated tuple line
   (`margin.py:132`) under a 14-line rulebook row that cites the whole 10/13/17% series; **0 engine lines**
   name it. The next IM step would be one line of data plus a note edit -- **but also three undated copies of
   0.17** (`MarginConfig.vsd_initial` and `maintenance_rate` defaults in the legacy `margin.py`, and
   `broker_profile.VSDC_INITIAL_MARGIN_RATIO`, which guards that no broker ratio is below VSDC's). Those are a
   real maintenance hazard: none is dated, so a future step that updates only the series leaves them stale.
2. **HOSE lot 10 -> 100 (2021-01-04) is mostly data, but the step is encoded as code:** 13 lines of rule
   data (the `HSX_ROUND_LOT_RAISED` constant and the cited rulebook row), and **4 engine lines** -- the
   `if exchange == HSX and on < HSX_ROUND_LOT_RAISED: return 10` branch in `core.constant.get_trading_unit`.
   The rulebook row delegates its value to that function rather than storing 10 and 100 as two rows, so a
   further lot change would need a code edit, not a table row.
3. **KRX cutover (2025-05-05) is a rule set, and most of it is data:** 79 lines in 11 units -- 8 dated rulebook rows (session
   schedules, legal order types, margin model), the ex-rights-code citation and the two `KRX_CUTOVER` constants, against
   **20 change-specific engine lines**: `Rulebook.edition_at`, three `edition_at(ts)` call sites in
   `exchange.py` (two regime tags and the amend rule, which is encoded as `edition_at(ts) == 'pre_krx'`
   rather than as a table row), and the broker-profile pre-KRX-document gap (15 lines). **Not counted**: the
   post-KRX margin model (`scenario_margin.py`, ~3,000 lines) and the broker-profile regime machinery, which
   the cutover motivated but which do not name its date; the anchor method cannot attribute them.
4. **HOSE tick change 2016-09-12: not measurable.** It is not encoded anywhere in `src/` -- the rulebook
   window starts 2020-01-01 (`rulebook.COVERAGE_START`), and `measurements/dated_rules.py` records that the
   only pre-2016 grid ever tried was a reconstruction, not a source.
5. **Two duplicated `KRX_CUTOVER` constants** (`rulebook.py:134`, `broker_profile.py:1504`) are the same
   date defined twice; counted as rule data, and the same kind of drift hazard as finding 1.

Rule data : change-specific engine, per change: **IM 15 : 0** (plus 3 undated copies), **lot 13 : 4**,
**KRX 79 : 20** (excluding the unattributable margin-model work).

## Output of `measurements/maintenance_effort.py --markdown`

Measured at HEAD `8295502`.

| Change | Effective | Rule data | Undated duplicate scalars | Engine, change-specific | Engine, per-family resolver (shared) | Tests |
|---|---|---:|---:|---:|---:|---:|
| VSD initial margin 13% -> 17% (HNXDS index futures) | 2022-12-15 | 15 (2 units) | 3 | 0 | 18 | 117 (8 test fns) |
| HOSE round lot 10 -> 100 shares | 2021-01-04 | 13 (2 units) | 0 | 4 | 17 | 18 (1 test fns) |
| KRX trading-system cutover (HOSE/HNX rule set) | 2025-05-05 | 79 (11 units) | 0 | 20 | 1 | 66 (5 test fns) |

Lines are non-blank source lines at `HEAD`. Rule data counts the whole row (value, dates, document, article, confidence, note); a unit is one dated row, dated tuple element, citation or date constant. Engine counts exclude comments and docstrings; the resolver column excludes lines already counted as change-specific.

### Which commits wrote those lines (`git blame -w -M`)

| Change | Class | Lines by commit |
|---|---|---|
| vsd_im_2022_12_15 | rule_data | `7ee32b9` 14, `0d91323` 1 |
| vsd_im_2022_12_15 | dup_scalar | `0d91323` 2, `5238c8d` 1 |
| vsd_im_2022_12_15 | mechanism | `7ee32b9` 10, `0d91323` 8 |
| vsd_im_2022_12_15 | tests | `68e30b1` 73, `bc7f793` 14, `7ee32b9` 13, `9c862f2` 9, `0d91323` 8 |
| hsx_lot_2021_01_04 | rule_data | `7ee32b9` 12, `0d91323` 1 |
| hsx_lot_2021_01_04 | engine_specific | `0d91323` 4 |
| hsx_lot_2021_01_04 | mechanism | `7ee32b9` 12, `0d91323` 5 |
| hsx_lot_2021_01_04 | tests | `7ee32b9` 18 |
| krx_cutover_2025_05_05 | rule_data | `7ee32b9` 38, `7b56e95` 28, `bc7f793` 11, `b737f6f` 1, `5238c8d` 1 |
| krx_cutover_2025_05_05 | engine_specific | `5238c8d` 15, `7ee32b9` 5 |
| krx_cutover_2025_05_05 | mechanism | `7ee32b9` 1 |
| krx_cutover_2025_05_05 | tests | `7ee32b9` 50, `5238c8d` 8, `bfc1197` 8 |

### How large those commits were (entanglement)

| Commit | Date | Files | +lines | -lines | Subject |
|---|---|---:|---:|---:|---|
| `9c862f2` | 2026-08-25 | 5 | 562 | 0 | Add plutus.market value and verdict types |
| `b737f6f` | 2026-08-25 | 14 | 13323 | 47 | Read the settlement series correctly and retire tradeoff T2 |
| `7ee32b9` | 2026-08-25 | 13 | 6972 | 16 | Build Tier 1: the exchange session, seven modules behind one API |
| `0d91323` | 2026-08-25 | 12 | 511 | 72 | Fix six verified rulebook defects and add broker terms as config |
| `bc7f793` | 2026-08-26 | 16 | 10053 | 522 | Tier 2: charges, sale advance, corporate actions, probabilistic fills, pair trading |
| `7b56e95` | 2026-08-26 | 12 | 3607 | 136 | Repair all ten Tier 1 defects; 997 -> 1035 passing |
| `bfc1197` | 2026-08-26 | 2 | 359 | 0 | Measure the corpus exposure to dated rule changes -- the lead claim's warrant |
| `5238c8d` | 2026-08-27 | 4 | 7506 | 138 | Add the broker-profile system with PLUTUS_DEFAULT, and apply the KRX corrections |
| `68e30b1` | 2026-08-27 | 40 | 22787 | 63 | Validate the whole simulator end to end; the accounting holds, the fill model does not |

- **krx_cutover_2025_05_05**: Not counted: the post-KRX margin model (scenario_margin.py, ~3,000 lines) and the broker-profile regime machinery, which the cutover motivated but which do not name its date. The KRX cutover is a rule SET: these rows are the dated rows that name it.
- **HOSE tick change 2016-09-12**: encoded in `src/`: no -- outside the rulebook window (COVERAGE_START 2020-01-01), so not measurable.

