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
- Recursively finds secret files (`.env`, `.env.*`, `arduino_secrets.h`, `secrets.h`, `firebase.json`, `service-account.json`, …) while skipping `node_modules/`, `.git/`, etc. Sample/template files (`*.example`, `*.sample`, `*.template`) are ignored by default. Respects a `.envsyncignore` file.
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
| `envsyncer add <pattern>` | Register an extra secret pattern to scan (e.g. `local.properties`) |
| `envsyncer exclude <pattern>` | Register an extra glob to skip (e.g. `*.local`) |
| `envsyncer setup` | Re-run first-time setup (auth + vault) |
| `envsyncer doctor` | Diagnose configuration and connectivity |

Add `--yes` / `-y` for non-interactive runs (conflicts are skipped, never auto-overwritten).

### Customizing what gets synced

- `envsyncer add local.properties` — include a new file type from now on (all projects).
- `envsyncer exclude '*.local'` — skip a pattern from now on (all projects).
- `envsyncer add` / `envsyncer exclude` with no argument lists the current patterns.
- Per-repo path exclusions: add a `.envsyncignore` file (gitignore syntax) to the repo.

## First run

`envsyncer` asks for a **GitHub Personal Access Token** (scope: `repo`). You can
paste one you already have, or let it open GitHub's token page for you. It then
finds or creates your private vault repo and remembers everything.

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
