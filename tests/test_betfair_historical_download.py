from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from tennis_genome.market.betfair_historical_download import (
    HistoricalDataClient,
    HistoricalFilter,
    _load_state,
    _month_windows,
    _safe_relative_remote_path,
    download_purchased_history,
)


class _FakeClient:
    def __init__(self, files_by_month: dict[int, list[str]]) -> None:
        self.files_by_month = files_by_month
        self.filters: list[HistoricalFilter] = []
        self.downloads: list[str] = []

    def list_files(self, filter_: HistoricalFilter) -> list[str]:
        self.filters.append(filter_)
        return list(self.files_by_month.get(filter_.start_date.month, []))

    def download_file(self, remote_path: str, target: Path) -> int:
        self.downloads.append(remote_path)
        payload = ("fixture:" + remote_path).encode("utf-8")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        return len(payload)


def test_filter_is_frozen_to_tennis_match_odds_market_files():
    filter_ = HistoricalFilter(
        plan_name="Advanced Plan",
        start_date=date(2021, 2, 3),
        end_date=date(2021, 2, 28),
        countries=("AU", "GB"),
    )
    assert filter_.to_api_payload() == {
        "sport": "Tennis",
        "plan": "Advanced Plan",
        "fromDay": 3,
        "fromMonth": 2,
        "fromYear": 2021,
        "toDay": 28,
        "toMonth": 2,
        "toYear": 2021,
        "eventId": None,
        "eventName": None,
        "marketTypesCollection": ["MATCH_ODDS"],
        "countriesCollection": ["AU", "GB"],
        "fileTypeCollection": ["M"],
    }


def test_filter_rejects_bad_dates_and_blank_plan():
    with pytest.raises(ValueError, match="plan_name"):
        HistoricalFilter("", date(2021, 1, 1), date(2021, 1, 2))
    with pytest.raises(ValueError, match="on or before"):
        HistoricalFilter("Advanced Plan", date(2021, 1, 2), date(2021, 1, 1))


def test_month_windows_are_calendar_bounded():
    assert _month_windows(date(2020, 1, 15), date(2020, 3, 2)) == [
        (date(2020, 1, 15), date(2020, 1, 31)),
        (date(2020, 2, 1), date(2020, 2, 29)),
        (date(2020, 3, 1), date(2020, 3, 2)),
    ]


def test_remote_path_must_stay_inside_historical_root():
    assert _safe_relative_remote_path(
        "/data/xds/historic/ADVANCED/28139610/1.130129050.bz2"
    ).as_posix() == "ADVANCED/28139610/1.130129050.bz2"
    with pytest.raises(ValueError, match="outside"):
        _safe_relative_remote_path("/tmp/1.130129050.bz2")
    with pytest.raises(ValueError, match="traversal"):
        _safe_relative_remote_path(
            "/data/xds/historic/ADVANCED/28139610/../escape.bz2"
        )
    with pytest.raises(ValueError, match="must be absolute"):
        _safe_relative_remote_path("ADVANCED/28139610/1.130129050.bz2")
    with pytest.raises(ValueError, match=r"\.bz2"):
        _safe_relative_remote_path(
            "/data/xds/historic/ADVANCED/28139610/not-market.txt"
        )


def test_client_repr_never_exposes_token():
    client = HistoricalDataClient(ssoid="super-secret-token")
    text = repr(client)
    assert "super-secret-token" not in text
    assert "<redacted>" in text


