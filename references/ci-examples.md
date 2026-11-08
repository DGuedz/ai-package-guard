# CI / Build Examples

## GitHub Actions (Node)

```yaml
name: Secure Install & Audit

on: [push, pull_request]

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-node@v4
        with:
          node-version: 20
          cache: 'npm'

      - name: Install (frozen + no scripts)
        run: npm ci --ignore-scripts

      - name: Audit
        run: npm audit --audit-level=moderate

      - name: Generate SBOM
        run: npm sbom --sbom-format cyclonedx > sbom.json

      - name: Upload SBOM
        uses: actions/upload-artifact@v4
        with:
          name: sbom
          path: sbom.json
```

## Local / pre-commit style check

```bash
# After AI suggests packages
python scripts/verify_packages.py express lodash some-ai-package

# Then only if clean:
npm install some-ai-package@1.2.3 --save-exact
git add package.json package-lock.json
```

## pnpm equivalent

```bash
pnpm install --frozen-lockfile
pnpm sbom --format cyclonedx > sbom.json
```

## Dependency Review Action (GitHub)

Add to your PR workflow:

```yaml
- uses: actions/dependency-review-action@v4
  with:
    fail-on-severity: moderate
```

This surfaces new dependencies and known issues automatically.
