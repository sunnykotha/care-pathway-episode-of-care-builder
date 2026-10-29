from decimal import Decimal

import pytest

from care_pathway.cost_analysis import (
    BenchmarkPrice,
    EpisodeCostItem,
    aggregate_episode_costs,
)
from care_pathway.episode_details import (
    ComplicationEvent,
    EpisodeAttribution,
    apply_episode_details,
)


def reports():
    items = [
        EpisodeCostItem(
            "e1", "knee", "c1", Decimal("100.00"), "surgery"
        ),
        EpisodeCostItem(
            "e2", "knee", "c2", Decimal("200.00"), "facility"
        ),
    ]
    benchmarks = [BenchmarkPrice("knee", Decimal("500.00"))]
    return aggregate_episode_costs(items, benchmarks)


def test_attributes_episode_to_responsible_provider_and_facility():
    result = apply_episode_details(
        reports(),
        [
            EpisodeAttribution("e1", "provider-1", "facility-1"),
        ],
    )

    first = next(report for report in result if report.episode_id == "e1")
    second = next(report for report in result if report.episode_id == "e2")

    assert first.responsible_provider_id == "provider-1"
    assert first.responsible_facility_id == "facility-1"
    assert second.responsible_provider_id is None
    assert second.responsible_facility_id is None


def test_complication_marks_episode_and_retains_claim_details():
    result = apply_episode_details(
        reports(),
        complications=[
            ComplicationEvent(
                "e1", "readmission-1", "infection", "Infection readmission"
            ),
        ],
    )

    first = next(report for report in result if report.episode_id == "e1")
    assert first.complications is True
    assert first.complication_claim_ids == ("readmission-1",)
    assert first.complication_descriptions == ("Infection readmission",)


def test_complication_events_are_ordered_by_claim_id():
    result = apply_episode_details(
        reports(),
        complications=[
            ComplicationEvent("e1", "c9", "infection", "Later event"),
            ComplicationEvent("e1", "c3", "infection", "Earlier event"),
        ],
    )

    first = next(report for report in result if report.episode_id == "e1")
    assert first.complication_claim_ids == ("c3", "c9")
    assert first.complication_descriptions == ("Earlier event", "Later event")


def test_episode_without_complication_remains_unflagged():
    result = apply_episode_details(reports())
    assert all(report.complications is False for report in result)
    assert all(report.complication_claim_ids == () for report in result)


def test_unknown_episode_attribution_is_rejected():
    with pytest.raises(ValueError, match="unknown episode"):
        apply_episode_details(
            reports(),
            [EpisodeAttribution("missing", "provider-1", "facility-1")],
        )


def test_duplicate_episode_attribution_is_rejected():
    with pytest.raises(ValueError, match="Duplicate attribution"):
        apply_episode_details(
            reports(),
            [
                EpisodeAttribution("e1", "provider-1", "facility-1"),
                EpisodeAttribution("e1", "provider-2", "facility-2"),
            ],
        )


def test_complication_for_unknown_episode_is_rejected():
    with pytest.raises(ValueError, match="unknown episode"):
        apply_episode_details(
            reports(),
            complications=[
                ComplicationEvent("missing", "c9", "infection", "Readmission"),
            ],
        )


def test_duplicate_complication_claim_within_episode_is_rejected():
    event = ComplicationEvent("e1", "c9", "infection", "Readmission")
    with pytest.raises(ValueError, match="Duplicate complication claim"):
        apply_episode_details(reports(), complications=[event, event])


@pytest.mark.parametrize(
    "values",
    [
        ("", "provider-1", "facility-1"),
        ("e1", "", "facility-1"),
        ("e1", "provider-1", ""),
    ],
)
def test_invalid_attribution_values_are_rejected(values):
    with pytest.raises(ValueError):
        EpisodeAttribution(*values)


@pytest.mark.parametrize(
    "values",
    [
        ("", "c1", "infection", "Readmission"),
        ("e1", "", "infection", "Readmission"),
        ("e1", "c1", "", "Readmission"),
        ("e1", "c1", "infection", ""),
    ],
)
def test_invalid_complication_values_are_rejected(values):
    with pytest.raises(ValueError):
        ComplicationEvent(*values)
