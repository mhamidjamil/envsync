# EnvSyncer — Architecture

## Goal

Zero-config secret syncing: `cd` into any repo, run `envsyncer`, and secret files
sync to a private GitHub vault. No per-project setup.

## Layered design

```
cli.py                     parse args, resolve --yes, delegate. No logic.
  └─ commands/*            orchestration, one file per command
       └─ core/            all business logic (pure where possible)
            ├─ github_client.py   the ONLY module that speaks HTTP to GitHub
            ├─ vault.py           owns the local⇄vault path mapping
            ├─ sync_engine.py     pure decision logic (no I/O) — heavily tested
            ├─ discovery/ignore   what counts as a secret; what to skip
            ├─ config/cache       ~/.envsyncer state + baseline hashes
            └─ setup/session      first-run flow + per-command bootstrap
       └─ ui/*             all colored output & prompts (one place → easy --yes)
       └─ utils/*          paths, logging, error hierarchy
```

Why layered: `github_client` is the single network seam (swappable, mockable);
`sync_engine` is pure so correctness is unit-testable; `ui` centralises
interactivity so non-interactive mode is one switch, not scattered `if`s.

## Path model (folder preservation)

- **Project root** = the git repo root; every relative path is computed from there.
- A local file `secret/.env` → vault path `<owner>/<repo>/<profile>/secret/.env`.
- `.envsyncer.json` records files **by relative path**, so `pull` restores each file
  to its exact original location on any machine — including nested folders.
- The vault repo always belongs to the authenticated user; `<owner>/<repo>` is only
  a logical folder key (the project may be someone else's repo you cloned).

## Vault backend: GitHub Contents API

Reads/writes files via `GET`/`PUT /repos/{owner}/{repo}/contents/{path}`. A `PUT`
**is** a commit + push, so syncing is auto-committed with no local clone/git state
to manage. The `~/.envsyncer/cache/` dir holds baseline hashes only.

## Sync decision logic

Comparison is by **SHA-256**, never timestamps. A per-project+profile **baseline**
(the hash at the last successful sync) is what lets us attribute divergence:

| State | Action |
|---|---|
| local only / remote only | upload / download |
| identical | in sync |
| differ, local == baseline | remote changed → download |
| differ, remote == baseline | local changed → upload |
| differ, both ≠ baseline (or no baseline) | **conflict** (never silent overwrite) |

Conflicts offer: show diff / replace local / replace remote / save-local-as-new-profile / cancel.

## Config & auth

- `~/.envsyncer/config.json`, `0600`, plain JSON (portable across your own machines).
  Comment header carried in `_readme`/`_docs` fields (JSON has no comments).
- Auth: GitHub Personal Access Token (scope `repo`), pasted or created via the
  browser during `setup`, validated with `GET /user`.

## Extensibility

- New secret type → add one glob to `DEFAULT_SECRET_PATTERNS`.
- New command → add a `commands/*` module + one wiring line in `cli.py`.
- Alternative vault backend → implement behind the `github_client`/`vault` seam.
