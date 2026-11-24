"""Margin-ladder properties: monotone in account health, exact at thresholds.

Two ladders, two public graders, deliberately not merged by the engine:

* **derivatives** -- ``deposit.margin_status(required, assets, terms)`` grades
  ``utilisation = MR / assets`` against the broker's warning / call / forced
  rungs. A rung is reached **at** its level (``>=``).
* **equity margin lending** -- ``margin_lending.account_status(ratio, policy)``
  grades ``AB / EB`` against the binding call and force-sell levels. A level is
  breached only **below** it: QD 87 Dieu 5.2 says "not lower than", so a ratio
  exactly on a level complies.

"Monotone" means: improving health -- more assets, less requirement, a higher
equity ratio -- never moves an account to a *more* severe status. The boundary
properties pin both sides of every threshold exactly, using Decimal arithmetic
so that "exactly at the level" is exact.
"""

from decimal import Decimal

from hypothesis import assume, example, given, settings
from hypothesis import strategies as st

from plutus.market.broker import BrokerTerms
from plutus.market.session.deposit import margin_status
from plutus.market.session.margin_lending import (
    BrokerMarginTerms, DayCount, ForcedSalePrice, LiquidationOrder,
    MarginAccountStatus, ProceedsComponent, account_status, binding_policy,
)
from plutus.market.session.types import MarginStatus

D = Decimal

DERIV_SEVERITY = {MarginStatus.OK: 0, MarginStatus.WARNING: 1,
                  MarginStatus.CALL: 2, MarginStatus.FORCED: 3}
EQUITY_SEVERITY = {MarginAccountStatus.OK: 0, MarginAccountStatus.CALL: 1,
                   MarginAccountStatus.FORCE_SELL: 2}

#: Two-decimal levels and money, so products and quotients stay exact. Capped at
#: 1.00: a forced-close rung above the QD 26 Dieu 13 breach is refused at
#: construction (BrokerTermLooserThanLaw, test_broker_cannot_relax.py), so a
#: legal ladder lives in (0, 1].
LEVELS = st.integers(min_value=1, max_value=100).map(lambda n: D(n) / 100)
MONEY = st.integers(min_value=1, max_value=10**9).map(D)


@st.composite
def broker_ladders(draw):
    """A legal ``BrokerTerms`` ladder: 0 < warning <= call <= forced."""
    w, c, f = sorted(draw(st.lists(LEVELS, min_size=3, max_size=3)))
    return BrokerTerms(warning_utilisation=w, margin_call_utilisation=c,
                       forced_close_utilisation=f)


# --------------------------------------------------------------------------
# Derivatives
# --------------------------------------------------------------------------

@settings(max_examples=300, deadline=None)
@given(terms=broker_ladders(), required=MONEY,
       assets=st.lists(MONEY, min_size=2, max_size=2))
def test_derivatives_status_is_monotone_in_assets(terms, required, assets):
    lo, hi = sorted(assets)
    worse = DERIV_SEVERITY[margin_status(required, lo, terms)]
    better = DERIV_SEVERITY[margin_status(required, hi, terms)]
    assert better <= worse


@settings(max_examples=300, deadline=None)
@given(terms=broker_ladders(), assets=MONEY,
       required=st.lists(MONEY, min_size=2, max_size=2))
def test_derivatives_status_is_monotone_in_requirement(terms, assets,
                                                       required):
    lo, hi = sorted(required)
    assert (DERIV_SEVERITY[margin_status(lo, assets, terms)]
            <= DERIV_SEVERITY[margin_status(hi, assets, terms)])


def expected_rung(terms, utilisation):
    if utilisation >= terms.forced_close_utilisation:
        return MarginStatus.FORCED
    if utilisation >= terms.margin_call_utilisation:
        return MarginStatus.CALL
    if utilisation >= terms.warning_utilisation:
        return MarginStatus.WARNING
    return MarginStatus.OK


@settings(max_examples=300, deadline=None)
@given(terms=broker_ladders(), assets=MONEY,
       rung=st.sampled_from(['warning_utilisation', 'margin_call_utilisation',
                             'forced_close_utilisation']))
