# Verification Checklist

Use this before any new dependency enters the project.

## Per-package checks

- [ ] Package exists on the official registry (`npm view`, `pip index`, crates.io, etc.)
- [ ] First published date is reasonable (flag if < 30 days unless you expected a brand-new package)
- [ ] Has a real, public source repository with history and activity
- [ ] Maintainer(s) have a track record (not a brand-new account)
- [ ] Download count / usage is consistent with how the AI described it
- [ ] No unexpected install scripts (or you reviewed them)
- [ ] Exact version pinned (`--save-exact` or equivalent)
- [ ] Lockfile updated and will be committed

## Build / delivery confirmation

- [ ] Lockfile is committed and reviewed
- [ ] CI uses frozen install (`npm ci`, `pnpm install --frozen-lockfile`, `cargo build --locked`, etc.)
- [ ] Install scripts disabled in CI by default (`--ignore-scripts`)
- [ ] SBOM generated and stored or compared in the pipeline
- [ ] PR shows clear lockfile diff for any new dependency

## AI / Agent specific

- [ ] AI only proposed the package; it did not run the install
- [ ] Verification summary was shown to the human before adding
- [ ] "No new dependency" alternative was considered
