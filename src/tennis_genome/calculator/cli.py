from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import load_validated_matchup_calculator
from .io import load_matchup_input


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the market-blind TGE-Independent-v1 matchup calculator"
    )
    parser.add_argument(
        "--bundle",
        required=True,
        type=Path,
        help="Path to tge_independent_v1_production.json",
    )
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Provider-neutral matchup input JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional output JSON path; stdout is always written",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    calculator = load_validated_matchup_calculator(args.bundle)
    matchup = load_matchup_input(args.input)
    result = calculator.calculate(matchup)
    rendered = json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n"
    if args.output is not None:
        args.output.write_text(rendered)
    print(rendered, end="")


if __name__ == "__main__":
    main()
