from datetime import date
from decimal import Decimal

import pytest

from care_pathway.cost_analysis import BenchmarkPrice, EpisodeCostItem
from care_pathway.episode_lifecycle import EpisodeLedger, TransferEvent


START = date(2026, 3, 10)
END = date(2026, 6, 8)


def make_item(claim_id="c1", amount="100", bucket="surgery"):
    return EpisodeCostItem(
        "e1", "knee", claim_id, Decimal(amount), bucket
    )


def make_ledger(items=()):
    return EpisodeLedger(
        "e1",
        "knee",
        START,
        END,
        BenchmarkPrice("knee", Decimal("500")),
        items,
    )


def test_closed_episode_accepts_late_claim_and_recalculates_cost():
    ledger = make_ledger([make_item("surgery", "400")])
    ledger.close()

    before = ledger.cost_report()
    ledger.add_claim(make_item("late-rehab", "150", "rehab"))
    after = ledger.cost_report()

    assert ledger.is_closed is True
    assert before.total_paid == Decimal("400.00")
    assert after.total_paid == Decimal("550.00")
    assert after.above_target is True
    assert ledger.revision_count == 1


def test_multiple_late_claims_increment_revision_count():
    ledger = make_ledger([make_item()])
    ledger.close()

    ledger.add_claim(make_item("late1", "20", "rehab"))
    ledger.add_claim(make_item("late2", "30", "facility"))

    assert ledger.revision_count == 2
    assert ledger.is_closed is True


def test_claim_added_before_closure_does_not_increment_revisions():
    ledger = make_ledger()
    ledger.add_claim(make_item("c2", "20", "facility"))

    assert ledger.revision_count == 0


def test_duplicate_claim_is_rejected_even_after_closure():
    ledger = make_ledger([make_item()])
    ledger.close()

    with pytest.raises(ValueError, match="Duplicate claim"):
        ledger.add_claim(make_item())


def test_claim_for_another_episode_is_rejected():
    ledger = make_ledger()
    wrong_episode = EpisodeCostItem(
        "e2", "knee", "c2", Decimal("10"), "rehab"
    )

    with pytest.raises(ValueError, match="different episode"):
        ledger.add_claim(wrong_episode)


def test_readmission_adds_cost_to_readmissions_bucket():
    ledger = make_ledger([make_item("surgery", "400")])
    ledger.record_readmission(
        "infection-readmission",
        date(2026, 3, 25),
        Decimal("250"),
    )

    report = ledger.cost_report()
    assert report.bucket_totals["readmissions"] == Decimal("250.00")
    assert report.total_paid == Decimal("650.00")


def test_readmission_outside_episode_dates_is_rejected():
    ledger = make_ledger()

    with pytest.raises(ValueError, match="within the episode"):
        ledger.record_readmission(
            "late-readmission",
            date(2026, 7, 1),
            Decimal("100"),
        )


def test_transfer_is_recorded_without_duplicate_cost():
    ledger = make_ledger([make_item("surgery", "400")])
    event = TransferEvent(
        "t1", date(2026, 3, 11), "facility-a", "facility-b"
    )

    ledger.record_transfer(event)

    assert ledger.transfers == (event,)
    assert ledger.cost_report().total_paid == Decimal("400.00")


def test_duplicate_transfer_is_rejected():
    ledger = make_ledger()
    event = TransferEvent(
        "t1", date(2026, 3, 11), "facility-a", "facility-b"
    )
    ledger.record_transfer(event)

    with pytest.raises(ValueError, match="Duplicate transfer ID"):
        ledger.record_transfer(event)


def test_transfer_outside_episode_dates_is_rejected():
    ledger = make_ledger()
    event = TransferEvent(
        "t1", date(2026, 7, 1), "facility-a", "facility-b"
    )

    with pytest.raises(ValueError, match="within the episode"):
        ledger.record_transfer(event)


def test_death_during_episode_is_flagged():
    ledger = make_ledger()
    ledger.record_patient_death(date(2026, 4, 1))

    assert ledger.patient_deceased_during_episode is True


def test_death_outside_episode_does_not_flag_episode_death():
    ledger = make_ledger()
    ledger.record_patient_death(date(2026, 7, 1))

    assert ledger.patient_deceased_during_episode is False


def test_episode_without_claims_cannot_produce_cost_report():
    ledger = make_ledger()

    with pytest.raises(ValueError, match="without claims"):
        ledger.cost_report()


def test_start_date_after_end_date_is_rejected():
    with pytest.raises(ValueError, match="cannot be after"):
        EpisodeLedger(
            "e1",
            "knee",
            END,
            START,
            BenchmarkPrice("knee", Decimal("500")),
        )


def test_mismatched_benchmark_type_is_rejected():
    with pytest.raises(ValueError, match="does not match"):
        EpisodeLedger(
            "e1",
            "knee",
            START,
            END,
            BenchmarkPrice("hip", Decimal("500")),
        )
