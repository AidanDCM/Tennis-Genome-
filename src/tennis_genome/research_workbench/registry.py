from __future__ import annotations

import json
import os
from pathlib import Path

from .contracts import WorkbenchRecord


class ImmutableResearchRegistry:
    """Content-addressed, append-only registry for workbench records."""

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    def register(self, namespace: str, record: WorkbenchRecord) -> Path:
        if not namespace or "/" in namespace or "\\" in namespace:
            raise ValueError("namespace must be a single non-empty path component")
        directory = self.root / namespace
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"{record.semantic_sha256}.json"
        payload = {
            "semantic_sha256": record.semantic_sha256,
            "record": record.canonical_payload(),
        }
        encoded = (
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        )
        if path.exists():
            if path.read_text(encoding="utf-8") != encoded:
                raise RuntimeError(f"immutable registry record was modified: {path}")
            return path

        temporary = path.with_suffix(path.suffix + f".tmp.{os.getpid()}")
        with temporary.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(path)
        return path
