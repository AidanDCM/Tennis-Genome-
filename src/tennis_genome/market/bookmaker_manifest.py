from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
from typing import Literal

from tennis_genome.market.providers.bookmaker_historical import (
    BookmakerSource,
    load_tennis_data_quotes,
    load_valuebetennis_quotes,
    sha256_file,
)

RootKey = Literal["valuebetennis", "tennis_data_atp", "tennis_data_wta"]
_MANIFEST_VERSION = "bookmaker-historical-bundle-v1"
_MARKET_POLICY = "BOOKMAKER_CLOSE_V1"
_NEUTRALIZATION_VERSION = "bookmaker-neutralization-v1"
_NOVIG_METHOD = "proportional_novig_two_way"
_DEVELOPMENT_END = date(2025, 12, 31)


@dataclass(frozen=True)
class BookmakerSourceFile:
    root_key: RootKey
    source_family: BookmakerSource
    tour: str | None
    relative_path: str
    size_bytes: int
    sha256: str
    row_count: int
    min_match_date: str
    max_match_date: str


@dataclass(frozen=True)
class ExcludedBookmakerSourceFile:
    root_key: RootKey
    source_family: BookmakerSource
    tour: str | None
    relative_path: str
    size_bytes: int
    sha256: str
    reason: str


@dataclass(frozen=True)
class BookmakerSourceManifest:
    manifest_version: str
    market_policy: str
    neutralization_version: str
    novig_method: str
    requested_start_date: str
    requested_end_date: str
    discovered_file_count: int
    included_file_count: int
    total_included_bytes: int
    files: tuple[BookmakerSourceFile, ...]
    excluded_files: tuple[ExcludedBookmakerSourceFile, ...]
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


def _parse_date(value: str, *, field: str) -> date:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError(f"{field} must be YYYY-MM-DD") from exc
    return parsed


def discover_csv_files(root: str | Path) -> list[Path]:
    root_path = Path(root)
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(root_path)
    return sorted(
        (path for path in root_path.rglob("*.csv") if path.is_file()),
        key=lambda path: path.relative_to(root_path).as_posix(),
    )


def _source_spec(root_key: RootKey) -> tuple[BookmakerSource, str | None]:
    if root_key == "valuebetennis":
        return "VALUEBETENNIS", None
    if root_key == "tennis_data_atp":
        return "TENNIS_DATA_UK", "ATP"
    if root_key == "tennis_data_wta":
        return "TENNIS_DATA_UK", "WTA"
    raise ValueError(f"unsupported bookmaker root key: {root_key}")


def _load_quotes(
    path: Path,
    *,
    root_key: RootKey,
    relative_path: str,
    file_hash: str,
):
    source_family, tour = _source_spec(root_key)
    if source_family == "VALUEBETENNIS":
        return load_valuebetennis_quotes(
            path,
            source_file=relative_path,
            source_file_sha256=file_hash,
        )
    return load_tennis_data_quotes(
        path,
        tour=tour,  # type: ignore[arg-type]
        source_file=relative_path,
        source_file_sha256=file_hash,
    )


def _manifest_payload(
    *,
    start: date,
    end: date,
    files: tuple[BookmakerSourceFile, ...],
    excluded_files: tuple[ExcludedBookmakerSourceFile, ...],
) -> dict[str, object]:
    return {
        "manifest_version": _MANIFEST_VERSION,
        "market_policy": _MARKET_POLICY,
        "neutralization_version": _NEUTRALIZATION_VERSION,
        "novig_method": _NOVIG_METHOD,
        "requested_start_date": start.isoformat(),
        "requested_end_date": end.isoformat(),
        "discovered_file_count": len(files) + len(excluded_files),
        "included_file_count": len(files),
        "total_included_bytes": sum(item.size_bytes for item in files),
        "files": [asdict(item) for item in files],
        "excluded_files": [asdict(item) for item in excluded_files],
    }


