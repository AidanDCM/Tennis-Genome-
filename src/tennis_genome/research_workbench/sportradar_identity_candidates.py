"""Offline, nonauthoritative player-identity candidate report."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import defaultdict
from pathlib import Path

import pandas as pd

from .sportradar_season_summaries_census import _canonical_json

_ISO_TO_HISTORICAL_IOC = {
    "BGR": "BUL",
    "CHE": "SUI",
    "CHL": "CHI",
    "DEU": "GER",
    "DNK": "DEN",
    "GRC": "GRE",
    "HRV": "CRO",
    "IDN": "INA",
    "NLD": "NED",
    "PHL": "PHI",
    "PRT": "POR",
}


def normalize_name(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode()
    text = text.casefold()
    if "," in text:
        surname, given = text.split(",", 1)
        text = given + " " + surname
    return " ".join(re.findall(r"[a-z0-9]+", text))


def build_candidate_report(
    *,
    capture_root: Path,
    canonical_root: Path,
) -> dict[str, object]:
    pages = sorted(capture_root.glob("seasons/*/page-*.json"))
    if not pages:
        raise ValueError("capture contains no retained summary pages")
    provider: dict[tuple[str, str], tuple[str, str | None]] = {}
    source_hashes: dict[str, str] = {}
    for page in pages:
        raw = page.read_bytes()
        source_hashes[str(page.relative_to(capture_root))] = hashlib.sha256(raw).hexdigest()
        payload = json.loads(raw)
        if not isinstance(payload, dict) or not isinstance(payload.get("summaries"), list):
            raise ValueError("retained season page is not a summaries object")
        for summary in payload["summaries"]:
            event = summary["sport_event"]
            category = event["sport_event_context"]["category"]["id"]
            if category not in {"sr:category:3", "sr:category:6"}:
                continue
            tour = "ATP" if category == "sr:category:3" else "WTA"
            for competitor in event.get("competitors", []):
                sr_id = str(competitor.get("id", "")).strip()
                name = str(competitor.get("name", "")).strip()
                country = str(competitor.get("country_code", "")).strip() or None
                if not sr_id or not name:
                    raise ValueError("provider competitor identity is missing")
                key = (tour, sr_id)
                earlier = provider.get(key)
                if earlier is not None and earlier != (name, country):
                    raise ValueError("provider competitor identity changed within retained pages")
                provider[key] = (name, country)

    canonical: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    canonical_hashes: dict[str, str] = {}
    for tour in ("ATP", "WTA"):
        lower = tour.lower()
        path = canonical_root / lower / f"{lower}_pre_match.parquet"
        raw = path.read_bytes()
        canonical_hashes[str(path.relative_to(canonical_root))] = hashlib.sha256(raw).hexdigest()
        frame = pd.read_parquet(
            path,
            columns=[
                "player_a_id",
                "player_b_id",
                "player_a_name",
                "player_b_name",
                "ioc_a",
                "ioc_b",
            ],
        )
        for side in ("a", "b"):
            for player_id, name, country in frame[
                [f"player_{side}_id", f"player_{side}_name", f"ioc_{side}"]
            ].itertuples(index=False, name=None):
                canonical[(tour, normalize_name(str(name)))][str(player_id)].add(
                    str(country).upper() if pd.notna(country) else ""
                )

    rows: list[dict[str, object]] = []
    counts: dict[str, int] = defaultdict(int)
    for (tour, sr_id), (name, country) in sorted(provider.items()):
        options = canonical.get((tour, normalize_name(name)), {})
        matches = [
            {"canonical_id": player_id, "historical_ioc": sorted(codes)}
            for player_id, codes in sorted(options.items())
        ]
        if not matches:
            disposition = "UNMATCHED"
        elif len(matches) > 1:
            disposition = "AMBIGUOUS_NAME"
        elif country is None or not any(matches[0]["historical_ioc"]):
            disposition = "UNIQUE_NAME_COUNTRY_UNAVAILABLE"
        elif country.upper() in matches[0]["historical_ioc"]:
            disposition = "UNIQUE_NAME_COUNTRY_AGREES"
        elif _ISO_TO_HISTORICAL_IOC.get(country.upper()) in matches[0]["historical_ioc"]:
            disposition = "UNIQUE_NAME_COUNTRY_CODE_CONVENTION"
        else:
            disposition = "UNIQUE_NAME_COUNTRY_CONFLICT"
        counts[disposition] += 1
        rows.append(
            {
                "tour": tour,
                "sportradar_id": sr_id,
                "sportradar_name": name,
                "sportradar_country_code": country,
                "normalized_name": normalize_name(name),
                "disposition": disposition,
                "candidates": matches,
            }
        )
    return {
        "schema": "sportradar-canonical-identity-candidates-v1",
        "authoritative_crosswalk": False,
        "provider_pages_sha256": source_hashes,
        "canonical_parquet_sha256": canonical_hashes,
        "provider_player_count": len(provider),
        "counts": dict(sorted(counts.items())),
        "rows": rows,
        "report_sha256": hashlib.sha256(_canonical_json(rows)).hexdigest(),
    }
