# Node & Firebase Security Tests

Concrete checks to run before shipping or in CI.  
Use these alongside the vibe-coding checklist and `ai-package-guard`.

## Node / npm Security Tests

### 1. Dependency integrity
```bash
# Frozen install (fails if lockfile is out of sync)
npm ci --ignore-scripts

# Audit
npm audit --audit-level=moderate

# SBOM
npm sbom --sbom-format cyclonedx > sbom.json
```

### 2. Secrets in source
```bash
# Search for common secret patterns
grep -rE "(api[_-]?key|secret|password|private[_-]?key|serviceAccount)" \
  --include="*.js" --include="*.ts" --include="*.json" --include="*.env" . \
  | grep -v node_modules | grep -v ".git"

# Ensure .env is ignored
grep -q "^\.env" .gitignore && echo "✅ .env ignored" || echo "❌ .env not in .gitignore"
```

### 3. Dangerous scripts
```bash
# List packages with install scripts
npm ls --json | jq '.. | .scripts? // empty | select(. != null)'
# Or simply rely on --ignore-scripts in CI
```

## Firebase Security Tests

### 1. Rules are not open
Check `firestore.rules`, `storage.rules`, or `database.rules.json`:

```bash
# Fail if open rules found
grep -E "allow (read|write|create|update|delete).*: if true" firestore.rules storage.rules 2>/dev/null \
  && echo "❌ Open rules detected" || echo "✅ No open rules"
```

### 2. Authentication required
Rules should contain `request.auth != null` (or equivalent) for sensitive paths.

### 3. Emulator test (recommended)
```bash
# Example: start emulator and run a rules test
firebase emulators:exec --only firestore "npm run test:rules"
```

### 4. App Check & service account
- Confirm App Check is enabled in Firebase Console for production.
- Service account JSON must **not** be in the client bundle or git.

## Automated Gate

Use the bundled gate instead of copying snippets. The grep one-liners above are
for quick manual checks only; `grep -v ".git"` in particular drops any line that
contains `.github` or `digit` and can hide real findings.

```bash
bash scripts/security-gate.sh path/to/project      # exit 1 = blocked
AUDIT_BLOCKING=1 bash scripts/security-gate.sh .    # also block on npm audit
```

It runs the frozen install, audit, credential scan, `.env` check and Firebase
rules check, and prints one `PASS|FAIL|WARN|SKIP <check>: ...` line per result
(secret values are never printed). `evals/run_tests.py` runs it against fixture
projects with known problems to prove each check fires.

## What “pass” means

| Check | Pass condition |
|-------|----------------|
| Frozen install | `npm ci` succeeds |
| Audit | No high/critical (or accepted exceptions) |
| Secrets | No private keys or service accounts in git |
| Firebase Rules | No `if true` on sensitive paths; auth required |
| SBOM | Generated and reviewed |

Run these in CI or before every release. Document any exceptions.
