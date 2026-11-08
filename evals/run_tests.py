#!/usr/bin/env python3
"""
Test runner for ai-package-guard.

Two kinds of checks live in this repo, and the report keeps them apart:

* Tool tests (this file) execute the bundled scripts and assert on results:
  registry lookups, typosquat detection, lockfile diff, and the security gate
  run against throwaway fixture projects built in a temp dir.
* Behavior evals (evals/evals.json) describe how an agent using the skill
  should answer. They need a model + grader and are NOT executed here. Each
  case lists the tool tests that back it in `tool_tests`; the report shows
  which cases have that backing and which are behavior-only.

Usage:
    python evals/run_tests.py            # all tests (needs network for registry tests)
    python evals/run_tests.py --offline  # skip tests that call npm / PyPI
"""

import argparse
import datetime
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
VERIFY = SCRIPTS / "verify_packages.py"
LOCKDIFF = SCRIPTS / "lockfile_diff.py"
GATE = SCRIPTS / "security-gate.sh"
EVALS = ROOT / "evals" / "evals.json"
TRIGGERS = ROOT / "evals" / "triggers.json"
REPORT_PATH = ROOT / "evals" / "test-report.json"

sys.path.insert(0, str(SCRIPTS))
import verify_packages as vp  # noqa: E402
import lockfile_diff as ld  # noqa: E402

TESTS = []


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")


def test(kind):
    """Register a test. kind: 'network' | 'offline' | 'gate' | 'structure'."""
    def wrap(fn):
        TESTS.append((fn.__name__.replace("test_", "", 1), kind, fn))
        return fn
    return wrap


class Fail(AssertionError):
    def __init__(self, msg, details=None):
        super().__init__(msg)
        self.details = details or {}


def check(cond, msg, **details):
    if not cond:
        raise Fail(msg, details)


def run(cmd, cwd=None, env=None):
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=cwd, env=env)
    return r.returncode, r.stdout, r.stderr


def verify_cli(*args):
    code, out, err = run([sys.executable, str(VERIFY)] + list(args))
    return code, json.loads(out)


# --------------------------------------------------------------------------- registry (network)

@test("network")
def test_registry_known_good_npm():
    code, data = verify_cli("express", "lodash")
    risks = [r["risk"] for r in data]
    check(code == 0 and risks == ["low", "low"], "established npm packages should be low risk", exit_code=code, risks=risks)
    return {"exit_code": code, "risks": risks}


@test("network")
def test_registry_nonexistent_npm():
    code, data = verify_cli("this-package-definitely-does-not-exist-xyz-999")
    r = data[0]
    check(code == 2 and r["exists"] is False and r["risk"] == "high", "missing package must be high risk", exit_code=code, result=r)
    return {"exit_code": code, "risk": r["risk"]}


@test("network")
def test_registry_mixed_npm():
    code, data = verify_cli("lodash", "fake-package-abc-123-xyz-999")
    risks = [r["risk"] for r in data]
    check(code == 2 and risks == ["low", "high"], "one bad package must fail the batch", exit_code=code, risks=risks)
    return {"exit_code": code, "risks": risks}


@test("network")
def test_registry_scoped_npm():
    code, data = verify_cli("@types/node", "@definitely-not-a-scope-xyz/nothing-here")
    risks = [r["risk"] for r in data]
    check(data[0]["exists"] is True and data[1]["exists"] is False, "scoped names must be looked up correctly", risks=risks)
    check(code == 2, "missing scoped package must fail", exit_code=code)
    return {"exit_code": code, "risks": risks}


@test("network")
def test_registry_known_good_pypi():
    code, data = verify_cli("--ecosystem", "pypi", "requests")
    check(code == 0 and data[0]["risk"] == "low", "requests should be low risk on PyPI", exit_code=code, result=data[0])
    return {"exit_code": code, "repository": data[0]["repository"]}


@test("network")
def test_registry_nonexistent_pypi():
    code, data = verify_cli("--ecosystem", "pypi", "definitely-not-a-real-pypi-pkg-xyz-999")
    check(code == 2 and data[0]["risk"] == "high", "missing PyPI package must be high risk", exit_code=code)
    return {"exit_code": code, "risk": data[0]["risk"]}


