import pytest

from repo_xray.config import DEFAULT_IGNORED_DIRS, Config, FeatureText, load_config, save_texts


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


def test_user_texts_are_read(tmp_path):
    (tmp_path / "xray.toml").write_text(
        'language = "es"\ndescription = "Tienda online"\n\n'
        '[features."web/auth"]\nname = "Acceso"\ndescription = "Entrar y registrarse"\n',
        encoding="utf-8",
    )

    config = load_config(tmp_path)

    assert config.language == "es"
    assert config.description == "Tienda online"
    assert config.features == {"web/auth": FeatureText(name="Acceso", description="Entrar y registrarse")}


@pytest.mark.parametrize("content", [
    'language = "fr"\n',
    '[features."web/auth"]\ncolour = "red"\n',
    'features = "nope"\n',
])
def test_invalid_user_texts_are_rejected(tmp_path, content):
    (tmp_path / "xray.toml").write_text(content, encoding="utf-8")

    with pytest.raises(ValueError):
        load_config(tmp_path)


def test_save_texts_round_trips_and_keeps_other_settings(tmp_path):
    (tmp_path / "xray.toml").write_text('extra_ignored_dirs = ["migrations"]\nmax_file_bytes = 500\n', encoding="utf-8")

    save_texts(tmp_path, "es", 'Tienda "online" \\ con barra', {
        "web/auth": FeatureText(name="Acceso", description="Entrar y\nregistrarse"),
        "api/order": FeatureText(),  # nothing to keep: left out
    })
    config = load_config(tmp_path)

    assert config.max_file_bytes == 500
    assert "migrations" in config.ignored_dirs
    assert config.language == "es"
    assert config.description == 'Tienda "online" \\ con barra'
    assert config.features == {"web/auth": FeatureText(name="Acceso", description="Entrar y\nregistrarse")}
    assert (tmp_path / "xray.toml").read_text(encoding="utf-8").startswith("# repo-xray settings")


def test_save_texts_removes_cleared_values(tmp_path):
    save_texts(tmp_path, "en", "Shop", {"web/auth": FeatureText(name="Login")})

    save_texts(tmp_path, None, None, {})

    assert load_config(tmp_path) == Config()
