#!/usr/bin/env python3
"""
Test runner for ai-package-guard with clear telemetry.
Outputs structured logs and a JSON report for CI.
"""

import json
import subprocess
import sys
import datetime
from pathlib import Path

ROOT = Path(__file__).parent.parent
SCRIPT = ROOT / "scripts" / "verify_packages.py"
EVALS = ROOT / "evals" / "evals.json"
TRIGGERS = ROOT / "evals" / "triggers.json"
REPORT_PATH = ROOT / "evals" / "test-report.json"

TELEMETRY = {
    "started_at": datetime.datetime.utcnow().isoformat() + "Z",
    "skill": "ai-package-guard",
    "tests": [],
    "summary": {},
}


def log(msg: str):
    print(msg, flush=True)


def run_verify(packages):
    cmd = [sys.executable, str(SCRIPT)] + packages
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def record(name: str, status: str, details: dict = None):
    entry = {
        "name": name,
        "status": status,
        "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
        "details": details or {},
    }
    TELEMETRY["tests"].append(entry)
    icon = "✅" if status == "pass" else "❌"
    log(f"  {icon} {name}")


def test_known_good():
    code, out, err = run_verify(["express", "lodash"])
    data = json.loads(out)
    ok = code == 0 and len(data) == 2 and all(r["risk"] == "low" for r in data)
    record("known_good_packages", "pass" if ok else "fail", {"exit_code": code, "risks": [r["risk"] for r in data]})
    if not ok:
        raise AssertionError("known good failed")


def test_nonexistent():
    code, out, err = run_verify(["this-package-definitely-does-not-exist-xyz-999"])
    data = json.loads(out)
    ok = code == 2 and data[0]["exists"] is False and data[0]["risk"] == "high"
    record("nonexistent_package", "pass" if ok else "fail", {"exit_code": code, "risk": data[0].get("risk")})
    if not ok:
        raise AssertionError("nonexistent failed")


def test_mixed():
    code, out, err = run_verify(["lodash", "fake-package-abc-123"])
    data = json.loads(out)
    risks = [r["risk"] for r in data]
    ok = code == 2 and "low" in risks and "high" in risks
    record("mixed_packages", "pass" if ok else "fail", {"exit_code": code, "risks": risks})
    if not ok:
        raise AssertionError("mixed failed")


def test_evals_structure():
    with open(EVALS) as f:
        data = json.load(f)
    ok = (
        data.get("skill") == "ai-package-guard"
        and len(data.get("test_cases", [])) >= 7
        and all("name" in tc and "input" in tc and "assertions" in tc for tc in data["test_cases"])
    )
    record("evals_structure", "pass" if ok else "fail", {"case_count": len(data.get("test_cases", []))})
    if not ok:
        raise AssertionError("evals structure failed")


def test_triggers_structure():
    with open(TRIGGERS) as f:
        data = json.load(f)
    positives = [t for t in data.get("test_cases", []) if t.get("should_trigger")]
    negatives = [t for t in data.get("test_cases", []) if not t.get("should_trigger")]
    ok = len(positives) >= 5 and len(negatives) >= 3
    record("triggers_structure", "pass" if ok else "fail", {"positives": len(positives), "negatives": len(negatives)})
    if not ok:
        raise AssertionError("triggers structure failed")


def main():
    log("=== ai-package-guard test runner ===")
    log(f"Started: {TELEMETRY['started_at']}\n")

    tests = [
        test_known_good,
        test_nonexistent,
        test_mixed,
        test_evals_structure,
        test_triggers_structure,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            record(t.__name__, "fail", {"error": str(e)})

    passed = sum(1 for t in TELEMETRY["tests"] if t["status"] == "pass")
    total = len(TELEMETRY["tests"])
    TELEMETRY["summary"] = {
        "passed": passed,
        "failed": total - passed,
        "total": total,
        "finished_at": datetime.datetime.utcnow().isoformat() + "Z",
        "success": passed == total,
    }

    log(f"\n=== Results: {passed}/{total} passed ===")
    log(f"Finished: {TELEMETRY['summary']['finished_at']}")

    # Write transparent report
    with open(REPORT_PATH, "w") as f:
        json.dump(TELEMETRY, f, indent=2)
    log(f"Report written to: {REPORT_PATH}")

    sys.exit(0 if TELEMETRY["summary"]["success"] else 1)


if __name__ == "__main__":
    main()
