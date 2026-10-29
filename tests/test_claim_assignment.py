from datetime import date, timedelta
from decimal import Decimal

import pytest

from care_pathway.claim_assignment import (
    Claim,
    EpisodeDefinition,
    assign_claims,
)
from care_pathway.episode_windows import EpisodeWindow


def make_episode(
    episode_id="episode-1",
    index_date=date(2026, 3, 10),
    admission_date=date(2026, 3, 10),
    discharge_date=None,
    diagnosis_codes=frozenset({"M17.11"}),
    providers=frozenset(),
    index_code="KNEE-REPLACEMENT",
):
    if discharge_date is None:
        discharge_date = index_date + timedelta(days=3)

    return EpisodeDefinition(
        episode_id=episode_id,
        patient_id="patient-1",
        window=EpisodeWindow(
            index_date=index_date,
            admission_date=admission_date,
            discharge_date=discharge_date,
        ),
        diagnosis_codes=diagnosis_codes,
        relevant_provider_ids=providers,
        index_procedure_code=index_code,
    )


def make_claim(
    claim_id="claim-1",
    service_date=date(2026, 2, 20),
    patient_id="patient-1",
    diagnosis_codes=frozenset({"M17.11"}),
    provider_id="provider-1",
    procedure_code=None,
):
    return Claim(
        claim_id=claim_id,
        patient_id=patient_id,
        service_date=service_date,
        diagnosis_codes=diagnosis_codes,
        provider_id=provider_id,
        paid_amount=Decimal("125.00"),
        procedure_code=procedure_code,
    )


def test_assigns_preoperative_claim():
    result = assign_claims([make_claim()], [make_episode()])
    assert len(result) == 1
    assert result[0].episode_id == "episode-1"
    assert result[0].cost_bucket == "preoperative"


def test_assigns_hospital_claim():
    claim = make_claim(service_date=date(2026, 3, 12))
    result = assign_claims([claim], [make_episode()])
    assert result[0].cost_bucket == "hospital"


def test_assigns_postacute_claim():
    claim = make_claim(service_date=date(2026, 4, 2))
    result = assign_claims([claim], [make_episode()])
    assert result[0].cost_bucket == "postacute"


def test_excludes_different_patient():
    claim = make_claim(patient_id="patient-2")
    assert assign_claims([claim], [make_episode()]) == []


def test_excludes_unrelated_diagnosis():
    claim = make_claim(diagnosis_codes=frozenset({"J18.9"}))
    assert assign_claims([claim], [make_episode()]) == []


def test_excludes_claim_outside_window():
    claim = make_claim(service_date=date(2026, 2, 7))
    assert assign_claims([claim], [make_episode()]) == []


def test_enforces_provider_restriction_when_configured():
    episode = make_episode(providers=frozenset({"provider-2"}))
    claim = make_claim(provider_id="provider-1")
    assert assign_claims([claim], [episode]) == []


def test_accepts_relevant_provider():
    episode = make_episode(providers=frozenset({"provider-1"}))
    claim = make_claim(provider_id="provider-1")
    assert len(assign_claims([claim], [episode])) == 1


def test_matching_index_procedure_goes_to_its_episode():
    first = make_episode(
        episode_id="first",
        index_date=date(2026, 3, 10),
    )
    second = make_episode(
        episode_id="second",
        index_date=date(2026, 3, 20),
    )
    claim = make_claim(
        service_date=date(2026, 3, 20),
        claim_id="index-claim",
        procedure_code="KNEE-REPLACEMENT",
    )

    result = assign_claims([claim], [first, second])
    assert len(result) == 1
    assert result[0].episode_id == "second"


def test_overlapping_claim_is_assigned_only_once_to_nearest_index():
    first = make_episode(
        episode_id="first",
        index_date=date(2026, 3, 10),
    )
    second = make_episode(
        episode_id="second",
        index_date=date(2026, 3, 20),
    )
    claim = make_claim(
        service_date=date(2026, 3, 18),
        procedure_code=None,
    )

    result = assign_claims([claim], [first, second])
    assert len(result) == 1
    assert result[0].episode_id == "second"


def test_tie_goes_to_more_recent_index_date():
    first = make_episode(
        episode_id="first",
        index_date=date(2026, 3, 10),
    )
    second = make_episode(
        episode_id="second",
        index_date=date(2026, 3, 20),
    )
    claim = make_claim(service_date=date(2026, 3, 15))

    result = assign_claims([claim], [first, second])
    assert result[0].episode_id == "second"


def test_rejects_duplicate_claim_ids():
    claim = make_claim()
    with pytest.raises(ValueError, match="Claim IDs must be unique"):
        assign_claims([claim, claim], [make_episode()])


def test_rejects_duplicate_episode_ids():
    claim = make_claim()
    with pytest.raises(ValueError, match="Episode IDs must be unique"):
        assign_claims([claim], [make_episode(), make_episode()])