# --------------------------------------------------------------------------- verifier logic (offline)

def _fake_registry(created, repo="git+https://github.com/x/y.git", exc=None):
    def fetch(name):
        if exc:
            raise exc
        return {"name": name, "time": {"created": created}, "dist-tags": {"latest": "1.0.0"}, "repository": {"url": repo}}
    return fetch


def _with_fetch(fetch, fn):
    old = vp.FETCHERS["npm"]
    vp.FETCHERS["npm"] = fetch
    try:
        return fn()
    finally:
        vp.FETCHERS["npm"] = old


OLD_DATE = "2015-01-01T00:00:00.000Z"


@test("offline")
def test_offline_new_package_flagged():
    created = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=2)).isoformat()
    r = _with_fetch(_fake_registry(created), lambda: vp.analyze("some-fresh-lib"))
    check(r["risk"] == "medium" and r["age_days"] == 2, "package 2 days old must be flagged", result=r)
    return {"risk": r["risk"], "age_days": r["age_days"]}


@test("offline")
def test_offline_no_repository_flagged():
    r = _with_fetch(_fake_registry(OLD_DATE, repo=""), lambda: vp.analyze("old-lib-without-repo"))
    check(r["risk"] == "medium", "package without repository must be flagged", result=r)
    return {"risk": r["risk"]}


@test("offline")
def test_offline_typosquat_flagged():
    names = ["expres", "lodahs", "axois", "dotenvv", "firebase_admin"]
    results = _with_fetch(_fake_registry(OLD_DATE), lambda: [vp.analyze(n) for n in names])
    flagged = {r["package"]: r.get("lookalike_of") for r in results}
    check(all(r["risk"] == "medium" for r in results), "look-alike names must be flagged even if old", flagged=flagged)
    clean = _with_fetch(_fake_registry(OLD_DATE), lambda: vp.analyze("express"))
    check(clean["risk"] == "low", "the real popular name must not be flagged", result=clean)
    # PEP 503: on PyPI "Python_Dotenv" IS "python-dotenv", so it must not be flagged.
    check(vp.lookalike_of("Python_Dotenv", "pypi") is None and vp.lookalike_of("reqeusts", "pypi") == "requests",
          "PyPI name normalization must follow PEP 503")
    return {"flagged": flagged}


@test("offline")
def test_offline_registry_error_is_not_verified():
    import urllib.error
    r = _with_fetch(_fake_registry(OLD_DATE, exc=urllib.error.URLError("timed out")), lambda: vp.analyze("lodash"))
    code = vp.exit_code([r])
    check(r["risk"] == "unknown" and r["exists"] is None and code == 3,
          "network failure must be 'unknown' (not verified), never 'does not exist'", result=r, exit_code=code)
    return {"risk": r["risk"], "exit_code": code}


# --------------------------------------------------------------------------- lockfile diff (offline)

def _lock(packages):
    pk = {"": {"name": "app", "version": "1.0.0"}}
    pk.update(packages)
    return {"name": "app", "version": "1.0.0", "lockfileVersion": 3, "requires": True, "packages": pk}


def _entry(version, integrity="sha512-AAA", resolved=None, **extra):
    e = {"version": version, "integrity": integrity}
    e["resolved"] = resolved or f"https://registry.npmjs.org/x/-/x-{version}.tgz"
    e.update(extra)
    return e


@test("offline")
def test_lockfile_diff_flags_risky_changes():
    base = _lock({"node_modules/lodash": _entry("4.17.21", "sha512-L")})
    head = _lock({
        "node_modules/lodash": _entry("4.17.21", "sha512-TAMPERED"),
        "node_modules/new-dep": _entry("1.0.0", hasInstallScript=True),
        "node_modules/git-dep": _entry("0.1.0", integrity="", resolved="git+ssh://git@github.com/x/y.git#abc"),
    })
    with tempfile.TemporaryDirectory() as d:
        b, h = Path(d, "base.json"), Path(d, "head.json")
        b.write_text(json.dumps(base))
        h.write_text(json.dumps(head))
        code, out, err = run([sys.executable, str(LOCKDIFF), str(b), str(h)])
        same_code, _, _ = run([sys.executable, str(LOCKDIFF), str(b), str(b)])
    rep = json.loads(out)
    flags = {x["package"]: x["flags"] for x in rep["added"] + rep["changed"]}
    check(code == 2 and rep["summary"]["added"] == 2 and rep["summary"]["flagged"] == 3, "risky lockfile changes must be flagged", report=rep["summary"], exit_code=code)
    check(any("tampering" in f for f in flags["lodash"]), "same version with new hash must be flagged", flags=flags)
    check(any("install script" in f for f in flags["new-dep"]), "install scripts must be flagged", flags=flags)
    check(any("outside the npm registry" in f for f in flags["git-dep"]) and any("integrity" in f for f in flags["git-dep"]),
          "git dependency without integrity must be flagged", flags=flags)
    check(same_code == 0, "identical lockfiles must pass", exit_code=same_code)
    return {"exit_code": code, "summary": rep["summary"]}


