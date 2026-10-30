"""Capture current ATP/WTA standings as timestamped source evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def capture(*, api_key: str, output_dir: Path) -> dict[str, object]:
    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("standings output directory must begin empty")

    started_at = datetime.now(UTC).isoformat()
    counts: dict[str, int] = {}
    hashes: dict[str, str] = {}
    received_at: dict[str, str] = {}
    for tour in ("ATP", "WTA"):
        query = urlencode(
            {"method": "get_standings", "APIkey": api_key, "event_type": tour}
        )
        request = Request(
            f"https://api.api-tennis.com/tennis/?{query}",
            headers={"Accept": "application/json"},
        )
        try:
            with urlopen(request, timeout=90) as response:  # noqa: S310 - fixed HTTPS host
                if response.status != 200:
                    raise RuntimeError(f"{tour} standings returned HTTP {response.status}")
                raw = response.read()
                received_at[tour.lower()] = datetime.now(UTC).isoformat()
        except HTTPError as exc:
            raise RuntimeError(f"{tour} standings returned HTTP {exc.code}") from None
        except URLError:
            raise RuntimeError(f"{tour} standings HTTPS transport failed") from None

        (output_dir / f"raw-{tour.lower()}-standings.json").write_bytes(raw)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError(f"{tour} standings response is not UTF-8 JSON") from exc
        if not isinstance(payload, dict) or payload.get("success") not in (1, "1"):
            raise ValueError(f"{tour} standings response did not report success")
        rows = payload.get("result")
        if not isinstance(rows, list) or any(not isinstance(row, dict) for row in rows):
            raise ValueError(f"{tour} standings result is not a list of objects")
        if not rows:
            raise ValueError(f"{tour} standings response is empty")
        for row in rows:
            if any("odd" in str(key).lower() for key in row):
                raise ValueError("standings response contains market fields")
            if not str(row.get("player_key", "")).strip():
                raise ValueError(f"{tour} standing is missing player_key")
            if not str(row.get("place", "")).strip():
                raise ValueError(f"{tour} standing is missing place")
        counts[tour.lower()] = len(rows)
        hashes[tour.lower()] = hashlib.sha256(raw).hexdigest()

    manifest: dict[str, object] = {
        "schema_version": "tennis-genome-api-tennis-trial-standings-v1",
        "request_started_at_utc": started_at,
        "observed_at_utc": datetime.now(UTC).isoformat(),
        "atp_received_at_utc": received_at["atp"],
        "wta_received_at_utc": received_at["wta"],
        "provider_request_count": 2,
        "market_blind": True,
        "rank_as_of_assumed": False,
        "atp_count": counts["atp"],
        "wta_count": counts["wta"],
        "raw_atp_sha256": hashes["atp"],
        "raw_wta_sha256": hashes["wta"],
    }
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = capture(
        api_key=os.environ.get("API_TENNIS_API", ""), output_dir=args.output_dir
    )
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
