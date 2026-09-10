from __future__ import annotations

import argparse
import calendar
import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path, PurePosixPath

_API_BASE = "https://historicdata.betfair.com/api/"
_TOKEN_ENV = "BETFAIR_SSOID"
_REMOTE_PREFIX = PurePosixPath("/data/xds/historic")
_STATE_VERSION = "betfair-historical-download-state-v1"


@dataclass(frozen=True)
class HistoricalFilter:
    plan_name: str
    start_date: date
    end_date: date
    countries: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.plan_name.strip():
            raise ValueError("plan_name must be non-empty")
        if self.start_date > self.end_date:
            raise ValueError("start_date must be on or before end_date")

    def to_api_payload(self) -> dict[str, object]:
        return {
            "sport": "Tennis",
            "plan": self.plan_name,
            "fromDay": self.start_date.day,
            "fromMonth": self.start_date.month,
            "fromYear": self.start_date.year,
            "toDay": self.end_date.day,
            "toMonth": self.end_date.month,
            "toYear": self.end_date.year,
            "eventId": None,
            "eventName": None,
            "marketTypesCollection": ["MATCH_ODDS"],
            "countriesCollection": list(self.countries),
            "fileTypeCollection": ["M"],
        }


@dataclass(frozen=True)
class DownloadStateEntry:
    remote_path: str
    relative_path: str
    byte_size: int
    sha256: str


@dataclass(frozen=True)
class DownloadReport:
    plan_name: str
    start_date: str
    end_date: str
    month_windows: int
    files_listed: int
    files_downloaded: int
    files_skipped_verified: int
    bytes_downloaded: int
    dry_run: bool
    state_path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_sha256(value: object, *, name: str) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(character not in "0123456789abcdef" for character in text):
        raise ValueError(f"{name} must be a lowercase SHA-256 hex digest")
    return text


def _month_windows(start: date, end: date) -> list[tuple[date, date]]:
    if start > end:
        raise ValueError("start must be on or before end")
    result: list[tuple[date, date]] = []
    cursor = date(start.year, start.month, 1)
    while cursor <= end:
        last_day = calendar.monthrange(cursor.year, cursor.month)[1]
        month_end = date(cursor.year, cursor.month, last_day)
        window_start = max(start, cursor)
        window_end = min(end, month_end)
        result.append((window_start, window_end))
        if cursor.month == 12:
            cursor = date(cursor.year + 1, 1, 1)
        else:
            cursor = date(cursor.year, cursor.month + 1, 1)
    return result


def _safe_relative_remote_path(remote_path: str) -> Path:
    path = PurePosixPath(remote_path)
    if not path.is_absolute():
        raise ValueError("Betfair historical remote path must be absolute")
    if any(part in {".", ".."} for part in path.parts):
        raise ValueError("Betfair historical remote path contains traversal components")
    prefix_parts = _REMOTE_PREFIX.parts
    if path.parts[: len(prefix_parts)] != prefix_parts:
        raise ValueError("Betfair historical remote path is outside the historic-data root")
    relative_parts = path.parts[len(prefix_parts) :]
    if len(relative_parts) < 3:
        raise ValueError("Betfair historical remote path is unexpectedly short")
    if not relative_parts[-1].endswith(".bz2"):
        raise ValueError("Betfair market download must be a .bz2 file")
    return Path(*relative_parts)


def _state_payload(entries: dict[str, DownloadStateEntry]) -> dict[str, object]:
    return {
        "state_version": _STATE_VERSION,
        "files": [
            asdict(entries[remote_path])
            for remote_path in sorted(entries)
        ],
    }


def _load_state(path: Path) -> dict[str, DownloadStateEntry]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("state_version") != _STATE_VERSION:
        raise ValueError("unexpected Betfair download state format")
    files = payload.get("files")
    if not isinstance(files, list):
        raise ValueError("Betfair download state files must be a list")
    result: dict[str, DownloadStateEntry] = {}
    for row in files:
        if not isinstance(row, dict):
            raise ValueError("invalid Betfair download state row")
        remote_path = str(row.get("remote_path", ""))
        relative_path = str(row.get("relative_path", ""))
        byte_size = int(row.get("byte_size", -1))
        sha256 = _require_sha256(row.get("sha256", ""), name="download state sha256")
        expected_relative = _safe_relative_remote_path(remote_path).as_posix()
        if relative_path != expected_relative:
            raise ValueError("download state relative path disagrees with remote path")
        if byte_size < 0:
            raise ValueError("download state byte_size must be non-negative")
        if remote_path in result:
            raise ValueError("duplicate remote path in Betfair download state")
        result[remote_path] = DownloadStateEntry(
            remote_path=remote_path,
            relative_path=relative_path,
            byte_size=byte_size,
            sha256=sha256,
        )
    return result


