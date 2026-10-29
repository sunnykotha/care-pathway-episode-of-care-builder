from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Iterable

from care_pathway.cost_analysis import (
    BenchmarkPrice,
    EpisodeCostItem,
    EpisodeCostReport,
    aggregate_episode_costs,
)


@dataclass(frozen=True)
class TransferEvent:
    transfer_id: str
    transfer_date: date
    from_facility_id: str
    to_facility_id: str

    def __post_init__(self):
        for name in ("transfer_id", "from_facility_id", "to_facility_id"):
            value = getattr(self, name)
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
        if not isinstance(self.transfer_date, date):
            raise ValueError("transfer_date must be a date.")
        if self.from_facility_id == self.to_facility_id:
            raise ValueError("Transfer facilities must be different.")


class EpisodeLedger:
    def __init__(
        self,
        episode_id: str,
        episode_type: str,
        start_date: date,
        end_date: date,
        benchmark: BenchmarkPrice,
        items: Iterable[EpisodeCostItem] = (),
    ):
        for name, value in (
            ("episode_id", episode_id),
            ("episode_type", episode_type),
        ):
            if not isinstance(value, str) or not value.strip():
                raise ValueError(f"{name} must be a non-empty string.")
        if not isinstance(start_date, date) or not isinstance(end_date, date):
            raise ValueError("Episode dates must be dates.")
        if start_date > end_date:
            raise ValueError("start_date cannot be after end_date.")
        if not isinstance(benchmark, BenchmarkPrice):
            raise ValueError("benchmark must be a BenchmarkPrice.")
        if benchmark.episode_type != episode_type:
            raise ValueError("Benchmark episode type does not match.")

        self.episode_id = episode_id
        self.episode_type = episode_type
        self.start_date = start_date
        self.end_date = end_date
        self.benchmark = benchmark
        self._items = []
        self._claim_ids = set()
        self._closed = False
        self._revision_count = 0
        self._death_date = None
        self._transfers = []

        for item in items:
            self.add_claim(item)

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def revision_count(self) -> int:
        return self._revision_count

    @property
    def patient_death_date(self) -> date | None:
        return self._death_date

    @property
    def patient_deceased_during_episode(self) -> bool:
        return (
            self._death_date is not None
            and self.start_date <= self._death_date <= self.end_date
        )

    @property
    def transfers(self) -> tuple[TransferEvent, ...]:
        return tuple(self._transfers)

    @property
    def claims(self) -> tuple[EpisodeCostItem, ...]:
        return tuple(self._items)

    def add_claim(self, item: EpisodeCostItem) -> None:
        if not isinstance(item, EpisodeCostItem):
            raise ValueError("item must be an EpisodeCostItem.")
        if item.episode_id != self.episode_id:
            raise ValueError("Claim belongs to a different episode.")
        if item.episode_type != self.episode_type:
            raise ValueError("Claim episode type does not match.")
        if item.claim_id in self._claim_ids:
            raise ValueError(
                f"Duplicate claim within episode: {item.claim_id}"
            )

        self._items.append(item)
        self._claim_ids.add(item.claim_id)

        if self._closed:
            self._revision_count += 1

    def close(self) -> None:
        self._closed = True

    def record_readmission(
        self,
        claim_id: str,
        service_date: date,
        paid_amount: Decimal,
    ) -> None:
        if not isinstance(service_date, date):
            raise ValueError("service_date must be a date.")
        if not self.start_date <= service_date <= self.end_date:
            raise ValueError("Readmission date must fall within the episode.")
        self.add_claim(
            EpisodeCostItem(
                episode_id=self.episode_id,
                episode_type=self.episode_type,
                claim_id=claim_id,
                paid_amount=paid_amount,
                cost_bucket="readmissions",
            )
        )

    def record_transfer(self, event: TransferEvent) -> None:
        if not isinstance(event, TransferEvent):
            raise ValueError("event must be a TransferEvent.")
        if not self.start_date <= event.transfer_date <= self.end_date:
            raise ValueError("Transfer date must fall within the episode.")
        if any(
            existing.transfer_id == event.transfer_id
            for existing in self._transfers
        ):
            raise ValueError(
                f"Duplicate transfer ID: {event.transfer_id}"
            )
        self._transfers.append(event)

    def record_patient_death(self, death_date: date) -> None:
        if not isinstance(death_date, date):
            raise ValueError("death_date must be a date.")
        self._death_date = death_date

    def cost_report(self) -> EpisodeCostReport:
        if not self._items:
            raise ValueError("Cannot report costs for an episode without claims.")
        return aggregate_episode_costs(
            self._items, [self.benchmark]
        )[0]