@example(terms=BrokerTerms(), assets=D('100'),
         rung='forced_close_utilisation')
@example(terms=BrokerTerms(), assets=D('100'), rung='margin_call_utilisation')
@example(terms=BrokerTerms(), assets=D('100'), rung='warning_utilisation')
def test_derivatives_thresholds_are_exact(terms, assets, rung):
    """``MR / assets`` exactly on a level reaches that rung; one VND of
    requirement less does not reach it."""
    level = getattr(terms, rung)
    at_level = assets * level            # exact: MR / assets == level
    status = margin_status(at_level, assets, terms)
    assert status is expected_rung(terms, level)
    assert DERIV_SEVERITY[status] >= DERIV_SEVERITY[{
        'warning_utilisation': MarginStatus.WARNING,
        'margin_call_utilisation': MarginStatus.CALL,
        'forced_close_utilisation': MarginStatus.FORCED}[rung]]

    just_below = at_level - D('1')
    assume(just_below > 0)
    below = margin_status(just_below, assets, terms)
    assert below is expected_rung(terms, just_below / assets)
    assert DERIV_SEVERITY[below] <= DERIV_SEVERITY[status]


def test_derivatives_degenerate_cases():
    """No requirement is OK whatever the assets; a requirement against no
    assets is FORCED, not an undefined ratio."""
    terms = BrokerTerms()
    assert margin_status(D('0'), D('0'), terms) is MarginStatus.OK
    assert margin_status(D('1'), D('0'), terms) is MarginStatus.FORCED


# --------------------------------------------------------------------------
# Equity margin lending
# --------------------------------------------------------------------------

REQUIRED = dict(
    forced_sale_price=ForcedSalePrice.FLOOR,
    day_count=DayCount.ACT_365,
    liquidation_order=LiquidationOrder.LARGEST_POSITION_FIRST,
    proceeds_application_order=tuple(ProceedsComponent),
)

#: Legal ratios: at or above the QD 87 Dieu 5.2 floor of 0.30.
LEGAL_LEVELS = st.integers(min_value=30, max_value=95).map(lambda n: D(n) / 100)
RATIOS = st.integers(min_value=0, max_value=300).map(lambda n: D(n) / 100)


@st.composite
def equity_policies(draw):
    liq, maint = sorted(draw(st.lists(LEGAL_LEVELS, min_size=2, max_size=2)))
    terms = BrokerMarginTerms(maintenance_margin_ratio=maint,
                              liquidation_margin_ratio=liq, **REQUIRED)
    return binding_policy(terms)


@settings(max_examples=300, deadline=None)
@given(policy=equity_policies(), ratios=st.lists(RATIOS, min_size=2,
                                                 max_size=2))
def test_equity_status_is_monotone_in_ratio(policy, ratios):
    lo, hi = sorted(ratios)
    assert (EQUITY_SEVERITY[account_status(hi, policy)]
            <= EQUITY_SEVERITY[account_status(lo, policy)])


@settings(max_examples=300, deadline=None)
@given(policy=equity_policies())
def test_equity_thresholds_are_exact(policy):
    """On a level complies with it; one basis point below breaches it."""
    bp = D('0.0001')
    force, call = policy.force_sell_level, policy.call_level

    assert account_status(force - bp, policy) is MarginAccountStatus.FORCE_SELL
    assert account_status(force, policy) is not MarginAccountStatus.FORCE_SELL
    assert account_status(call, policy) is MarginAccountStatus.OK
    if call > force:
        assert account_status(call - bp, policy) is MarginAccountStatus.CALL
        assert account_status(force, policy) is MarginAccountStatus.CALL
    else:
        # Collapsed levels: no CALL band at all.
        assert account_status(call - bp, policy) \
            is MarginAccountStatus.FORCE_SELL


@settings(max_examples=200, deadline=None)
@given(policy=equity_policies(), debt=MONEY)
def test_equity_no_assets_with_debt_is_force_sell(policy, debt):
    assert account_status(None, policy, debt=debt) \
        is MarginAccountStatus.FORCE_SELL
    assert account_status(None, policy) is MarginAccountStatus.OK
