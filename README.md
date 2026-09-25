# EnvSyncer

Effortless, cross-platform sync of your project's **secret files** to a **private GitHub vault**.

Clone any repo, run one command, and your `.env` (and other secrets) are pulled
down — or pushed up — exactly where they belong. No per-project config, ever.

```bash
pipx install envsyncer   # recommended — global command, no venv to manage
cd my-project
envsyncer
```

## Installing

**Recommended — [`pipx`](https://pipx.pypa.io):** installs EnvSyncer in its own
isolated environment while exposing `envsyncer` globally on your PATH. No virtual
environment to create or activate, and it can't clash with your system Python
(which is what triggers pip's *"externally-managed-environment"* error).

```bash
brew install pipx          # or: python3 -m pip install --user pipx
pipx ensurepath            # then restart your terminal once
pipx install envsyncer
```

Alternatives if you prefer plain pip:

```bash
pip install --user envsyncer      # per-user install
# or inside a virtualenv:
python3 -m venv .venv && . .venv/bin/activate && pip install envsyncer
```

## What it does

- Detects the current git repo (SSH or HTTPS remotes) and identifies it as `owner/repository`.
- Recursively finds secret files (`.env`, `.env.*`, `arduino_secrets.h`, `secrets.h`, `firebase.json`, `service-account.json`, …) while skipping `node_modules/`, `.git/`, nested repositories and worktrees, etc. Sample/template files (`*.example`, `*.sample`, `*.template`) are ignored by default. Respects a `.envsyncignore` file.
- **Anything already stored in the vault keeps syncing** even if no pattern matches it, so a file cannot silently turn into "remote only" and be overwritten by a stale copy when the pattern list changes or differs between machines.
- Stores them in a **private** GitHub repo (default `my-env`) under
  `owner/repository/<profile>/<original relative path>` — **folder structure is preserved**,
  so a file at `secret/.env` comes back down at `secret/.env` on any machine.
- Each sync is **a single commit** in the vault, no matter how many files changed.
- Compares by **SHA-256** (never timestamps) and, using a per-project baseline,
  correctly tells apart "only local changed", "only remote changed", and a real conflict.
- Supports multiple **profiles** per project (`main`, `dev`, `staging`, …).

## Commands

| Command | What it does |
|---|---|
| `envsyncer` | Detect repo, resolve profile, and sync (the default) |
| `envsyncer status` | Show what a sync would do — read-only |
| `envsyncer push` | Upload all local secrets to the active profile |
| `envsyncer pull` | Download the active profile's secrets to local |
| `envsyncer profile` | Show the active/available profiles |
| `envsyncer profile <name>` | Switch (or create) the active profile |
| `envsyncer delete [path…]` | Remove file(s) from the vault — local copies stay |
| `envsyncer add <pattern>` | Register an extra secret pattern to scan (e.g. `local.properties`) |
| `envsyncer exclude <pattern>` | Register an extra glob to skip (e.g. `*.local`) |
| `envsyncer setup` | Re-run first-time setup (auth + vault) |
| `envsyncer doctor` | Diagnose configuration and connectivity |

Add `--yes` / `-y` for non-interactive runs (conflicts are skipped, never auto-overwritten).

### Customizing what gets synced

- `envsyncer add local.properties` — include a new file type from now on (all projects).
- `envsyncer exclude '*.local'` — skip a pattern from now on (all projects).
- Patterns match a bare file name anywhere in the project (`*.pem`), a path relative to the
  project root when they contain a slash (`android/local.properties`), or a full absolute
  path, which is reduced to a path inside the project it names.
- `envsyncer add --remove <pattern>` / `envsyncer exclude --remove <pattern>` — undo either one.
  Adding a pattern to one list drops it from the other, so the two can never cancel out.
- `envsyncer add` / `envsyncer exclude` with no argument lists the current patterns.
- Per-repo path exclusions: add a `.envsyncignore` file (gitignore syntax) to the repo.

### Removing something from the vault

Excluding a file stops it being uploaded, but whatever is already in the vault stays there
and will keep showing up as "in the vault but not in this project". `envsyncer delete
<path>` removes it for good (with a confirmation); the same choice is offered inline during
a sync whenever a file exists in the vault but not on this machine. Your local copy is
never touched.

## First run

`envsyncer` asks for a **GitHub Personal Access Token** (scope: `repo`). You can
paste one you already have, or let it open GitHub's token page for you. It then
finds or creates your private vault repo and remembers everything.

## Prompt for AI coding tools

Set up EnvSyncer from this repository on my machine and use it to back up my project secret files. Read this README, inspect the machine's existing GitHub authentication and EnvSyncer configuration, and locate the existing private vault before changing anything. For my GitHub account, the vault is mhamidjamil/self_envsyncer; never upload secrets to this public envsync repository or create a second vault. Scan Git projects under my home directory, including nested projects with their own Git remotes, and use each project's owner and repository name plus a profile named after this machine so backups from different machines stay separate. Preserve each secret file's relative path, run an initial upload, verify the remote files and hashes without displaying secret values, and schedule a check for local changes every three days. Keep missing files in the vault rather than deleting them. Report the vault, the projects and file counts, the schedule, and any projects that could not be backed up. Do not change project secrets or push application code.

## Configuration

Lives at `~/.envsyncer/config.json` (created with `0600` permissions). It is plain
JSON so you can **copy it between your own machines** and the tool works immediately.

> ⚠️ **Never share your config with other people.** A `repo`-scoped token grants
> full access to all your private repositories. To share secrets with teammates,
> add them as collaborators on the vault repo and have each use their own token.

## Development

```bash
pip install -e ".[dev]"
pytest
```

## License

MIT
