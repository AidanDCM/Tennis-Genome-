"""Retain one bounded API-Tennis player-profile or draw response."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def _provider_get(url: str) -> bytes:
    try:
        with urlopen(Request(url, headers={"Accept": "application/json"}), timeout=90) as response:  # noqa: S310 - fixed HTTPS host
            if response.status != 200:
                raise RuntimeError(f"API-Tennis returned HTTP {response.status}")
            return response.read()
    except HTTPError as exc:
        raise RuntimeError(f"API-Tennis returned HTTP {exc.code}") from None
    except URLError:
        raise RuntimeError("API-Tennis HTTPS transport failed") from None


def _contains_market_key(value: object) -> bool:
    if isinstance(value, dict):
        return any(
            any(token in str(key).lower() for token in ("odd", "bookmaker"))
            or _contains_market_key(child)
            for key, child in value.items()
        )
    if isinstance(value, list):
        return any(_contains_market_key(child) for child in value)
    return False


def capture(
    *,
    api_key: str,
    method: str,
    tournament_key: int,
    season: int,
    output_dir: Path,
    provider_get: Callable[[str], bytes] = _provider_get,
) -> dict[str, object]:
    if not api_key.strip():
        raise ValueError("API_TENNIS_API must be configured")
    if method not in {"get_players", "get_draw"}:
        raise ValueError("method must be get_players or get_draw")
    if tournament_key <= 0 or not 2000 <= season <= 2100:
        raise ValueError("invalid tournament key or season")
    output_dir.mkdir(parents=True, exist_ok=True)
    if any(output_dir.iterdir()):
        raise ValueError("metadata output directory must begin empty")
    params: dict[str, object] = {
        "method": method,
        "APIkey": api_key,
        "tournament_key": tournament_key,
    }
    if method == "get_draw":
        params["tournament_season"] = season
    url = "https://api.api-tennis.com/tennis/?" + urlencode(params)
    raw = provider_get(url)
    received_at = datetime.now(UTC).isoformat()
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("metadata response is not UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("success") not in (1, "1"):
        raise ValueError("metadata response did not report success")
    result = payload.get("result")
    if not isinstance(result, (list, dict)) or not result:
        raise ValueError("metadata result is empty or malformed")
    if _contains_market_key(payload):
        raise ValueError("metadata response contains market fields")
    sample = result[0] if isinstance(result, list) else result
    manifest: dict[str, object] = {
        "schema_version": "tennis-genome-api-tennis-tournament-metadata-probe-v1",
        "method": method,
        "tournament_key": tournament_key,
        "requested_season": season if method == "get_draw" else None,
        "received_at_utc": received_at,
        "provider_request_count": 1,
        "result_type": type(result).__name__,
        "result_count": len(result),
        "sample_keys": sorted(sample) if isinstance(sample, dict) else [],
        "raw_sha256": hashlib.sha256(raw).hexdigest(),
        "market_blind": True,
        "production_admitted": False,
    }
    (output_dir / "raw-response.json").write_bytes(raw)
    (output_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--method", required=True, choices=("get_players", "get_draw"))
    parser.add_argument("--tournament-key", type=int, required=True)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    manifest = capture(
        api_key=os.environ.get("API_TENNIS_API", ""),
        method=args.method,
        tournament_key=args.tournament_key,
        season=args.season,
        output_dir=args.output_dir,
    )
    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
