# CR-0001: Load GBIF/eBird credentials from environment variables instead of source literals

## Scope
Fix BUG-0006: remove the literal GBIF password/email/username and eBird API
key from `sightings.py` and `ebird.py`, reading them from environment
variables instead, with a clear error if unset.

## Why now
`sightings.py:11-13` and `ebird.py:10` currently commit a real-looking
password, email, and API key in plaintext. This is a live security
exposure (`BUG-0006`, severity high) — anyone with read access to the repo
or its git history gets the credentials. The code fix here doesn't remove
the already-pushed history (that requires history rewrite + remote
coordination the user must decide on, and credential rotation, which is
outside a code CR), but it stops the exposure from getting worse and
establishes the pattern BUG-0006's preventive action (PA-0004) requires.

## The change
`sightings.py`:
```python
# before
GBIF_USER = "alpuglisi"
GBIF_PWD = "Password1994!"
GBIF_EMAIL = "albert.puglisi94@gmail.com"
...
if __name__ == "__main__":
    if GBIF_USER == "your_gbif_username":
        print("WARNING: Please insert your GBIF credentials ...")
        exit(1)

# after
GBIF_USER = os.environ.get("GBIF_USER")
GBIF_PWD = os.environ.get("GBIF_PWD")
GBIF_EMAIL = os.environ.get("GBIF_EMAIL")
...
if __name__ == "__main__":
    missing = [n for n, v in (("GBIF_USER", GBIF_USER),
                               ("GBIF_PWD", GBIF_PWD),
                               ("GBIF_EMAIL", GBIF_EMAIL)) if not v]
    if missing:
        print(f"ERROR: set the following environment variable(s) before "
              f"running: {', '.join(missing)}")
        exit(1)
```
`ebird.py`:
```python
# before
API_KEY = "69gtab3miaee"
...
def main():
    if API_KEY == "YOUR_API_KEY_HERE":
        print("WARNING: ...")

# after
API_KEY = os.environ.get("EBIRD_API_KEY")
...
def main():
    if not API_KEY:
        print("ERROR: set the EBIRD_API_KEY environment variable before "
              "running.")
        return
```
(`ebird.py` gains an `import os`.)

The `if __name__ == "__main__"` early-exit behavior for missing credentials
is preserved (previously exit(1) triggered only on the literal placeholder
string; now it triggers whenever the env var is unset/empty, which is a
strict superset of the old check and closer to the evident intent).

## Impact on other parts of the system
- Only these two standalone, non-imported scripts are affected (confirmed:
  neither is imported by any other file in the repo).
- Anyone currently running these scripts will need to set
  `GBIF_USER`/`GBIF_PWD`/`GBIF_EMAIL`/`EBIRD_API_KEY` in their environment
  before their next run — a one-time workflow change, documented in the
  script's own error message.
- No data format, schema, or downstream file changes.

## Risk assessment
**Risk level: low**, with one **accepted residual risk**: the credentials
already pushed to the remote in commit `29c194a` (and the current working
tree, until this CR lands) remain in git history even after this fix.
**Mitigation:** this CR's corrective action explicitly recommends
credential rotation by the account owner (already flagged in BUG-0006) as
a separate, non-code action; a git-history rewrite (e.g. `git filter-repo`)
is out of scope for this CR since it rewrites shared history and needs the
user's explicit sign-off given its blast radius on any existing clones/PRs.

## Test plan
- Cannot validate live GBIF/eBird API calls in this environment (no network
  egress to those specific external APIs configured, and doing so would
  require real credentials, which this CR is explicitly removing from the
  repo).
- Validated instead by: (a) `python -c "import ast; ast.parse(open('sightings.py').read())"`
  and same for `ebird.py`, confirming both files still parse; (b) a static
  read-through confirming no other reference to the removed literals
  remains in either file; (c) manually confirming the missing-env-var path
  prints the intended message and exits/returns without attempting a
  request.

## Deliverables
- [ ] `sightings.py`: replace literal credentials with `os.environ.get(...)`
      + a clear missing-env-var error message.
- [ ] `ebird.py`: replace literal API key with `os.environ.get(...)` + a
      clear missing-env-var error message; add `import os`.
- [ ] Verify no other repo file references the removed literal values.
- [ ] Update `BUG-0006-hardcoded-credentials.md` corrective action section
      and `BUG_LOG.md` status.
- [ ] Flag credential rotation to the user as a standing action item (not
      a code deliverable — cannot be done from this session).

## Out of scope
- Rotating the actual GBIF password / eBird API key (must be done by the
  account owner outside this repo).
- Rewriting git history to remove the already-committed literal values.
- Building a general secrets-management module beyond `os.environ.get`
  (no other script in the repo currently needs one; revisit if that
  changes).

## Reviewer verdicts
See independent review below (§ Review).
