from envsyncer.core.discovery import discover_secrets


def _write(path, content=b"x"):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def test_discovers_nested_secrets_and_preserves_relative_paths(tmp_path):
    _write(tmp_path / ".env")
    _write(tmp_path / "secret" / ".env")            # nested — the key requirement
    _write(tmp_path / "config" / "firebase.json")
    _write(tmp_path / "arduino" / "arduino_secrets.h")
    _write(tmp_path / "lib" / "secrets.h")          # nested, non-arduino header
    _write(tmp_path / "README.md")                  # not a secret

    rels = {sf.relative_path for sf in discover_secrets(tmp_path)}
    assert rels == {
        ".env",
        "secret/.env",
        "config/firebase.json",
        "arduino/arduino_secrets.h",
        "lib/secrets.h",
    }


def test_default_ignored_dirs_are_skipped(tmp_path):
    _write(tmp_path / "node_modules" / ".env")
    _write(tmp_path / ".git" / ".env")
    _write(tmp_path / "app" / ".env")

    rels = {sf.relative_path for sf in discover_secrets(tmp_path)}
    assert rels == {"app/.env"}


def test_envsyncignore_excludes_matches(tmp_path):
    _write(tmp_path / ".env")
    _write(tmp_path / "ignoreme" / ".env")
    (tmp_path / ".envsyncignore").write_text("ignoreme/\n", encoding="utf-8")

    rels = {sf.relative_path for sf in discover_secrets(tmp_path)}
    assert rels == {".env"}


def test_env_variants_match(tmp_path):
    _write(tmp_path / ".env.local")
    _write(tmp_path / ".env.production")
    rels = {sf.relative_path for sf in discover_secrets(tmp_path)}
    assert rels == {".env.local", ".env.production"}


def test_default_excludes_examples_and_samples(tmp_path):
    _write(tmp_path / ".env")
    _write(tmp_path / ".env.example")
    _write(tmp_path / ".env.sample")
    _write(tmp_path / "config.template")
    rels = {sf.relative_path for sf in discover_secrets(tmp_path)}
    assert rels == {".env"}


def test_extra_includes_and_excludes(tmp_path):
    _write(tmp_path / "local.properties")   # extra include
    _write(tmp_path / ".env")
    _write(tmp_path / ".env.local")         # excluded by extra exclude "*.local"
    rels = {
        sf.relative_path
        for sf in discover_secrets(
            tmp_path,
            extra_includes=("local.properties",),
            extra_excludes=("*.local",),
        )
    }
    assert rels == {".env", "local.properties"}
