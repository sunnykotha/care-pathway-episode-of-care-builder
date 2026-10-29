from decimal import Decimal

import pytest

from care_pathway.cost_analysis import (
    BenchmarkPrice,
    EpisodeCostItem,
    aggregate_episode_costs,
    detect_cost_outliers,
)


def item(episode_id, claim_id, amount, bucket, episode_type="knee"):
    return EpisodeCostItem(
        episode_id=episode_id,
        episode_type=episode_type,
        claim_id=claim_id,
        paid_amount=Decimal(amount),
        cost_bucket=bucket,
    )


def benchmark(target="1000.00"):
    return [BenchmarkPrice("knee", Decimal(target))]


def test_aggregates_costs_by_bucket_and_episode():
    items = [
        item("e1", "c1", "500.00", "surgery"),
        item("e1", "c2", "200.00", "facility"),
        item("e1", "c3", "150.00", "rehab"),
        item("e1", "c4", "300.00", "readmissions"),
    ]

    report = aggregate_episode_costs(items, benchmark())[0]

    assert report.bucket_totals["surgery"] == Decimal("500.00")
    assert report.bucket_totals["facility"] == Decimal("200.00")
    assert report.bucket_totals["rehab"] == Decimal("150.00")
    assert report.bucket_totals["readmissions"] == Decimal("300.00")
    assert report.total_paid == Decimal("1150.00")


def test_compares_total_with_bundled_target():
    items = [item("e1", "c1", "1200.00", "surgery")]
    report = aggregate_episode_costs(items, benchmark("1000.00"))[0]

    assert report.target_price == Decimal("1000.00")
    assert report.difference_from_target == Decimal("200.00")
    assert report.above_target is True


def test_cost_equal_to_target_is_not_above_target():
    items = [item("e1", "c1", "1000.00", "surgery")]
    report = aggregate_episode_costs(items, benchmark())[0]
    assert report.above_target is False


def test_aggregates_multiple_episodes():
    items = [
        item("e2", "c2", "200.00", "rehab"),
        item("e1", "c1", "100.00", "surgery"),
    ]

    reports = aggregate_episode_costs(items, benchmark())

    assert [r.episode_id for r in reports] == ["e1", "e2"]
    assert [r.total_paid for r in reports] == [
        Decimal("100.00"),
        Decimal("200.00"),
    ]


def test_missing_benchmark_is_rejected():
    items = [item("e1", "c1", "100.00", "surgery")]
    with pytest.raises(ValueError, match="Missing benchmark"):
        aggregate_episode_costs(items, [])


def test_duplicate_claim_within_episode_is_rejected():
    claim = item("e1", "c1", "100.00", "surgery")
    with pytest.raises(ValueError, match="Duplicate claim"):
        aggregate_episode_costs([claim, claim], benchmark())


def test_inconsistent_episode_type_is_rejected():
    items = [
        item("e1", "c1", "100.00", "surgery", "knee"),
        item("e1", "c2", "100.00", "rehab", "hip"),
    ]
    benchmarks = [
        BenchmarkPrice("knee", Decimal("1000")),
        BenchmarkPrice("hip", Decimal("1200")),
    ]
    with pytest.raises(ValueError, match="inconsistent episode types"):
        aggregate_episode_costs(items, benchmarks)


@pytest.mark.parametrize("amount", ["-1.00", "NaN", "Infinity"])
def test_invalid_paid_amount_is_rejected(amount):
    with pytest.raises(ValueError):
        item("e1", "c1", amount, "surgery")


def test_invalid_cost_bucket_is_rejected():
    with pytest.raises(ValueError, match="cost_bucket"):
        item("e1", "c1", "100.00", "other")


def test_invalid_benchmark_is_rejected():
    with pytest.raises(ValueError):
        BenchmarkPrice("knee", Decimal("-1"))


def test_detects_high_cost_outlier():
    items = []
    for index, amount in enumerate(
        ["100", "110", "120", "130", "140", "1000"]
    ):
        items.append(item(f"e{index}", f"c{index}", amount, "surgery"))

    reports = aggregate_episode_costs(items, benchmark("500"))
    flagged = detect_cost_outliers(reports)

    outlier = next(r for r in flagged if r.episode_id == "e5")
    assert outlier.outlier_iqr is True
    assert outlier.outlier_2sd is True
    assert outlier.is_outlier is True


def test_single_episode_is_not_statistically_flagged():
    items = [item("e1", "c1", "1000", "surgery")]
    reports = detect_cost_outliers(
        aggregate_episode_costs(items, benchmark())
    )
    assert reports[0].is_outlier is False


def test_outlier_detection_preserves_benchmark_comparison():
    items = [
        item("e1", "c1", "100", "surgery"),
        item("e2", "c2", "110", "surgery"),
        item("e3", "c3", "120", "surgery"),
        item("e4", "c4", "130", "surgery"),
        item("e5", "c5", "1000", "surgery"),
    ]

    original = aggregate_episode_costs(items, benchmark("500"))
    flagged = detect_cost_outliers(original)
    outlier = next(r for r in flagged if r.episode_id == "e5")

    assert outlier.above_target is True
    assert outlier.difference_from_target == Decimal("500")
    assert outlier.total_paid == Decimal("1000")
