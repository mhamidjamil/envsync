import pytest

from envsyncer.core.local_repo import parse_remote
from envsyncer.utils.errors import LocalRepoError


@pytest.mark.parametrize(
    "url, owner, name",
    [
        ("git@github.com:octocat/hello-world.git", "octocat", "hello-world"),
        ("git@github.com:octocat/hello-world", "octocat", "hello-world"),
        ("https://github.com/octocat/hello-world.git", "octocat", "hello-world"),
        ("https://github.com/octocat/hello-world", "octocat", "hello-world"),
        ("ssh://git@github.com/octocat/hello-world.git", "octocat", "hello-world"),
        ("https://github.com/octocat/hello-world/", "octocat", "hello-world"),
    ],
)
def test_parse_remote_variants(url, owner, name):
    identity = parse_remote(url)
    assert identity.owner == owner
    assert identity.name == name
    assert identity.key == f"{owner}/{name}"


def test_parse_remote_rejects_garbage():
    with pytest.raises(LocalRepoError):
        parse_remote("not-a-remote-url")
