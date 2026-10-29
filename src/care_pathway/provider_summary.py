from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from care_pathway.cost_analysis import EpisodeCostReport


@dataclass(frozen=True)
class ProviderSummary:
    provider_id: str | None
    episode_count: int
    total_paid: Decimal
    total_benchmark: Decimal
    episodes_above_target: int
    complication_episodes: int
    outlier_episodes: int


def summarize_by_provider(
    reports: Iterable[EpisodeCostReport],
) -> list[ProviderSummary]:
    reports = list(reports)

    episode_ids = [report.episode_id for report in reports]
    if len(episode_ids) != len(set(episode_ids)):
        raise ValueError("Episode reports must have unique episode IDs.")

    grouped = {}
    for report in reports:
        provider_id = report.responsible_provider_id
        values = grouped.setdefault(
            provider_id,
            {
                "episode_count": 0,
                "total_paid": Decimal("0.00"),
                "total_benchmark": Decimal("0.00"),
                "episodes_above_target": 0,
                "complication_episodes": 0,
                "outlier_episodes": 0,
            },
        )
        values["episode_count"] += 1
        values["total_paid"] += report.total_paid
        values["total_benchmark"] += report.target_price
        values["episodes_above_target"] += int(report.above_target)
        values["complication_episodes"] += int(report.complications)
        values["outlier_episodes"] += int(report.is_outlier)

    summaries = [
        ProviderSummary(provider_id=provider_id, **values)
        for provider_id, values in grouped.items()
    ]
    return sorted(
        summaries,
        key=lambda summary: (
            summary.provider_id is None,
            summary.provider_id or "",
        ),
    )
