from pathlib import Path

from tracker.config import Config, DEFAULT_DB_PATH


def test_default_db_path_is_a_real_path(monkeypatch):
    monkeypatch.delenv("TRACKER_DB_PATH", raising=False)

    config = Config.from_env()

    assert isinstance(config.db_path, str)
    assert Path(config.db_path).is_absolute()
    assert config.db_path == DEFAULT_DB_PATH


def test_db_path_can_be_overridden(monkeypatch, tmp_path):
    expected = tmp_path / "tracker.db"
    monkeypatch.setenv("TRACKER_DB_PATH", str(expected))

    assert Config.from_env().db_path == str(expected)
