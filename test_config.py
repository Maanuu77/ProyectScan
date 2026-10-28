import pytest

from config import DEFAULT_IGNORED_DIRS, Config, load_config


def test_defaults_when_no_config_file(tmp_path):
    assert load_config(tmp_path) == Config()


def test_extra_ignored_dirs_extend_defaults(tmp_path):
    (tmp_path / "xray.toml").write_text('extra_ignored_dirs = ["migrations"]\n')

    config = load_config(tmp_path)

    assert "migrations" in config.ignored_dirs
    assert DEFAULT_IGNORED_DIRS <= config.ignored_dirs


def test_scalar_settings_are_overridden(tmp_path):
    (tmp_path / "xray.toml").write_text("max_file_bytes = 10\nignore_hidden_dirs = false\n")

    config = load_config(tmp_path)

    assert config.max_file_bytes == 10
    assert config.ignore_hidden_dirs is False


def test_unknown_keys_are_rejected(tmp_path):
    (tmp_path / "xray.toml").write_text('ignored_dirs = []\ncolour = "red"\n')

    with pytest.raises(ValueError, match="colour, ignored_dirs"):
        load_config(tmp_path)
