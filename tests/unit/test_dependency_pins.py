"""
Unit Test -- Group M: Pinned Dependency Versions (NFR-16)
Maps to Master Test Plan Section 3.3.3, Test Case TC-RB-069.

Formalises what was previously only verified by ad-hoc manual code review
during the SRS/backlog reconciliation audit (which found and flagged a typo
in one dependency name). Reads the real requirements.txt from the project
root and asserts every non-comment, non-blank line is an exact pin
(package==X.Y.Z), not a range/caret/unpinned entry.
"""
import re
from pathlib import Path

import pytest

REQUIREMENTS_PATH = Path(__file__).resolve().parents[2] / "requirements.txt"

EXACT_PIN_RE = re.compile(r"^[A-Za-z0-9_.\-\[\]]+==[A-Za-z0-9.\-]+$")


def _read_requirement_lines():
    assert REQUIREMENTS_PATH.exists(), f"requirements.txt not found at {REQUIREMENTS_PATH}"
    lines = []
    for raw in REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def test_UT20_TC_RB_069_all_dependencies_are_exactly_pinned():
    lines = _read_requirement_lines()
    assert lines, "requirements.txt appears to be empty"

    unpinned = [line for line in lines if not EXACT_PIN_RE.match(line)]
    assert not unpinned, (
        "NFR-16 violation: the following requirements.txt entries are not "
        f"exact pins (package==version): {unpinned}"
    )


def test_UT21_no_duplicate_package_entries():
    """A secondary sanity check: no package should be listed twice with
    two different pinned versions, which would make the pin ambiguous."""
    lines = _read_requirement_lines()
    names = [line.split("==")[0].lower() for line in lines if "==" in line]
    duplicates = {n for n in names if names.count(n) > 1}
    assert not duplicates, f"Duplicate/conflicting pins found for: {duplicates}"
