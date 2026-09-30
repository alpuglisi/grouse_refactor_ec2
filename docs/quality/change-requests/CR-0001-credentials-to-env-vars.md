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
is preserved for `sightings.py` (previously `exit(1)` triggered only on the
literal placeholder string; now it triggers whenever any of the three env
vars is unset/empty, a strict superset of the old check). For `ebird.py`,
this is a **genuine behavior improvement, not mere preservation**: the
current `main()` only prints a warning on the placeholder value and falls
through to run anyway (no `return`/`exit` at all) — the proposed `return`
on a missing key is new, deliberate fail-fast behavior.

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
- [x] `sightings.py`: replace literal credentials with `os.environ.get(...)`
      + a clear missing-env-var error message.
- [x] `ebird.py`: replace literal API key with `os.environ.get(...)` + a
      clear missing-env-var error message; add `import os`.
- [x] Verify no other repo file references the removed literal values.
- [x] Update `BUG-0006-hardcoded-credentials.md` corrective action section
      and `BUG_LOG.md` status.
- [x] Flag credential rotation to the user as a standing action item (not
      a code deliverable — cannot be done from this session).

## Out of scope
- Rotating the actual GBIF password / eBird API key (must be done by the
  account owner outside this repo).
- Rewriting git history to remove the already-committed literal values.
- Building a general secrets-management module beyond `os.environ.get`
  (no other script in the repo currently needs one; revisit if that
  changes).

## § Review

**Reviewer (independent agent, re-derived from current source): APPROVE.**
Verified the current literals in both files match this CR's quotes
exactly, confirmed via independent grep that neither `sightings.py` nor
`ebird.py` is imported anywhere else in the repo (only these two scripts
are affected), and confirmed the fix is mechanically correct.

One non-blocking accuracy note: the CR's claim that the missing-env-var
early exit "preserves" prior behavior as "a strict superset of the old
check" is true for `sightings.py` (already `exit(1)`) but not for
`ebird.py` — `ebird.py`'s current `main()` only prints a warning and falls
through to run anyway (no `return`), so the proposed `return` is a
genuine, deliberate behavior improvement, not mere preservation.

**Disposition: accepted, corrected below.** The claim is narrowed to
`sightings.py` only, and `ebird.py`'s change is now described accurately
as a real behavior improvement rather than continuity.

**Author sign-off:** approved for implementation as revised.
