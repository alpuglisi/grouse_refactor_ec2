# BUG-0006: Live-looking credentials hardcoded in `sightings.py` and `ebird.py`

## 1. Description
`sightings.py` hardcodes a GBIF username, password, and email used directly
for HTTP Basic Auth; `ebird.py` hardcodes an eBird API key used directly as
an auth header value. Both are committed in plaintext to the repository.

## 2. Where encountered
- `sightings.py:11-13`
- `ebird.py:10`

## 3. What it caused to fail
Committing real-looking credentials to source control is a concrete defect
(secret leakage into version control history) regardless of whether the
credentials are currently valid — anyone with read access to the repository
(and its full git history, even if a later commit removes them) obtains
the account's password and API key. This is a security-relevant flaw per
`CLAUDE.md` §2's scope ("a security-relevant flaw").

## 4. What the defect was
`sightings.py:11-13` assigns a literal `GBIF_USER`, `GBIF_PWD`, and
`GBIF_EMAIL` (a live-looking account password and email, used directly for
HTTP Basic Auth). `ebird.py:10` assigns a literal `API_KEY` (a live-looking
eBird API key, used directly as an auth header value).

**Redacted intentionally:** the actual literal values are not reproduced in
this document. They are already present in this repository's git history
(`sightings.py`/`ebird.py`, commit `29c194a` and the current working tree)
— quoting them a second time here in a second tracked file would only
duplicate the exposure. Anyone actioning this bug (rotation, or writing the
fix) can read the live values directly from the source files at the
line numbers above.

## 5. Root cause analysis (Five Whys)
1. Why are real credentials visible in the repository? Because they are
   written as literal string constants in the source files.
2. Why are they literals instead of loaded from configuration? Because no
   environment-variable or secrets-file convention was established when
   these scripts were written.
3. Why was no such convention established? Because these were one-off/
   personal download scripts, likely written for a single author's local
   use without anticipating the repository being reviewed or shared.
4. Why does that matter now? Because the repository has git history and
   (per this session's task) is being reviewed and pushed to a remote —
   any credential committed here is exposed to anyone with repo access,
   past or present.

**Root cause:** no secrets-management convention (env vars, `.env` +
`.gitignore`, or a secrets manager) exists in this codebase, so credentials
were written directly into source as the path of least resistance.

## 6. Corrective action
CR-0001 (approved after independent review): `sightings.py` and `ebird.py`
now read `GBIF_USER`/`GBIF_PWD`/`GBIF_EMAIL`/`EBIRD_API_KEY` from the
environment via `os.environ.get(...)`, with a clear error message and
early exit/return when unset. Verified: both files parse, and grep
confirms no reference to the removed literal values remains anywhere in
the repo. **Status: code fix CLOSED — credential rotation still OPEN,
must be done by the account owner** (the values already pushed to the
remote in commit `29c194a` remain in git history regardless of this code
fix; rotating the actual GBIF password and eBird API key at the source is
outside what a code change can do, and a git-history rewrite was
explicitly out of scope for CR-0001 pending the user's sign-off on that
separate, higher-blast-radius action).

## 7. Recurrence review
Searched `BUG_LOG.md` and `PREVENTIVE_ACTIONS.md`: no prior bug concerns
credential handling. Result: **none found**.

## 8. Preventive action
**PA-0004** (see `PREVENTIVE_ACTIONS.md`): never commit literal credentials
(passwords, API keys, tokens) in source; read them from environment
variables or a git-ignored local secrets file, with `.gitignore` already
denying everything but root `.py`/`.md` files as a partial backstop that
does not, on its own, prevent someone from typing a secret directly into a
tracked `.py` file.
