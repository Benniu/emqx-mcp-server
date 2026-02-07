"""
Configuration Module for EMQX MCP Server

This module loads configuration parameters from environment variables,
specifically for connecting to the EMQX Cloud or self-hosted EMQX API.
"""

import os
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


@dataclass(frozen=True)
class EMQXConfig:
    """EMQX API configuration."""
    api_url: str
    api_key: str
    api_secret: str

    def validate(self) -> None:
        """Validate that all required configuration is present.

        Raises:
            ValueError: If any required configuration is missing.
        """
        missing = []
        if not self.api_url:
            missing.append("EMQX_API_URL")
        if not self.api_key:
            missing.append("EMQX_API_KEY")
        if not self.api_secret:
            missing.append("EMQX_API_SECRET")
        if missing:
            raise ValueError(
                f"Missing required environment variables: {', '.join(missing)}. "
                "Please set them in your environment or .env file."
            )


def load_config() -> EMQXConfig:
    """Load configuration from environment variables."""
    return EMQXConfig(
        api_url=os.getenv("EMQX_API_URL", ""),
        api_key=os.getenv("EMQX_API_KEY", ""),
        api_secret=os.getenv("EMQX_API_SECRET", ""),
    )


# Module-level backward-compatible aliases
_config = load_config()
EMQX_API_URL = _config.api_url
EMQX_API_KEY = _config.api_key
EMQX_API_SECRET = _config.api_secret


def validate_config() -> None:
    """Validate the module-level configuration."""
    _config.validate()
