"""Retain exact WTA public match statistics for frozen API-Tennis sample cases.

This checks post-match source accuracy only. WTA MatchTimeStamp is not certified
as actual start, and the data is not admitted into the production predictor.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import unicodedata
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.audit_api_tennis_retained_history import verify_capture
from tennis_genome.research_workbench.api_tennis_enrichment import (
    api_tennis_point_count_issues,
    parse_api_tennis_match_enrichment,
)

API = "https://api.wtatennis.com/tennis"
HEADERS = {"User-Agent": "Tennis-Genome-source-audit/1.0", "Origin": "https://www.wtatennis.com"}


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _surname(value: str) -> str:
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    return " ".join(value.casefold().replace("-", " ").split())


def _check_match(provider: dict[str, Any], official: dict[str, Any], entry: dict[str, Any]) -> None:
    if official.get("EventID") != str(entry["tournament_id"]):
        raise ValueError("official tournament identity mismatch")
    if official.get("MatchID") != entry["match_id"]:
        raise ValueError("official match identity mismatch")
    if official.get("DrawMatchType") != "S" or official.get("MatchState") != "F":
        raise ValueError("official match is not finished singles")
    if official.get("MatchTimeStamp", "")[:10] != provider["event_date"]:
        raise ValueError("official and provider event dates disagree")
    expected_winner = {"First Player": "2", "Second Player": "3"}.get(provider["event_winner"])
    if official.get("Winner") != expected_winner:
        raise ValueError("official and provider winners disagree")
    parsed = parse_api_tennis_match_enrichment(provider)
    if api_tennis_point_count_issues(parsed):
        raise ValueError("sampled provider point statistics no longer pass internal gate")
    expected_draw = "Q" if parsed.qualification else "M"
    if official.get("DrawLevelType") != expected_draw:
        raise ValueError("official and provider draw levels disagree")
    for source_side, official_side in (("first", "A"), ("second", "B")):
        abbreviated = provider[f"event_{source_side}_player"]
        parts = re.fullmatch(r"([A-Za-z])\.(?:\s+[A-Za-z]\.)*\s+(.+)", abbreviated)
        if parts is None:
            raise ValueError("provider player name cannot be compared safely")
        initial, surname = parts.groups()
        first_name = official[f"PlayerNameFirst{official_side}"]
        last_name = official[f"PlayerNameLast{official_side}"]
        if _surname(surname) != _surname(last_name) or not first_name.casefold().startswith(
            initial.casefold()
        ):
            raise ValueError("official and provider player names disagree")


def _reference(
    provider: dict[str, Any],
    official: dict[str, Any],
    stats: list[dict[str, Any]],
    entry: dict[str, Any],
) -> dict[str, Any]:
    _check_match(provider, official, entry)
    match_rows = [row for row in stats if row.get("setnum") == 0]
    if len(match_rows) != 1:
        raise ValueError("official full-match stat row must be unique")
    row = match_rows[0]
    if row.get("eventid") != str(entry["tournament_id"]) or row.get("matchid") != entry[
        "match_id"
    ]:
        raise ValueError("official statistic event identity mismatch")
    players = []
    for source_side, official_side in (("first", "a"), ("second", "b")):
        won = row[f"ptstotwonserv{official_side}"]
        total = row[f"totservplayed{official_side}"]
        if type(won) is not int or type(total) is not int or not 0 <= won <= total:
            raise ValueError("official service-point count invalid")
        players.append(
            {
                "provider_player_key": provider[f"{source_side}_player_key"],
                "provider_player_name": provider[f"event_{source_side}_player"],
                "official_service_points_won": won,
                "official_service_points_total": total,
            }
        )
    return {
        "event_key": provider["event_key"],
        "event_date": provider["event_date"],
        "tour_event_type": "Wta Singles",
        "official_url": (
            f"https://www.wtatennis.com/tournaments/{entry['tournament_id']}/"
            f"{entry['slug']}/2026/scores/{entry['match_id']}"
        ),
        "players": players,
    }


def _get_json(url: str) -> tuple[bytes, object, str]:
    request = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(request, timeout=25) as response:
        if response.status != 200 or response.headers.get_content_type() != "application/json":
            raise ValueError("official API did not return JSON 200")
        raw = response.read()
    return raw, json.loads(raw), datetime.now(UTC).isoformat()


def capture(
    *, sample_path: Path, mapping_path: Path, capture_dirs: list[Path], output_dir: Path
) -> dict[str, Any]:
    if output_dir.exists():
        raise FileExistsError(output_dir)
    sample_raw, mapping_raw = sample_path.read_bytes(), mapping_path.read_bytes()
    sample, mapping = json.loads(sample_raw), json.loads(mapping_raw)
    if sample.get("schema_version") != "api-tennis-official-source-sample-v1":
        raise ValueError("unrecognized frozen sample")
    selected = {row["event_key"]: row for row in sample["selected"]}
    if len(selected) != sample["selected_count"]:
        raise ValueError("duplicate sample event")
    if len({entry["event_key"] for entry in mapping}) != len(mapping):
        raise ValueError("duplicate mapped event")
    provider_rows: dict[int, dict[str, Any]] = {}
    verified_captures = {}
    for root in capture_dirs:
        evidence, rows = verify_capture(root)
        verified_captures[evidence["workflow_run_id"]] = evidence
        for row in rows:
            if row["event_key"] in provider_rows:
                raise ValueError("duplicate provider event")
            provider_rows[row["event_key"]] = row
    captured: dict[str, bytes] = {}
    requests = []
    references = []
    tournament_matches = {}
    for entry in mapping:
        event_key = entry["event_key"]
        selected_row = selected.get(event_key)
        provider = provider_rows.get(event_key)
        if selected_row is None or provider is None or selected_row["tour"] != "WTA":
            raise ValueError("mapping event absent from frozen WTA sample")
        if selected_row["capture_workflow_run_id"] not in verified_captures:
            raise ValueError("provider event capture was not verified")
        if provider["event_date"] != selected_row["event_date"]:
            raise ValueError("frozen sample date differs from verified capture")
        tournament_id, match_id = entry["tournament_id"], entry["match_id"]
        if tournament_id not in tournament_matches:
            url = f"{API}/tournaments/{tournament_id}/2026/matches"
            raw, payload, observed = _get_json(url)
            if not isinstance(payload, dict) or not isinstance(payload.get("matches"), list):
                raise ValueError("official tournament match list malformed")
            name = f"wta-tournament-{tournament_id}-2026-matches.json"
            captured[name] = raw
            requests.append(
                {"url": url, "filename": name, "observed_at_utc": observed, "sha256": _sha(raw)}
            )
            tournament_matches[tournament_id] = payload["matches"]
        matches = [
            row for row in tournament_matches[tournament_id] if row.get("MatchID") == match_id
        ]
        if len(matches) != 1:
            raise ValueError("mapped official match is not unique")
        url = f"{API}/tournaments/{tournament_id}/2026/matches/{match_id}/stats"
        raw, payload, observed = _get_json(url)
        if not isinstance(payload, list):
            raise ValueError("official statistics response malformed")
        name = f"wta-{tournament_id}-2026-{match_id}-stats.json"
        if name in captured:
            raise ValueError("duplicate official stat request")
        captured[name] = raw
        requests.append(
            {"url": url, "filename": name, "observed_at_utc": observed, "sha256": _sha(raw)}
        )
        references.append(_reference(provider, matches[0], payload, entry))
    output_dir.mkdir(parents=True)
    for name, raw in captured.items():
        (output_dir / name).write_bytes(raw)
    reference_raw = (json.dumps(references, indent=2, sort_keys=True) + "\n").encode()
    (output_dir / "reference.json").write_bytes(reference_raw)
    manifest = {
        "schema_version": "tennis-genome-wta-official-fixed-sample-capture-v1",
        "sample_sha256": _sha(sample_raw),
        "mapping_sha256": _sha(mapping_raw),
        "reference_sha256": _sha(reference_raw),
        "verified_provider_captures": list(verified_captures.values()),
        "requests": requests,
        "api_tennis_provider_request_count": 0,
        "official_public_request_count": len(requests),
        "source_admission": "RESEARCH_ONLY",
        "official_match_timestamp_certified_as_actual_start": False,
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def verify_official_capture(root: Path) -> dict[str, Any]:
    """Recheck retained official bytes and references without network access."""
    manifest = json.loads((root / "manifest.json").read_bytes())
    if manifest.get("schema_version") != "tennis-genome-wta-official-fixed-sample-capture-v1":
        raise ValueError("unsupported official capture manifest")
    requests = manifest["requests"]
    if len(requests) != manifest["official_public_request_count"]:
        raise ValueError("official request count mismatch")
    if manifest["api_tennis_provider_request_count"] != 0:
        raise ValueError("official capture must not spend API-Tennis credits")
    seen = set()
    for request in requests:
        name = request["filename"]
        if name in seen or Path(name).name != name:
            raise ValueError("duplicate or unsafe official capture filename")
        seen.add(name)
        if not request["url"].startswith(API + "/"):
            raise ValueError("unexpected official API URL")
        if _sha((root / name).read_bytes()) != request["sha256"]:
            raise ValueError("official raw file hash mismatch")
    reference_raw = (root / "reference.json").read_bytes()
    if _sha(reference_raw) != manifest["reference_sha256"]:
        raise ValueError("official reference hash mismatch")
    if not isinstance(json.loads(reference_raw), list):
        raise ValueError("official reference must be a list")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--capture-dir", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = capture(
        sample_path=args.sample,
        mapping_path=args.mapping,
        capture_dirs=args.capture_dir,
        output_dir=args.output_dir,
    )
    verify_official_capture(args.output_dir)
    print(json.dumps({"official_public_request_count": result["official_public_request_count"]}))


if __name__ == "__main__":
    main()
