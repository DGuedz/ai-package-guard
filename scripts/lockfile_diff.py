#!/usr/bin/env python3
"""
Compare two npm lockfiles (v2/v3) and list what a PR really changes.

Usage:
    python lockfile_diff.py base/package-lock.json head/package-lock.json
    git show origin/main:package-lock.json > /tmp/base.json && \
        python lockfile_diff.py /tmp/base.json package-lock.json

Flags, for every added or changed package:
    - missing `integrity` hash
    - `resolved` outside https://registry.npmjs.org/ (git, http, other host)
    - `hasInstallScript: true`

Exit codes:
    0  nothing added, changed or flagged
    2  something needs review (see the JSON report)
    1  usage error or unsupported lockfile
"""

import json
import sys
from typing import Any, Dict

REGISTRY = "https://registry.npmjs.org/"


def load_packages(path: str) -> Dict[str, Dict[str, Any]]:
    with open(path) as f:
        data = json.load(f)
    if "packages" not in data:
        raise ValueError(f"{path}: lockfileVersion {data.get('lockfileVersion')} is not supported (need v2 or v3)")
    return {k: v for k, v in data["packages"].items() if k}  # "" is the root project


def name_of(key: str) -> str:
    return key.split("node_modules/")[-1]


def flags_for(entry: Dict[str, Any]) -> list:
    out = []
    if entry.get("link"):
        return out
    if not entry.get("integrity"):
        out.append("missing integrity hash")
    resolved = entry.get("resolved", "")
    if resolved and not resolved.startswith(REGISTRY):
        out.append(f"resolved outside the npm registry: {resolved}")
    if entry.get("hasInstallScript"):
        out.append("has install script")
    return out


def diff(base: Dict[str, Dict[str, Any]], head: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    added, removed, changed = [], [], []
    for key in sorted(set(head) - set(base)):
        e = head[key]
        added.append({"package": name_of(key), "path": key, "version": e.get("version"), "flags": flags_for(e)})
    for key in sorted(set(base) - set(head)):
        removed.append({"package": name_of(key), "path": key, "version": base[key].get("version")})
    for key in sorted(set(base) & set(head)):
        b, h = base[key], head[key]
        if b.get("version") != h.get("version") or b.get("integrity") != h.get("integrity") or b.get("resolved") != h.get("resolved"):
            changed.append({
                "package": name_of(key), "path": key,
                "from": b.get("version"), "to": h.get("version"),
                "integrity_changed_same_version": b.get("version") == h.get("version") and b.get("integrity") != h.get("integrity"),
                "flags": flags_for(h),
            })
    for c in changed:
        if c["integrity_changed_same_version"]:
            c["flags"].append("same version, different integrity hash (possible tampering)")
    flagged = [x for x in added + changed if x["flags"]]
    return {
        "added": added, "removed": removed, "changed": changed,
        "summary": {"added": len(added), "removed": len(removed), "changed": len(changed), "flagged": len(flagged)},
        "needs_review": bool(added or changed or flagged),
    }


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 2:
        print(__doc__, file=sys.stderr)
        return 1
    try:
        report = diff(load_packages(argv[0]), load_packages(argv[1]))
    except (OSError, ValueError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print(json.dumps(report, indent=2))
    return 2 if report["needs_review"] else 0


if __name__ == "__main__":
    sys.exit(main())
