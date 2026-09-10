from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal, cast

DataPackage = Literal["ADVANCED", "PRO"]
_MANIFEST_VERSION = "betfair-historical-bundle-v1"
_PROVIDER = "BETFAIR_HISTORICAL"
_SPORT = "TENNIS"
_MARKET_TYPE = "MATCH_ODDS"
_DEVELOPMENT_END = date(2025, 12, 31)
_SUPPORTED_SUFFIXES = {"", ".bz2", ".json", ".jsonl", ".txt"}


@dataclass(frozen=True)
class HistoricalSourceFile:
    relative_path: str
    size_bytes: int
    sha256: str


@dataclass(frozen=True)
class HistoricalSourceManifest:
    manifest_version: str
    provider: str
    sport: str
    market_type: str
    data_package: DataPackage
    requested_start_date: str
    requested_end_date: str
    file_count: int
    total_bytes: int
    files: tuple[HistoricalSourceFile, ...]
    bundle_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _canonical_json_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_date(value: str, *, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return parsed


def _package(value: str) -> DataPackage:
    upper = value.upper()
    if upper not in {"ADVANCED", "PRO"}:
        raise ValueError("confirmatory Betfair source package must be ADVANCED or PRO")
    return cast(DataPackage, upper)


def discover_source_files(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(root_path)
    files = [
        path
        for path in root_path.rglob("*")
        if path.is_file() and path.suffix.lower() in _SUPPORTED_SUFFIXES
    ]
    return sorted(files, key=lambda path: path.relative_to(root_path).as_posix())


def _manifest_payload(
    *,
    data_package: DataPackage,
    requested_start_date: str,
    requested_end_date: str,
    files: tuple[HistoricalSourceFile, ...],
) -> dict[str, object]:
    return {
        "manifest_version": _MANIFEST_VERSION,
        "provider": _PROVIDER,
        "sport": _SPORT,
        "market_type": _MARKET_TYPE,
        "data_package": data_package,
        "requested_start_date": requested_start_date,
        "requested_end_date": requested_end_date,
        "file_count": len(files),
        "total_bytes": sum(item.size_bytes for item in files),
        "files": [asdict(item) for item in files],
    }


def build_historical_source_manifest(
    *,
    root: str | Path,
    data_package: str,
    requested_start_date: str,
    requested_end_date: str,
) -> HistoricalSourceManifest:
    package = _package(data_package)
    start = _parse_date(requested_start_date, field="requested_start_date")
    end = _parse_date(requested_end_date, field="requested_end_date")
    if start > end:
        raise ValueError("requested_start_date must not be after requested_end_date")
    if end > _DEVELOPMENT_END:
        raise ValueError("MARKET-HIST confirmatory source interval must end by 2025-12-31")

    root_path = Path(root)
    paths = discover_source_files(root_path)
    if not paths:
        raise ValueError("Betfair source directory contains no supported files")
    files = tuple(
        HistoricalSourceFile(
            relative_path=path.relative_to(root_path).as_posix(),
            size_bytes=path.stat().st_size,
            sha256=_sha256_file(path),
        )
        for path in paths
    )
    if any(item.size_bytes <= 0 for item in files):
        raise ValueError("Betfair source bundle contains an empty file")
    payload = _manifest_payload(
        data_package=package,
        requested_start_date=start.isoformat(),
        requested_end_date=end.isoformat(),
        files=files,
    )
    bundle_sha256 = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return HistoricalSourceManifest(
        **payload,
        files=files,
        bundle_sha256=bundle_sha256,
    )


def load_historical_source_manifest(path: str | Path) -> HistoricalSourceManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("source manifest must be a JSON object")
    files_raw = raw.get("files")
    if not isinstance(files_raw, list) or not files_raw:
        raise ValueError("source manifest files must be a non-empty list")
    files = tuple(
        HistoricalSourceFile(
            relative_path=str(item["relative_path"]),
            size_bytes=int(item["size_bytes"]),
            sha256=str(item["sha256"]).lower(),
        )
        for item in files_raw
    )
    package = _package(str(raw.get("data_package", "")))
    start = _parse_date(str(raw.get("requested_start_date", "")), field="requested_start_date")
    end = _parse_date(str(raw.get("requested_end_date", "")), field="requested_end_date")
    if start > end or end > _DEVELOPMENT_END:
        raise ValueError("source manifest interval is outside frozen research scope")
    if raw.get("manifest_version") != _MANIFEST_VERSION:
        raise ValueError("unexpected source manifest version")
    if raw.get("provider") != _PROVIDER or raw.get("sport") != _SPORT:
        raise ValueError("unexpected source manifest provider or sport")
    if raw.get("market_type") != _MARKET_TYPE:
        raise ValueError("source manifest market type must be MATCH_ODDS")
    for item in files:
        if item.size_bytes <= 0:
            raise ValueError("source manifest contains non-positive file size")
        if len(item.sha256) != 64 or any(char not in "0123456789abcdef" for char in item.sha256):
            raise ValueError("source manifest contains invalid file SHA-256")
    if len({item.relative_path for item in files}) != len(files):
        raise ValueError("source manifest contains duplicate relative paths")
    if int(raw.get("file_count", -1)) != len(files):
        raise ValueError("source manifest file_count mismatch")
    if int(raw.get("total_bytes", -1)) != sum(item.size_bytes for item in files):
        raise ValueError("source manifest total_bytes mismatch")
    payload = _manifest_payload(
        data_package=package,
        requested_start_date=start.isoformat(),
        requested_end_date=end.isoformat(),
        files=files,
    )
    expected_digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    provided_digest = str(raw.get("bundle_sha256", "")).lower()
    if provided_digest != expected_digest:
        raise ValueError("source manifest bundle SHA-256 mismatch")
    return HistoricalSourceManifest(
        **payload,
        files=files,
        bundle_sha256=provided_digest,
    )


def verify_historical_source_manifest(
    manifest: HistoricalSourceManifest,
    *,
    root: str | Path,
) -> None:
    root_path = Path(root)
    discovered = discover_source_files(root_path)
    discovered_paths = [path.relative_to(root_path).as_posix() for path in discovered]
    expected_paths = [item.relative_path for item in manifest.files]
    if discovered_paths != expected_paths:
        raise ValueError("source directory file set differs from manifest")
    expected_by_path = {item.relative_path: item for item in manifest.files}
    for path in discovered:
        relative = path.relative_to(root_path).as_posix()
        expected = expected_by_path[relative]
        if path.stat().st_size != expected.size_bytes:
            raise ValueError(f"source file size changed after manifest: {relative}")
        if _sha256_file(path) != expected.sha256:
            raise ValueError(f"source file hash changed after manifest: {relative}")


def write_historical_source_manifest(
    manifest: HistoricalSourceManifest,
    path: str | Path,
) -> None:
    Path(path).write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Hash a local licensed Betfair historical Tennis MATCH_ODDS bundle"
    )
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--data-package", required=True, choices=("ADVANCED", "PRO"))
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_historical_source_manifest(
        root=args.root,
        data_package=args.data_package,
        requested_start_date=args.start_date,
        requested_end_date=args.end_date,
    )
    write_historical_source_manifest(manifest, args.output)
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
