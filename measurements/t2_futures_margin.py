"""RIVF'26 T2 group C: the derivatives-margin rows on a DB slice, plus fact-check F1.

Runs, on one data root, exactly what ``reproduce_measurements.measure_exchange_margin``
runs (``regime_split.measure_regime_split``; ``measure_account_margin_incidence`` at
holds 5/10/20, funding ``BEST_JOINT_FIT``, daily VM settlement, Wilson 95% CIs), and
adds the F1 decomposition on the same 381-entry book: mean IM at a flat 13% vs a flat
17% (the 13% -> 17% step alone), and the post-KRX grid against each.

Writes JSON to stdout. Results: ``docs/reference/tables/t2/futures_margin.md``.

    PYTHONPATH=src:. python measurements/t2_futures_margin.py <slice-root>
"""
import json
import math
import sys
from collections import Counter
from decimal import Decimal

from measurements.margin_incidence_account import (
    BEST_JOINT_FIT, VN30F_MULTIPLIER, _series, _windows,
    measure_account_margin_incidence)
from measurements.regime_split import (
    _Held, _POST_KRX_AS_OF, _POST_KRX_MF, _POST_KRX_PARAMS, measure_regime_split)
from plutus.market.margin import vsd_initial_margin
from plutus.market.session.overnight import scenario_grid_requirement

root = sys.argv[1]


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return round(100 * (c - h), 2), round(100 * (c + h), 2)


out = {}
series = _series(root)
obs = sum(len(v) for v in series.values())
days = sorted({d for v in series.values() for d, _ in v})
out['book'] = {'contracts': len(series), 'observations': obs,
               'first_day': str(days[0]), 'last_day': str(days[-1])}

# Regime split, exactly as the script computes it.
rs = measure_regime_split(root)
out['regime_split'] = rs
pre, post = Decimal(rs['pre_krx_mean_mr']), Decimal(rs['post_krx_mean_mr'])
out['regime_split']['ratio_of_means_pct'] = float((post / pre - 1) * 100)

# F1: the same book, decomposed.
rates = Counter()
im13 = im17 = pre_dated = grid_tot = Decimal(0)
n = 0
for ticker, window in _windows(root, 10):
    day, price = window[0]
    notional = VN30F_MULTIPLIER * price
    r = vsd_initial_margin(day)
    rates[str(r)] += 1
    im13 += Decimal('0.13') * notional
    im17 += Decimal('0.17') * notional
    pre_dated += r * notional
    g = scenario_grid_requirement(
        as_of=_POST_KRX_AS_OF, account_id='f1', positions={ticker: _Held(1)},
        parameters=_POST_KRX_PARAMS, underlying_closes={'VN30': price},
        minimum_margin_factor=_POST_KRX_MF)
    grid_tot += g.amount
    n += 1
out['f1'] = {
    'positions': n,
    'dated_rate_mix': dict(rates),
    'mean_im_at_13pct': str((im13 / n).quantize(Decimal('1'))),
    'mean_im_at_17pct': str((im17 / n).quantize(Decimal('1'))),
    'step_13_to_17_pct': float((im17 / im13 - 1) * 100),
    'mean_pre_dated': str((pre_dated / n).quantize(Decimal('1'))),
    'mean_grid': str((grid_tot / n).quantize(Decimal('1'))),
    'grid_vs_flat17_pct': float((grid_tot / im17 - 1) * 100),
    'grid_vs_flat13_pct': float((grid_tot / im13 - 1) * 100),
}

# Margin-call incidence, exactly as reproduce_measurements.measure_exchange_margin.
for h in (5, 10, 20):
    r = measure_account_margin_incidence(
        root, holding_days=h, funding_multiple=BEST_JOINT_FIT, settle_daily=True)
    out[f'hold_{h}'] = {
        'entries': r.entries, 'called': r.called, 'forced': r.forced,
        'call_pct': round(100 * r.called / r.entries, 2),
        'forced_pct': round(100 * r.forced / r.entries, 2),
        'call_ci95': wilson(r.called, r.entries),
        'forced_ci95': wilson(r.forced, r.entries),
        'contracts': r.contracts}
print(json.dumps(out, indent=1))
