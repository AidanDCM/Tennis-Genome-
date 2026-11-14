"""Read-only diagnostics for WTA Web Shadow source-identity mismatches.

This module cannot settle a prediction, infer an outcome, or relax result gates.
The command-line entry point verifies pinned prediction hashes and official
source hashes using the existing WTA intake code before printing JSON.
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any

# This mirrors the *existing* legacy compiler interpretation for diagnostics;
# it is NOT an authoritative mapping of official WTA source round codes.
_LEGACY_ROUNDS = {
    "1": "F",
    "2": "SF",
    "3": "QF",
    "4": "R16",
    "5": "R32",
    "6": "R64",
    "7": "R128",
}


def _key(name: str) -> str:
    value = unicodedata.normalize("NFKD", name)
    value = "".join(c for c in value if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", value.lower())


def _pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((_key(a), _key(b))))


def _event_matches(row: dict[str, Any], tournament: dict[str, Any]) -> bool:
    event_id = row.get("EventID")
    year = row.get("EventYear")
    return (
        isinstance(event_id, str)
        and event_id.isascii()
        and event_id.isdecimal()
        and int(event_id) == int(tournament["group_id"])
        and type(year) is int
        and year == int(tournament["year"])
    )


def _main_singles(row: dict[str, Any]) -> bool:
    return row.get("DrawMatchType") == "S" and row.get("DrawLevelType") == "M"


def _row_pair(row: dict[str, Any]) -> tuple[str, str]:
    def player(side: str) -> str:
        first = row[f"PlayerNameFirst{side}"]
        last = row[f"PlayerNameLast{side}"]
        if not isinstance(first, str) or not isinstance(last, str):
            raise ValueError("source player identity is malformed")
        if not first.strip() or not last.strip():
            raise ValueError("source player identity is empty")
        return f"{first} {last}"

    return _pair(player("A"), player("B"))


def _evidence(row: dict[str, Any]) -> dict[str, Any]:
    token = str(row.get("RoundID", "")).strip()
    return {
        "source_match_id": row.get("MatchID"),
        "source_round_id_raw": token,
        "legacy_compiler_round_interpretation": _LEGACY_ROUNDS.get(token),
        "source_match_state": row.get("MatchState"),
        "source_match_timestamp_raw": row.get("MatchTimeStamp"),
        "source_last_updated_raw": row.get("LastUpdated"),
    }


def diagnose_match(
    pending: dict[str, Any], rows: list[dict[str, Any]]
) -> dict[str, Any]:
    """Describe candidates only; never return a settlement or winner."""
    tournament = pending["tournament"]
    expected_pair = _pair(pending["player_a"], pending["player_b"])
    record: dict[str, Any] = {
        "match_id": pending["match_id"],
        "prediction_path": pending["prediction_path"],
        "prediction_sha256": pending["prediction_sha256"],
        "prediction_round": pending["round"],
        "scheduled_start": pending["scheduled_start"].isoformat(),
        "source_match_id_from_prediction": pending["source_match_id"],
        "diagnostic_only": True,
        "production_eligible": False,
        "candidate_count": 0,
    }

    source_id = pending["source_match_id"]
    if source_id is not None:
        # NEVER fall back to a similarly named pair after an exact ID conflict.
        exact = [
            row for row in rows
            if str(row.get("MatchID", "")).strip() == source_id
        ]
        record["candidate_count"] = len(exact)
        if len(exact) != 1:
            record["reason"] = (
                "exact_id_absent" if not exact else "exact_id_ambiguous"
            )
            return record
        row = exact[0]
        record.update(_evidence(row))
        if not _event_matches(row, tournament):
            record["reason"] = "exact_id_event_conflict"
        elif not _main_singles(row):
            record["reason"] = "exact_id_draw_conflict"
        elif _row_pair(row) != expected_pair:
            record["reason"] = "exact_id_player_conflict"
        else:
            # Identity matches do not establish round, chronology or outcome.
            record["reason"] = "exact_id_identity_candidate_only"
        return record

    candidates = [
        row for row in rows
        if _event_matches(row, tournament)
        and _main_singles(row)
        and _row_pair(row) == expected_pair
    ]
    record["candidate_count"] = len(candidates)
    if len(candidates) != 1:
        record["reason"] = (
            "legacy_pair_absent" if not candidates else "legacy_pair_ambiguous"
        )
        return record
    row = candidates[0]
    record.update(_evidence(row))
    record["reason"] = (
        "legacy_strict_round_candidate_only"
        if record["legacy_compiler_round_interpretation"] == pending["round"]
        else "legacy_round_discrepancy"
    )
    return record


def diagnose_pending(
    *,
    config_path: Path,
    scorecard_path: Path,
    acquisition_manifest_path: Path,
    source_root: Path,
    repo_root: Path,
    observed_at: str,
) -> dict[str, Any]:
    """Verify immutable inputs, then inspect candidates without writing files."""
    from scripts.web_shadow_wta_result_core import (
        _configured_tournaments,
        _load_json,
        _parse_time,
        _pending_predictions,
        _verify_acquisition,
    )

    _parse_time(observed_at, field="observed_at")
    tournaments = _configured_tournaments(_load_json(config_path))
    sources = _verify_acquisition(
        manifest_path=acquisition_manifest_path,
        source_root=source_root.resolve(),
        tournaments=tournaments,
        observed_at=observed_at,
    )
    by_tournament = {
        (int(s["group_id"]), int(s["year"])): s for s in sources
    }
    pending = _pending_predictions(
        scorecard_path=scorecard_path,
        repo_root=repo_root.resolve(),
        tournaments=tournaments,
    )
    diagnostics: list[dict[str, Any]] = []
    for item in sorted(pending, key=lambda x: x["match_id"]):
        t = item["tournament"]
        src = by_tournament[(int(t["group_id"]), int(t["year"]))]
        diag = diagnose_match(item, src["matches"])
        diag["source_url"] = src["matches_source_url"]
        diag["source_sha256"] = src["matches_sha256"]
        diagnostics.append(diag)
    return {
        "schema_version": "tennis-genome-wta-pending-diagnostic-v1",
        "production_eligible": False,
        "diagnostic_only": True,
        "observed_at": observed_at,
        "verified_tournament_source_count": len(sources),
        "pending_prediction_count": len(pending),
        "reason_counts": dict(sorted(Counter(
            d["reason"] for d in diagnostics
        ).items())),
        "diagnostics": diagnostics,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in (
        "config", "scorecard", "acquisition-manifest", "source-root", "repo-root"
    ):
        parser.add_argument(f"--{flag}", required=True, type=Path)
    parser.add_argument("--observed-at", required=True)
    args = parser.parse_args()
    print(json.dumps(
        diagnose_pending(
            config_path=args.config,
            scorecard_path=args.scorecard,
            acquisition_manifest_path=args.acquisition_manifest,
            source_root=args.source_root,
            repo_root=args.repo_root,
            observed_at=args.observed_at,
        ),
        indent=2,
        sort_keys=True,
        allow_nan=False,
    ))


if __name__ == "__main__":
    main()
