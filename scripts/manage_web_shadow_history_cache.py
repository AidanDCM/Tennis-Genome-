from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from tennis_genome.data.parquet import load_canonical_parquet

_SCHEMA = "tennis-genome-web-shadow-history-cache-v1"
_RECEIPT = Path("data/wta-live-base/history-cache-receipt.json")
_HASHED_FILES = (
    Path("data/wta-live-base/wta_pre_match.parquet"),
    Path("data/wta-live-base/wta_outcomes.parquet"),
    Path("data/wta-live-base/wta_stats.parquet"),
    Path("data/wta-live-base/wta_manifest.json"),
    Path("data/wta-live-base/2026-source-reconciliation.json"),
    Path("data/wta-live-base/build_output.json"),
    Path("data/wta_players.csv"),
)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _history_summary(root: Path) -> dict[str, Any]:
    base = root / "data/wta-live-base"
    history = load_canonical_parquet(
        pre_match_path=base / "wta_pre_match.parquet",
        outcome_path=base / "wta_outcomes.parquet",
        stats_path=base / "wta_stats.parquet",
    )
    if not history:
        raise RuntimeError("cached canonical WTA history is empty")

    eligible = [
        match
        for match in history
        if not match.outcome.walkover and not match.outcome.retirement
    ]
    if not eligible:
        raise RuntimeError("cached eligible WTA history is empty")

    return {
        "canonical_match_count": len(history),
        "eligible_match_count": len(eligible),
        "max_eligible_event_date": max(
            match.pre_match.event_date for match in eligible
        ).isoformat(),
    }


def _binding(
    *,
    archive_repo: str,
    archive_commit: str,
    matches_2026_blob: str,
    qual_itf_2026_blob: str,
    expected_history_max_date: str,
) -> dict[str, str]:
    date.fromisoformat(expected_history_max_date)
    values = {
        "archive_repo": archive_repo.strip(),
        "archive_commit": archive_commit.strip(),
        "matches_2026_blob": matches_2026_blob.strip(),
        "qual_itf_2026_blob": qual_itf_2026_blob.strip(),
        "expected_history_max_date": expected_history_max_date.strip(),
    }
    if any(not value for value in values.values()):
        raise ValueError("history cache binding fields must be non-empty")
    return values


def write_history_cache_receipt(
    *,
    root: Path,
    archive_repo: str,
    archive_commit: str,
    matches_2026_blob: str,
    qual_itf_2026_blob: str,
    expected_history_max_date: str,
) -> dict[str, Any]:
    binding = _binding(
        archive_repo=archive_repo,
        archive_commit=archive_commit,
        matches_2026_blob=matches_2026_blob,
        qual_itf_2026_blob=qual_itf_2026_blob,
        expected_history_max_date=expected_history_max_date,
    )
    history = _history_summary(root)
    if history["max_eligible_event_date"] != expected_history_max_date:
        raise RuntimeError(
            "canonical history maximum date differs from pinned cache binding"
        )

    hashes: dict[str, str] = {}
    for relative in _HASHED_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"history cache file is missing: {relative}")
        hashes[relative.as_posix()] = _sha256_file(path)

    receipt: dict[str, Any] = {
        "schema_version": _SCHEMA,
        "binding": binding,
        "history": history,
        "files_sha256": hashes,
    }
    path = root / _RECEIPT
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    return receipt


def verify_history_cache_receipt(
    *,
    root: Path,
    archive_repo: str,
    archive_commit: str,
    matches_2026_blob: str,
    qual_itf_2026_blob: str,
    expected_history_max_date: str,
) -> dict[str, Any]:
    expected_binding = _binding(
        archive_repo=archive_repo,
        archive_commit=archive_commit,
        matches_2026_blob=matches_2026_blob,
        qual_itf_2026_blob=qual_itf_2026_blob,
        expected_history_max_date=expected_history_max_date,
    )
    receipt_path = root / _RECEIPT
    if not receipt_path.is_file():
        raise FileNotFoundError("history cache receipt is missing")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    if not isinstance(receipt, dict):
        raise ValueError("history cache receipt must contain an object")
    if receipt.get("schema_version") != _SCHEMA:
        raise ValueError("unsupported history cache receipt schema")
    if receipt.get("binding") != expected_binding:
        raise RuntimeError("history cache binding differs from pinned source")

    hashes = receipt.get("files_sha256")
    if not isinstance(hashes, dict):
        raise ValueError("history cache receipt lacks file hashes")
    expected_paths = {path.as_posix() for path in _HASHED_FILES}
    if set(hashes) != expected_paths:
        raise RuntimeError("history cache receipt file set is not exact")
    for relative in _HASHED_FILES:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"restored history cache file is missing: {relative}")
        observed = _sha256_file(path)
        if observed != hashes[relative.as_posix()]:
            raise RuntimeError(f"restored history cache hash mismatch: {relative}")

    observed_history = _history_summary(root)
    if observed_history != receipt.get("history"):
        raise RuntimeError("restored history cache summary differs from receipt")
    if observed_history["max_eligible_event_date"] != expected_history_max_date:
        raise RuntimeError("restored history cache maximum date differs from pinned source")
    return receipt


def _add_binding_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--archive-repo", required=True)
    parser.add_argument("--archive-commit", required=True)
    parser.add_argument("--matches-2026-blob", required=True)
    parser.add_argument("--qual-itf-2026-blob", required=True)
    parser.add_argument("--expected-history-max-date", required=True)
    parser.add_argument("--root", type=Path, default=Path("."))


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Write or verify the content-bound Web Shadow history cache receipt"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    write_parser = subparsers.add_parser("write")
    verify_parser = subparsers.add_parser("verify")
    _add_binding_args(write_parser)
    _add_binding_args(verify_parser)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    kwargs = {
        "root": args.root,
        "archive_repo": args.archive_repo,
        "archive_commit": args.archive_commit,
        "matches_2026_blob": args.matches_2026_blob,
        "qual_itf_2026_blob": args.qual_itf_2026_blob,
        "expected_history_max_date": args.expected_history_max_date,
    }
    if args.command == "write":
        receipt = write_history_cache_receipt(**kwargs)
    else:
        receipt = verify_history_cache_receipt(**kwargs)
    print(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False))


if __name__ == "__main__":
    main()
