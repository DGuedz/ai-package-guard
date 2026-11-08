#!/usr/bin/env python3
"""
Verify npm package candidates for AI package hallucination / slopsquatting risk.
Usage: python verify_packages.py pkg1 pkg2 pkg3
"""

import json
import sys
import urllib.request
import datetime
from typing import Dict, Any

AGE_THRESHOLD_DAYS = 30


def fetch_npm_info(name: str) -> Dict[str, Any]:
    url = f"https://registry.npmjs.org/{name}"
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data
    except Exception as e:
        return {"error": str(e)}


def analyze(name: str) -> Dict[str, Any]:
    info = fetch_npm_info(name)
    result = {
        "package": name,
        "exists": "error" not in info and "name" in info,
        "risk": "unknown",
        "reasons": [],
        "created": None,
        "repository": None,
        "latest": None,
    }

    if not result["exists"]:
        result["risk"] = "high"
        result["reasons"].append("Package does not exist on npm registry")
        return result

    time_data = info.get("time", {})
    created = time_data.get("created")
    result["created"] = created
    result["latest"] = info.get("dist-tags", {}).get("latest")

    repo = info.get("repository")
    if isinstance(repo, dict):
        result["repository"] = repo.get("url")
    elif isinstance(repo, str):
        result["repository"] = repo

    # Age check
    if created:
        try:
            created_dt = datetime.datetime.fromisoformat(created.replace("Z", "+00:00"))
            age_days = (datetime.datetime.now(datetime.timezone.utc) - created_dt).days
            result["age_days"] = age_days
            if age_days < AGE_THRESHOLD_DAYS:
                result["reasons"].append(f"Very new package ({age_days} days old)")
        except Exception:
            pass

    if not result["repository"]:
        result["reasons"].append("No repository URL listed")

    if result["reasons"]:
        result["risk"] = "medium" if result["exists"] else "high"
    else:
        result["risk"] = "low"

    return result


def main():
    if len(sys.argv) < 2:
        print("Usage: python verify_packages.py package1 [package2 ...]")
        sys.exit(1)

    packages = sys.argv[1:]
    results = [analyze(p) for p in packages]

    print(json.dumps(results, indent=2))

    high_risk = [r for r in results if r["risk"] in ("high", "medium")]
    if high_risk:
        print("\n⚠️  Packages requiring review:", file=sys.stderr)
        for r in high_risk:
            print(f"  - {r['package']}: {r['risk']} — {', '.join(r['reasons'])}", file=sys.stderr)
        sys.exit(2)
    else:
        print("\n✅ All packages look established.", file=sys.stderr)


if __name__ == "__main__":
    main()
