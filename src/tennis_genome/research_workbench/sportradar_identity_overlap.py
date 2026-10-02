"""Corroborate provider identities with pinned same-match ATP evidence offline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from .sportradar_identity_candidates import normalize_name


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def corroborate_overlap_identities(
    *, capture_root: Path, canonical_csv: Path, season_tournaments: dict[str, str]
) -> dict[str, object]:
    """Return reviewed evidence candidates; never emit an authoritative crosswalk."""
    if not season_tournaments:
        raise ValueError("season mapping is empty")
    frame = pd.read_csv(canonical_csv, dtype={"winner_id": str, "loser_id": str})
    evidence: dict[str, dict[str, object]] = {}
    canonical_to_provider: dict[str, str] = {}
    page_hashes: dict[str, str] = {}
    joined = 0
    excluded = 0
    for season_id, tournament in sorted(season_tournaments.items()):
        if not season_id.startswith("sr:season:") or not tournament.strip():
            raise ValueError("invalid season mapping")
        cohort = frame.loc[frame["tourney_name"].eq(tournament)]
        by_pair: dict[tuple[str, str], object] = {}
        for row in cohort.itertuples(index=False):
            pair = tuple(sorted((normalize_name(row.winner_name), normalize_name(row.loser_name))))
            if pair in by_pair:
                raise ValueError("duplicate canonical player pair in tournament")
            by_pair[pair] = row
        pages = sorted((capture_root / season_id.replace(":", "_")).glob("page-*-offset-*.json"))
        if not pages:
            raise ValueError(f"missing retained season pages: {season_id}")
        seen_pairs: set[tuple[str, str]] = set()
        for page in pages:
            page_hashes[str(page.relative_to(capture_root))] = _sha256(page)
            payload = json.loads(page.read_bytes())
            if not isinstance(payload, dict) or not isinstance(payload.get("summaries"), list):
                raise ValueError("retained page is not a summaries response")
            for summary in payload["summaries"]:
                event = summary.get("sport_event", {})
                context = event.get("sport_event_context", {})
                if (
                    context.get("category", {}).get("id") != "sr:category:3"
                    or context.get("season", {}).get("id") != season_id
                    or context.get("competition", {}).get("type") != "singles"
                ):
                    raise ValueError("provider summary is outside requested ATP singles season")
                players = event.get("competitors", [])
                if len(players) != 2 or any(not p.get("id") or not p.get("name") for p in players):
                    continue
                names = [normalize_name(p["name"]) for p in players]
                pair = tuple(sorted(names))
                reference = by_pair.get(pair)
                if reference is None:
                    continue
                if pair in seen_pairs:
                    raise ValueError("duplicate provider player pair in tournament")
                seen_pairs.add(pair)
                status = summary.get("sport_event_status", {})
                if status.get("status") not in {"closed", "ended"}:
                    excluded += 1
                    continue
                expected = {
                    normalize_name(reference.winner_name): str(reference.winner_id),
                    normalize_name(reference.loser_name): str(reference.loser_id),
                }
                if len(expected) != 2 or len(set(names)) != 2:
                    raise ValueError("nonunique player names in matched pair")
                provider_winner = status.get("winner_id")
                winner = next(
                    p
                    for p in players
                    if normalize_name(p["name"]) == normalize_name(reference.winner_name)
                )
                if provider_winner != winner["id"]:
                    raise ValueError("winner conflict in matched provider event")
                event_id = event.get("id")
                if not event_id:
                    raise ValueError("matched event has no ID")
                joined += 1
                for player in players:
                    provider_id = str(player["id"])
                    canonical_id = expected[normalize_name(player["name"])]
                    prior = evidence.get(provider_id)
                    if prior is not None and prior["canonical_id"] != canonical_id:
                        raise ValueError("one provider ID maps to multiple canonical IDs")
                    other_provider = canonical_to_provider.get(canonical_id)
                    if other_provider is not None and other_provider != provider_id:
                        raise ValueError("one canonical ID maps to multiple provider IDs")
                    canonical_to_provider[canonical_id] = provider_id
                    if prior is None:
                        prior = {
                            "provider_id": provider_id,
                            "canonical_id": canonical_id,
                            "matches": [],
                        }
                        evidence[provider_id] = prior
                    prior["matches"].append({"provider_event_id": event_id, "season_id": season_id})
    rows = sorted(evidence.values(), key=lambda row: row["provider_id"])
    return {
        "schema": "sportradar-pinned-atp-identity-overlap-v1",
        "authoritative_crosswalk": False,
        "canonical_csv_sha256": _sha256(canonical_csv),
        "provider_pages_sha256": dict(sorted(page_hashes.items())),
        "matched_events": joined,
        "nonterminal_excluded": excluded,
        "corroborated_players": len(rows),
        "rows": rows,
    }
