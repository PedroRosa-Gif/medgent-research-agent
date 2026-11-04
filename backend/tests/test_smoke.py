"""Smoke tests: the package imports and configuration bootstraps correctly."""

import medgent
from medgent.config import Settings, get_settings


def test_package_version_is_string() -> None:
    assert isinstance(medgent.__version__, str)
    assert medgent.__version__ == "0.1.0"


def test_get_settings_returns_settings_with_defaults() -> None:
    settings = get_settings()
    assert isinstance(settings, Settings)
    assert settings.llm_provider == "ollama"
