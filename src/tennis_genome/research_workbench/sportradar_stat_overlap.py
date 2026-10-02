"""Retrospective compatibility audit of Sportradar versus pinned ATP stats."""

from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

import pandas as pd

from .sportradar_identity_candidates import normalize_name

_FIELDS = {
    "aces": "ace",
    "double_faults": "df",
    "first_serve_successful": "1stIn",
    "first_serve_points_won": "1stWon",
    "second_serve_points_won": "2ndWon",
}


def _pair(a: str, b: str) -> tuple[str, str]:
    return tuple(sorted((normalize_name(a), normalize_name(b))))


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _compare_season(
    *, season_dir: Path, tournament: str, canonical: pd.DataFrame
) -> dict[str, object]:
    pages = sorted(season_dir.glob("page-*-offset-*.json"))
    if not pages:
        raise ValueError(f"season has no retained summary pages: {season_dir.name}")
    summaries: list[dict[str, object]] = []
    for page in pages:
        payload = json.loads(page.read_bytes())
        if not isinstance(payload, dict) or not isinstance(payload.get("summaries"), list):
            raise ValueError("retained page is not a Season Summaries response")
        summaries.extend(payload["summaries"])
    cohort = canonical[canonical["tourney_name"].eq(tournament)]
    by_pair: dict[tuple[str, str], object] = {}
    for row in cohort.itertuples(index=False):
        key = _pair(row.winner_name, row.loser_name)
        if key in by_pair:
            raise ValueError("canonical tournament contains duplicate player pair")
        by_pair[key] = row
    counts: Counter[str] = Counter()
    seen: set[tuple[str, str]] = set()
    for summary in summaries:
        event = summary.get("sport_event", {})
        players = event.get("competitors", [])
        if len(players) != 2:
            continue
        key = _pair(players[0]["name"], players[1]["name"])
        reference = by_pair.get(key)
        if reference is None:
            continue
        if key in seen:
            raise ValueError("provider season contains duplicate canonical player pair")
        seen.add(key)
        counts["pair_matches"] += 1
        status = summary.get("sport_event_status", {})
        score = str(getattr(reference, "score", "") or "").upper()
        if (
            status.get("status") not in {"closed", "ended"}
            or str(status.get("winning_reason", "")).lower()
            in {"walkover", "retirement", "defaulted"}
            or any(token in score for token in ("RET", "W/O", "DEF"))
        ):
            counts["abnormal_or_nonterminal_skipped"] += 1
            continue
        provider_stats = summary.get("statistics", {}).get("totals", {}).get("competitors", [])
        if len(provider_stats) != 2:
            counts["matched_without_stats"] += 1
            continue
        by_id = {row["id"]: row.get("statistics", {}) for row in provider_stats}
        if len(by_id) != 2:
            raise ValueError("provider stats competitor IDs are nonunique")
        for player in players:
            side = (
                "w"
                if normalize_name(player["name"]) == normalize_name(reference.winner_name)
                else "l"
            )
            if (status.get("winner_id") == player["id"]) != (side == "w"):
                counts["winner_disagreement"] += 1
            values = by_id.get(player["id"])
            if values is None:
                raise ValueError("provider stats competitor ID differs from event")
            for source_field, canonical_field in _FIELDS.items():
                observed = values.get(source_field)
                baseline = getattr(reference, f"{side}_{canonical_field}")
                if observed is None or pd.isna(baseline):
                    continue
                counts[f"{source_field}_compared"] += 1
                if int(observed) == int(baseline):
                    counts[f"{source_field}_equal"] += 1
            won = values.get("service_points_won")
            lost = values.get("service_points_lost")
            baseline = getattr(reference, f"{side}_svpt")
            if won is not None and lost is not None and not pd.isna(baseline):
                counts["service_points_compared"] += 1
                if int(won) + int(lost) == int(baseline):
                    counts["service_points_equal"] += 1
    return {
        "season_id": season_dir.name.replace("_", ":"),
        "tournament": tournament,
        "provider_summary_count": len(summaries),
        "canonical_match_count": len(cohort),
        "page_sha256": {page.name: _hash(page) for page in pages},
        "response_headers_sha256": {
            page.with_suffix(".headers").name: _hash(page.with_suffix(".headers")) for page in pages
        },
        "counts": dict(sorted(counts.items())),
    }


def audit_stat_overlap(
    *, capture_root: Path, canonical_csv: Path, season_tournaments: dict[str, str]
) -> dict[str, object]:
    if not season_tournaments:
        raise ValueError("at least one season/tournament mapping is required")
    canonical = pd.read_csv(canonical_csv, low_memory=False)
    results = []
    total: Counter[str] = Counter()
    for season_id, tournament in sorted(season_tournaments.items()):
        if not season_id.startswith("sr:season:") or not tournament.strip():
            raise ValueError("season mapping is invalid")
        result = _compare_season(
            season_dir=capture_root / season_id.replace(":", "_"),
            tournament=tournament,
            canonical=canonical,
        )
        results.append(result)
        total.update(result["counts"])
    return {
        "schema": "sportradar-pinned-atp-stat-overlap-v1",
        "research_only": True,
        "canonical_csv_sha256": _hash(canonical_csv),
        "seasons": results,
        "total_counts": dict(sorted(total.items())),
        "mixed_source_stats_approved": False,
    }
