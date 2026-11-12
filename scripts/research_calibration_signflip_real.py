"""Read-only sign-flip sensitivity for existing chronological WTA calibration study.

Run: python scripts/research_calibration_signflip_real.py --repo-root .
This is a retrospective exploratory sharp-null diagnostic, not a model
selection p-value, and never modifies the champion or source records.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC
from pathlib import Path

# Support both package imports (pytest) and direct script execution (GitHub Actions).
if __package__:
    from .research_cluster_sign_flip import sign_flip_sensitivity
    from .research_web_shadow_calibration import adjusted, experiment, read_rows, score
else:
    from research_cluster_sign_flip import sign_flip_sensitivity
    from research_web_shadow_calibration import adjusted, experiment, read_rows, score


def evaluate(root: Path) -> dict:
    rows, statuses = read_rows(root)
    result = experiment(rows)
    ids = result["evaluation_ids"]
    index = {row["id"]: row for row in rows}
    if len(ids) != len(set(ids)) or any(mid not in index for mid in ids):
        raise ValueError("evaluation IDs must be unique and present")
    evaluated = [index[mid] for mid in ids]
    # Reconstruct the exact adaptive selection from the frozen study algorithm.
    # Check it reproduces the study's recorded Brier and log-loss metrics.
    slopes = (0.5, 0.7, 0.9, 1.0, 1.1)
    adaptive = []
    for row in evaluated:
        prior = [
            r for r in rows
            if r["start"] < row["start"] and r["observed"] < row["start"]
        ]
        if len(prior) < result["min_train"]:
            raise ValueError("insufficient causally available training history")
        adaptive.append(
            min(slopes, key=lambda s: score(prior, s)["log_loss"]
                + 0.01 * (s - 1.0) ** 2)
        )
    if any(result["selected_slopes"][str(s)] != adaptive.count(s) for s in slopes):
        raise ValueError("adaptive slope counts do not reproduce original study")
    keys = [row["start"].astimezone(UTC).date().isoformat() for row in evaluated]
    output = {}
    for label, chosen in (("adaptive", adaptive), ("fixed_half", [0.5] * len(ids))):
        brier = []
        log_loss = []
        for row, slope in zip(evaluated, chosen, strict=True):
            p = float(row["p"])
            y = int(row["correct"])
            q = adjusted(p, slope)
            brier.append((p - y) ** 2 - (q - y) ** 2)
            log_loss.append(
                math.log(q / p) if y else math.log1p(-q) - math.log1p(-p)
            )
        # Sensitivity only: omit each date; do not refit locked probabilities.
        leave_one_date_out = []
        for day in sorted(set(keys)):
            keep = [i for i, key in enumerate(keys) if key != day]
            if not keep:
                raise ValueError("date exclusion left no observations")
            leave_one_date_out.append({
                "excluded_date": day,
                "excluded_n": len(keys) - len(keep),
                "remaining_n": len(keep),
                "brier_improvement": sum(brier[i] for i in keep) / len(keep),
                "log_loss_improvement": sum(log_loss[i] for i in keep) / len(keep),
            })
        output[label] = {
            "brier": sign_flip_sensitivity(brier, keys),
            "log_loss": sign_flip_sensitivity(log_loss, keys),
            "leave_one_date_out": leave_one_date_out,
        }
        expected = (
            result["paired_brier_improvement"] if label == "adaptive"
            else result["baseline"]["brier"] - result["fixed_half_control"]["brier"]
        )
        if abs(sum(brier) / len(brier) - expected) > 1e-10:
            raise ValueError("Brier improvement does not reproduce original study")
    return {
        "research_only": True,
        "production_eligible": False,
        "source": "web-shadow/scorecard.json",
        "settlement_statuses": statuses,
        "evaluation_n": len(ids),
        "evaluation_ids": ids,
        "date_clusters": len(set(keys)),
        "results": output,
        "interpretation": (
            "Exploratory cluster sign-flip fractions conditional on unverified "
            "sign-exchangeability; reused observations, repeated testing, and "
            "temporal dependence prevent confirmatory significance claims."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    print(json.dumps(evaluate(args.repo_root), indent=2))


if __name__ == "__main__":
    main()
