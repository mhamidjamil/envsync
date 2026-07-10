from envsyncer.core.config import Config


def test_add_include_persists_and_dedups():
    config = Config.blank()
    assert config.add_include("local.properties") is True
    assert config.add_include("local.properties") is False   # already there
    assert "local.properties" in config.include_patterns()


def test_add_exclude_persists_and_dedups():
    config = Config.blank()
    assert config.add_exclude("*.local") is True
    assert config.add_exclude("*.local") is False
    assert "*.local" in config.exclude_patterns()


def test_patterns_default_empty():
    config = Config.blank()
    assert config.include_patterns() == ()
    assert config.exclude_patterns() == ()
