from __future__ import annotations

import subprocess
from pathlib import Path


def test_show_ruff_canonical_imports() -> None:
    targets = [
        "src/tennis_genome/research_workbench/__init__.py",
        "tests/test_research_workbench_protected.py",
    ]
    subprocess.run(["ruff", "check", "--fix", *targets], check=False)
    rendered = []
    for target in targets:
        lines = Path(target).read_text(encoding="utf-8").splitlines()
        rendered.append(f"=== {target} ===\n" + "\n".join(lines[:35]))
    raise AssertionError("\n".join(rendered))