def _write_state(path: Path, entries: dict[str, DownloadStateEntry]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_text(
        json.dumps(_state_payload(entries), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


class HistoricalDataClient:
    """Minimal Betfair Historical Data API client with secret-safe representation."""

    def __init__(self, *, ssoid: str, api_base: str = _API_BASE) -> None:
        if not ssoid.strip():
            raise ValueError("Betfair ssoid must be non-empty")
        if api_base != _API_BASE:
            raise ValueError("api_base is frozen to the official Betfair Historical Data API")
        self._ssoid = ssoid
        self._api_base = api_base

    def __repr__(self) -> str:
        return f"{type(self).__name__}(api_base={self._api_base!r}, ssoid=<redacted>)"

    @classmethod
    def from_environment(cls) -> HistoricalDataClient:
        value = os.environ.get(_TOKEN_ENV, "")
        if not value.strip():
            raise RuntimeError(
                f"set {_TOKEN_ENV} in the environment before using Betfair downloads"
            )
        return cls(ssoid=value)

    def _headers(self, *, json_request: bool) -> dict[str, str]:
        headers = {"ssoid": self._ssoid}
        if json_request:
            headers["Content-Type"] = "application/json"
        return headers

    def _post_json(self, operation: str, payload: dict[str, object]) -> object:
        url = urllib.parse.urljoin(self._api_base, operation)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
            headers=self._headers(json_request=True),
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            body = exc.read(512).decode("utf-8", errors="replace")
            raise RuntimeError(
                f"Betfair Historical Data API {operation} failed with HTTP {exc.code}: {body}"
            ) from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Betfair Historical Data API {operation} request failed") from exc

    def get_my_data(self) -> list[dict[str, object]]:
        payload = self._post_json("GetMyData", {})
        if not isinstance(payload, list) or not all(isinstance(row, dict) for row in payload):
            raise ValueError("GetMyData returned an unexpected payload")
        return payload

    def get_collection_options(self, filter_: HistoricalFilter) -> dict[str, object]:
        payload = self._post_json("GetCollectionsOptions", filter_.to_api_payload())
        if not isinstance(payload, dict):
            raise ValueError("GetCollectionsOptions returned an unexpected payload")
        return payload

    def get_basket_size(self, filter_: HistoricalFilter) -> dict[str, object]:
        payload = self._post_json("GetAdvBasketSize", filter_.to_api_payload())
        if not isinstance(payload, dict):
            raise ValueError("GetAdvBasketSize returned an unexpected payload")
        return payload

    def list_files(self, filter_: HistoricalFilter) -> list[str]:
        payload = self._post_json("DownloadListOfFiles", filter_.to_api_payload())
        if not isinstance(payload, list) or not all(isinstance(value, str) for value in payload):
            raise ValueError("DownloadListOfFiles returned an unexpected payload")
        paths = sorted(set(payload))
        for remote_path in paths:
            _safe_relative_remote_path(remote_path)
        return paths

    def download_file(self, remote_path: str, target: Path) -> int:
        _safe_relative_remote_path(remote_path)
        query = urllib.parse.urlencode({"filePath": remote_path})
        url = urllib.parse.urljoin(self._api_base, "DownloadFile") + "?" + query
        request = urllib.request.Request(
            url,
            headers=self._headers(json_request=False),
            method="GET",
        )
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            total = 0
            with (
                urllib.request.urlopen(request, timeout=120) as response,
                target.open("wb") as handle,
            ):
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    handle.write(chunk)
                    total += len(chunk)
            return total
        except urllib.error.HTTPError as exc:
            if target.exists():
                target.unlink()
            raise RuntimeError(
                f"Betfair Historical Data API DownloadFile failed with HTTP {exc.code}"
            ) from exc
        except (urllib.error.URLError, OSError) as exc:
            if target.exists():
                target.unlink()
            raise RuntimeError("Betfair Historical Data file download failed") from exc


def _verify_existing(
    *,
    root: Path,
    remote_path: str,
    state: dict[str, DownloadStateEntry],
) -> bool:
    relative = _safe_relative_remote_path(remote_path)
    target = root / relative
    entry = state.get(remote_path)
    if not target.exists():
        return False
    if entry is None:
        raise FileExistsError(
            f"untracked existing Betfair file blocks resume: {relative.as_posix()}"
        )
    if entry.relative_path != relative.as_posix():
        raise ValueError("download state path mismatch")
    if target.stat().st_size != entry.byte_size or _sha256_file(target) != entry.sha256:
        raise ValueError(
            "existing Betfair file no longer matches resume state: "
            f"{relative.as_posix()}"
        )
    return True


def download_purchased_history(
    *,
    client: HistoricalDataClient,
    plan_name: str,
    start_date: date,
    end_date: date,
    output_root: str | Path,
    countries: tuple[str, ...] = (),
    dry_run: bool = False,
) -> DownloadReport:
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    state_path = root / "download-state.json"
    state = _load_state(state_path)
    windows = _month_windows(start_date, end_date)

    listed: list[str] = []
    for window_start, window_end in windows:
        filter_ = HistoricalFilter(
            plan_name=plan_name,
            start_date=window_start,
            end_date=window_end,
            countries=countries,
        )
        listed.extend(client.list_files(filter_))
    remote_paths = sorted(set(listed))

    downloaded = 0
    skipped = 0
    bytes_downloaded = 0
    for remote_path in remote_paths:
        if _verify_existing(root=root, remote_path=remote_path, state=state):
            skipped += 1
            continue
        if dry_run:
            continue
        relative = _safe_relative_remote_path(remote_path)
        target = root / relative
        temporary = target.with_name(target.name + ".part")
        if temporary.exists():
            temporary.unlink()
        reported_size = client.download_file(remote_path, temporary)
        if not temporary.exists():
            raise RuntimeError(
                "Betfair download client did not create the expected temporary file"
            )
        actual_size = temporary.stat().st_size
        if reported_size != actual_size:
            temporary.unlink()
            raise RuntimeError("Betfair download byte count disagrees with downloaded file size")
        digest = _sha256_file(temporary)
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary.replace(target)
        state[remote_path] = DownloadStateEntry(
            remote_path=remote_path,
            relative_path=relative.as_posix(),
            byte_size=actual_size,
            sha256=digest,
        )
        _write_state(state_path, state)
        downloaded += 1
        bytes_downloaded += actual_size

    return DownloadReport(
        plan_name=plan_name,
        start_date=start_date.isoformat(),
        end_date=end_date.isoformat(),
        month_windows=len(windows),
        files_listed=len(remote_paths),
        files_downloaded=downloaded,
        files_skipped_verified=skipped,
        bytes_downloaded=bytes_downloaded,
        dry_run=dry_run,
        state_path=state_path.as_posix(),
    )


def _parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("date must be YYYY-MM-DD") from exc


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download already-purchased Betfair Historical Tennis market files safely"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("purchases", help="show purchased historical data packages")

    download = subparsers.add_parser(
        "download",
        help="download purchased Tennis MATCH_ODDS M files month-by-month",
    )
    download.add_argument("--plan", required=True, help="exact plan string returned by GetMyData")
    download.add_argument("--start-date", required=True, type=_parse_date)
    download.add_argument("--end-date", required=True, type=_parse_date)
    download.add_argument("--output-root", required=True, type=Path)
    download.add_argument("--country", action="append", default=[])
    download.add_argument("--dry-run", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    client = HistoricalDataClient.from_environment()
    if args.command == "purchases":
        print(json.dumps(client.get_my_data(), indent=2, sort_keys=True))
        return
    report = download_purchased_history(
        client=client,
        plan_name=args.plan,
        start_date=args.start_date,
        end_date=args.end_date,
        output_root=args.output_root,
        countries=tuple(sorted(set(args.country))),
        dry_run=args.dry_run,
    )
    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
