from datetime import date
from decimal import Decimal

import pytest

from care_pathway.claim_assignment import Claim
from care_pathway.episode_builder import EpisodeIndexEvent, build_episodes


def make_event(claim_id="index-1", service_date=date(2026, 3, 10), admission=date(2026, 3, 10), discharge=date(2026, 3, 13)):
    claim = Claim(
        claim_id=claim_id,
        patient_id="patient-1",
        service_date=service_date,
        diagnosis_codes=frozenset({"M17.11"}),
        provider_id="provider-1",
        paid_amount=Decimal("12000.00"),
        procedure_code="KNEE-REPLACEMENT",
    )
    return EpisodeIndexEvent(claim, admission, discharge)


def test_builds_episode_from_index_event():
    episodes = build_episodes([make_event()])
    assert len(episodes) == 1
    episode = episodes[0]
    assert episode.episode_id == "episode:index-1"
    assert episode.patient_id == "patient-1"
    assert episode.window.index_date == date(2026, 3, 10)
    assert episode.window.preoperative_start == date(2026, 2, 8)
    assert episode.window.postacute_end == date(2026, 6, 11)
    assert episode.index_procedure_code == "KNEE-REPLACEMENT"


def test_builds_multiple_episodes():
    episodes = build_episodes([
        make_event("index-1"),
        make_event("index-2", service_date=date(2026, 4, 10), admission=date(2026, 4, 10), discharge=date(2026, 4, 12)),
    ])
    assert [episode.episode_id for episode in episodes] == [
        "episode:index-1", "episode:index-2"
    ]


def test_rejects_index_event_without_procedure_code():
    claim = Claim("c1", "patient-1", date(2026, 3, 10), frozenset({"M17.11"}), "provider-1", Decimal("100"), None)
    with pytest.raises(ValueError, match="procedure code"):
        EpisodeIndexEvent(claim, date(2026, 3, 10), date(2026, 3, 13))


def test_rejects_admission_after_index_date():
    with pytest.raises(ValueError, match="Admission cannot be after"):
        make_event(admission=date(2026, 3, 11))


def test_rejects_discharge_before_index_date():
    with pytest.raises(ValueError, match="Index date cannot be after discharge"):
        make_event(discharge=date(2026, 3, 9))


def test_rejects_duplicate_index_claim_ids():
    with pytest.raises(ValueError, match="must be unique"):
        build_episodes([make_event("same"), make_event("same")])


def test_rejects_negative_window_length():
    with pytest.raises(ValueError, match="non-negative integer"):
        build_episodes([make_event()], preoperative_days=-1)
from datetime import date
from decimal import Decimal

from care_pathway.claim_assignment import Claim, assign_claims
from care_pathway.episode_builder import EpisodeIndexEvent, build_episodes


def test_built_episode_accepts_related_preoperative_and_postacute_claims():
    index_claim = Claim(
        "index-claim", "patient-1", date(2026, 3, 10),
        frozenset({"M17.11"}), "provider-1", Decimal("12000"),
        "KNEE-REPLACEMENT"
    )
    episode = build_episodes([
        EpisodeIndexEvent(index_claim, date(2026, 3, 10), date(2026, 3, 13))
    ])[0]
    claims = [
        Claim("preop", "patient-1", date(2026, 2, 20), frozenset({"M17.11"}), "provider-1", Decimal("150")),
        index_claim,
        Claim("rehab", "patient-1", date(2026, 4, 2), frozenset({"M17.11"}), "provider-1", Decimal("1200")),
    ]
    assignments = assign_claims(claims, [episode])
    assert {item.claim_id: item.cost_bucket for item in assignments} == {
        "preop": "preoperative",
        "index-claim": "hospital",
        "rehab": "postacute",
    }
