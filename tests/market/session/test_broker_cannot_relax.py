"""A broker term may tighten an exchange / depository rule, never relax it.

The rulebook's claim is that gazetted rules are the floor every firm trades
above. This file records, as tests, where the code enforces that and where it
does not (T8.1, RIVF'26 camera-ready):

* **Equity margin lending -- enforced.** ``BrokerMarginTerms`` refuses any term
  looser than the QD 87 floors at construction (``BrokerTermLooserThanLaw``),
  and ``binding_policy`` re-grades against a later regulation by taking the
  stricter layer.
* **Derivatives margin -- NOT enforced, two ways.** ``BrokerProfile.margin_buffer``
  is added to the VSDC initial-margin rate with no sign check, so a negative
  buffer margins a contract *below* VSDC's ratio; and
  ``BrokerTerms.forced_close_utilisation`` has no upper bound, so a value above
  1.00 leaves an account whose assets are below the margin requirement -- the
  whole QD 26 Dieu 13 breach -- graded CALL or WARNING instead of FORCED.

The two NOT-enforced cases are ``xfail(strict=True)``: they fail today and
show the relaxation, and they will turn the suite red (XPASS) the day a guard
lands, so the marker has to be removed together with the fix. Behaviour is
deliberately unchanged here; the decision is the owner's.
"""

from decimal import Decimal

import pytest

from plutus.market.broker import BrokerTerms
from plutus.market.session.deposit import margin_status
from plutus.market.session.margin_lending import (
    QD_87_2017, BrokerMarginTerms, BrokerTermLooserThanLaw, DayCount,
    ForcedSalePrice, LiquidationOrder, MarginRegulation, ProceedsComponent,
    binding_policy,
)
from plutus.market.session.types import BrokerProfile, MarginStatus

D = Decimal

REQUIRED = dict(
    maintenance_margin_ratio=D('0.35'),
    liquidation_margin_ratio=D('0.32'),
    forced_sale_price=ForcedSalePrice.FLOOR,
    day_count=DayCount.ACT_365,
    liquidation_order=LiquidationOrder.LARGEST_POSITION_FIRST,
    proceeds_application_order=tuple(ProceedsComponent),
)


# --------------------------------------------------------------------------
# Equity margin lending: enforced
# --------------------------------------------------------------------------

@pytest.mark.parametrize('field,value', [
    ('maintenance_margin_ratio', D('0.29')),   # QD 87 Dieu 5.2 floor 0.30
    ('liquidation_margin_ratio', D('0.29')),
    ('initial_margin_ratio', D('0.49')),       # QD 87 Dieu 5.1 floor 0.50
    ('cure_business_days', 4),                 # QD 87 Dieu 7.1 ceiling 3
])
def test_an_equity_margin_term_looser_than_qd87_is_refused(field, value):
    with pytest.raises(BrokerTermLooserThanLaw):
        BrokerMarginTerms(**{**REQUIRED, field: value})


def test_binding_policy_never_loosens_when_the_floor_rises():
    """A firm validated under a 30 % floor is graded against a 35 % one."""
    terms = BrokerMarginTerms(**REQUIRED)
    raised = MarginRegulation(**{
        **{f: getattr(QD_87_2017, f)
           for f in QD_87_2017.__dataclass_fields__},
        'maintenance_margin_ratio_floor': D('0.36')})
    policy = binding_policy(terms, raised)
    assert policy.call_level == D('0.36')
    assert policy.force_sell_level == D('0.36')


# --------------------------------------------------------------------------
# Derivatives margin: NOT enforced
# --------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason=(
    'FINDING T8.1: BrokerProfile.margin_buffer has no sign check '
    '(types.py BrokerProfile, deposit.py account_margin_requirement and '
    'DerivativesAccount.reserve add it to the VSDC rate), so a negative '
    'buffer relaxes the depository initial-margin ratio.'))
def test_a_negative_margin_buffer_is_refused():
    with pytest.raises(ValueError):
        BrokerProfile(name='relaxing', margin_buffer=D('-0.05'))


@pytest.mark.xfail(strict=True, reason=(
    'FINDING T8.1: as above, through the session config path.'))
def test_a_negative_margin_buffer_in_config_is_refused():
    with pytest.raises(ValueError):
        BrokerProfile.from_config({'name': 'relaxing',
                                   'margin_buffer': -0.05})


@pytest.mark.xfail(strict=True, reason=(
    'FINDING T8.1: BrokerTerms.__post_init__ (market/broker.py) checks only '
    'that the ladder is non-decreasing, so forced_close_utilisation > 1.00 is '
    'accepted and deposit.margin_status grades assets < MR -- the QD 26 '
    'Dieu 13 breach -- as CALL instead of FORCED.'))
def test_a_broker_cannot_grade_a_dieu13_breach_below_forced():
    terms = BrokerTerms(forced_close_utilisation=D('1.50'))
    # assets 90 < required 100: VSDC's binary breach.
    assert margin_status(D('100'), D('90'), terms) is MarginStatus.FORCED


def test_at_the_default_ladder_a_dieu13_breach_is_forced():
    """The control: with the default top rung the regulated breach binds."""
    assert margin_status(D('100'), D('99.99'), BrokerTerms()) \
        is MarginStatus.FORCED
