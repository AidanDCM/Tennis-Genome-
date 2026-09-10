from __future__ import annotations

from dataclasses import asdict
from typing import Any

from tennis_genome.profiles.state import PlayerProfileSnapshot


def profile_record(snapshot: PlayerProfileSnapshot) -> dict[str, Any]:
    """Return the schema-facing deterministic record for a profile snapshot.

    `data_cutoff` is the source date because this public historical dataset has
    date precision only. Dynamic state is nevertheless frozen before every
    current-date outcome/stat update, so this date must not be interpreted as a
    trustworthy match-start timestamp.
    """
    payload = asdict(snapshot)
    payload["profile_hash"] = snapshot.profile_hash
    payload["valid_from"] = snapshot.valid_from.isoformat()
    payload["valid_until"] = (
        snapshot.valid_until.isoformat() if snapshot.valid_until is not None else None
    )
    payload["data_cutoff"] = snapshot.valid_from.isoformat()
    return payload
