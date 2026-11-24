"""The rule tables are a partition of the timeline, per key -- checked, not trusted.

``RuleInterval`` is half-open, and the rulebook's whole claim is that every
instant resolves to **exactly one** row. Two failure shapes break that claim
silently:

* an **overlap** -- two rows for one key both cover a date. ``_pick()`` used
  to return the later one, so a transcription slip (a successor row typed
  with a start date one day early) changed the answer at one date and
  reported nothing;
* a **gap** -- no row covers a date between two rows of one key. The resolver
  then falls through to a wildcard key or answers UNKNOWN with no row behind
  it, so "nobody wrote this down" and "a source says it is unknown" become
  indistinguishable.

:func:`validate_rule_tables` checks every ``_*_table()`` and every key. The
tests below pin its behaviour on synthetic tables, then pin what it finds on
the real ones -- including the *edge* spans the owner still has to decide on
(:data:`OPEN_EDGES`), so a new one cannot appear unnoticed and a closed one
must be removed from the list.
"""

from datetime import date, datetime, timedelta

import pytest

from plutus.market.session.rulebook import (
    COVERAGE_END, COVERAGE_START, OverlappingRuleRows, RuleInterval, RuleName,
    RuleStatus, Rulebook, RuleTableFinding, _build_tables, _pick,
    validate_rule_tables,
)
from plutus.market.session.types import TradingMethod, Venue


def row(start, end=None, value='v', status=RuleStatus.KNOWN):
    return RuleInterval(value=value, effective_from=start, effective_to=end,
                        status=status)


def kinds(report):
    return sorted(f.kind for f in report.findings)


# --------------------------------------------------------------------------
# _pick() refuses an overlap instead of choosing
# --------------------------------------------------------------------------

def test_pick_raises_on_overlapping_rows():
    """Two rows covering one date is a data defect, not a correction.

    Returning the later row made an overlap behave like a silent amendment;
    raising makes it a loud one at the first resolution that touches it.
    """
    series = (row(date(2020, 1, 1), date(2021, 1, 2), value='old'),
              row(date(2021, 1, 1), value='new'))
    with pytest.raises(OverlappingRuleRows) as caught:
        _pick(series, date(2021, 1, 1))
    assert 'old' in str(caught.value) and 'new' in str(caught.value)


def test_pick_is_unaffected_outside_the_overlap():
    series = (row(date(2020, 1, 1), date(2021, 1, 2), value='old'),
              row(date(2021, 1, 1), value='new'))
    assert _pick(series, date(2020, 6, 1)).value == 'old'
    assert _pick(series, date(2021, 1, 2)).value == 'new'


def test_pick_on_abutting_rows_belongs_to_exactly_one():
    """The half-open boundary: the cutover date is the successor's."""
    series = (row(date(2020, 1, 1), date(2021, 1, 4), value='10'),
              row(date(2021, 1, 4), value='100'))
    assert _pick(series, date(2021, 1, 3)).value == '10'
    assert _pick(series, date(2021, 1, 4)).value == '100'


def test_pick_returns_none_in_a_gap():
    series = (row(date(2020, 1, 1), date(2020, 6, 1)),
              row(date(2020, 7, 1)))
    assert _pick(series, date(2020, 6, 15)) is None


# --------------------------------------------------------------------------
# The validator, on synthetic tables
# --------------------------------------------------------------------------

def synthetic(**by_key):
    """One rule's table, wrapped as a full table set."""
    return {RuleName.TICK_SIZE: {(k,): v for k, v in by_key.items()}}


def test_a_clean_partition_has_no_findings():
    report = validate_rule_tables(synthetic(a=(
        row(date(2019, 1, 1), date(2021, 1, 4)), row(date(2021, 1, 4)))))
    assert report.findings == ()
    assert (report.tables, report.keys, report.rows) == (1, 1, 2)


def test_an_overlap_is_found_with_both_rows():
    first = row(date(2019, 1, 1), date(2021, 1, 5), value='old')
    second = row(date(2021, 1, 4), value='new')
    report = validate_rule_tables(synthetic(a=(first, second)))
    assert kinds(report) == ['overlap']
    finding = report.findings[0]
    assert finding.rows == (first, second)
    assert finding.span == (date(2021, 1, 4), date(2021, 1, 5))


def test_an_overlap_is_found_even_when_rows_are_out_of_order():
    report = validate_rule_tables(synthetic(a=(
        row(date(2021, 1, 4)), row(date(2019, 1, 1), date(2021, 1, 5)))))
    assert kinds(report) == ['overlap']


def test_an_interior_gap_is_found():
    report = validate_rule_tables(synthetic(a=(
        row(date(2019, 1, 1), date(2021, 1, 4)), row(date(2021, 1, 5)))))
    assert kinds(report) == ['gap']
    assert report.findings[0].span == (date(2021, 1, 4), date(2021, 1, 5))


def test_a_gap_filled_by_an_explicit_unknown_row_is_not_a_gap():
    """The one sanctioned way to say "nobody knows": as a row."""
    report = validate_rule_tables(synthetic(a=(
        row(date(2019, 1, 1), date(2021, 1, 4)),
        row(date(2021, 1, 4), date(2022, 1, 1), status=RuleStatus.UNKNOWN),
        row(date(2022, 1, 1)))))
    assert report.findings == ()


def test_an_empty_interval_is_found():
    report = validate_rule_tables(synthetic(a=(
        row(date(2021, 1, 4), date(2021, 1, 4)),)))
    assert 'empty' in kinds(report)


