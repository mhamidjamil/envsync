from envsyncer.core.config import Config
from envsyncer.core.metadata import build_profile_metadata, parse_profile_metadata
from envsyncer.core.vault import VaultManager
from envsyncer.models import RemoteFile


def _vault():
    config = Config.blank()
    config.set_github("token", "octocat")
    config.vault_repo = "my-env"
    return VaultManager(client=None, config=config)  # path mapping needs no client


def test_vault_path_preserves_relative_folder():
    vault = _vault()
    # A nested local file must map into the same nested path under the profile.
    assert vault.vault_path("octocat/app", "main", "secret/.env") == \
        "octocat/app/main/secret/.env"


def test_profile_root():
    assert _vault().profile_root("octocat/app", "dev") == "octocat/app/dev"


def test_metadata_roundtrip_keeps_relative_paths_and_hashes():
    files = {
        "secret/.env": RemoteFile("secret/.env", "abc", 10),
        "firebase.json": RemoteFile("firebase.json", "def", 20),
    }
    data = build_profile_metadata("octocat/app", "main", files)
    parsed = parse_profile_metadata(data)
    assert parsed["secret/.env"].sha256 == "abc"
    assert parsed["firebase.json"].size == 20
    assert data["project"] == "octocat/app"
    assert data["profile"] == "main"
