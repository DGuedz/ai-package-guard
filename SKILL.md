---
name: ai-package-guard
description: "Protect builds and AI-generated code from package hallucination / slopsquatting attacks. Use when adding dependencies, reviewing AI-suggested packages, setting up secure CI installs, generating SBOMs, or confirming exactly what is delivered in a build."
type: workflow
lifecycle: active
---

# AI Package Guard — Secure Dependency Workflow

Prevent AI package hallucination (slopsquatting) and ensure every build delivers only verified, locked dependencies.

**Core rule**: Never install an AI-suggested package directly. Treat it as a candidate that must be verified before it enters `package.json`, lockfile, or the build.

## When to Use This Skill

- AI (Claude, Codex, Copilot, etc.) suggests a new package or edits dependency files
- Setting up or hardening a CI/build pipeline
- Reviewing a lockfile diff or new dependency
- Generating or verifying an SBOM
- Agent is about to run `npm install`, `pnpm add`, `pip install`, etc.

## Mandatory Workflow (Node / npm / pnpm)

Follow these steps in order for any new or AI-suggested dependency:

1. **Extract candidates**  
   List every package name the AI proposed. Do not install yet.

2. **Verify each package on the registry**  
   Run:
   ```bash
   npm view <package-name> name version time.created time.modified repository maintainers --json
   ```
   Reject or escalate if:
   - Package does not exist
   - `time.created` is < 30 days and it is presented as a "standard" library
   - No real GitHub repository or empty repo
   - Unknown / single new maintainer with no history

3. **Human or explicit confirmation gate**  
   Present a short summary (name, age, repo, weekly downloads if available, why it is needed) and require confirmation before adding it to `package.json`.

4. **Add with exact version + update lockfile**  
   ```bash
   npm install <package>@<verified-version> --save-exact
   # or pnpm add <package>@<version>
   ```
   Commit both `package.json` and the lockfile (`package-lock.json` / `pnpm-lock.yaml`).

5. **Secure install in CI / production**  
   Always use frozen lockfile + ignore scripts:
   ```bash
   npm ci --ignore-scripts
   # or
   pnpm install --frozen-lockfile
   ```
   Never use plain `npm install` in CI.

6. **Confirm what is delivered**  
   - Review the lockfile diff in the PR
   - Generate SBOM:
     ```bash
     npm sbom --sbom-format cyclonedx > sbom.json
     ```
   - Optionally run `npm audit` and a tool like Socket if available

See `references/verification-checklist.md` for the full checklist and `references/ci-examples.md` for ready-to-use GitHub Actions / scripts.

## Quick Verification Script

Use the bundled script for batch checks:

```bash
python scripts/verify_packages.py package1 package2 package3
```

It queries the npm registry and flags packages younger than 30 days or missing repository info.

## Other Ecosystems (brief)

| Ecosystem | Lockfile | Secure CI install | Verification |
|-----------|----------|-------------------|--------------|
| Python    | poetry.lock / requirements.txt + hashes | `pip install --require-hashes` | `pip index versions <name>` or PyPI JSON API |
| Rust      | Cargo.lock | `cargo build --locked` | crates.io API |
| PHP       | composer.lock | `composer install --no-dev` | Packagist |

Always prefer lockfiles + frozen installs + human gate on new deps.

## Agent Behavior Rules

- **Propose, do not install** new dependencies unless the user explicitly confirms after verification.
- When editing `package.json` or lockfiles, stop and run the verification steps above.
- Prefer well-known packages. Suggest "no new dependency" alternatives when possible.
- If using an AI agent that can execute shell, require a `verify_package` step before any install command.

## Common Issues

| Problem | Fix |
|---------|-----|
| AI invents package name | Run `npm view` → package does not exist → reject |
| Package exists but is brand new | Flag for review; check maintainer and repo |
| Lockfile not committed | Force commit; CI must use `npm ci` |
| Postinstall scripts in CI | Use `--ignore-scripts` by default |
| Want deeper analysis | Recommend Socket.dev CLI or GitHub dependency-review-action |
