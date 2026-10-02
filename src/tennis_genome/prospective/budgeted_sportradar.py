"""Durable, bounded Sportradar capture for low-volume supervised operation.

This module is transport infrastructure, not a prediction or formal eligibility
decision. Requests are charged before sending, including failed attempts.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.request import Request, urlopen

_SAFE_PATH = re.compile(r"^[A-Za-z0-9_./:?-]+$")
_HOST = "https://api.sportradar.com"


class RequestBudgetExceeded(RuntimeError):
    """The configured local ceiling would be exceeded by another attempt."""


@dataclass(frozen=True)
class CapturedResponse:
    body: bytes
    sha256: str
    observed_at: datetime
    from_cache: bool
    status: int


Transport = Callable[[str, Mapping[str, str]], tuple[int, bytes]]


def _http_get(url: str, headers: Mapping[str, str]) -> tuple[int, bytes]:
    request = Request(url, headers=dict(headers))
    with urlopen(request, timeout=30) as response:  # noqa: S310 - fixed HTTPS host
        return response.status, response.read()


def _utc_now() -> datetime:
    return datetime.now(UTC)


class BudgetedSportradarStore:
    """One process-safe writer and a persistent content-addressed response cache."""

    def __init__(
        self,
        root: Path,
        *,
        daily_limit: int,
        weekly_limit: int,
        transport: Transport = _http_get,
        now: Callable[[], datetime] = _utc_now,
    ) -> None:
        if daily_limit < 0 or weekly_limit < 0:
            raise ValueError("request ceilings must be nonnegative")
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)
        self.daily_limit = daily_limit
        self.weekly_limit = weekly_limit
        self.transport = transport
        self.now = now
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS attempts ("
                "id INTEGER PRIMARY KEY, request_key TEXT NOT NULL, "
                "sent_at TEXT NOT NULL, result TEXT NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS responses ("
                "id INTEGER PRIMARY KEY, request_key TEXT NOT NULL, "
                "observed_at TEXT NOT NULL, sha256 TEXT NOT NULL, "
                "status INTEGER NOT NULL)"
            )
            db.execute("CREATE INDEX IF NOT EXISTS attempts_time ON attempts(sent_at)")
            db.execute(
                "CREATE INDEX IF NOT EXISTS responses_lookup "
                "ON responses(request_key, observed_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.root / "requests.sqlite3", timeout=45)
        db.execute("PRAGMA busy_timeout=45000")
        return db

    @staticmethod
    def _key(access: str, path: str) -> str:
        if access not in {"trial", "production"}:
            raise ValueError("unsupported Sportradar access level")
        if not path or not _SAFE_PATH.fullmatch(path) or path.startswith("/"):
            raise ValueError("unsupported Sportradar endpoint path")
        if ".." in path or "//" in path or "?" in path or "#" in path:
            raise ValueError("endpoint must be a canonical path without query parameters")
        if not path.endswith(".json"):
            raise ValueError("Sportradar endpoint must request JSON")
        return f"tennis/{access}/v3/en/{path}"

    def _retained(self, sha256: str) -> bytes:
        body = (self.root / "objects" / sha256).read_bytes()
        if hashlib.sha256(body).hexdigest() != sha256:
            raise ValueError("retained Sportradar response hash mismatch")
        return body

    def capture(
        self,
        path: str,
        *,
        api_key: str,
        access: str = "trial",
        max_age: timedelta | None = None,
        offline: bool = False,
    ) -> CapturedResponse:
        if max_age is not None and max_age < timedelta(0):
            raise ValueError("max_age must be nonnegative")
        key = self._key(access, path)
        instant = self.now()
        if instant.tzinfo is None or instant.utcoffset() is None:
            raise ValueError("clock must be timezone-aware")
        instant = instant.astimezone(UTC)
        # Reserve under a SQLite write lock before any outbound attempt.
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT observed_at, sha256, status FROM responses "
                "WHERE request_key=? AND observed_at<=? "
                "ORDER BY observed_at DESC, id DESC LIMIT 1",
                (key, instant.isoformat()),
            ).fetchone()
            if row is not None:
                observed = datetime.fromisoformat(row[0])
                if offline or (max_age is not None and instant - observed <= max_age):
                    body = self._retained(row[1])
                    return CapturedResponse(body, row[1], observed, True, row[2])
            if offline:
                raise FileNotFoundError(f"no retained Sportradar response for {key}")
            if not api_key.strip():
                raise ValueError("SPORTRADAR_API_KEY is not configured")
            pending = db.execute(
                "SELECT 1 FROM attempts WHERE request_key=? AND result='RESERVED' LIMIT 1",
                (key,),
            ).fetchone()
            if pending is not None:
                raise RuntimeError("Sportradar endpoint already has an unresolved request")
            day_start = instant.replace(hour=0, minute=0, second=0, microsecond=0)
            daily_used = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE sent_at>=?",
                (day_start.isoformat(),),
            ).fetchone()[0]
            weekly_used = db.execute(
                "SELECT COUNT(*) FROM attempts WHERE sent_at>=?",
                ((instant - timedelta(days=7)).isoformat(),),
            ).fetchone()[0]
            if daily_used >= self.daily_limit or weekly_used >= self.weekly_limit:
                raise RequestBudgetExceeded("local Sportradar request ceiling reached")
            attempt = db.execute(
                "INSERT INTO attempts(request_key, sent_at, result) VALUES(?, ?, 'RESERVED')",
                (key, instant.isoformat()),
            ).lastrowid
            # Commit the reservation before the network call. A crash consumes
            # one local budget slot conservatively, even if the send is unknown.
            db.commit()

        url = f"{_HOST}/{key}"
        try:
            status, body = self.transport(
                url, {"x-api-key": api_key, "Accept": "application/json"}
            )
            if status != 200:
                raise RuntimeError(f"Sportradar returned HTTP {status}")
            try:
                json.loads(body)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError("Sportradar returned non-JSON HTTP 200 body") from exc
            digest = hashlib.sha256(body).hexdigest()
            object_dir = self.root / "objects"
            object_dir.mkdir(exist_ok=True)
            target = object_dir / digest
            if not target.exists():
                temp = object_dir / f".{digest}.{os.getpid()}.{attempt}.tmp"
                with temp.open("xb") as handle:
                    handle.write(body)
                    handle.flush()
                    os.fsync(handle.fileno())
                os.replace(temp, target)
            # The bytes are durable before the index points to them.
            with self._connect() as db:
                db.execute(
                    "INSERT INTO responses(request_key, observed_at, sha256, status) "
                    "VALUES(?, ?, ?, ?)",
                    (key, instant.isoformat(), digest, status),
                )
                db.execute("UPDATE attempts SET result='SUCCEEDED' WHERE id=?", (attempt,))
            return CapturedResponse(body, digest, instant, False, status)
        except Exception:
            with self._connect() as db:
                db.execute("UPDATE attempts SET result='FAILED' WHERE id=?", (attempt,))
            raise

    def usage(self) -> dict[str, int]:
        instant = self.now().astimezone(UTC)
        day_start = instant.replace(hour=0, minute=0, second=0, microsecond=0)
        with self._connect() as db:
            return {
                "attempts_today": db.execute(
                    "SELECT COUNT(*) FROM attempts WHERE sent_at>=?",
                    (day_start.isoformat(),),
                ).fetchone()[0],
                "attempts_rolling_seven_days": db.execute(
                    "SELECT COUNT(*) FROM attempts WHERE sent_at>=?",
                    ((instant - timedelta(days=7)).isoformat(),),
                ).fetchone()[0],
                "retained_responses": db.execute("SELECT COUNT(*) FROM responses").fetchone()[0],
            }
