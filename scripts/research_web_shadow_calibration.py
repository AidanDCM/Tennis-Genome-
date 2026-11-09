"""Research-only chronological calibration ablation for non-production Web Shadow.

Usage: python scripts/research_web_shadow_calibration.py --repo-root .
Never writes predictions, champion artifacts, or the scorecard.
"""
from __future__ import annotations

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path


def sigmoid(x: float) -> float:
    if x >= 0:
        return 1 / (1 + math.exp(-x))
    z = math.exp(x)
    return z / (1 + z)


def adjusted(p: float, slope: float) -> float:
    if not 0 < p < 1 or slope <= 0:
        raise ValueError("probability and slope must be strictly positive/interior")
    return sigmoid(slope * math.log(p / (1 - p)))


def score(rows: list[dict], slope: float) -> dict:
    if not rows:
        raise ValueError("no evaluation rows")
    probs = [adjusted(r["p"], slope) for r in rows]
    outcomes = [int(r["correct"]) for r in rows]
    n = len(rows)
    return {
        "n": n,
        "accuracy": sum((p >= 0.5) == bool(y) for p, y in zip(probs, outcomes, strict=True)) / n,
        "brier": sum((p-y)**2 for p, y in zip(probs, outcomes, strict=True)) / n,
        "log_loss": -sum(
            y * math.log(p) + (1 - y) * math.log1p(-p)
            for p, y in zip(probs, outcomes, strict=True)
        ) / n,
        "mean_selected_probability": sum(probs) / n,
    }


def read_rows(root: Path) -> tuple[list[dict], dict]:
    sc = json.loads((root / "web-shadow/scorecard.json").read_text())
    if sc["production_eligible"] is not False:
        raise ValueError("requires non-production scorecard")
    rows = []
    statuses = {}
    seen = set()
    for slate in sc["slates"]:
        for entry in slate["predictions"]:
            if entry["status"] != "SETTLED":
                continue
            mid = entry["match_id"]
            if mid in seen:
                raise ValueError(f"duplicate match: {mid}")
            seen.add(mid)
            path = Path(entry["settlement_path"])
            if path.is_absolute() or ".." in path.parts or path.parts[0] != "web-shadow":
                raise ValueError(f"unsafe settlement path: {path}")
            settlement = json.loads((root / path).read_text())
            if (settlement["match_id"] != mid or
                    settlement["record_sha256"] != entry["settlement_record_sha256"]):
                raise ValueError(f"settlement mismatch: {mid}")
            status = settlement["status"]
            statuses[status] = statuses.get(status, 0) + 1
            if status != "COMPLETED":
                continue
            prediction = json.loads((root / entry["prediction_path"]).read_text())
            if prediction["record_sha256"] != entry["prediction_record_sha256"]:
                raise ValueError(f"prediction mismatch: {mid}")
            committed = datetime.fromisoformat(prediction["committed_at"])
            start = datetime.fromisoformat(entry["scheduled_start"])
            observed = datetime.fromisoformat(settlement["result_observed_at"])
            if any(d.tzinfo is None for d in (committed, start, observed)):
                raise ValueError(f"missing timezone: {mid}")
            if not committed < start:
                raise ValueError(f"not committed before start: {mid}")
            if not observed >= start:
                raise ValueError(f"result observed before scheduled start: {mid}")
            correct = settlement["winner"] == entry["selected_player"]
            if settlement["prediction_correct"] is not correct:
                raise ValueError(f"result label mismatch: {mid}")
            p = float(entry["selected_probability"])
            if not 0.5 <= p < 1:
                raise ValueError(f"invalid selected probability: {mid}")
            rows.append({"id": mid, "start": start.astimezone(UTC),
                         "observed": observed.astimezone(UTC),
                         "p": p, "correct": correct})
    rows.sort(key=lambda x: (x["start"], x["id"]))
    if len(rows) != sc["metrics"]["settled_match_count"]:
        raise ValueError("eligible row count differs from scorecard")
    baseline = score(rows, 1.0)
    for key, sc_key in (("accuracy", "accuracy"), ("brier", "brier_score"),
                        ("log_loss", "log_loss")):
        if abs(baseline[key] - sc["metrics"][sc_key]) > 1e-10:
            raise ValueError(f"scorecard reproduction mismatch: {key}")
    return rows, statuses


def experiment(rows: list[dict], min_train: int = 30) -> dict:
    if len(rows) <= min_train:
        raise ValueError("insufficient sample")
    # First 30 completed outcomes become available before an evaluation starts.
    # Every later test is strictly out of training time. No final test label
    # is used to fit slope. A simple predeclared grid limits search.
    slopes = (0.5, 0.7, 0.9, 1.0, 1.1)
    tests = []
    for i in range(min_train, len(rows)):
        current = rows[i]
        training = [r for r in rows[:i] if r["observed"] < current["start"]]
        if len(training) < min_train:
            continue
        # Penalize moving away from 1.0 to reduce small-sample overfitting.
        chosen = min(slopes, key=lambda s: score(training, s)["log_loss"] +
                     0.01 * (s - 1.0)**2)
        tests.append((current, chosen))
    if not tests:
        raise ValueError("no causally eligible evaluation rows")
    baseline = score([r for r, _ in tests], 1.0)
    challenger_probs = [adjusted(r["p"], s) for r, s in tests]
    outcomes = [int(r["correct"]) for r, _ in tests]
    n = len(tests)
    challenger = {
        "n": n,
        "accuracy": sum((p >= 0.5) == bool(y) for p, y in zip(challenger_probs, outcomes, strict=True))/n,
        "brier": sum((p-y)**2 for p, y in zip(challenger_probs, outcomes, strict=True))/n,
        "log_loss": -sum(
            y * math.log(p) + (1 - y) * math.log1p(-p)
            for p, y in zip(challenger_probs, outcomes, strict=True)
        ) / n,
    }
    if abs(challenger["accuracy"] - baseline["accuracy"]) > 1e-12:
        raise AssertionError("positive slope must preserve winner accuracy")
    return {"evaluated_n": n, "min_train": min_train, "slope_grid": list(slopes),
            "baseline": baseline, "challenger": challenger,
            "paired_brier_improvement": baseline["brier"] - challenger["brier"],
            "paired_log_loss_improvement": baseline["log_loss"] - challenger["log_loss"],
            "selected_slopes": {str(s): sum(v == s for _, v in tests) for s in slopes},
            "evaluation_ids": [r["id"] for r, _ in tests],
            "research_only": True, "production_eligible": False,
            "warning": "Exploratory reused paper scorecard, not independent forward validation."}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args()
    rows, statuses = read_rows(args.repo_root)
    print(json.dumps({"source": "web-shadow/scorecard.json",
                      "completed_n": len(rows), "settlement_statuses": statuses,
                      "experiment": experiment(rows)}, indent=2))


if __name__ == "__main__":
    main()
