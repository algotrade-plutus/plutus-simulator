"""T8.6 -- the policy-surface counts the paper quotes, recomputed from code.

Two numbers in the RIVF'26 submission come from the engine rather than from the
survey documents, and reviewer R2 (m5) asked for their breakdowns:

* **"244 broker fields"** -- every :class:`FieldCoverage` entry of every shipped
  :class:`~plutus.market.session.broker_profile.BrokerProfile`. Each carries a
  :class:`Coverage` status; the profile partitions them with
  :meth:`BrokerProfile.published_fields` (``PUBLISHED`` + ``PUBLISHED_STALE``)
  and :meth:`BrokerProfile.supplied_fields` (``FILLED_FROM_DEFAULT``: a value
  another profile supplied). ``INFERRED`` (derived from the firm's own
  arithmetic, or PLUTUS_DEFAULT's median-of-the-pool) is the other kind of
  "ours" and is reported separately, as the module itself does.

  As shipped, no profile carries a ``FILLED_FROM_DEFAULT`` field: supply happens
  only when a caller opts in with ``get_profile(firm, fill_from=PLUTUS_DEFAULT)``,
  which fills the firm's BLOCKING fields. Both views are reported.

* **"97 enforced rule versions"** -- the dated rows of the rulebook. The
  authoritative count is runtime: every :class:`RuleInterval` in
  ``rulebook._build_tables('vn-2020-2026')``, which is what ``Rulebook.at(ts)``
  resolves against. The 97 in the paper was a *source-text* count
  (``PAPER-COMPENDIUM.md`` commit ``fd7a031``: "84 cited + 13 unsourced = 97"),
  which this script reproduces as grep counts over ``rulebook.py`` so the
  difference is visible: 84 is the number of ``confidence=Confidence.`` keyword
  occurrences and 13 the number of ``_unsourced(`` occurrences, which includes
  the function's own definition and a docstring mention, and misses rows built
  in loops and rows that take ``_unsourced``'s default grade.

Run::

    PYTHONPATH=src python measurements/t8_counts.py
"""

from __future__ import annotations

import re
import sys
import warnings
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple

ROOT = Path(__file__).resolve().parents[1]

from plutus.market.session import broker_profile as bp  # noqa: E402
from plutus.market.session import rulebook as rb  # noqa: E402
from plutus.market.session.types import Confidence  # noqa: E402

GRADES = [g.name for g in Confidence]
FIRM_VINTAGES = {'SSI_FOREIGN': 'SSI', 'SSI_2025_09': 'SSI',
                 'Pinetree_2024': 'Pinetree'}


# ---------------------------------------------------------------------------
# broker fields
# ---------------------------------------------------------------------------

def broker_rows() -> List[Dict]:
    rows = []
    with warnings.catch_warnings():
        warnings.simplefilter('ignore')
        default = bp.get_profile('PLUTUS_DEFAULT', warn=False)
        for name in bp.PROFILE_NAMES:
            p = bp._BUILDERS[name]()
            filled = (p.filled_from(default) if p.blocking_fields() else p)
            rows.append({
                'profile': name,
                'firm': FIRM_VINTAGES.get(name, name),
                'fields': len(p.coverage),
                'published': len(p.published_fields()),
                'supplied': len(p.supplied_fields()),
                'inferred': len(p.inferred_fields()),
                'status': Counter(c.status.name for c in p.coverage.values()),
                'supplied_if_filled': len(filled.supplied_fields()),
            })
    return rows


# ---------------------------------------------------------------------------
# rule versions
# ---------------------------------------------------------------------------

def rule_rows() -> Tuple[Dict[str, Dict], Dict[str, int]]:
    tables = rb._build_tables(rb.RULEBOOK_IDS[0])
    per_rule: Dict[str, Dict] = {}
    for name, table in tables.items():
        rows = [r for series in table.values() for r in series]
        distinct = {(r.citation, repr(r.value), r.effective_from,
                     r.effective_to, r.status) for r in rows}
        per_rule[name.value] = {
            'keys': len(table),
            'rows': len(rows),
            'distinct': len(distinct),
            'grade': Counter(r.citation.confidence.name for r in rows),
            'status': Counter(r.status.name for r in rows),
            'distinct_grade': Counter(d[0].confidence.name for d in distinct),
            'cross': Counter((r.status.name, r.citation.confidence.name)
                             for r in rows),
        }
    text = (ROOT / 'src/plutus/market/session/rulebook.py').read_text()
    grep = {
        'confidence=Confidence.': len(re.findall(r'confidence=Confidence\.',
                                                text)),
        '_unsourced(': len(re.findall(r'_unsourced\(', text)),
        '_interval(': len(re.findall(r'(?<!def )_interval\(', text)),
    }
    return per_rule, grep


# ---------------------------------------------------------------------------
# output
# ---------------------------------------------------------------------------

def _sum(counters) -> Counter:
    total: Counter = Counter()
    for c in counters:
        total.update(c)
    return total


