"""FEL classifier -- every FillDecision lands on exactly one evidence level."""
from decimal import Decimal

import pytest

from plutus.market.session.evidence_level import (AssumptionKind,
                                                  FillEvidenceLevel,
                                                  assumption_kind,
                                                  fill_evidence_level)
from plutus.market.session.types import (DataField, FillDecision, FillEvidence,
                                         FillOutcome)


def _fill(evidence, confidence=Decimal("1")):
    return FillDecision.fill(quantity=100, price=Decimal("10"),
                             evidence=evidence, confidence=confidence)


def test_traded_through_is_proven():
    d = _fill(FillEvidence.TRADED_THROUGH)
    assert fill_evidence_level(d) is FillEvidenceLevel.PROVEN
    assert assumption_kind(d) is AssumptionKind.NONE


def test_auction_cross_is_proven():
    assert fill_evidence_level(_fill(FillEvidence.AUCTION_PRICE)) \
        is FillEvidenceLevel.PROVEN


def test_no_fill_is_proven():
    # A definite miss is settled by the data just as a definite fill is.
    d = FillDecision.no_fill("the market never reached the limit")
    assert fill_evidence_level(d) is FillEvidenceLevel.PROVEN
    assert assumption_kind(d) is AssumptionKind.NONE


def test_touched_is_assumed_touch():
    d = _fill(FillEvidence.TOUCHED_AT_LIMIT)
    assert fill_evidence_level(d) is FillEvidenceLevel.ASSUMED
    assert assumption_kind(d) is AssumptionKind.TOUCH


def test_modelled_is_assumed_modelled():
    d = _fill(FillEvidence.MODELLED, confidence=Decimal("0.6"))
    assert fill_evidence_level(d) is FillEvidenceLevel.ASSUMED
    assert assumption_kind(d) is AssumptionKind.MODELLED


def test_indeterminate_is_unevidenced():
    d = FillDecision.indeterminate("no volume to size against",
                                   missing=[DataField.VOLUME])
    assert fill_evidence_level(d) is FillEvidenceLevel.UNEVIDENCED
    assert assumption_kind(d) is AssumptionKind.NONE


def test_levels_are_ordered():
    assert FillEvidenceLevel.PROVEN > FillEvidenceLevel.ASSUMED
    assert FillEvidenceLevel.ASSUMED > FillEvidenceLevel.UNEVIDENCED


def test_every_outcome_maps_and_only_assumed_carries_a_kind():
    """Totality: each FillOutcome yields a level, and a non-NONE assumption kind
    appears only at the ASSUMED level."""
    samples = [
        _fill(FillEvidence.TRADED_THROUGH), _fill(FillEvidence.AUCTION_PRICE),
        _fill(FillEvidence.TOUCHED_AT_LIMIT), _fill(FillEvidence.MODELLED),
        FillDecision.no_fill("miss"),
        FillDecision.indeterminate("silent", missing=[DataField.BOOK]),
    ]
    seen_outcomes = set()
    for d in samples:
        level = fill_evidence_level(d)
        assert isinstance(level, FillEvidenceLevel)
        seen_outcomes.add(d.outcome)
        if assumption_kind(d) is not AssumptionKind.NONE:
            assert level is FillEvidenceLevel.ASSUMED
    assert seen_outcomes == set(FillOutcome)


# -- the caller-side reading: grading the events advance_to returns ---------

def _event(kind, evidence=None):
    from datetime import datetime

    from plutus.market.session.types import Event
    detail = {} if evidence is None else {"evidence": evidence}
    return Event(kind=kind, ts=datetime(2022, 11, 9, 15), seq=1,
                 quantity=100, price=Decimal("10"), detail=detail)


@pytest.mark.parametrize("evidence, level", [
    (FillEvidence.TRADED_THROUGH, FillEvidenceLevel.PROVEN),
    (FillEvidence.AUCTION_PRICE, FillEvidenceLevel.PROVEN),
    (FillEvidence.TOUCHED_AT_LIMIT, FillEvidenceLevel.ASSUMED),
    (FillEvidence.MODELLED, FillEvidenceLevel.ASSUMED),
])
def test_a_fill_event_is_graded_like_its_decision(evidence, level):
    from plutus.market.session.evidence_level import event_evidence_level
    from plutus.market.session.types import EventKind
    for kind in (EventKind.FILLED, EventKind.PARTIALLY_FILLED):
        assert event_evidence_level(_event(kind, evidence)) is level
        assert level is fill_evidence_level(_fill(evidence))


def test_an_indeterminate_event_is_unevidenced_and_other_kinds_are_not_graded():
    from plutus.market.session.evidence_level import event_evidence_level
    from plutus.market.session.types import EventKind
    assert (event_evidence_level(_event(EventKind.INDETERMINATE))
            is FillEvidenceLevel.UNEVIDENCED)
    for kind in (EventKind.ACCEPTED, EventKind.REJECTED, EventKind.CANCELLED):
        assert event_evidence_level(_event(kind)) is None
