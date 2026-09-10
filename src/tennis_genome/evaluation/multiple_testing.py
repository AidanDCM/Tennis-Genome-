from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class HolmResult:
    label: str
    raw_p_value: float
    adjusted_p_value: float
    rank: int


def holm_adjust(p_values: dict[str, float]) -> dict[str, HolmResult]:
    """Holm step-down family-wise p-value adjustment.

    Returns multiplicity-adjusted p-values while preserving the caller's labels.
    Equal p-values are ordered deterministically by label.
    """

    if not p_values:
        raise ValueError("p_values must be non-empty")
    for label, value in p_values.items():
        if not label:
            raise ValueError("Holm labels must be non-empty")
        if not 0.0 <= float(value) <= 1.0:
            raise ValueError("Holm p-values must be in [0, 1]")

    ordered = sorted(
        ((label, float(value)) for label, value in p_values.items()),
        key=lambda item: (item[1], item[0]),
    )
    family_size = len(ordered)
    running_max = 0.0
    results: dict[str, HolmResult] = {}
    for index, (label, raw) in enumerate(ordered):
        multiplier = family_size - index
        adjusted = min(1.0, raw * multiplier)
        running_max = max(running_max, adjusted)
        results[label] = HolmResult(
            label=label,
            raw_p_value=raw,
            adjusted_p_value=running_max,
            rank=index + 1,
        )
    return results
