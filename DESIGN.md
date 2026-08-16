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

## Vault backend: GitHub API

Reads use the Contents API (`GET .../contents/{path}`), falling back to the Git
Data blob API for files over 1 MB — the Contents API inlines nothing above that
size, and decoding the empty payload would hand back a zero-byte secret. Writes
are **batched into a single commit** via the Git Data API: the vault stages all
changed files, then `commit()` uploads them as blobs, builds one tree on the
branch tip, creates one commit, and fast-forwards the ref. Deletions ride in the
same tree as null-sha entries, so removing a file is also one commit. A sync of N
files produces exactly one vault commit, with no local clone/git state to manage.
The `~/.envsyncer/cache/` dir holds baseline hashes only.

## What counts as "local"

Two sources, unioned:

1. Files matching a secret pattern (built-in, `envsyncer add`, minus the excludes).
2. **Files the active profile already tracks that exist on disk.** Being in the
   vault is a stronger statement than any glob: it means this project syncs the
   file. Without this, changing the pattern list — or syncing from a machine whose
   config is a little older — drops a tracked file out of the scan, it reads as
   "remote only", and a stale vault copy is offered as an overwrite of newer local
   work. An explicit `envsyncer exclude` or `.envsyncignore` still wins; the file
   is then reported as *excluded locally* rather than downloaded behind your back.

## Sync decision logic

Comparison is by **SHA-256**, never timestamps. A per-project+profile **baseline**
(the hash at the last successful sync) is what lets us attribute divergence:

| State | Action |
|---|---|
| local only | upload |
| in the vault, absent locally | ask: download / delete from vault / skip |
| in the vault, excluded locally | ask, defaulting to delete from vault |
| identical | in sync (and the baseline is recorded) |
| differ, local == baseline | remote changed → download |
| differ, remote == baseline | local changed → upload |
| differ, both ≠ baseline (or no baseline) | **conflict** (never silent overwrite) |

Conflicts offer: show diff / replace local / replace remote / save-local-as-new-profile / cancel.
Downloaded secrets are written `0600`, and a vault path that would escape the project root
is refused rather than followed.

## Config & auth

- `~/.envsyncer/config.json`, `0600`, plain JSON (portable across your own machines).
  Comment header carried in `_readme`/`_docs` fields (JSON has no comments).
- Auth: GitHub Personal Access Token (scope `repo`), pasted or created via the
  browser during `setup`, validated with `GET /user`.

## Extensibility

- New secret type → add one glob to `DEFAULT_SECRET_PATTERNS` (built-in), or at
  runtime with `envsyncer add <pattern>` (persisted in config, all projects).
  Patterns match a bare name, a slash-bearing path relative to the project root,
  or an absolute path (reduced to the project-relative form).
- Exclude a pattern → `DEFAULT_EXCLUDE_PATTERNS`, `envsyncer exclude <pattern>`,
  or a per-repo `.envsyncignore`. Either command takes `--remove` to undo, and
  adding to one list drops the pattern from the other so they cannot cancel out.
- New command → add a `commands/*` module + one wiring line in `cli.py`.
- Alternative vault backend → implement behind the `github_client`/`vault` seam.
