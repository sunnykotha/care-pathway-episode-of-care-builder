from dataclasses import dataclass
from datetime import date, timedelta


@dataclass(frozen=True)
class EpisodeWindow:
    index_date: date
    admission_date: date
    discharge_date: date
    preoperative_days: int = 30
    postacute_days: int = 90

    def __post_init__(self):
        for name in ("index_date", "admission_date", "discharge_date"):
            value = getattr(self, name)
            if not isinstance(value, date):
                raise ValueError(f"{name} must be a date.")

        for name in ("preoperative_days", "postacute_days"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{name} must be a non-negative integer.")

        if self.admission_date > self.index_date:
            raise ValueError("Admission date cannot be after the index date.")

        if self.index_date > self.discharge_date:
            raise ValueError("Index date cannot be after the discharge date.")

    @property
    def preoperative_start(self) -> date:
        return self.index_date - timedelta(days=self.preoperative_days)

    @property
    def preoperative_end(self) -> date:
        return self.admission_date - timedelta(days=1)

    @property
    def hospital_start(self) -> date:
        return self.admission_date

    @property
    def hospital_end(self) -> date:
        return self.discharge_date

    @property
    def postacute_start(self) -> date:
        return self.discharge_date + timedelta(days=1)

    @property
    def postacute_end(self) -> date:
        return self.discharge_date + timedelta(days=self.postacute_days)

    def bucket_for(self, service_date: date) -> str | None:
        if not isinstance(service_date, date):
            raise ValueError("service_date must be a date.")

        if self.hospital_start <= service_date <= self.hospital_end:
            return "hospital"

        if self.preoperative_start <= service_date <= self.preoperative_end:
            return "preoperative"

        if self.postacute_start <= service_date <= self.postacute_end:
            return "postacute"

        return None
