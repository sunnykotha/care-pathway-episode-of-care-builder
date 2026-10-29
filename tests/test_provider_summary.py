from decimal import Decimal

import pytest

from care_pathway.cost_analysis import (
    BenchmarkPrice,
    EpisodeCostItem,
    aggregate_episode_costs,
    detect_cost_outliers,
)
from care_pathway.episode_details import (
    ComplicationEvent,
    EpisodeAttribution,
    apply_episode_details,
)
from care_pathway.provider_summary import summarize_by_provider


def make_reports():
    items = [
        EpisodeCostItem("e1", "knee", "c1", Decimal("100"), "surgery"),
        EpisodeCostItem("e2", "knee", "c2", Decimal("600"), "facility"),
        EpisodeCostItem("e3", "knee", "c3", Decimal("200"), "rehab"),
    ]
    reports = aggregate_episode_costs(
        items, [BenchmarkPrice("knee", Decimal("500"))]
    )
    reports = apply_episode_details(
        reports,
        attributions=[
            EpisodeAttribution("e1", "provider-a", "facility-1"),
            EpisodeAttribution("e2", "provider-a", "facility-2"),
        ],
        complications=[
            ComplicationEvent("e2", "c2", "infection", "Infection readmission"),
        ],
    )
    return detect_cost_outliers(reports)


def test_summarizes_episode_counts_and_costs_by_provider():
    summaries = summarize_by_provider(make_reports())
    by_provider = {summary.provider_id: summary for summary in summaries}

    provider = by_provider["provider-a"]
    assert provider.episode_count == 2
    assert provider.total_paid == Decimal("700.00")
    assert provider.total_benchmark == Decimal("1000.00")


def test_counts_above_target_episodes():
    summaries = summarize_by_provider(make_reports())
    provider = next(s for s in summaries if s.provider_id == "provider-a")

    assert provider.episodes_above_target == 1


def test_counts_complication_episodes():
    summaries = summarize_by_provider(make_reports())
    provider = next(s for s in summaries if s.provider_id == "provider-a")

    assert provider.complication_episodes == 1


def test_unassigned_episodes_have_none_provider_id():
    summaries = summarize_by_provider(make_reports())
    unassigned = next(s for s in summaries if s.provider_id is None)

    assert unassigned.episode_count == 1
    assert unassigned.total_paid == Decimal("200.00")


def test_unassigned_provider_is_sorted_after_named_providers():
    summaries = summarize_by_provider(make_reports())

    assert summaries[-1].provider_id is None


def test_empty_input_returns_empty_list():
    assert summarize_by_provider([]) == []


def test_duplicate_episode_reports_are_rejected():
    reports = make_reports()

    with pytest.raises(ValueError, match="unique episode IDs"):
        summarize_by_provider([reports[0], reports[0]])


def test_provider_summaries_do_not_mutate_input_reports():
    reports = make_reports()
    before = list(reports)

    summarize_by_provider(reports)

    assert reports == before


def test_outlier_count_is_reported():
    reports = make_reports()
    summaries = summarize_by_provider(reports)

    expected = sum(
        1 for report in reports
        if report.responsible_provider_id == "provider-a"
        and report.is_outlier
    )
    provider = next(s for s in summaries if s.provider_id == "provider-a")

    assert provider.outlier_episodes == expected
