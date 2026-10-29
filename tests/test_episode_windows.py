from datetime import date

import pytest

from care_pathway.episode_windows import EpisodeWindow


@pytest.fixture
def episode():
    return EpisodeWindow(
        index_date=date(2026, 3, 10),
        admission_date=date(2026, 3, 10),
        discharge_date=date(2026, 3, 13),
    )


def test_default_episode_windows(episode):
    assert episode.preoperative_start == date(2026, 2, 8)
    assert episode.preoperative_end == date(2026, 3, 9)
    assert episode.hospital_start == date(2026, 3, 10)
    assert episode.hospital_end == date(2026, 3, 13)
    assert episode.postacute_start == date(2026, 3, 14)
    assert episode.postacute_end == date(2026, 6, 11)


def test_worked_example_dates_belong_to_episode(episode):
    assert episode.bucket_for(date(2026, 2, 20)) == "preoperative"
    assert episode.bucket_for(date(2026, 3, 10)) == "hospital"
    assert episode.bucket_for(date(2026, 3, 13)) == "hospital"
    assert episode.bucket_for(date(2026, 4, 2)) == "postacute"
    assert episode.bucket_for(date(2026, 6, 5)) == "postacute"


def test_preoperative_start_is_included(episode):
    assert episode.bucket_for(date(2026, 2, 8)) == "preoperative"


def test_date_before_window_is_excluded(episode):
    assert episode.bucket_for(date(2026, 2, 7)) is None


def test_date_after_postacute_window_is_excluded(episode):
    assert episode.bucket_for(date(2026, 6, 12)) is None


def test_hospital_dates_are_inclusive(episode):
    assert episode.bucket_for(date(2026, 3, 10)) == "hospital"
    assert episode.bucket_for(date(2026, 3, 13)) == "hospital"


def test_custom_window_lengths():
    episode = EpisodeWindow(
        index_date=date(2026, 3, 10),
        admission_date=date(2026, 3, 9),
        discharge_date=date(2026, 3, 13),
        preoperative_days=10,
        postacute_days=30,
    )
    assert episode.preoperative_start == date(2026, 2, 28)
    assert episode.preoperative_end == date(2026, 3, 8)
    assert episode.postacute_end == date(2026, 4, 12)


@pytest.mark.parametrize(
    "kwargs",
    [
        {"admission_date": date(2026, 3, 11)},
        {"discharge_date": date(2026, 3, 9)},
        {"preoperative_days": -1},
        {"postacute_days": -1},
        {"preoperative_days": 1.5},
        {"postacute_days": True},
    ],
)
def test_invalid_window_configuration_is_rejected(kwargs):
    values = {
        "index_date": date(2026, 3, 10),
        "admission_date": date(2026, 3, 10),
        "discharge_date": date(2026, 3, 13),
    }
    values.update(kwargs)

    with pytest.raises(ValueError):
        EpisodeWindow(**values)


def test_invalid_service_date_is_rejected():
    episode = EpisodeWindow(
        index_date=date(2026, 3, 10),
        admission_date=date(2026, 3, 10),
        discharge_date=date(2026, 3, 13),
    )

    with pytest.raises(ValueError):
        episode.bucket_for("2026-03-10")
