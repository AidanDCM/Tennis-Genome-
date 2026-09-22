from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from scripts.web_shadow_wta_acquisition_core import (
    acquire_wta_sources,
    matches_url,
    tournament_index_url,
    tournament_url,
)


def _raw(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":")).encode("utf-8")


def _config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "schema_version": (
                    "tennis-genome-web-shadow-intake-config-v1"
                ),
                "production_eligible": False,
                "selection_rule": {
                    "minimum_lead_hours": 8,
                    "maximum_horizon_hours": 48,
                    "maximum_matches_per_slate": 8,
                },
                "tournaments": [
                    {
                        "group_id": 1152,
                        "year": 2026,
                        "slug": "singapore",
                        "display_name": "Singapore",
                        "tournament_id": "web:wta:singapore:2026",
                        "tournament_level": "P",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


def _responses() -> dict[str, bytes]:
    index = _raw(
        {
            "pageInfo": {
                "page": 0,
                "pageSize": 100,
                "numEntries": 1,
            },
            "content": [
                {
                    "tournamentGroup": {
                        "id": 1152,
                        "name": "Singapore",
                    },
                    "year": 2026,
                    "title": "Singapore",
                }
            ],
        }
    )
    tournament = _raw(
        {
            "tournamentGroup": {
                "id": 1152,
                "name": "Singapore",
            },
            "year": 2026,
            "title": "Singapore",
            "surface": "Hard",
        }
    )
    matches = _raw(
        {
            "matches": [
                {
                    "MatchID": "M1",
                    "EventID": "1152",
                    "EventYear": 2026,
                }
            ]
        }
    )
    return {
        tournament_index_url(2026, page=0): index,
        tournament_url(1152, 2026): tournament,
        matches_url(1152, 2026): matches,
    }


def test_urls_are_official_and_deterministic() -> None:
    assert tournament_url(1152, 2026) == (
        "https://api.wtatennis.com/tennis/tournaments/1152/2026"
    )
    assert matches_url(1152, 2026) == (
        "https://api.wtatennis.com/tennis/tournaments/1152/2026/matches"
    )
    index_url = tournament_index_url(2026)
    assert index_url.startswith(
        "https://api.wtatennis.com/tennis/tournaments/?"
    )
    assert "pageSize=100" in index_url
    assert "excludeLevels=ITF" in index_url
    assert "from=2026-01-01" in index_url
    assert "to=2026-12-31" in index_url


def test_acquisition_preserves_provider_bytes(tmp_path: Path) -> None:
    config = tmp_path / "config.json"
    source_root = tmp_path / "source"
    _config(config)
    responses = _responses()
    calls: list[str] = []

    def fake_fetcher(url: str) -> bytes:
        calls.append(url)
        return responses[url]

    manifest = acquire_wta_sources(
        config_path=config,
        source_root=source_root,
        observed_at="2026-09-22T12:00:00+00:00",
        fetcher=fake_fetcher,
    )

    assert calls == [
        tournament_index_url(2026, page=0),
        tournament_url(1152, 2026),
        matches_url(1152, 2026),
    ]
    assert (
        source_root / "tournament-index-2026-page-0.json"
    ).read_bytes() == responses[tournament_index_url(2026, page=0)]
    assert (
        source_root / "singapore-tournament.json"
    ).read_bytes() == responses[tournament_url(1152, 2026)]
    assert (
        source_root / "singapore-matches.json"
    ).read_bytes() == responses[matches_url(1152, 2026)]
    assert manifest["production_eligible"] is False
    assert manifest["source_policy"]["index_role"] == (
        "audit_and_discovery_only"
    )
    assert manifest["source_records"][0]["raw_match_count"] == 1
    assert manifest["source_records"][0]["matches_sha256"] == hashlib.sha256(
        responses[matches_url(1152, 2026)]
    ).hexdigest()


def test_acquisition_rejects_configured_target_missing_from_index(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.json"
    source_root = tmp_path / "source"
    _config(config)
    responses = _responses()
    responses[tournament_index_url(2026, page=0)] = _raw(
        {
            "pageInfo": {"page": 0, "pageSize": 100},
            "content": [],
        }
    )

    with pytest.raises(
        ValueError,
        match="configured WTA tournaments absent",
    ):
        acquire_wta_sources(
            config_path=config,
            source_root=source_root,
            observed_at="2026-09-22T12:00:00+00:00",
            fetcher=lambda url: responses[url],
        )


def test_acquisition_rejects_tournament_identity_mismatch(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.json"
    source_root = tmp_path / "source"
    _config(config)
    responses = _responses()
    responses[tournament_url(1152, 2026)] = _raw(
        {
            "tournamentGroup": {"id": 9999},
            "year": 2026,
            "surface": "Hard",
        }
    )

    with pytest.raises(ValueError, match="identity mismatch"):
        acquire_wta_sources(
            config_path=config,
            source_root=source_root,
            observed_at="2026-09-22T12:00:00+00:00",
            fetcher=lambda url: responses[url],
        )


def test_acquisition_paginates_tournament_index(
    tmp_path: Path,
) -> None:
    config = tmp_path / "config.json"
    source_root = tmp_path / "source"
    _config(config)
    responses = _responses()
    filler = {
        "tournamentGroup": {"id": 9000},
        "year": 2026,
    }
    target = {
        "tournamentGroup": {"id": 1152},
        "year": 2026,
    }
    responses[tournament_index_url(2026, page=0)] = _raw(
        {
            "pageInfo": {"page": 0, "pageSize": 100},
            "content": [filler] * 100,
        }
    )
    responses[tournament_index_url(2026, page=1)] = _raw(
        {
            "pageInfo": {"page": 1, "pageSize": 100},
            "content": [target],
        }
    )

    manifest = acquire_wta_sources(
        config_path=config,
        source_root=source_root,
        observed_at="2026-09-22T12:00:00+00:00",
        fetcher=lambda url: responses[url],
    )

    assert len(manifest["index_records"]) == 2
    assert (
        source_root / "tournament-index-2026-page-1.json"
    ).is_file()