def build_bookmaker_source_manifest(
    *,
    valuebet_root: str | Path,
    tennis_data_atp_root: str | Path,
    tennis_data_wta_root: str | Path,
    requested_start_date: str,
    requested_end_date: str,
) -> BookmakerSourceManifest:
    start = _parse_date(requested_start_date, field="requested_start_date")
    end = _parse_date(requested_end_date, field="requested_end_date")
    if start > end:
        raise ValueError("requested_start_date must not be after requested_end_date")
    if end > _DEVELOPMENT_END:
        raise ValueError("confirmatory bookmaker source interval must end by 2025-12-31")

    roots: dict[RootKey, Path] = {
        "valuebetennis": Path(valuebet_root),
        "tennis_data_atp": Path(tennis_data_atp_root),
        "tennis_data_wta": Path(tennis_data_wta_root),
    }
    included: list[BookmakerSourceFile] = []
    excluded: list[ExcludedBookmakerSourceFile] = []

    for root_key in ("valuebetennis", "tennis_data_atp", "tennis_data_wta"):
        root = roots[root_key]
        source_family, tour = _source_spec(root_key)
        for path in discover_csv_files(root):
            relative = path.relative_to(root).as_posix()
            file_hash = sha256_file(path)
            size = path.stat().st_size
            if size <= 0:
                raise ValueError(f"bookmaker source file is empty: {root_key}/{relative}")
            try:
                quotes = _load_quotes(
                    path,
                    root_key=root_key,
                    relative_path=relative,
                    file_hash=file_hash,
                )
            except ValueError:
                excluded.append(
                    ExcludedBookmakerSourceFile(
                        root_key=root_key,
                        source_family=source_family,
                        tour=tour,
                        relative_path=relative,
                        size_bytes=size,
                        sha256=file_hash,
                        reason="STRUCTURAL_INVALID",
                    )
                )
                continue
            if not quotes:
                excluded.append(
                    ExcludedBookmakerSourceFile(
                        root_key=root_key,
                        source_family=source_family,
                        tour=tour,
                        relative_path=relative,
                        size_bytes=size,
                        sha256=file_hash,
                        reason="NO_ROWS",
                    )
                )
                continue
            dates = [quote.match_date for quote in quotes]
            file_min = min(dates)
            file_max = max(dates)
            if file_max < start or file_min > end:
                excluded.append(
                    ExcludedBookmakerSourceFile(
                        root_key=root_key,
                        source_family=source_family,
                        tour=tour,
                        relative_path=relative,
                        size_bytes=size,
                        sha256=file_hash,
                        reason="OUTSIDE_REQUESTED_INTERVAL",
                    )
                )
                continue
            if file_min < start or file_max > end:
                raise ValueError(
                    "bookmaker source file straddles requested confirmatory interval: "
                    f"{root_key}/{relative} ({file_min}..{file_max})"
                )
            included.append(
                BookmakerSourceFile(
                    root_key=root_key,
                    source_family=source_family,
                    tour=tour,
                    relative_path=relative,
                    size_bytes=size,
                    sha256=file_hash,
                    row_count=len(quotes),
                    min_match_date=file_min.isoformat(),
                    max_match_date=file_max.isoformat(),
                )
            )

    included_tuple = tuple(
        sorted(included, key=lambda item: (item.root_key, item.relative_path))
    )
    excluded_tuple = tuple(
        sorted(excluded, key=lambda item: (item.root_key, item.relative_path))
    )
    if not included_tuple:
        raise ValueError("bookmaker source bundle contains no in-scope usable source files")
    payload = _manifest_payload(
        start=start,
        end=end,
        files=included_tuple,
        excluded_files=excluded_tuple,
    )
    digest = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    return BookmakerSourceManifest(
        manifest_version=_MANIFEST_VERSION,
        market_policy=_MARKET_POLICY,
        neutralization_version=_NEUTRALIZATION_VERSION,
        novig_method=_NOVIG_METHOD,
        requested_start_date=start.isoformat(),
        requested_end_date=end.isoformat(),
        discovered_file_count=len(included_tuple) + len(excluded_tuple),
        included_file_count=len(included_tuple),
        total_included_bytes=sum(item.size_bytes for item in included_tuple),
        files=included_tuple,
        excluded_files=excluded_tuple,
        bundle_sha256=digest,
    )