def test_environment_token_is_required(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("BETFAIR_SSOID", raising=False)
    with pytest.raises(RuntimeError, match="BETFAIR_SSOID"):
        HistoricalDataClient.from_environment()


def test_environment_token_is_loaded_without_becoming_public_state(
    monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setenv("BETFAIR_SSOID", "fixture-token")
    client = HistoricalDataClient.from_environment()
    assert "fixture-token" not in repr(client)


def test_download_is_month_chunked_deduplicated_and_resumable(tmp_path: Path):
    first = "/data/xds/historic/ADVANCED/100/1.100000001.bz2"
    second = "/data/xds/historic/ADVANCED/101/1.100000002.bz2"
    client = _FakeClient({1: [first], 2: [first, second]})

    report = download_purchased_history(
        client=client,  # type: ignore[arg-type]
        plan_name="Advanced Plan",
        start_date=date(2021, 1, 20),
        end_date=date(2021, 2, 10),
        output_root=tmp_path,
    )
    assert report.month_windows == 2
    assert report.files_listed == 2
    assert report.files_downloaded == 2
    assert report.files_skipped_verified == 0
    assert client.downloads == [first, second]
    assert [(row.start_date, row.end_date) for row in client.filters] == [
        (date(2021, 1, 20), date(2021, 1, 31)),
        (date(2021, 2, 1), date(2021, 2, 10)),
    ]
    assert (tmp_path / "ADVANCED/100/1.100000001.bz2").exists()
    assert (tmp_path / "ADVANCED/101/1.100000002.bz2").exists()

    state_before = (tmp_path / "download-state.json").read_bytes()
    resumed = _FakeClient({1: [first], 2: [first, second]})
    second_report = download_purchased_history(
        client=resumed,  # type: ignore[arg-type]
        plan_name="Advanced Plan",
        start_date=date(2021, 1, 20),
        end_date=date(2021, 2, 10),
        output_root=tmp_path,
    )
    assert second_report.files_downloaded == 0
    assert second_report.files_skipped_verified == 2
    assert resumed.downloads == []
    assert (tmp_path / "download-state.json").read_bytes() == state_before


def test_resume_rejects_locally_tampered_file(tmp_path: Path):
    remote = "/data/xds/historic/ADVANCED/100/1.100000001.bz2"
    client = _FakeClient({1: [remote]})
    download_purchased_history(
        client=client,  # type: ignore[arg-type]
        plan_name="Advanced Plan",
        start_date=date(2021, 1, 1),
        end_date=date(2021, 1, 31),
        output_root=tmp_path,
    )
    target = tmp_path / "ADVANCED/100/1.100000001.bz2"
    target.write_bytes(b"tampered")
    with pytest.raises(ValueError, match="no longer matches resume state"):
        download_purchased_history(
            client=_FakeClient({1: [remote]}),  # type: ignore[arg-type]
            plan_name="Advanced Plan",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 31),
            output_root=tmp_path,
        )


def test_resume_rejects_untracked_existing_file(tmp_path: Path):
    remote = "/data/xds/historic/ADVANCED/100/1.100000001.bz2"
    target = tmp_path / "ADVANCED/100/1.100000001.bz2"
    target.parent.mkdir(parents=True)
    target.write_bytes(b"untracked")
    with pytest.raises(FileExistsError, match="untracked existing"):
        download_purchased_history(
            client=_FakeClient({1: [remote]}),  # type: ignore[arg-type]
            plan_name="Advanced Plan",
            start_date=date(2021, 1, 1),
            end_date=date(2021, 1, 31),
            output_root=tmp_path,
        )


def test_stale_part_file_is_replaced_safely(tmp_path: Path):
    remote = "/data/xds/historic/ADVANCED/100/1.100000001.bz2"
    part = tmp_path / "ADVANCED/100/1.100000001.bz2.part"
    part.parent.mkdir(parents=True)
    part.write_bytes(b"partial-old-download")
    report = download_purchased_history(
        client=_FakeClient({1: [remote]}),  # type: ignore[arg-type]
        plan_name="Advanced Plan",
        start_date=date(2021, 1, 1),
        end_date=date(2021, 1, 31),
        output_root=tmp_path,
    )
    assert report.files_downloaded == 1
    assert not part.exists()
    assert (tmp_path / "ADVANCED/100/1.100000001.bz2").read_bytes().startswith(
        b"fixture:"
    )


def test_dry_run_lists_but_does_not_write_files_or_state(tmp_path: Path):
    remote = "/data/xds/historic/BASIC/100/1.100000001.bz2"
    client = _FakeClient({1: [remote]})
    report = download_purchased_history(
        client=client,  # type: ignore[arg-type]
        plan_name="Basic Plan",
        start_date=date(2021, 1, 1),
        end_date=date(2021, 1, 31),
        output_root=tmp_path,
        dry_run=True,
    )
    assert report.dry_run is True
    assert report.files_listed == 1
    assert report.files_downloaded == 0
    assert client.downloads == []
    assert not (tmp_path / "BASIC/100/1.100000001.bz2").exists()
    assert not (tmp_path / "download-state.json").exists()


def test_corrupt_state_is_rejected(tmp_path: Path):
    state_path = tmp_path / "download-state.json"
    state_path.write_text(
        json.dumps({"state_version": "wrong", "files": []}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="unexpected Betfair download state"):
        _load_state(state_path)
