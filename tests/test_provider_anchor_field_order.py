from __future__ import annotations

from pathlib import Path


def test_trusted_provider_anchor_validation_ignores_json_object_order() -> None:
    workflow = (
        Path(__file__).resolve().parents[1]
        / ".github/workflows/prospective_provider_capture_anchor.yml"
    ).read_text(encoding="utf-8")

    assert "set(inputs) != set(ANCHOR_INPUT_FIELDS)" in workflow
    assert "tuple(inputs) != ANCHOR_INPUT_FIELDS" not in workflow