def main() -> int:
    out: List[str] = []
    w = out.append

    brows = broker_rows()
    statuses = [s.name for s in bp.Coverage]
    total_fields = sum(r['fields'] for r in brows)
    total_pub = sum(r['published'] for r in brows)
    total_sup = sum(r['supplied'] for r in brows)
    total_inf = sum(r['inferred'] for r in brows)
    total_sup_filled = sum(r['supplied_if_filled'] for r in brows)
    status_total = _sum(r['status'] for r in brows)
    firms = sorted({r['firm'] for r in brows} - {'PLUTUS_DEFAULT'})

    w('## Broker fields')
    w('')
    w(f'{len(brows)} shipped profiles = {len(firms)} firms + PLUTUS_DEFAULT '
      f'(a synthesis) + {len(FIRM_VINTAGES)} vintages/variants '
      f'({", ".join(FIRM_VINTAGES)}).')
    w('')
    w('| Profile | Fields | Published | Supplied (as shipped) | Inferred | '
      'Not published by the firm | Supplied if `fill_from=PLUTUS_DEFAULT` |')
    w('|---|---:|---:|---:|---:|---:|---:|')
    for r in brows:
        other = r['fields'] - r['published'] - r['supplied'] - r['inferred']
        w(f'| {r["profile"]} | {r["fields"]} | {r["published"]} | '
          f'{r["supplied"]} | {r["inferred"]} | {other} | '
          f'{r["supplied_if_filled"]} |')
    other_total = total_fields - total_pub - total_sup - total_inf
    w(f'| **Total** | **{total_fields}** | **{total_pub}** | **{total_sup}** | '
      f'**{total_inf}** | **{other_total}** | **{total_sup_filled}** |')
    w('')
    w('Coverage status over all fields:')
    w('')
    w('| Status | Fields |')
    w('|---|---:|')
    for s in statuses:
        w(f'| {s} | {status_total.get(s, 0)} |')
    w(f'| **Total** | **{sum(status_total.values())}** |')
    w('')

    per_rule, grep = rule_rows()
    w('## Enforced rule versions (runtime rulebook tables)')
    w('')
    w('| Rule family | Keys | Rows | Distinct rows | ' +
      ' | '.join(GRADES) + ' | KNOWN | NOT_APPLICABLE | UNKNOWN |')
    w('|---|---:|---:|---:|' + '---:|' * (len(GRADES) + 3))
    for name, d in per_rule.items():
        w(f'| `{name}` | {d["keys"]} | {d["rows"]} | {d["distinct"]} | ' +
          ' | '.join(str(d['grade'].get(g, 0)) for g in GRADES) + ' | ' +
          ' | '.join(str(d['status'].get(s, 0))
                     for s in ('KNOWN', 'NOT_APPLICABLE', 'UNKNOWN')) + ' |')
    g_all = _sum(d['grade'] for d in per_rule.values())
    s_all = _sum(d['status'] for d in per_rule.values())
    gd_all = _sum(d['distinct_grade'] for d in per_rule.values())
    keys = sum(d['keys'] for d in per_rule.values())
    rows = sum(d['rows'] for d in per_rule.values())
    distinct = sum(d['distinct'] for d in per_rule.values())
    w(f'| **Total ({len(per_rule)} families)** | **{keys}** | **{rows}** | '
      f'**{distinct}** | ' +
      ' | '.join(f'**{g_all.get(g, 0)}**' for g in GRADES) + ' | ' +
      ' | '.join(f'**{s_all.get(s, 0)}**'
                 for s in ('KNOWN', 'NOT_APPLICABLE', 'UNKNOWN')) + ' |')
    w('')
    w('Grade histogram over distinct rows (a row shared by several keys '
      'counted once): ' +
      ', '.join(f'{g} {gd_all.get(g, 0)}' for g in GRADES) +
      f' (total {sum(gd_all.values())}).')
    w('')
    cross = _sum(d['cross'] for d in per_rule.values())
    w('Grade by status (all rows):')
    w('')
    w('| Status | ' + ' | '.join(GRADES) + ' | Total |')
    w('|---|' + '---:|' * (len(GRADES) + 1))
    for s in ('KNOWN', 'NOT_APPLICABLE', 'UNKNOWN'):
        vals = [cross.get((s, g), 0) for g in GRADES]
        w(f'| {s} | ' + ' | '.join(map(str, vals)) + f' | {sum(vals)} |')
    w('')
    w('## Source-text counts (how the paper\'s 97 was obtained)')
    w('')
    w('| Pattern in `rulebook.py` | Occurrences |')
    w('|---|---:|')
    for k, v in grep.items():
        w(f'| `{k}` | {v} |')
    w(f'| `confidence=Confidence.` + `_unsourced(` | '
      f'{grep["confidence=Confidence."] + grep["_unsourced("]} |')
    print('\n'.join(out))
    return 0


if __name__ == '__main__':
    sys.exit(main())
