from envsyncer.core.hashing import sha256_bytes, sha256_file


def test_sha256_bytes_known_value():
    # SHA-256 of b"" is the well-known empty-string digest.
    assert sha256_bytes(b"") == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


def test_sha256_file_matches_bytes(tmp_path):
    path = tmp_path / "secret.env"
    payload = b"API_KEY=abc123\n"
    path.write_bytes(payload)
    assert sha256_file(path) == sha256_bytes(payload)
