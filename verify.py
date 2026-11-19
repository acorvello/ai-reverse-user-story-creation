"""Evidence verification: checks that what the model cites actually exists."""

from __future__ import annotations

from pathlib import Path

from .models import Feature
from .scanner import line_count


def verify_evidence(root: str | Path, feature: Feature) -> list[str]:
    """Return a list of problems. An empty list means every citation is valid."""
    problems: list[str] = []
    for rule in feature.rules:
        for item in rule.evidence:
            try:
                total = line_count(root, item.file)
            except FileNotFoundError:
                problems.append(f"Evidence file not found: {item.file}")
                continue
            except ValueError:
                problems.append(f"Evidence path is outside the repository: {item.file}")
                continue
            if item.end_line > total:
                problems.append(
                    f"Line range {item.start_line}-{item.end_line} exceeds the {total} lines of {item.file}"
                )
    return problems
