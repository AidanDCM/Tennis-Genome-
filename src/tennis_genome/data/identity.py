from __future__ import annotations

import re
import unicodedata
from hashlib import sha256

from tennis_genome.data.canonical import Tour

_MISSING = {"", "nan", "none", "null", "<na>"}


def normalize_player_name(name: str) -> str:
    """Normalize a player name for deterministic fallback identity matching."""
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_name = ascii_name.casefold().strip()
    ascii_name = re.sub(r"[^a-z0-9]+", " ", ascii_name)
    return " ".join(ascii_name.split())


def clean_source_id(value: object) -> str | None:
    """Normalize common CSV identifier representations without guessing identity."""
    if value is None:
        return None
    text = str(value).strip()
    if text.casefold() in _MISSING:
        return None
    if text.endswith(".0"):
        integer_part = text[:-2]
        if integer_part.lstrip("-").isdigit():
            text = integer_part
    return text


def canonical_player_id(*, tour: Tour, source_id: object, name: str) -> str:
    """Create a stable tour-scoped ID.

    Source IDs are preferred. Name hashes are only a fallback and must later be
    audited for collisions, aliases, and name changes before production use.
    """
    cleaned_id = clean_source_id(source_id)
    if cleaned_id is not None:
        return f"{tour.lower()}:id:{cleaned_id}"

    normalized_name = normalize_player_name(name)
    if not normalized_name:
        raise ValueError("cannot create fallback player ID from an empty name")
    digest = sha256(normalized_name.encode("utf-8")).hexdigest()[:16]
    return f"{tour.lower()}:name:{digest}"


def orient_pair(
    *,
    winner_id: str,
    loser_id: str,
    winner_name: str,
    loser_name: str,
) -> tuple[str, str, str, str, bool]:
    """Orient A/B independently of the outcome.

    Historical CSVs commonly store winner fields first. Using that order would
    make ``player_a`` synonymous with the winner and leak the label. We instead
    sort stable player IDs, then attach the outcome afterward.
    """
    if winner_id == loser_id:
        raise ValueError("winner and loser resolved to the same canonical player ID")

    if winner_id < loser_id:
        return winner_id, loser_id, winner_name, loser_name, True
    return loser_id, winner_id, loser_name, winner_name, False
