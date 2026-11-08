#!/usr/bin/env python3
"""
Verify package candidates for AI package hallucination / slopsquatting risk.

Usage:
    python verify_packages.py [--ecosystem npm|pypi] pkg1 [pkg2 ...]

Risk levels:
    low      exists, older than 30 days, has a source repository, name not a near-copy
    medium   exists but needs human review (new, no repository, or looks like a typosquat)
    high     does not exist on the registry
    unknown  registry could not be reached; the package was NOT verified

Exit codes:
    0  every package is low risk
    2  at least one package is medium or high risk
    3  no medium/high, but at least one lookup failed (fail closed: not verified)
"""

import argparse
import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional

AGE_THRESHOLD_DAYS = 30
USER_AGENT = "ai-package-guard/1.1 (+https://github.com/DGuedz/ai-package-guard)"
RETRIES = 2          # extra attempts after the first one, for transient failures only
RETRY_DELAY_S = 1.0  # doubled on each retry

# Well-known names used to spot look-alikes. A candidate that is exactly one of
# these is fine; a candidate one edit away from one of these is flagged.
POPULAR = {
    "npm": [
        "express", "lodash", "react", "react-dom", "next", "vue", "axios", "chalk",
        "commander", "debug", "dotenv", "moment", "dayjs", "uuid", "zod", "yup",
        "typescript", "webpack", "vite", "esbuild", "rollup", "babel-core", "eslint",
        "prettier", "jest", "vitest", "mocha", "chai", "supertest", "nodemon",
        "mongoose", "sequelize", "prisma", "pg", "mysql2", "redis", "ioredis",
        "jsonwebtoken", "bcrypt", "bcryptjs", "cors", "helmet", "body-parser",
        "cookie-parser", "multer", "socket.io", "ws", "firebase", "firebase-admin",
        "firebase-functions", "stripe", "openai", "inquirer", "yargs", "glob",
        "rimraf", "fs-extra", "node-fetch", "cross-env", "concurrently", "tailwindcss",
        "postcss", "autoprefixer", "sharp", "classnames", "clsx", "rxjs", "underscore",
        "async", "request", "colors", "minimist", "semver", "cheerio", "puppeteer",
    ],
    "pypi": [
        "requests", "numpy", "pandas", "scipy", "django", "flask", "fastapi",
        "pydantic", "sqlalchemy", "boto3", "botocore", "urllib3", "certifi",
        "setuptools", "pip", "wheel", "pytest", "black", "ruff", "mypy", "click",
        "jinja2", "pyyaml", "python-dotenv", "httpx", "aiohttp", "uvicorn",
        "gunicorn", "celery", "redis", "psycopg2", "psycopg2-binary", "pillow",
        "matplotlib", "scikit-learn", "tensorflow", "torch", "transformers",
        "openai", "anthropic", "beautifulsoup4", "lxml", "cryptography",
        "firebase-admin", "google-cloud-storage", "selenium", "tqdm", "rich",
    ],
}


class NotFound(Exception):
    pass


def _transient(e: Exception) -> bool:
    if isinstance(e, urllib.error.HTTPError):
        return e.code == 429 or e.code >= 500
    return isinstance(e, (urllib.error.URLError, TimeoutError, ConnectionError))


