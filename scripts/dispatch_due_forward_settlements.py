from __future__ import annotations

import hashlib
import io
import json
import os
import urllib.error
import urllib.request
import zipfile
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

REPOSITORY = "AidanDCM/Tennis-Genome-"
SETTLEMENT_WORKFLOW = "prospective_settlement_capture.yml"
SETTLEMENT_GRACE = timedelta(hours=4)
SETTLEMENT_MAX_AGE = timedelta(hours=30)
MAX_DISPATCHES_PER_RUN = 10


def _parse_time(value: object) -> datetime:
    text = str(value).strip()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return parsed.astimezone(UTC)


def settlement_due(*, scheduled_start: datetime, now: datetime) -> bool:
    if scheduled_start.tzinfo is None or scheduled_start.utcoffset() is None:
        raise ValueError("scheduled_start must be timezone-aware")
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    age = now.astimezone(UTC) - scheduled_start.astimezone(UTC)
    return SETTLEMENT_GRACE <= age <= SETTLEMENT_MAX_AGE


class GitHubApi:
    def __init__(self, *, repository: str, token: str) -> None:
        if repository != REPOSITORY:
            raise ValueError("unexpected repository")
        if not token.strip():
            raise ValueError("GitHub token is required")
        self.repository = repository
        self.token = token

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
    ) -> bytes:
        url = f"https://api.github.com/repos/{self.repository}/{path.lstrip('/')}"
        data = None
        if payload is not None:
            data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=data,
            method=method,
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "User-Agent": "tennis-genome-forward-settlement-monitor",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"GitHub API {method} {path} failed with HTTP {exc.code}: {body}"
            ) from exc

    def json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, object] | None = None,
    ) -> dict[str, object]:
        raw = self._request(path, method=method, payload=payload)
        if not raw:
            return {}
        value = json.loads(raw.decode("utf-8"))
        if not isinstance(value, dict):
            raise RuntimeError("GitHub API response must be a JSON object")
        return value

    def list_artifacts(self) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        page = 1
        while True:
            payload = self.json(f"actions/artifacts?per_page=100&page={page}")
            rows = payload.get("artifacts", [])
            if not isinstance(rows, list):
                raise RuntimeError("GitHub artifact listing is malformed")
            batch = [row for row in rows if isinstance(row, dict)]
            result.extend(batch)
            if len(batch) < 100:
                break
            page += 1
        return result

    def run_artifacts(self, run_id: int) -> list[dict[str, object]]:
        payload = self.json(f"actions/runs/{run_id}/artifacts?per_page=100")
        rows = payload.get("artifacts", [])
        if not isinstance(rows, list):
            raise RuntimeError("GitHub run artifact listing is malformed")
        return [row for row in rows if isinstance(row, dict)]

    def artifact_zip(self, artifact_id: int) -> zipfile.ZipFile:
        raw = self._request(f"actions/artifacts/{artifact_id}/zip")
        return zipfile.ZipFile(io.BytesIO(raw))

    def dispatch(self, workflow: str, inputs: dict[str, str]) -> None:
        self._request(
            f"actions/workflows/{workflow}/dispatches",
            method="POST",
            payload={"ref": "main", "inputs": inputs},
        )


def _active_by_name(
    artifacts: list[dict[str, object]],
) -> dict[str, list[dict[str, object]]]:
    result: dict[str, list[dict[str, object]]] = {}
    for artifact in artifacts:
        if artifact.get("expired") is not False:
            continue
        name = str(artifact.get("name", ""))
        if not name:
            continue
        result.setdefault(name, []).append(artifact)
    return result


def _zip_bytes(archive: zipfile.ZipFile, *names: str) -> bytes:
    for name in names:
        try:
            return archive.read(name)
        except KeyError:
            continue
    raise ValueError(f"artifact is missing required file alternatives: {names}")


def _zip_json(archive: zipfile.ZipFile, *names: str) -> dict[str, object]:
    value = json.loads(_zip_bytes(archive, *names).decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"artifact JSON must be an object: {names}")
    return value