def test_a_key_starting_inside_coverage_is_an_implicit_edge():
    report = validate_rule_tables(synthetic(a=(row(date(2022, 3, 31)),)))
    assert kinds(report) == ['edge']
    assert report.findings[0].span == (COVERAGE_START, date(2022, 3, 31))


def test_a_key_ending_inside_coverage_is_an_implicit_edge():
    report = validate_rule_tables(synthetic(a=(
        row(date(2019, 1, 1), date(2022, 1, 1)),)))
    assert kinds(report) == ['edge']
    assert report.findings[0].span == (date(2022, 1, 1),
                                       COVERAGE_END + timedelta(days=1))


def test_a_gap_that_a_wildcard_fills_with_a_known_row_is_flagged_as_fallthrough():
    """The dangerous gap: the resolver answers, from a less specific row."""
    tables = {RuleName.TICK_SIZE: {
        ('X', 'ETF'): (row(date(2022, 3, 31), value='0.001'),),
        ('X', None): (row(date(2019, 1, 1), value='0.1'),),
    }}
    report = validate_rule_tables(tables)
    assert kinds(report) == ['edge']
    assert report.findings[0].falls_through_to == (('X', None),)


# --------------------------------------------------------------------------
# The real tables
# --------------------------------------------------------------------------

#: Spans inside COVERAGE_START..COVERAGE_END where a key has **no row at all**,
#: neither a value nor an explicit ``_unsourced`` one. Every one resolves to
#: UNKNOWN today (none falls through to a wildcard value -- pinned below), so
#: none is a wrong number; each is an *implicit* absence the owner has to
#: either source or turn into an explicit row. Listed, not fixed: adding rows
#: changes the row counts FEATURES.md and the paper quote.
OPEN_EDGES = {
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.HSX, 'first_trading_day'),
     COVERAGE_START, date(2021, 7, 5)),
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.HSX, 'resumption'),
     COVERAGE_START, date(2021, 7, 5)),
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.HSX, 'convertible_bond_ex_rights'),
     COVERAGE_START, date(2022, 3, 31)),
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.HNX, 'first_trading_day'),
     COVERAGE_START, date(2022, 3, 31)),
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.HNX, 'resumption'),
     COVERAGE_START, date(2022, 3, 31)),
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.UPCOM, 'first_trading_day'),
     COVERAGE_START, date(2022, 11, 16)),
    (RuleName.WIDENED_TRADING_LIMIT, (Venue.UPCOM, 'illiquidity'),
     COVERAGE_START, date(2022, 11, 16)),
    (RuleName.TICK_SIZE,
     (Venue.HNX, 'ETF_CW', TradingMethod.ORDER_MATCHING),
     COVERAGE_START, date(2022, 3, 31)),
    (RuleName.TICK_SIZE, (Venue.HNX, None, TradingMethod.PUT_THROUGH),
     COVERAGE_START, date(2022, 3, 31)),
    (RuleName.TICK_SIZE, (Venue.UPCOM, None, TradingMethod.PUT_THROUGH),
     COVERAGE_START, date(2022, 11, 16)),
    # A charge that ends / starts: the 2022-01-01 basis switch from a
    # per-day position fee to a per-fill clearing fee. Deliberate (see the
    # row's note); "not levied" is currently expressed as no row.
    (RuleName.CHARGE, ('vsdc_derivatives_position_management',),
     date(2022, 1, 1), date(2026, 8, 26)),
    (RuleName.CHARGE, ('vsdc_derivatives_clearing',),
     COVERAGE_START, date(2022, 1, 1)),
}

REAL = validate_rule_tables()


def test_the_real_tables_are_counted():
    """The census quoted in the camera-ready: tables, keys, rows."""
    assert (REAL.tables, REAL.keys, REAL.rows) == (12, 93, 114)


def test_the_real_tables_have_no_overlap():
    assert [f for f in REAL.findings if f.kind == 'overlap'] == []


def test_the_real_tables_have_no_interior_gap():
    assert [f for f in REAL.findings if f.kind == 'gap'] == []


def test_the_real_tables_have_no_empty_interval():
    assert [f for f in REAL.findings if f.kind == 'empty'] == []


def test_no_real_edge_falls_through_to_a_wildcard_value():
    """Every implicit absence answers UNKNOWN, never a less specific value."""
    assert [f for f in REAL.findings if f.falls_through_to] == []


def test_the_real_open_edges_are_exactly_the_listed_ones():
    found = {(f.rule, f.key, f.span[0], f.span[1])
             for f in REAL.findings if f.kind == 'edge'}
    assert found == OPEN_EDGES


@pytest.mark.parametrize('rule,key,start,end', sorted(
    OPEN_EDGES, key=lambda e: (e[0].value, str(e[1]))))
def test_every_open_edge_resolves_unknown(rule, key, start, end):
    """What makes the open edges safe today: the resolver says it does not know."""
    book = Rulebook()
    for on in (start, end - timedelta(days=1)):
        resolution = book._resolve(rule, key, datetime(on.year, on.month,
                                                       on.day, 10))
        assert resolution.status is RuleStatus.UNKNOWN


def test_the_shipped_rulebook_resolves_every_key_on_every_boundary():
    """``_pick`` now raises on overlap, so resolving every boundary of every
    real key is a full overlap check through the production path."""
    book = Rulebook()
    for rule, table in _build_tables('vn-2020-2026').items():
        for key, series in table.items():
            for r in series:
                for on in (r.effective_from, r.effective_to):
                    if on is None:
                        continue
                    book._resolve(rule, key, datetime(on.year, on.month,
                                                      on.day, 10))
