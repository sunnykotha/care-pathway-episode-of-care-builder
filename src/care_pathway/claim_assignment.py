from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from care_pathway.episode_windows import EpisodeWindow


@dataclass(frozen=True)
class Claim:
    claim_id: str
    patient_id: str
    service_date: date
    diagnosis_codes: frozenset[str]
    provider_id: str
    paid_amount: Decimal
    procedure_code: str | None = None

    def __post_init__(self):
        for name in ("claim_id", "patient_id", "provider_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")

        if not isinstance(self.service_date, date):
            raise ValueError("service_date must be a date.")

        if not isinstance(self.diagnosis_codes, (set, frozenset)):
            raise ValueError("diagnosis_codes must be a set of codes.")

        if not self.diagnosis_codes or any(
            not isinstance(code, str) or not code.strip()
            for code in self.diagnosis_codes
        ):
            raise ValueError("diagnosis_codes must contain non-empty codes.")

        if not isinstance(self.paid_amount, Decimal):
            raise ValueError("paid_amount must be a Decimal.")

        if not self.paid_amount.is_finite() or self.paid_amount < 0:
            raise ValueError("paid_amount must be finite and non-negative.")

        if self.procedure_code is not None and (
            not isinstance(self.procedure_code, str)
            or not self.procedure_code.strip()
        ):
            raise ValueError("procedure_code must be non-empty when supplied.")


@dataclass(frozen=True)
class EpisodeDefinition:
    episode_id: str
    patient_id: str
    window: EpisodeWindow
    diagnosis_codes: frozenset[str]
    relevant_provider_ids: frozenset[str] = frozenset()
    index_procedure_code: str | None = None

    def __post_init__(self):
        if not isinstance(self.episode_id, str) or not self.episode_id.strip():
            raise ValueError("episode_id must be a non-empty string.")

        if not isinstance(self.patient_id, str) or not self.patient_id.strip():
            raise ValueError("patient_id must be a non-empty string.")

        if not isinstance(self.window, EpisodeWindow):
            raise ValueError("window must be an EpisodeWindow.")

        if not isinstance(self.diagnosis_codes, (set, frozenset)):
            raise ValueError("diagnosis_codes must be a set of codes.")

        if not self.diagnosis_codes or any(
            not isinstance(code, str) or not code.strip()
            for code in self.diagnosis_codes
        ):
            raise ValueError("diagnosis_codes must contain non-empty codes.")

        if not isinstance(self.relevant_provider_ids, (set, frozenset)):
            raise ValueError("relevant_provider_ids must be a set of IDs.")

        if any(
            not isinstance(provider, str) or not provider.strip()
            for provider in self.relevant_provider_ids
        ):
            raise ValueError("Provider IDs must be non-empty strings.")

        if self.index_procedure_code is not None and (
            not isinstance(self.index_procedure_code, str)
            or not self.index_procedure_code.strip()
        ):
            raise ValueError("index_procedure_code must be non-empty when supplied.")


@dataclass(frozen=True)
class ClaimAssignment:
    claim_id: str
    episode_id: str
    cost_bucket: str


def _eligible(claim: Claim, episode: EpisodeDefinition) -> bool:
    window = episode.window

    if claim.patient_id != episode.patient_id:
        return False

    if not (
        window.preoperative_start
        <= claim.service_date
        <= window.postacute_end
    ):
        return False

    if not claim.diagnosis_codes.intersection(episode.diagnosis_codes):
        return False

    if (
        episode.relevant_provider_ids
        and claim.provider_id not in episode.relevant_provider_ids
    ):
        return False

    return True


def assign_claims(
    claims: Iterable[Claim],
    episodes: Iterable[EpisodeDefinition],
) -> list[ClaimAssignment]:
    claims = list(claims)
    episodes = list(episodes)

    claim_ids = [claim.claim_id for claim in claims]
    if len(claim_ids) != len(set(claim_ids)):
        raise ValueError("Claim IDs must be unique.")

    episode_ids = [episode.episode_id for episode in episodes]
    if len(episode_ids) != len(set(episode_ids)):
        raise ValueError("Episode IDs must be unique.")

    assignments = []

    for claim in claims:
        candidates = [
            episode
            for episode in episodes
            if _eligible(claim, episode)
        ]

        if not candidates:
            continue

        index_matches = [
            episode
            for episode in candidates
            if episode.index_procedure_code is not None
            and claim.procedure_code == episode.index_procedure_code
            and claim.service_date == episode.window.index_date
        ]

        if index_matches:
            candidates = index_matches

        selected = min(
            candidates,
            key=lambda episode: (
                abs((claim.service_date - episode.window.index_date).days),
                -episode.window.index_date.toordinal(),
                episode.episode_id,
            ),
        )

        bucket = selected.window.bucket_for(claim.service_date)
        if bucket is not None:
            assignments.append(
                ClaimAssignment(
                    claim_id=claim.claim_id,
                    episode_id=selected.episode_id,
                    cost_bucket=bucket,
                )
            )

    return assignments
