# Vibe Coding Security Checklist  
Claude / Codex + Firebase + Node

Use this checklist **before** considering any AI-generated system ready for real users.  
Crosses the mentor’s advice (Geraldo Alvês) with the `ai-package-guard` workflow.

## 1. Prompt & AI Output Discipline

- [ ] Explicit anti-hallucination instruction used  
  Example: “Pense em tudo. Não invente pacotes, regras de segurança, configs ou chaves. Se não tiver certeza, diga.”
- [ ] AI only **proposes** changes. Human (or explicit gate) approves before install or deploy.
- [ ] Every new dependency was verified with `scripts/verify_packages.py` or `npm view` (see ai-package-guard).
- [ ] Lockfile committed and CI uses frozen install (`npm ci --ignore-scripts`).

## 2. Secrets & Keys (most common failure point)

- [ ] No API keys, service account JSON, or Firebase config with secrets in the repo.
- [ ] `.env` (or equivalent) is in `.gitignore` and never committed.
- [ ] Firebase Admin SDK credentials are only on the server / Cloud Functions, never in the client.
- [ ] Client-side Firebase config uses only the public keys (apiKey is public by design, but restrict with App Check + Rules).
- [ ] You can answer: “Where are every key and who can access them?”

## 3. Firebase Security Rules (critical)

- [ ] Firestore / Realtime Database / Storage rules are **not** open (`allow read, write: if true` is forbidden in production).
- [ ] Rules require authentication for any sensitive data.
- [ ] Rules tested with the Firebase Emulator or Rules Playground.
- [ ] App Check enabled (or planned) for production.
- [ ] Service account has least privilege.

## 4. Node / Backend Hardening

- [ ] All new npm packages verified and pinned.
- [ ] `npm ci --ignore-scripts` in CI.
- [ ] No secrets in source or logs.
- [ ] Input validation on any Cloud Function or API route.
- [ ] Rate limiting or App Check on public endpoints.

## 5. Recurring Security Testing (mentor’s advice)

- [ ] Security review at least every 2 weeks (or before every release).
- [ ] Check for:
  - Unauthorized data access
  - Open rules
  - Exposed secrets
  - Dependency vulnerabilities (`npm audit`)
  - Unexpected packages in lockfile / SBOM
- [ ] Stress / forced-access tests run on staging.
- [ ] Results documented (even briefly).

## 6. Delivery Confirmation

- [ ] SBOM generated (`npm sbom`) and reviewed.
- [ ] Lockfile diff reviewed in the PR.
- [ ] Staging environment matches production security posture.
- [ ] Rollback plan exists.

## Quick “Ready for users?” gate

Only proceed if **all** of the following are true:

1. Dependencies verified (ai-package-guard)
2. No secrets in git
3. Firebase Rules closed and tested
4. CI uses frozen + ignore-scripts install
5. Recent security check performed

If any item fails → fix before shipping.