def _source_file_from_dict(item: dict[str, object]) -> BookmakerSourceFile:
    root_key = str(item["root_key"])
    if root_key not in {"valuebetennis", "tennis_data_atp", "tennis_data_wta"}:
        raise ValueError("bookmaker manifest contains invalid root_key")
    source = str(item["source_family"])
    if source not in {"VALUEBETENNIS", "TENNIS_DATA_UK"}:
        raise ValueError("bookmaker manifest contains invalid source family")
    return BookmakerSourceFile(
        root_key=root_key,  # type: ignore[arg-type]
        source_family=source,  # type: ignore[arg-type]
        tour=None if item.get("tour") is None else str(item["tour"]),
        relative_path=str(item["relative_path"]),
        size_bytes=int(item["size_bytes"]),
        sha256=str(item["sha256"]).lower(),
        row_count=int(item["row_count"]),
        min_match_date=str(item["min_match_date"]),
        max_match_date=str(item["max_match_date"]),
    )


def _excluded_file_from_dict(item: dict[str, object]) -> ExcludedBookmakerSourceFile:
    root_key = str(item["root_key"])
    source = str(item["source_family"])
    if root_key not in {"valuebetennis", "tennis_data_atp", "tennis_data_wta"}:
        raise ValueError("bookmaker manifest contains invalid excluded root_key")
    if source not in {"VALUEBETENNIS", "TENNIS_DATA_UK"}:
        raise ValueError("bookmaker manifest contains invalid excluded source family")
    return ExcludedBookmakerSourceFile(
        root_key=root_key,  # type: ignore[arg-type]
        source_family=source,  # type: ignore[arg-type]
        tour=None if item.get("tour") is None else str(item["tour"]),
        relative_path=str(item["relative_path"]),
        size_bytes=int(item["size_bytes"]),
        sha256=str(item["sha256"]).lower(),
        reason=str(item["reason"]),
    )


def load_bookmaker_source_manifest(path: str | Path) -> BookmakerSourceManifest:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("bookmaker source manifest must be a JSON object")
    if raw.get("manifest_version") != _MANIFEST_VERSION:
        raise ValueError("unexpected bookmaker source manifest version")
    if raw.get("market_policy") != _MARKET_POLICY:
        raise ValueError("unexpected bookmaker market policy")
    if raw.get("neutralization_version") != _NEUTRALIZATION_VERSION:
        raise ValueError("unexpected bookmaker neutralization version")
    if raw.get("novig_method") != _NOVIG_METHOD:
        raise ValueError("unexpected bookmaker no-vig method")
    start = _parse_date(str(raw.get("requested_start_date", "")), field="requested_start_date")
    end = _parse_date(str(raw.get("requested_end_date", "")), field="requested_end_date")
    if start > end or end > _DEVELOPMENT_END:
        raise ValueError("bookmaker manifest interval is outside frozen research scope")

    files_raw = raw.get("files")
    excluded_raw = raw.get("excluded_files", [])
    if not isinstance(files_raw, list) or not files_raw:
        raise ValueError("bookmaker manifest files must be a non-empty list")
    if not isinstance(excluded_raw, list):
        raise ValueError("bookmaker manifest excluded_files must be a list")
    files = tuple(_source_file_from_dict(item) for item in files_raw if isinstance(item, dict))
    excluded = tuple(
        _excluded_file_from_dict(item) for item in excluded_raw if isinstance(item, dict)
    )
    if len(files) != len(files_raw) or len(excluded) != len(excluded_raw):
        raise ValueError("bookmaker manifest file entries must be objects")
    identities = [(item.root_key, item.relative_path) for item in (*files, *excluded)]
    if len(set(identities)) != len(identities):
        raise ValueError("bookmaker manifest contains duplicate file identities")
    for item in (*files, *excluded):
        if item.size_bytes <= 0:
            raise ValueError("bookmaker manifest contains non-positive file size")
        if len(item.sha256) != 64 or any(c not in "0123456789abcdef" for c in item.sha256):
            raise ValueError("bookmaker manifest contains invalid SHA-256")
    if int(raw.get("discovered_file_count", -1)) != len(files) + len(excluded):
        raise ValueError("bookmaker manifest discovered_file_count mismatch")
    if int(raw.get("included_file_count", -1)) != len(files):
        raise ValueError("bookmaker manifest included_file_count mismatch")
    if int(raw.get("total_included_bytes", -1)) != sum(item.size_bytes for item in files):
        raise ValueError("bookmaker manifest total_included_bytes mismatch")
    payload = _manifest_payload(start=start, end=end, files=files, excluded_files=excluded)
    expected = hashlib.sha256(_canonical_json_bytes(payload)).hexdigest()
    provided = str(raw.get("bundle_sha256", "")).lower()
    if provided != expected:
        raise ValueError("bookmaker manifest bundle SHA-256 mismatch")
    return BookmakerSourceManifest(
        manifest_version=_MANIFEST_VERSION,
        market_policy=_MARKET_POLICY,
        neutralization_version=_NEUTRALIZATION_VERSION,
        novig_method=_NOVIG_METHOD,
        requested_start_date=start.isoformat(),
        requested_end_date=end.isoformat(),
        discovered_file_count=len(files) + len(excluded),
        included_file_count=len(files),
        total_included_bytes=sum(item.size_bytes for item in files),
        files=files,
        excluded_files=excluded,
        bundle_sha256=provided,
    )


