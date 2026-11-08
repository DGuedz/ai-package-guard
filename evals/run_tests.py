#!/usr/bin/env python3
"""
Test runner for ai-package-guard.
Runs unit tests on verify_packages.py + structural checks on skill files.
"""

import json
import subprocess
import sys
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "verify_packages.py"
EVALS = ROOT / "evals" / "evals.json"
TRIGGERS = ROOT / "evals" / "triggers.json"


def run_verify(packages, expect_exit=0):
    """Run verify_packages.py and return (exit_code, stdout, stderr)."""
    cmd = [sys.executable, str(SCRIPT)] + packages
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def test_known_good():
    print("→ Testing known-good packages (express, lodash)...")
    code, out, err = run_verify(["express", "lodash"], expect_exit=0)
    data = json.loads(out)
    assert len(data) == 2
    assert all(r["risk"] == "low" for r in data)
    assert code == 0
    print("  ✅ PASS")


def test_nonexistent():
    print("→ Testing nonexistent package...")
    code, out, err = run_verify(["this-package-definitely-does-not-exist-xyz-999"], expect_exit=2)
    data = json.loads(out)
    assert data[0]["exists"] is False
    assert data[0]["risk"] == "high"
    assert code == 2
    print("  ✅ PASS")


def test_mixed():
    print("→ Testing mixed (good + bad)...")
    code, out, err = run_verify(["lodash", "fake-package-abc-123"], expect_exit=2)
    data = json.loads(out)
    assert any(r["risk"] == "low" for r in data)
    assert any(r["risk"] == "high" for r in data)
    assert code == 2
    print("  ✅ PASS")


def test_evals_structure():
    print("→ Validating evals.json structure...")
    with open(EVALS) as f:
        data = json.load(f)
    assert data["skill"] == "ai-package-guard"
    assert len(data["test_cases"]) >= 5
    for tc in data["test_cases"]:
        assert "name" in tc and "input" in tc and "assertions" in tc
        assert len(tc["assertions"]) >= 2
    print("  ✅ PASS")


def test_triggers_structure():
    print("→ Validating triggers.json structure...")
    with open(TRIGGERS) as f:
        data = json.load(f)
    assert data["skill"] == "ai-package-guard"
    positives = [t for t in data["test_cases"] if t["should_trigger"]]
    negatives = [t for t in data["test_cases"] if not t["should_trigger"]]
    assert len(positives) >= 4
    assert len(negatives) >= 2
    print("  ✅ PASS")


def main():
    print("=== ai-package-guard test runner ===\n")
    tests = [
        test_known_good,
        test_nonexistent,
        test_mixed,
        test_evals_structure,
        test_triggers_structure,
    ]
    failed = 0
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            failed += 1
    print(f"\n=== Results: {len(tests) - failed}/{len(tests)} passed ===")
    sys.exit(0 if failed == 0 else 1)


if __name__ == "__main__":
    main()