# --------------------------------------------------------------------------- security gate on fixtures

HAS_NPM = shutil.which("npm") is not None


def gate(files):
    """Build a throwaway project from {path: content}, run the gate, return (code, output)."""
    with tempfile.TemporaryDirectory() as d:
        for rel, content in files.items():
            p = Path(d, rel)
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content)
        env = dict(os.environ, AUDIT_BLOCKING="0")
        code, out, err = run(["bash", str(GATE), d], env=env)
    return code, out + err


def fails_check(out, check_id):
    return any(line.startswith(f"FAIL {check_id}:") for line in out.splitlines())


CLOSED_RULES = """rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // never: allow read, write: if true;
    match /users/{uid} {
      allow read, write: if request.auth != null && request.auth.uid == uid;
    }
  }
}
"""

CLEAN_PROJECT = {
    "package.json": json.dumps({"name": "fixture", "version": "1.0.0", "private": True}),
    "package-lock.json": json.dumps({"name": "fixture", "version": "1.0.0", "lockfileVersion": 3, "requires": True,
                                     "packages": {"": {"name": "fixture", "version": "1.0.0"}}}),
    ".gitignore": "node_modules\n.env\n",
    ".env": "API_URL=http://localhost\n",
    "firestore.rules": CLOSED_RULES,
    "src/index.js": "// digit check: the old gate dropped lines matching .git\nconst x = 1;\n",
}


def _fake_service_account():
    # Built at runtime so no credential-shaped string is committed to the repo.
    return json.dumps({"type": "service_" + "account", "project_id": "demo",
                       "private_" + "key": "-----BEGIN " + "PRIVATE KEY-----\nNOTAREALKEY\n-----END PRIVATE KEY-----\n"})


@test("gate")
def test_gate_clean_project_passes():
    if not HAS_NPM:
        raise Fail("npm not installed; cannot run gate install check")
    code, out = gate(CLEAN_PROJECT)
    check(code == 0 and "PASS install" in out and "PASS secrets" in out and "PASS rules" in out and "PASS env" in out,
          "clean project must pass every check", exit_code=code, output=out[-1500:])
    return {"exit_code": code}


@test("gate")
def test_gate_detects_service_account():
    secret = _fake_service_account()
    code, out = gate({"src/firebase-admin.json": secret})
    check(code == 1 and fails_check(out, "secrets"), "service account JSON must fail the gate", exit_code=code, output=out[-800:])
    check("NOTAREALKEY" not in out, "gate must never print the secret value")
    return {"exit_code": code}


@test("gate")
def test_gate_detects_cloud_tokens():
    aws = "AKIA" + "IOSFODNN7EXAMPLE"
    gh = "ghp_" + "a" * 36
    code, out = gate({"src/config.ts": f"export const k = '{aws}';\n", "scripts/deploy.sh": f"TOKEN={gh}\n"})
    hits = [l for l in out.splitlines() if l.startswith("FAIL secrets:")]
    check(code == 1 and len(hits) == 2, "AWS key and GitHub token must both be found", hits=hits, output=out[-800:])
    check(aws not in out and gh not in out, "gate must never print the secret value")
    return {"exit_code": code, "hits": len(hits)}


