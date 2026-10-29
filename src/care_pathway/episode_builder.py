from dataclasses import dataclass
from datetime import date
from typing import Iterable

from care_pathway.claim_assignment import Claim, EpisodeDefinition
from care_pathway.episode_windows import EpisodeWindow


@dataclass(frozen=True)
class EpisodeIndexEvent:
    index_claim: Claim
    admission_date: date
    discharge_date: date

    def __post_init__(self):
        if not isinstance(self.index_claim, Claim):
            raise ValueError("index_claim must be a Claim.")
        if not self.index_claim.procedure_code:
            raise ValueError("Index claim must have a procedure code.")
        if not isinstance(self.admission_date, date):
            raise ValueError("admission_date must be a date.")
        if not isinstance(self.discharge_date, date):
            raise ValueError("discharge_date must be a date.")
        if self.admission_date > self.index_claim.service_date:
            raise ValueError("Admission cannot be after the index date.")
        if self.index_claim.service_date > self.discharge_date:
            raise ValueError("Index date cannot be after discharge.")


def build_episodes(
    index_events: Iterable[EpisodeIndexEvent],
    preoperative_days: int = 30,
    postacute_days: int = 90,
) -> list[EpisodeDefinition]:
    events = list(index_events)
    episodes = []
    episode_ids = set()

    for event in events:
        if not isinstance(event, EpisodeIndexEvent):
            raise ValueError("Every item must be an EpisodeIndexEvent.")

        claim = event.index_claim
        episode_id = f"episode:{claim.claim_id}"
        if episode_id in episode_ids:
            raise ValueError("Index claim IDs must be unique.")
        episode_ids.add(episode_id)

        episodes.append(
            EpisodeDefinition(
                episode_id=episode_id,
                patient_id=claim.patient_id,
                window=EpisodeWindow(
                    index_date=claim.service_date,
                    admission_date=event.admission_date,
                    discharge_date=event.discharge_date,
                    preoperative_days=preoperative_days,
                    postacute_days=postacute_days,
                ),
                diagnosis_codes=frozenset(claim.diagnosis_codes),
                relevant_provider_ids=frozenset({claim.provider_id}),
                index_procedure_code=claim.procedure_code,
            )
        )

    return episodes
