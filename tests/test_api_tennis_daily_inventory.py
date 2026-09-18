from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from tennis_genome.research_workbench.api_tennis_daily_inventory import (
    capture_api_tennis_daily_inventory,
)


def _row(
    *,
    event_key: int,
    event_type_type: str,
    status: str = "Not Started",
) -> dict[str, object]:
    return {
        "event_key": event_key,
        "event_date": "2026-09-18",
        "event_time": "12:00",
        "event_type_type": event_type_type,
        "event_status": status,
        "event_first_player": f"Player {event_key}A",
        "event_second_player": f"Player {event_key}B",
    }


def _raw(*rows: dict[str, object]) -> bytes:
    return json.dumps({"success": 1, "result": list(rows)}).encode("utf-8")


def test_daily_inventory_uses_one_unfiltered_request_and_filters_offline() -> None:
    seen: list[str] = []

    def provider_get(url: str) -> bytes:
        seen.append(url)
        return _raw(
            _row(event_key=1, event_type_type="Atp Singles"),
            _row(event_key=2, event_type_type="Wta Singles", status="Finished"),
            _row(event_key=3, event_type_type="Atp Doubles"),
        )

    raw, filtered, manifest = capture_api_tennis_daily_inventory(
        schedule_date=date(2026, 9, 18),
        api_key="secret",
        provider_get=provider_get,
    )

    assert len(seen) == 1
    query = parse_qs(urlparse(seen[0]).query)
    assert query["method"] == ["get_fixtures"]
    assert query["date_start"] == ["2026-09-18"]
    assert query["date_stop"] == ["2026-09-18"]
    assert query["timezone"] == ["UTC"]
    assert "event_type_key" not in query
    assert query["APIkey"] == ["secret"]

    filtered_payload = json.loads(filtered.decode("utf-8"))
    assert [row["event_key"] for row in filtered_payload["result"]] == [1, 2]
    assert manifest["provider_request_count"] == 1
    assert manifest["raw_fixture_count"] == 3
    assert manifest["atp_wta_singles_count"] == 2
    assert manifest["atp_singles_count"] == 1
    assert manifest["wta_singles_count"] == 1
    assert manifest["query_event_type_filter"] is None
    assert manifest["market_blind"] is True
    assert raw.startswith(b'{"success"')


def test_daily_inventory_rejects_market_semantic_fields() -> None:
    row = _row(event_key=1, event_type_type="Wta Singles")
    row["odds"] = {"home": 1.8}

    with pytest.raises(ValueError, match="market-semantic"):
        capture_api_tennis_daily_inventory(
            schedule_date=date(2026, 9, 18),
            api_key="secret",
            provider_get=lambda _: _raw(row),
        )


def test_daily_inventory_rejects_wrong_date_and_duplicate_event_keys() -> None:
    wrong_date = _row(event_key=1, event_type_type="Wta Singles")
    wrong_date["event_date"] = "2026-09-17"
    with pytest.raises(ValueError, match="outside schedule_date"):
        capture_api_tennis_daily_inventory(
            schedule_date=date(2026, 9, 18),
            api_key="secret",
            provider_get=lambda _: _raw(wrong_date),
        )

    with pytest.raises(ValueError, match="duplicate event_key"):
        capture_api_tennis_daily_inventory(
            schedule_date=date(2026, 9, 18),
            api_key="secret",
            provider_get=lambda _: _raw(
                _row(event_key=9, event_type_type="Atp Singles"),
                _row(event_key=9, event_type_type="Wta Singles"),
            ),
        )


def test_daily_inventory_workflow_freezes_single_call_and_retention_contract() -> None:
    text = Path(".github/workflows/api_tennis_daily_inventory.yml").read_text(
        encoding="utf-8"
    )

    assert "API_TENNIS_API: ${{ secrets.API_TENNIS_API }}" in text
    assert "provider_request_count" in text
    assert "did not use exactly one provider request" in text
    assert "query_event_type_filter" in text
    assert "unexpectedly used an event-type provider filter" in text
    assert "api-tennis-daily-inventory-${{ inputs.schedule_date }}" in text
    assert "retention-days: 90" in text
    assert "| tee api-tennis-daily-inventory-summary.json" in text
    normalized = " ".join(text.replace("\\\n", " ").split())
    assert (
        "cp api-tennis-daily-inventory-summary.json "
        "api-tennis-daily-inventory/summary.json"
        in normalized
    )
    assert (
        "actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02"
        in text
    )


def test_trusted_dispatch_bridge_allows_daily_inventory_by_date_only() -> None:
    text = Path(".github/workflows/trusted_dispatch_bridge.yml").read_text(
        encoding="utf-8"
    )

    contract = text.split("'api_tennis_daily_inventory.yml':", maxsplit=1)[1]
    contract = contract.split("},", maxsplit=1)[0]
    assert "'schedule_date'" in contract
    assert "prediction_artifact_id" not in contract
