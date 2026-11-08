#!/usr/bin/env bash
# security-gate.sh - Node + Firebase security gate.
#
# Usage:  bash scripts/security-gate.sh [project-dir]     (default: .)
# Exit:   0 = pass, 1 = at least one blocking check failed
#
# Env:
#   AUDIT_BLOCKING=1      make `npm audit` findings (moderate+) block the gate
#   GATE_EXCLUDE_DIRS     extra space-separated directory names to skip in scans
#
# Output lines start with PASS / FAIL / WARN / SKIP and a check id, so CI and
# tests can assert on specific checks. Secret VALUES are never printed, only
# file:line.

set -uo pipefail

TARGET="${1:-.}"
if [ ! -d "$TARGET" ]; then
  echo "FAIL usage: '$TARGET' is not a directory"
  exit 1
fi
cd "$TARGET" || exit 1

FAIL=0
pass() { echo "PASS $1: $2"; }
fail() { echo "FAIL $1: $2"; FAIL=1; }
warn() { echo "WARN $1: $2"; }
skip() { echo "SKIP $1: $2"; }

EXCLUDES=(--exclude-dir=node_modules --exclude-dir=.git)
for d in ${GATE_EXCLUDE_DIRS:-}; do
  EXCLUDES+=("--exclude-dir=$d")
done

echo "=== ai-package-guard security gate ==="
echo "Target:  $(pwd)"
echo "Started: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"

# --- 1. Frozen install --------------------------------------------------------
if [ -f package.json ]; then
  if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
    if npm ci --ignore-scripts --no-audit --no-fund >/dev/null 2>&1; then
      pass install "npm ci --ignore-scripts succeeded"
    else
      fail install "npm ci --ignore-scripts failed (lockfile out of sync or bad package)"
    fi
  else
    fail install "package.json without package-lock.json: frozen install is impossible"
  fi
else
  skip install "no package.json"
fi

# --- 2. Audit -------------------------------------------------------------------
if [ -f package-lock.json ] || [ -f npm-shrinkwrap.json ]; then
  if npm audit --audit-level=moderate >/dev/null 2>&1; then
    pass audit "no moderate+ advisories"
  elif [ "${AUDIT_BLOCKING:-0}" = "1" ]; then
    fail audit "npm audit reported moderate+ advisories (or could not run)"
  else
    warn audit "npm audit reported moderate+ advisories (or could not run); set AUDIT_BLOCKING=1 to block"
  fi
else
  skip audit "no lockfile"
fi

# --- 3. Secrets -----------------------------------------------------------------
# Patterns are for real credential formats, not generic words like "secret".
# The Firebase web apiKey is public by design and is intentionally not flagged.
SECRET_PATTERNS=(
  '-----BEGIN ([A-Z]+ )?PRIVATE KEY-----'
  '"type"[[:space:]]*:[[:space:]]*"service_account"'
  '"private_key"[[:space:]]*:[[:space:]]*"'
  'AKIA[0-9A-Z]{16}'
  '(sk|rk)_live_[0-9A-Za-z]{16,}'
  'gh[pousr]_[A-Za-z0-9]{36}'
  'xox[abprs]-[A-Za-z0-9-]{10,}'
)
SECRET_HITS=""
for p in "${SECRET_PATTERNS[@]}"; do
  hits=$(grep -rnIE "${EXCLUDES[@]}" -e "$p" . 2>/dev/null | cut -d: -f1,2 || true)
  if [ -n "$hits" ]; then
    SECRET_HITS="$SECRET_HITS$hits"$'\n'
  fi
done
if [ -n "$SECRET_HITS" ]; then
  while IFS= read -r loc; do
    [ -n "$loc" ] && fail secrets "possible credential at $loc"
  done <<< "$(printf '%s' "$SECRET_HITS" | sort -u)"
else
  pass secrets "no known credential formats found"
fi

# --- 4. .env files must be ignored and untracked --------------------------------
ENV_FILES=$(find . \( -name node_modules -o -name .git \) -prune -o -type f -name '.env*' -print 2>/dev/null \
  | grep -vE '\.(example|sample|template)$' || true)
if [ -z "$ENV_FILES" ]; then
  skip env "no .env files"
else
  IN_GIT=0
  git rev-parse --is-inside-work-tree >/dev/null 2>&1 && IN_GIT=1
  ENV_OK=1
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if [ "$IN_GIT" = "1" ]; then
      if git ls-files --error-unmatch "$f" >/dev/null 2>&1; then
        fail env "$f is tracked by git"; ENV_OK=0
      elif ! git check-ignore -q "$f"; then
        fail env "$f is not ignored by .gitignore"; ENV_OK=0
      fi
    elif [ ! -f .gitignore ] || ! grep -qE '^/?\.env' .gitignore; then
      fail env "$f exists but .gitignore has no .env entry"; ENV_OK=0
    fi
  done <<< "$ENV_FILES"
  [ "$ENV_OK" = "1" ] && pass env ".env files are ignored"
fi

# --- 5. Firebase rules ----------------------------------------------------------
# Comments are stripped before matching so `// if true` does not count.
strip_comments() { sed -e 's#//.*$##' "$1"; }

RULES_FILES=$(find . \( -name node_modules -o -name .git \) -prune -o -type f -name '*.rules' -print 2>/dev/null || true)
DB_RULES_FILES=$(find . \( -name node_modules -o -name .git \) -prune -o -type f -name 'database.rules.json' -print 2>/dev/null || true)

if [ -z "$RULES_FILES" ] && [ -z "$DB_RULES_FILES" ]; then
  skip rules "no Firebase rules files"
else
  RULES_OK=1
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    body=$(strip_comments "$f")
    if printf '%s\n' "$body" | grep -qE 'if[[:space:]]+true'; then
      fail rules "$f grants access with 'if true'"; RULES_OK=0
    fi
    if printf '%s\n' "$body" | grep -qE 'allow[[:space:]]+[a-z, ]+[[:space:]]*;'; then
      fail rules "$f has an 'allow' without a condition (open access)"; RULES_OK=0
    fi
    if printf '%s\n' "$body" | grep -qE 'request\.time[[:space:]]*<'; then
      fail rules "$f uses test-mode rules (open until a date)"; RULES_OK=0
    fi
    if ! printf '%s\n' "$body" | grep -q 'request\.auth'; then
      warn rules "$f never checks request.auth"
    fi
  done <<< "$RULES_FILES"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    if grep -qE '"\.(read|write)"[[:space:]]*:[[:space:]]*(true|"true")' "$f"; then
      fail rules "$f has \".read\" or \".write\" set to true"; RULES_OK=0
    fi
  done <<< "$DB_RULES_FILES"
  [ "$RULES_OK" = "1" ] && pass rules "no open Firebase rules found"
fi

echo "Finished: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
if [ "$FAIL" -eq 0 ]; then
  echo "RESULT: PASSED"
  exit 0
fi
echo "RESULT: FAILED"
exit 1