@test("gate")
def test_gate_scans_dot_github_and_digit_lines():
    # Regression: the old gate piped through `grep -v ".git"`, which dropped any
    # line containing ".github", "digit", etc. and hid real findings.
    aws = "AKIA" + "IOSFODNN7EXAMPLE"
    code, out = gate({".github/workflows/deploy.yml": f"env:\n  KEY: {aws}  # digit\n"})
    check(code == 1 and fails_check(out, "secrets"), "secret under .github must be found", output=out[-800:])
    return {"exit_code": code}


@test("gate")
def test_gate_ignores_public_firebase_web_config():
    # apiKey in the Firebase web config is public by design: must not fail.
    code, out = gate({"src/firebase.js": "export const cfg = { apiKey: 'AIzaSyD-public-web-key', projectId: 'demo' };\n"})
    check(code == 0 and "PASS secrets" in out, "public Firebase web config must not be a false positive", output=out[-800:])
    return {"exit_code": code}


@test("gate")
def test_gate_open_rules_variants():
    cases = {
        "if_true": ("firestore.rules", "service cloud.firestore { match /{d=**} { allow read, write: if true; } }"),
        "no_condition": ("firestore.rules", "service cloud.firestore { match /{d=**} { allow read, write; } }"),
        "test_mode": ("firestore.rules", "service cloud.firestore { match /{d=**} { allow read, write: if request.time < timestamp.date(2030, 1, 1); } }"),
        "storage_open": ("storage.rules", "service firebase.storage { match /b/{bucket}/o { match /{all=**} { allow read, write: if true; } } }"),
        "rtdb_open": ("database.rules.json", '{ "rules": { ".read": true, ".write": "auth != null" } }'),
    }
    missed = []
    for label, (path, body) in cases.items():
        code, out = gate({path: body})
        if not (code == 1 and fails_check(out, "rules")):
            missed.append(label)
    code, out = gate({"firestore.rules": CLOSED_RULES})
    check(not missed, "every open-rules variant must fail the gate", missed=missed)
    check(code == 0, "closed rules (with 'if true' only in a comment) must pass", output=out[-800:])
    return {"variants": sorted(cases)}


@test("gate")
def test_gate_missing_lockfile_fails():
    code, out = gate({"package.json": json.dumps({"name": "x", "version": "1.0.0", "dependencies": {"lodash": "^4"}})})
    check(code == 1 and fails_check(out, "install"), "package.json without lockfile must fail", output=out[-800:])
    return {"exit_code": code}


@test("gate")
def test_gate_env_not_ignored_fails():
    code, out = gate({".env": "STRIPE_KEY=placeholder\n", ".gitignore": "node_modules\n"})
    check(code == 1 and fails_check(out, "env"), ".env missing from .gitignore must fail", output=out[-800:])
    return {"exit_code": code}


# --------------------------------------------------------------------------- structure

TEST_NAMES = None  # filled in main()


@test("structure")
def test_evals_structure():
    data = json.loads(EVALS.read_text())
    cases = data.get("test_cases", [])
    check(data.get("skill") == "ai-package-guard", "wrong skill name")
    bad = [c.get("name") for c in cases if not all(k in c for k in ("name", "input", "assertions", "tool_tests"))]
    check(not bad, "every eval case needs name, input, assertions and tool_tests", bad=bad)
    unknown = sorted({t for c in cases for t in c["tool_tests"]} - TEST_NAMES)
    check(not unknown, "tool_tests must reference real tests", unknown=unknown)
    return {"case_count": len(cases)}


@test("structure")
def test_triggers_structure():
    data = json.loads(TRIGGERS.read_text())
    pos = [t for t in data.get("test_cases", []) if t.get("should_trigger")]
    neg = [t for t in data.get("test_cases", []) if not t.get("should_trigger")]
    check(len(pos) >= 5 and len(neg) >= 3, "need at least 5 positive and 3 negative trigger cases", positives=len(pos), negatives=len(neg))
    return {"positives": len(pos), "negatives": len(neg)}


# --------------------------------------------------------------------------- main

def git_sha():
    if os.environ.get("GITHUB_SHA"):
        return os.environ["GITHUB_SHA"]
    code, out, _ = run(["git", "-C", str(ROOT), "rev-parse", "HEAD"])
    return out.strip() if code == 0 else None


