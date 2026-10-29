from dataclasses import dataclass, replace
from typing import Iterable

from care_pathway.cost_analysis import EpisodeCostReport


@dataclass(frozen=True)
class EpisodeAttribution:
    episode_id: str
    responsible_provider_id: str
    responsible_facility_id: str

    def __post_init__(self):
        for name in (
            "episode_id",
            "responsible_provider_id",
            "responsible_facility_id",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")


@dataclass(frozen=True)
class ComplicationEvent:
    episode_id: str
    claim_id: str
    complication_code: str
    description: str

    def __post_init__(self):
        for name in (
            "episode_id",
            "claim_id",
            "complication_code",
            "description",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")


def apply_episode_details(
    reports: Iterable[EpisodeCostReport],
    attributions: Iterable[EpisodeAttribution] = (),
    complications: Iterable[ComplicationEvent] = (),
) -> list[EpisodeCostReport]:
    reports = list(reports)
    attributions = list(attributions)
    complications = list(complications)

    report_ids = [report.episode_id for report in reports]
    if len(report_ids) != len(set(report_ids)):
        raise ValueError("Episode reports must have unique episode IDs.")
    known_ids = set(report_ids)

    attribution_by_episode = {}
    for attribution in attributions:
        if attribution.episode_id not in known_ids:
            raise ValueError(
                f"Attribution references unknown episode: {attribution.episode_id}"
            )
        if attribution.episode_id in attribution_by_episode:
            raise ValueError(
                f"Duplicate attribution for episode: {attribution.episode_id}"
            )
        attribution_by_episode[attribution.episode_id] = attribution

    events_by_episode = {}
    seen_claims = set()
    for event in complications:
        if event.episode_id not in known_ids:
            raise ValueError(
                f"Complication references unknown episode: {event.episode_id}"
            )
        claim_key = (event.episode_id, event.claim_id)
        if claim_key in seen_claims:
            raise ValueError(
                f"Duplicate complication claim {event.claim_id} "
                f"within episode {event.episode_id}."
            )
        seen_claims.add(claim_key)
        events_by_episode.setdefault(event.episode_id, []).append(event)

    enriched = []
    for report in reports:
        attribution = attribution_by_episode.get(report.episode_id)
        events = sorted(
            events_by_episode.get(report.episode_id, []),
            key=lambda event: event.claim_id,
        )
        changes = {
            "complications": bool(events),
            "complication_claim_ids": tuple(event.claim_id for event in events),
            "complication_descriptions": tuple(
                event.description for event in events
            ),
        }
        if attribution is not None:
            changes["responsible_provider_id"] = (
                attribution.responsible_provider_id
            )
            changes["responsible_facility_id"] = (
                attribution.responsible_facility_id
            )
        enriched.append(replace(report, **changes))

    return enriched