def _get_json(url: str) -> Dict[str, Any]:
    """GET JSON. 404 -> NotFound at once; 429/5xx/network errors are retried, then re-raised."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    delay = RETRY_DELAY_S
    for attempt in range(RETRIES + 1):
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                return json.loads(resp.read().decode())
        except urllib.error.HTTPError as e:
            if e.code == 404:
                raise NotFound(url)
            if attempt == RETRIES or not _transient(e):
                raise
        except Exception as e:
            if attempt == RETRIES or not _transient(e):
                raise
        time.sleep(delay)
        delay *= 2
    raise RuntimeError("unreachable")


def fetch_npm(name: str) -> Dict[str, Any]:
    # Scoped names must be encoded as @scope%2Fname.
    return _get_json("https://registry.npmjs.org/" + urllib.parse.quote(name, safe="@"))


def fetch_pypi(name: str) -> Dict[str, Any]:
    return _get_json("https://pypi.org/pypi/" + urllib.parse.quote(name, safe="") + "/json")


FETCHERS = {"npm": fetch_npm, "pypi": fetch_pypi}


def normalize(name: str, ecosystem: str) -> str:
    # PyPI treats "-", "_" and "." as the same name (PEP 503); npm does not, so
    # on npm "firebase_admin" is a different package and a look-alike.
    name = name.lower()
    if ecosystem == "pypi":
        name = name.replace("_", "-").replace(".", "-")
    return name


def edit_distance(a: str, b: str) -> int:
    """Optimal string alignment distance (a swap of two adjacent letters counts as 1)."""
    d = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
    for i in range(len(a) + 1):
        d[i][0] = i
    for j in range(len(b) + 1):
        d[0][j] = j
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = 0 if a[i - 1] == b[j - 1] else 1
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[len(a)][len(b)]


def lookalike_of(name: str, ecosystem: str) -> Optional[str]:
    if name.startswith("@"):
        return None
    n = normalize(name, ecosystem)
    popular = POPULAR.get(ecosystem, [])
    if n in {normalize(p, ecosystem) for p in popular}:
        return None
    for p in popular:
        if len(p) >= 4 and edit_distance(n, normalize(p, ecosystem)) <= 1:
            return p
    return None


def _npm_meta(info: Dict[str, Any]) -> Dict[str, Any]:
    repo = info.get("repository")
    if isinstance(repo, dict):
        repo = repo.get("url")
    return {
        "created": (info.get("time") or {}).get("created"),
        "latest": (info.get("dist-tags") or {}).get("latest"),
        "repository": repo if isinstance(repo, str) and repo else None,
    }


def _pypi_meta(info: Dict[str, Any]) -> Dict[str, Any]:
    uploads = [
        f.get("upload_time_iso_8601")
        for files in (info.get("releases") or {}).values()
        for f in files
        if f.get("upload_time_iso_8601")
    ]
    meta = info.get("info") or {}
    urls = list((meta.get("project_urls") or {}).values()) + [meta.get("home_page") or ""]
    repo = next((u for u in urls if u and any(h in u for h in ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org"))), None)
    return {"created": min(uploads) if uploads else None, "latest": meta.get("version"), "repository": repo}


def analyze(name: str, ecosystem: str = "npm", now: Optional[datetime.datetime] = None) -> Dict[str, Any]:
    now = now or datetime.datetime.now(datetime.timezone.utc)
    result: Dict[str, Any] = {
        "package": name,
        "ecosystem": ecosystem,
        "exists": None,
        "risk": "unknown",
        "reasons": [],
        "created": None,
        "age_days": None,
        "repository": None,
        "latest": None,
    }

    try:
        info = FETCHERS[ecosystem](name)
    except NotFound:
        result["exists"] = False
        result["risk"] = "high"
        result["reasons"].append(f"Package does not exist on the {ecosystem} registry")
        return result
    except Exception as e:  # network, rate limit, 5xx, bad JSON
        result["reasons"].append(f"Registry lookup failed, package NOT verified: {type(e).__name__}: {e}")
        return result

    result["exists"] = True
    result.update(_npm_meta(info) if ecosystem == "npm" else _pypi_meta(info))

    if result["created"]:
        try:
            created_dt = datetime.datetime.fromisoformat(result["created"].replace("Z", "+00:00"))
            result["age_days"] = (now - created_dt).days
            if result["age_days"] < AGE_THRESHOLD_DAYS:
                result["reasons"].append(f"Very new package ({result['age_days']} days old)")
        except ValueError:
            result["reasons"].append("Could not parse creation date")
    else:
        result["reasons"].append("No creation date on the registry")

    if not result["repository"]:
        result["reasons"].append("No source repository listed")

    similar = lookalike_of(name, ecosystem)
    if similar:
        result["lookalike_of"] = similar
        result["reasons"].append(f"Name is one edit away from popular package '{similar}' (possible typosquat)")

    result["risk"] = "medium" if result["reasons"] else "low"
    return result


def exit_code(results: List[Dict[str, Any]]) -> int:
    risks = {r["risk"] for r in results}
    if risks & {"high", "medium"}:
        return 2
    if "unknown" in risks:
        return 3
    return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Verify package candidates before installing them.")
    parser.add_argument("--ecosystem", choices=sorted(FETCHERS), default="npm")
    parser.add_argument("packages", nargs="+")
    args = parser.parse_args(argv)

    results = [analyze(p, args.ecosystem) for p in args.packages]
    print(json.dumps(results, indent=2))

    code = exit_code(results)
    flagged = [r for r in results if r["risk"] != "low"]
    if flagged:
        print("\nPackages requiring review:", file=sys.stderr)
        for r in flagged:
            print(f"  - {r['package']}: {r['risk']} - {'; '.join(r['reasons'])}", file=sys.stderr)
    else:
        print("\nAll packages look established.", file=sys.stderr)
    return code


if __name__ == "__main__":
    sys.exit(main())
