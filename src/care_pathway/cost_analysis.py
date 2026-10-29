from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

import pandas as pd


COST_BUCKETS = ("surgery", "facility", "rehab", "readmissions")


@dataclass(frozen=True)
class EpisodeCostItem:
    episode_id: str
    episode_type: str
    claim_id: str
    paid_amount: Decimal
    cost_bucket: str

    def __post_init__(self):
        for name in ("episode_id", "episode_type", "claim_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")

        if not isinstance(self.paid_amount, Decimal):
            raise ValueError("paid_amount must be a Decimal.")

        if not self.paid_amount.is_finite() or self.paid_amount < 0:
            raise ValueError("paid_amount must be finite and non-negative.")

        if self.cost_bucket not in COST_BUCKETS:
            raise ValueError(
                f"cost_bucket must be one of {COST_BUCKETS}."
            )


@dataclass(frozen=True)
class BenchmarkPrice:
    episode_type: str
    target_price: Decimal

    def __post_init__(self):
        if not isinstance(self.episode_type, str) or not self.episode_type.strip():
            raise ValueError("episode_type must be a non-empty string.")

        if not isinstance(self.target_price, Decimal):
            raise ValueError("target_price must be a Decimal.")

        if not self.target_price.is_finite() or self.target_price < 0:
            raise ValueError("target_price must be finite and non-negative.")


@dataclass(frozen=True)
class EpisodeCostReport:
    episode_id: str
    episode_type: str
    bucket_totals: dict[str, Decimal]
    total_paid: Decimal
    target_price: Decimal
    difference_from_target: Decimal
    above_target: bool
    complications: bool = False
    complication_claim_ids: tuple[str, ...] = ()
    complication_descriptions: tuple[str, ...] = ()
    responsible_provider_id: str | None = None
    responsible_facility_id: str | None = None
    outlier_2sd: bool = False
    outlier_iqr: bool = False

    @property
    def is_outlier(self) -> bool:
        return self.outlier_2sd or self.outlier_iqr


def aggregate_episode_costs(
    items: Iterable[EpisodeCostItem],
    benchmarks: Iterable[BenchmarkPrice],
) -> list[EpisodeCostReport]:
    items = list(items)
    benchmarks = list(benchmarks)

    benchmark_types = [b.episode_type for b in benchmarks]
    if len(benchmark_types) != len(set(benchmark_types)):
        raise ValueError("Benchmark episode types must be unique.")

    benchmark_by_type = {b.episode_type: b for b in benchmarks}

    claim_keys = [(item.episode_id, item.claim_id) for item in items]
    if len(claim_keys) != len(set(claim_keys)):
        raise ValueError("Duplicate claim within an episode.")

    episode_types = {}
    bucket_totals = {}
    complications = {}

    for item in items:
        previous_type = episode_types.setdefault(
            item.episode_id, item.episode_type
        )
        if previous_type != item.episode_type:
            raise ValueError(
                f"Episode {item.episode_id} has inconsistent episode types."
            )

        if item.episode_type not in benchmark_by_type:
            raise ValueError(
                f"Missing benchmark for episode type: {item.episode_type}"
            )

        totals = bucket_totals.setdefault(
            item.episode_id,
            {bucket: Decimal("0.00") for bucket in COST_BUCKETS},
        )
        totals[item.cost_bucket] += item.paid_amount
        complications.setdefault(item.episode_id, False)

    reports = []

    for episode_id in sorted(episode_types):
        episode_type = episode_types[episode_id]
        totals = bucket_totals[episode_id]
        total = sum(totals.values(), Decimal("0.00"))
        target = benchmark_by_type[episode_type].target_price

        reports.append(
            EpisodeCostReport(
                episode_id=episode_id,
                episode_type=episode_type,
                bucket_totals=dict(totals),
                total_paid=total,
                target_price=target,
                difference_from_target=total - target,
                above_target=total > target,
                complications=complications[episode_id],
            )
        )

    return reports


def detect_cost_outliers(
    reports: Iterable[EpisodeCostReport],
) -> list[EpisodeCostReport]:
    reports = list(reports)

    if len(reports) < 2:
        return reports

    costs = pd.Series(
        [float(report.total_paid) for report in reports],
        dtype="float64",
    )

    mean = costs.mean()
    standard_deviation = costs.std(ddof=0)
    threshold_2sd = mean + 2 * standard_deviation

    q1 = costs.quantile(0.25)
    q3 = costs.quantile(0.75)
    iqr = q3 - q1
    threshold_iqr = q3 + 1.5 * iqr

    updated = []

    for report in reports:
        cost = float(report.total_paid)
        updated.append(
            EpisodeCostReport(
                episode_id=report.episode_id,
                episode_type=report.episode_type,
                bucket_totals=report.bucket_totals,
                total_paid=report.total_paid,
                target_price=report.target_price,
                difference_from_target=report.difference_from_target,
                above_target=report.above_target,
                complications=report.complications,
                complication_claim_ids=report.complication_claim_ids,
                complication_descriptions=report.complication_descriptions,
                responsible_provider_id=report.responsible_provider_id,
                responsible_facility_id=report.responsible_facility_id,
                outlier_2sd=bool(cost > threshold_2sd),
                outlier_iqr=bool(cost > threshold_iqr),
            )
        )

    return updated
