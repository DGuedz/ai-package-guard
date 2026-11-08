#!/usr/bin/env bash
# security-gate.sh — Basic Node + Firebase security gate
# Exit 0 = pass, non-zero = fail
# Usage: ./scripts/security-gate.sh

set -euo pipefail

echo "=== ai-package-guard security gate ==="
echo "Started: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

FAIL=0

# 1. Frozen install
echo ""
echo "[1/4] Frozen install (npm ci --ignore-scripts)"
if npm ci --ignore-scripts; then
  echo "  ✅ npm ci succeeded"
else
  echo "  ❌ npm ci failed"
  FAIL=1
fi

# 2. Audit (warn-only for now, still recorded)
echo ""
echo "[2/4] npm audit"
if npm audit --audit-level=moderate; then
  echo "  ✅ audit clean (or no moderate+)"
else
  echo "  ⚠️  audit found issues (recorded, not blocking)"
fi

# 3. Secrets scan
echo ""
echo "[3/4] Secrets scan"
if grep -rE "serviceAccount|private_key|BEGIN PRIVATE KEY" \
     --include="*.json" --include="*.js" --include="*.ts" --include="*.env" . \
     2>/dev/null | grep -v node_modules | grep -v ".git" | grep -v package-lock; then
  echo "  ❌ Possible secret found"
  FAIL=1
else
  echo "  ✅ No obvious secrets detected"
fi

# 4. Firebase open rules
echo ""
echo "[4/4] Firebase rules check"
if [ -f firestore.rules ] && grep -q "if true" firestore.rules; then
  echo "  ❌ Open Firestore rules detected"
  FAIL=1
else
  echo "  ✅ No open Firestore rules (or file not present)"
fi

echo ""
echo "Finished: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [ "$FAIL" -eq 0 ]; then
  echo "✅ Security gate PASSED"
  exit 0
else
  echo "❌ Security gate FAILED"
  exit 1
fi