def verify_bookmaker_source_manifest(
    manifest: BookmakerSourceManifest,
    *,
    valuebet_root: str | Path,
    tennis_data_atp_root: str | Path,
    tennis_data_wta_root: str | Path,
) -> None:
    roots: dict[str, Path] = {
        "valuebetennis": Path(valuebet_root),
        "tennis_data_atp": Path(tennis_data_atp_root),
        "tennis_data_wta": Path(tennis_data_wta_root),
    }
    expected = {
        (item.root_key, item.relative_path): item
        for item in (*manifest.files, *manifest.excluded_files)
    }
    discovered: set[tuple[str, str]] = set()
    for root_key, root in roots.items():
        for path in discover_csv_files(root):
            identity = (root_key, path.relative_to(root).as_posix())
            discovered.add(identity)
            if identity not in expected:
                raise ValueError(f"bookmaker source directory has unmanifested file: {identity}")
            item = expected[identity]
            if path.stat().st_size != item.size_bytes:
                raise ValueError(f"bookmaker source file size changed: {identity}")
            if sha256_file(path) != item.sha256:
                raise ValueError(f"bookmaker source file hash changed: {identity}")
    if discovered != set(expected):
        missing = sorted(set(expected).difference(discovered))
        raise ValueError(f"bookmaker manifest source file missing: {missing}")


def write_bookmaker_source_manifest(manifest: BookmakerSourceManifest, path: str | Path) -> None:
    Path(path).write_text(
        json.dumps(manifest.to_dict(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Freeze outcome-blind bookmaker historical source files"
    )
    parser.add_argument("--valuebet-root", required=True, type=Path)
    parser.add_argument("--tennis-data-atp-root", required=True, type=Path)
    parser.add_argument("--tennis-data-wta-root", required=True, type=Path)
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--output", required=True, type=Path)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    manifest = build_bookmaker_source_manifest(
        valuebet_root=args.valuebet_root,
        tennis_data_atp_root=args.tennis_data_atp_root,
        tennis_data_wta_root=args.tennis_data_wta_root,
        requested_start_date=args.start_date,
        requested_end_date=args.end_date,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    write_bookmaker_source_manifest(manifest, args.output)
    print(json.dumps(manifest.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