def eval_coverage(results):
    status = {r["name"]: r["status"] for r in results}
    cases = json.loads(EVALS.read_text()).get("test_cases", [])
    rows = []
    for c in cases:
        tt = c.get("tool_tests", [])
        st = [status.get(t, "not_run") for t in tt]
        if not tt:
            state = "behavior_only"
        elif all(s == "pass" for s in st):
            state = "tool_backed_pass"
        elif "fail" in st:
            state = "tool_backed_fail"
        else:
            state = "tool_backed_partial_run"
        rows.append({"case": c["name"], "state": state, "tool_tests": tt})
    return {
        "total_cases": len(rows),
        "tool_backed": sum(1 for r in rows if r["state"] != "behavior_only"),
        "behavior_only": [r["case"] for r in rows if r["state"] == "behavior_only"],
        "note": "Behavior evals are not executed by this runner; tool_backed means the scripts the agent relies on for that case were tested.",
        "cases": rows,
    }


def write_step_summary(report):
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    s, cov = report["summary"], report["eval_coverage"]
    lines = [
        "### ai-package-guard tests",
        f"- Tool tests: **{s['passed']}/{s['total']} passed**, {s['skipped']} skipped",
        f"- Commit: `{report['git_sha']}`",
        f"- Behavior evals: {cov['total_cases']} cases, {cov['tool_backed']} backed by tool tests, "
        f"{len(cov['behavior_only'])} behavior-only (not executed here)",
        "",
        "| Test | Kind | Status | ms |",
        "|---|---|---|---|",
    ]
    lines += [f"| {t['name']} | {t['kind']} | {t['status']} | {t['duration_ms']} |" for t in report["tests"]]
    with open(path, "a") as f:
        f.write("\n".join(lines) + "\n")


def main():
    global TEST_NAMES
    ap = argparse.ArgumentParser()
    ap.add_argument("--offline", action="store_true", help="skip tests that call npm / PyPI")
    args = ap.parse_args()
    TEST_NAMES = {name for name, _, _ in TESTS}

    report = {
        "skill": "ai-package-guard",
        "started_at": now_iso(),
        "git_sha": git_sha(),
        "environment": {
            "ci": bool(os.environ.get("CI")),
            "python": platform.python_version(),
            "platform": platform.platform(),
            "npm_available": HAS_NPM,
            "offline": args.offline,
        },
        "tests": [],
    }
    print("=== ai-package-guard test runner ===")
    print(f"Started: {report['started_at']}  commit: {report['git_sha']}\n")

    for name, kind, fn in TESTS:
        t0 = time.monotonic()
        entry = {"name": name, "kind": kind, "started_at": now_iso()}
        if args.offline and kind == "network":
            entry.update(status="skipped", details={"reason": "--offline"})
        else:
            try:
                entry.update(status="pass", details=fn() or {})
            except Fail as e:
                entry.update(status="fail", details={"error": str(e), **e.details})
            except Exception as e:  # unexpected crash in the test itself
                entry.update(status="fail", details={"error": f"{type(e).__name__}: {e}"})
        entry["duration_ms"] = int((time.monotonic() - t0) * 1000)
        report["tests"].append(entry)
        icon = {"pass": "PASS", "fail": "FAIL", "skipped": "SKIP"}[entry["status"]]
        print(f"  {icon}  [{kind}] {name}")
        if entry["status"] == "fail":
            print(f"        {entry['details'].get('error')}")

    passed = sum(t["status"] == "pass" for t in report["tests"])
    failed = sum(t["status"] == "fail" for t in report["tests"])
    skipped = sum(t["status"] == "skipped" for t in report["tests"])
    report["summary"] = {
        "passed": passed, "failed": failed, "skipped": skipped,
        "total": len(report["tests"]) - skipped,
        "finished_at": now_iso(),
        "success": failed == 0,
    }
    report["eval_coverage"] = eval_coverage(report["tests"])

    cov = report["eval_coverage"]
    print(f"\n=== Results: {passed}/{passed + failed} passed, {skipped} skipped ===")
    print(f"Behavior evals: {cov['total_cases']} cases; {cov['tool_backed']} backed by tool tests; "
          f"{len(cov['behavior_only'])} behavior-only (not executed here)")
    REPORT_PATH.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report: {REPORT_PATH}")
    write_step_summary(report)
    sys.exit(0 if report["summary"]["success"] else 1)


if __name__ == "__main__":
    main()
