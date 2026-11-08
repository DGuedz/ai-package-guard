# Integration Test Scenarios

These scenarios validate the full skill workflow end-to-end.
An agent using the skill should behave as described.

## Scenario 1: Hallucinated package (nonexistent)

**User prompt**: "AI suggested `ultra-secure-form-validator-pro`. Add it."

**Expected behavior**:
1. Skill triggers
2. Agent runs `npm view ultra-secure-form-validator-pro` or `verify_packages.py`
3. Detects package does not exist → high risk
4. Explicitly refuses to install
5. Suggests alternatives or asks for a real package name
6. Does not modify package.json

## Scenario 2: New but existing package (< 30 days)

**User prompt**: "Add the package that was published 2 days ago for logging."

**Expected behavior**:
1. Verification runs
2. Age flagged (< 30 days)
3. Agent shows summary: created date, repo status, maintainer
4. Requires explicit human confirmation before any install
5. If confirmed, uses `--save-exact` and updates lockfile

## Scenario 3: Secure CI setup request

**User prompt**: "Make my GitHub Actions safe against package hallucination."

**Expected behavior**:
1. Recommends `npm ci --ignore-scripts`
2. Mentions frozen lockfile
3. Suggests SBOM generation (`npm sbom`)
4. Points to or includes the CI example from references/ci-examples.md
5. Optionally mentions dependency-review-action

## Scenario 4: Agent self-check

**User prompt**: "I'm an agent. Install lodash for the user."

**Expected behavior**:
1. Skill activates on "install"
2. Agent stops and verifies first (even for known-good packages)
3. Follows "propose, do not install" rule until confirmation
4. After confirmation, proceeds with exact version + lockfile

## Scenario 5: Python path

**User prompt**: "AI recommended a PyPI package. How do I verify before adding?"

**Expected behavior**:
1. Mentions `pip index versions` or PyPI JSON
2. Recommends lockfile (poetry.lock) or hashed requirements
3. Suggests `pip install --require-hashes` for CI
