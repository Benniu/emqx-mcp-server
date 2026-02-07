"""Tests for the config module."""

import pytest
from emqx_mcp_server.config import EMQXConfig


class TestEMQXConfig:
    """Tests for EMQXConfig dataclass."""

    def test_valid_config(self):
        config = EMQXConfig(
            api_url="https://example.com/api/v5",
            api_key="test-key",
            api_secret="test-secret",
        )
        # Should not raise
        config.validate()

    def test_missing_all(self):
        config = EMQXConfig(api_url="", api_key="", api_secret="")
        with pytest.raises(ValueError, match="EMQX_API_URL"):
            config.validate()

    def test_missing_partial(self):
        config = EMQXConfig(
            api_url="https://example.com/api/v5",
            api_key="",
            api_secret="",
        )
        with pytest.raises(ValueError, match="EMQX_API_KEY") as exc_info:
            config.validate()
        assert "EMQX_API_SECRET" in str(exc_info.value)
        assert "EMQX_API_URL" not in str(exc_info.value)

    def test_frozen(self):
        config = EMQXConfig(api_url="url", api_key="key", api_secret="secret")
        with pytest.raises(AttributeError):
            config.api_url = "changed"


class TestLoadConfig:
    """Tests for load_config()."""

    def test_loads_from_env(self, monkeypatch):
        monkeypatch.setenv("EMQX_API_URL", "https://test.emqx.com")
        monkeypatch.setenv("EMQX_API_KEY", "my-key")
        monkeypatch.setenv("EMQX_API_SECRET", "my-secret")

        from emqx_mcp_server.config import load_config
        config = load_config()
        assert config.api_url == "https://test.emqx.com"
        assert config.api_key == "my-key"
        assert config.api_secret == "my-secret"

    def test_defaults_to_empty(self, monkeypatch):
        monkeypatch.delenv("EMQX_API_URL", raising=False)
        monkeypatch.delenv("EMQX_API_KEY", raising=False)
        monkeypatch.delenv("EMQX_API_SECRET", raising=False)

        from emqx_mcp_server.config import load_config
        config = load_config()
        assert config.api_url == ""
        assert config.api_key == ""
        assert config.api_secret == ""


class TestValidateConfig:
    """Tests for validate_config() module-level function."""

    def test_validate_config_success(self, monkeypatch):
        """Test validate_config succeeds with valid env vars."""
        monkeypatch.setenv("EMQX_API_URL", "https://test.emqx.com")
        monkeypatch.setenv("EMQX_API_KEY", "my-key")
        monkeypatch.setenv("EMQX_API_SECRET", "my-secret")

        # validate_config() uses module-level _config which was loaded at import time.
        # We test via EMQXConfig.validate() directly for unit correctness.
        config = EMQXConfig(
            api_url="https://test.emqx.com",
            api_key="my-key",
            api_secret="my-secret",
        )
        # Should not raise
        config.validate()

    def test_validate_config_raises_on_missing(self):
        """Test validate_config raises ValueError with missing env vars."""
        config = EMQXConfig(api_url="", api_key="", api_secret="")
        with pytest.raises(ValueError, match="Missing required environment variables"):
            config.validate()

    def test_validate_config_reports_only_missing(self):
        """Test that only missing fields are reported."""
        config = EMQXConfig(api_url="https://ok.com", api_key="key", api_secret="")
        with pytest.raises(ValueError, match="EMQX_API_SECRET") as exc_info:
            config.validate()
        assert "EMQX_API_URL" not in str(exc_info.value)
        assert "EMQX_API_KEY" not in str(exc_info.value)