def _positive_int(value: object, *, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be a positive integer") from exc
    if parsed <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return parsed


def _one_active(
    by_name: dict[str, list[dict[str, object]]],
    name: str,
) -> dict[str, object] | None:
    matches = by_name.get(name, [])
    if not matches:
        return None
    if len(matches) != 1:
        raise ValueError(f"expected at most one active artifact named {name}")
    return matches[0]


def _candidate_from_prediction(
    *,
    api: GitHubApi,
    artifact: dict[str, object],
    by_name: dict[str, list[dict[str, object]]],
    now: datetime,
) -> tuple[dict[str, str] | None, str]:
    artifact_id = _positive_int(artifact.get("id"), field="prediction_artifact_id")
    verified_name = f"full-stack-forward-verified-settlement-{artifact_id}"
    if _one_active(by_name, verified_name) is not None:
        return None, "already_finalized"

    archive = api.artifact_zip(artifact_id)
    resolution = _zip_json(archive, "forward-004-target-resolution.json")
    scheduled_start = _parse_time(resolution.get("scheduled_start"))
    if not settlement_due(scheduled_start=scheduled_start, now=now):
        return None, "outside_settlement_window"

    prediction_sha = _zip_bytes(
        archive,
        "prediction-work/prediction-record-sha256.txt",
    ).decode("utf-8").strip()
    if len(prediction_sha) != 64 or any(
        char not in "0123456789abcdef" for char in prediction_sha
    ):
        raise ValueError("prediction record SHA is invalid")

    capture_name = f"prospective-trusted-settlement-capture-{prediction_sha}"
    if _one_active(by_name, capture_name) is not None:
        return None, "settlement_capture_exists"

    anchor_name = f"prospective-prediction-anchor-{prediction_sha}"
    anchor_artifact = _one_active(by_name, anchor_name)
    if anchor_artifact is None:
        return None, "prediction_anchor_artifact_missing"
    anchor_id = _positive_int(anchor_artifact.get("id"), field="anchor_artifact_id")
    anchor_zip = api.artifact_zip(anchor_id)
    comment_id = _positive_int(
        _zip_bytes(
            anchor_zip,
            "comment-id.txt",
            "prediction-anchor/comment-id.txt",
        ).decode("utf-8").strip(),
        field="prediction_anchor_comment_id",
    )

    provider_run = _zip_json(archive, "provider-run.json")
    provider_run_id = _positive_int(provider_run.get("id"), field="provider_run_id")
    provider_name = f"trusted-provider-capture-{provider_run_id}"
    provider_matches = [
        item
        for item in api.run_artifacts(provider_run_id)
        if item.get("expired") is False and str(item.get("name", "")) == provider_name
    ]
    if len(provider_matches) != 1:
        raise ValueError(
            f"expected one active trusted provider artifact on run {provider_run_id}"
        )
    provider_artifact_id = _positive_int(
        provider_matches[0].get("id"),
        field="provider_artifact_id",
    )

    identity_bytes = _zip_bytes(
        archive,
        "prediction-work/sportradar-identity-binding.json",
    )
    identity = json.loads(identity_bytes.decode("utf-8"))
    if not isinstance(identity, dict):
        raise ValueError("prediction identity binding must be an object")
    if identity.get("schema_version") != "full-stack-pilot-sportradar-identity-v1":
        raise ValueError("unexpected prediction identity schema")
    identity_sha = hashlib.sha256(identity_bytes).hexdigest()

    event_id = str(resolution.get("event_id", ""))
    if not event_id.startswith("sr:sport_event:"):
        raise ValueError("Forward-004 resolution event ID is invalid")

    return (
        {
            "prediction_record_sha256": prediction_sha,
            "prediction_artifact_id": str(artifact_id),
            "provider_artifact_id": str(provider_artifact_id),
            "prediction_anchor_comment_id": str(comment_id),
            "identity_binding_sha256": identity_sha,
            "sportradar_event_id": event_id,
            "sportradar_access_level": "trial",
        },
        "due",
    )


def run_monitor(
    *,
    api: GitHubApi,
    now: datetime,
) -> dict[str, object]:
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    artifacts = api.list_artifacts()
    by_name = _active_by_name(artifacts)
    predictions = sorted(
        (
            artifact
            for artifact in artifacts
            if artifact.get("expired") is False
            and str(artifact.get("name", "")).startswith("wta-forward-004-")
        ),
        key=lambda item: int(item.get("id", 0)),
    )

    rows: list[dict[str, Any]] = []
    dispatch_count = 0
    error_count = 0
    for artifact in predictions:
        artifact_id = int(artifact.get("id", 0))
        try:
            candidate, status = _candidate_from_prediction(
                api=api,
                artifact=artifact,
                by_name=by_name,
                now=now,
            )
            if candidate is not None and dispatch_count < MAX_DISPATCHES_PER_RUN:
                api.dispatch(SETTLEMENT_WORKFLOW, candidate)
                dispatch_count += 1
                rows.append(
                    {
                        "prediction_artifact_id": artifact_id,
                        "status": "dispatched",
                        "sportradar_event_id": candidate["sportradar_event_id"],
                    }
                )
            elif candidate is not None:
                rows.append(
                    {
                        "prediction_artifact_id": artifact_id,
                        "status": "dispatch_cap_reached",
                    }
                )
            else:
                rows.append(
                    {
                        "prediction_artifact_id": artifact_id,
                        "status": status,
                    }
                )
        except Exception as exc:  # noqa: BLE001
            error_count += 1
            rows.append(
                {
                    "prediction_artifact_id": artifact_id,
                    "status": "error",
                    "error": str(exc),
                }
            )

    return {
        "schema_version": "tennis-genome-forward-settlement-monitor-v1",
        "repository": api.repository,
        "checked_at": now.astimezone(UTC).isoformat(),
        "prediction_artifact_count": len(predictions),
        "dispatch_count": dispatch_count,
        "error_count": error_count,
        "rows": rows,
    }


def main() -> None:
    api = GitHubApi(
        repository=os.environ.get("GITHUB_REPOSITORY", ""),
        token=os.environ.get("GH_TOKEN", ""),
    )
    report = run_monitor(api=api, now=datetime.now(UTC))
    path = Path("settlement-monitor-report.json")
    path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(path.read_text(encoding="utf-8"), end="")
    if int(report["error_count"]) > 0:
        raise SystemExit("settlement monitor encountered malformed retained evidence")


if __name__ == "__main__":
    main()
