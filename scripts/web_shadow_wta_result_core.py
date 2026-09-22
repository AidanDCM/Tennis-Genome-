from __future__ import annotations

import hashlib
import json
import re
import shutil
import tempfile
import unicodedata
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from scripts.freeze_web_shadow_artifact import _canonical_sha256

_CONFIG_SCHEMA = "tennis-genome-web-shadow-intake-config-v1"
_SCORECARD_SCHEMA = "tennis-genome-web-shadow-scorecard-v1"
_RESULT_SCHEMA = "tennis-genome-web-shadow-public-result-v1"
_BATCH_SCHEMA = "tennis-genome-web-shadow-result-batch-v1"
_MANIFEST_SCHEMA = "tennis-genome-web-shadow-wta-result-intake-v1"
_ACQUISITION_SCHEMA = "tennis-genome-web-shadow-wta-acquisition-v1"
_ROUND_ID_MAP = {
    1: "F",
    2: "SF",
    3: "QF",
    4: "R16",
    5: "R32",
    6: "R64",
    7: "R128",
}


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON must contain an object: {path}")
    return payload


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            payload,
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
            allow_nan=False,
        )
        + "\n",
        encoding="utf-8",
    )


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_time(value: object, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty ISO-8601 string")
    try:
        parsed = datetime.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError(f"{field} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return parsed


def _text(value: object, *, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be a non-empty string")
    return value.strip()


def _integer(value: object, *, field: str) -> int:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be an integer")
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be an integer") from exc


def _slug(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    normalized = "".join(
        char for char in normalized if not unicodedata.combining(char)
    )
    result = re.sub(r"[^a-z0-9]+", "-", normalized.lower()).strip("-")
    if not result:
        raise ValueError("cannot build an empty slug")
    return result


def _name_key(value: str) -> str:
    return _slug(value).replace("-", "")


def _player_name(row: dict[str, Any], side: str) -> str:
    first = _text(row.get(f"PlayerNameFirst{side}"), field=f"PlayerNameFirst{side}")
    last = _text(row.get(f"PlayerNameLast{side}"), field=f"PlayerNameLast{side}")
    return f"{first} {last}"


def _player_pair(player_a: str, player_b: str) -> tuple[str, str]:
    return tuple(sorted((_name_key(player_a), _name_key(player_b))))


def _status(row: dict[str, Any]) -> str:
    if row.get("MatchState") != "F":
        raise ValueError("cannot classify a non-finished WTA row")
    evidence = " ".join(
        str(row.get(field, ""))
        for field in ("ResultString", "ScoreString", "Message")
    ).lower()
    if re.search(r"(?:\bw/o\b|\bwalkover\b)", evidence):
        return "WALKOVER"
    if re.search(r"(?:\bret\.|\bretired\b|\bretirement\b)", evidence):
        return "RETIREMENT"
    if re.search(r"(?:\bdefaulted\b|\bdefault\b|\bdef\.\b)", evidence):
        return "DEFAULTED"
    return "COMPLETED"


def _score(row: dict[str, Any], *, status: str) -> str:
    raw = row.get("ScoreString")
    if isinstance(raw, str) and raw.strip():
        return re.sub(r"\s*,\s*", " ", raw.strip())
    if status == "WALKOVER":
        return "W/O"
    if status == "DEFAULTED":
        return "DEFAULT"
    result = row.get("ResultString")
    if isinstance(result, str) and result.strip():
        return result.strip()
    raise ValueError("finished WTA result lacks score evidence")


def _configured_tournaments(config: dict[str, Any]) -> list[dict[str, Any]]:
    if config.get("schema_version") != _CONFIG_SCHEMA:
        raise ValueError("unsupported Web Shadow intake config schema")
    if config.get("production_eligible") is not False:
        raise ValueError("Web Shadow intake config must remain non-production")
    tournaments = config.get("tournaments")
    if not isinstance(tournaments, list) or not tournaments:
        raise ValueError("intake config must define tournaments")

    result: list[dict[str, Any]] = []
    identities: set[tuple[int, int]] = set()
    tournament_ids: set[str] = set()
    for item in tournaments:
        if not isinstance(item, dict):
            raise ValueError("intake tournament entries must be objects")
        group_id = _integer(item.get("group_id"), field="group_id")
        year = _integer(item.get("year"), field="year")
        slug = _text(item.get("slug"), field="slug")
        tournament_id = _text(item.get("tournament_id"), field="tournament_id")
        if slug != _slug(slug):
            raise ValueError("configured tournament slug is not canonical")
        if (group_id, year) in identities or tournament_id in tournament_ids:
            raise ValueError("configured WTA tournament identities must be unique")
        identities.add((group_id, year))
        tournament_ids.add(tournament_id)
        result.append(
            {
                "group_id": group_id,
                "year": year,
                "slug": slug,
                "tournament_id": tournament_id,
            }
        )
    return result


def _verify_acquisition(
    *,
    manifest_path: Path,
    source_root: Path,
    tournaments: list[dict[str, Any]],
    observed_at: str,
) -> list[dict[str, Any]]:
    manifest = _load_json(manifest_path)
    if manifest.get("schema_version") != _ACQUISITION_SCHEMA:
        raise ValueError("unsupported WTA acquisition manifest schema")
    if manifest.get("production_eligible") is not False:
        raise ValueError("WTA acquisition escaped non-production isolation")
    if manifest.get("observed_at") != observed_at:
        raise ValueError("WTA acquisition observation time mismatch")
    records = manifest.get("source_records")
    if not isinstance(records, list):
        raise ValueError("WTA acquisition manifest lacks source_records")

    by_identity: dict[tuple[int, int], dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("WTA acquisition source record must be an object")
        identity = (
            _integer(record.get("group_id"), field="source group_id"),
            _integer(record.get("year"), field="source year"),
        )
        if identity in by_identity:
            raise ValueError("duplicate WTA acquisition source identity")
        by_identity[identity] = record

    verified: list[dict[str, Any]] = []
    for tournament in tournaments:
        identity = int(tournament["group_id"]), int(tournament["year"])
        record = by_identity.get(identity)
        if record is None:
            raise ValueError(f"missing WTA acquisition source: {identity}")
        matches_filename = _text(
            record.get("matches_filename"),
            field="matches_filename",
        )
        matches_path = source_root / matches_filename
        if not matches_path.is_file():
            raise FileNotFoundError(f"missing retained WTA matches: {matches_path}")
        if _sha256_file(matches_path) != record.get("matches_sha256"):
            raise ValueError("retained WTA matches SHA differs from acquisition manifest")
        payload = _load_json(matches_path)
        matches = payload.get("matches")
        if not isinstance(matches, list) or not all(
            isinstance(row, dict) for row in matches
        ):
            raise ValueError("retained WTA matches payload is invalid")
        verified.append(
            {
                **tournament,
                "matches_path": matches_path,
                "matches_source_url": _text(
                    record.get("matches_source_url"),
                    field="matches_source_url",
                ),
                "matches_sha256": record["matches_sha256"],
                "matches": matches,
            }
        )
    return verified


def _pending_predictions(
    *,
    scorecard_path: Path,
    repo_root: Path,
    tournaments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    scorecard = _load_json(scorecard_path)
    if scorecard.get("schema_version") != _SCORECARD_SCHEMA:
        raise ValueError("unsupported Web Shadow scorecard schema")
    if scorecard.get("production_eligible") is not False:
        raise ValueError("Web Shadow scorecard must remain non-production")

    tournament_by_id = {
        str(item["tournament_id"]): item for item in tournaments
    }
    pending: list[dict[str, Any]] = []
    for slate in scorecard.get("slates", []):
        if not isinstance(slate, dict):
            raise ValueError("scorecard slate entries must be objects")
        slate_id = _text(slate.get("slate_id"), field="slate_id")
        entries = slate.get("predictions")
        if not isinstance(entries, list):
            raise ValueError("scorecard slate predictions must be a list")
        for entry in entries:
            if not isinstance(entry, dict):
                raise ValueError("scorecard prediction entry must be an object")
            if entry.get("status") != "PENDING":
                continue
            prediction_value = _text(
                entry.get("prediction_path"),
                field="prediction_path",
            )
            prediction_path = repo_root / prediction_value
            if not prediction_path.is_file():
                raise FileNotFoundError(f"pending prediction is missing: {prediction_value}")
            prediction = _load_json(prediction_path)
            observed_sha = str(prediction.get("record_sha256", "")).strip()
            unsigned = dict(prediction)
            unsigned.pop("record_sha256", None)
            if _canonical_sha256(unsigned) != observed_sha:
                raise ValueError("pending prediction record digest mismatch")
            expected_sha = _text(
                entry.get("prediction_record_sha256"),
                field="prediction_record_sha256",
            )
            if observed_sha != expected_sha:
                raise ValueError("pending prediction SHA differs from scorecard")
            fixture = prediction.get("fixture")
            if not isinstance(fixture, dict):
                raise ValueError("pending prediction fixture is missing")
            match_id = _text(entry.get("match_id"), field="match_id")
            if fixture.get("match_id") != match_id:
                raise ValueError("pending prediction match identity mismatch")
            tournament_id = _text(
                fixture.get("tournament_id"),
                field="tournament_id",
            )
            tournament = tournament_by_id.get(tournament_id)
            if tournament is None:
                raise ValueError(
                    f"pending WTA prediction tournament is not configured: {tournament_id}"
                )
            player_a = _text(fixture.get("player_a"), field="player_a")
            player_b = _text(fixture.get("player_b"), field="player_b")
            round_name = _text(fixture.get("round"), field="round")
            start = _parse_time(
                fixture.get("scheduled_start"),
                field="scheduled_start",
            )

            source_match_id: str | None = None
            parts = match_id.split(":")
            if (
                len(parts) == 5
                and parts[:2] == ["web", "wta"]
                and parts[2].isdigit()
                and parts[3].isdigit()
                and int(parts[2]) == int(tournament["group_id"])
                and int(parts[3]) == int(tournament["year"])
            ):
                source_match_id = parts[4]

            pending.append(
                {
                    "slate_id": slate_id,
                    "match_id": match_id,
                    "prediction_path": prediction_value,
                    "prediction_sha256": observed_sha,
                    "tournament": tournament,
                    "player_a": player_a,
                    "player_b": player_b,
                    "player_pair": _player_pair(player_a, player_b),
                    "round": round_name,
                    "scheduled_start": start,
                    "source_match_id": source_match_id,
                }
            )
    return pending


def _row_identity(
    row: dict[str, Any],
    *,
    tournament: dict[str, Any],
) -> dict[str, Any] | None:
    if row.get("DrawMatchType") != "S" or row.get("DrawLevelType") != "M":
        return None
    event_id = _text(row.get("EventID"), field="EventID")
    event_year = _integer(row.get("EventYear"), field="EventYear")
    if event_id != str(tournament["group_id"]) or event_year != int(
        tournament["year"]
    ):
        raise ValueError("WTA result row tournament identity mismatch")
    source_match_id = _text(row.get("MatchID"), field="MatchID")
    round_id = _integer(row.get("RoundID"), field="RoundID")
    round_name = _ROUND_ID_MAP.get(round_id)
    if round_name is None:
        return None
    player_a = _player_name(row, "A")
    player_b = _player_name(row, "B")
    return {
        "row": row,
        "source_match_id": source_match_id,
        "round": round_name,
        "player_a": player_a,
        "player_b": player_b,
        "player_pair": _player_pair(player_a, player_b),
    }


def _match_row(
    pending: dict[str, Any],
    rows: list[dict[str, Any]],
) -> dict[str, Any] | None:
    identities = [
        identity
        for row in rows
        if (identity := _row_identity(row, tournament=pending["tournament"]))
        is not None
    ]
    source_match_id = pending["source_match_id"]
    if source_match_id is not None:
        matches = [
            item
            for item in identities
            if item["source_match_id"] == source_match_id
        ]
        if len(matches) != 1:
            if not matches:
                return None
            raise ValueError("official WTA MatchID is not unique in retained source")
        match = matches[0]
        if match["player_pair"] != pending["player_pair"]:
            raise ValueError("official WTA MatchID player identity mismatch")
        if match["round"] != pending["round"]:
            raise ValueError("official WTA MatchID round identity mismatch")
        return match

    matches = [
        item
        for item in identities
        if item["player_pair"] == pending["player_pair"]
        and item["round"] == pending["round"]
    ]
    if len(matches) > 1:
        raise ValueError(
            "legacy Web Shadow result identity is ambiguous in official WTA source"
        )
    return matches[0] if matches else None


def _result_record(
    *,
    pending: dict[str, Any],
    match: dict[str, Any],
    source_url: str,
    observed: datetime,
) -> tuple[dict[str, Any], dict[str, Any]] | None:
    row = match["row"]
    if row.get("MatchState") != "F":
        return None
    if observed <= pending["scheduled_start"].astimezone(UTC):
        raise ValueError("finished WTA result was observed before scheduled start")
    winner_code = str(row.get("Winner", "")).strip()
    if winner_code == "2":
        winner = match["player_a"]
    elif winner_code == "3":
        winner = match["player_b"]
    else:
        raise ValueError("finished WTA result has unsupported Winner code")
    status = _status(row)
    score = _score(row, status=status)
    result = {
        "schema_version": _RESULT_SCHEMA,
        "match_id": pending["match_id"],
        "prediction_path": pending["prediction_path"],
        "expected_prediction_record_sha256": pending["prediction_sha256"],
        "winner": winner,
        "status": status,
        "score": score,
        "result_source_url": source_url,
        "result_observed_at": observed.isoformat(),
        "production_eligible": False,
    }
    evidence = {
        "match_id": pending["match_id"],
        "source_match_id": match["source_match_id"],
        "prediction_path": pending["prediction_path"],
        "prediction_record_sha256": pending["prediction_sha256"],
        "winner": winner,
        "status": status,
        "score": score,
        "source_last_updated": row.get("LastUpdated"),
        "source_result_string": row.get("ResultString"),
    }
    return result, evidence


def build_wta_web_shadow_results(
    *,
    config_path: Path,
    scorecard_path: Path,
    acquisition_manifest_path: Path,
    source_root: Path,
    repo_root: Path,
    observed_at: str,
    snapshot_id: str,
) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    source_root = source_root.resolve()
    observed = _parse_time(observed_at, field="observed_at").astimezone(UTC)
    if snapshot_id != _slug(snapshot_id):
        raise ValueError("snapshot_id must be a canonical slug")

    config = _load_json(config_path)
    tournaments = _configured_tournaments(config)
    sources = _verify_acquisition(
        manifest_path=acquisition_manifest_path,
        source_root=source_root,
        tournaments=tournaments,
        observed_at=observed_at,
    )
    source_by_identity = {
        (int(item["group_id"]), int(item["year"])): item for item in sources
    }
    pending = _pending_predictions(
        scorecard_path=scorecard_path,
        repo_root=repo_root,
        tournaments=tournaments,
    )

    completed: list[tuple[dict[str, Any], dict[str, Any]]] = []
    unresolved = 0
    unfinished = 0
    for item in sorted(
        pending,
        key=lambda row: (
            row["scheduled_start"],
            row["slate_id"],
            row["match_id"],
        ),
    ):
        tournament = item["tournament"]
        source = source_by_identity[
            (int(tournament["group_id"]), int(tournament["year"]))
        ]
        match = _match_row(item, source["matches"])
        if match is None:
            unresolved += 1
            continue
        compiled = _result_record(
            pending=item,
            match=match,
            source_url=str(source["matches_source_url"]),
            observed=observed,
        )
        if compiled is None:
            unfinished += 1
            continue
        completed.append(compiled)

    if not completed:
        return {
            "schema_version": _MANIFEST_SCHEMA,
            "production_eligible": False,
            "snapshot_id": snapshot_id,
            "observed_at": observed.isoformat(),
            "pending_prediction_count": len(pending),
            "result_count": 0,
            "unresolved_prediction_count": unresolved,
            "unfinished_prediction_count": unfinished,
            "result_paths": [],
            "results": [],
        }

    evidence_root = repo_root / "web-shadow" / "result-evidence" / snapshot_id
    if evidence_root.exists():
        raise FileExistsError(f"result evidence snapshot already exists: {snapshot_id}")

    with tempfile.TemporaryDirectory(prefix="wta-result-stage-") as temp_name:
        staged = Path(temp_name)
        staged_results = staged / "results"
        staged_evidence = staged / "evidence"
        staged_results.mkdir(parents=True)
        staged_evidence.mkdir(parents=True)

        result_paths: list[str] = []
        evidence_rows: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        for result, evidence in completed:
            stem = Path(str(result["prediction_path"])).stem
            suffix = str(result["expected_prediction_record_sha256"])[:10]
            filename = f"{observed.date().isoformat()}-{stem}-{suffix}.json"
            relative = Path("web-shadow/results") / filename
            relative_value = relative.as_posix()
            if relative_value in seen_paths or (repo_root / relative).exists():
                raise ValueError(f"result path collision: {relative_value}")
            seen_paths.add(relative_value)
            _write_json(staged_results / filename, result)
            result_paths.append(relative_value)
            evidence_rows.append({**evidence, "result_path": relative_value})

        shutil.copytree(source_root, staged_evidence / "sources")
        shutil.copyfile(
            acquisition_manifest_path,
            staged_evidence / "acquisition-manifest.json",
        )
        source_records = [
            {
                "slug": source["slug"],
                "group_id": source["group_id"],
                "year": source["year"],
                "matches_source_url": source["matches_source_url"],
                "matches_sha256": source["matches_sha256"],
                "raw_match_count": len(source["matches"]),
            }
            for source in sources
        ]
        manifest = {
            "schema_version": _MANIFEST_SCHEMA,
            "production_eligible": False,
            "snapshot_id": snapshot_id,
            "observed_at": observed.isoformat(),
            "pending_prediction_count": len(pending),
            "result_count": len(result_paths),
            "unresolved_prediction_count": unresolved,
            "unfinished_prediction_count": unfinished,
            "source_records": source_records,
            "result_paths": result_paths,
            "results": evidence_rows,
        }
        _write_json(staged_evidence / "result-intake-manifest.json", manifest)
        active_results = {
            "schema_version": _BATCH_SCHEMA,
            "result_paths": result_paths,
        }
        _write_json(staged / "active-results.json", active_results)

        results_root = repo_root / "web-shadow" / "results"
        results_root.mkdir(parents=True, exist_ok=True)
        copied_results: list[Path] = []
        try:
            for path in sorted(staged_results.glob("*.json")):
                destination = results_root / path.name
                shutil.copyfile(path, destination)
                copied_results.append(destination)
            evidence_root.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(staged_evidence, evidence_root)
            shutil.copyfile(
                staged / "active-results.json",
                repo_root / "web-shadow" / "active-results.json",
            )
        except Exception:
            for path in copied_results:
                path.unlink(missing_ok=True)
            shutil.rmtree(evidence_root, ignore_errors=True)
            raise

    return manifest
