"""Shared fixtures for EMQX MCP Server tests."""

import logging
import pytest

from emqx_mcp_server.config import EMQXConfig
from emqx_mcp_server.emqx_client import EMQXClient


TEST_CONFIG = EMQXConfig(
    api_url="https://emqx.example.com/api/v5",
    api_key="test-key",
    api_secret="test-secret",
)


@pytest.fixture
def logger():
    """Provide a logger instance for tests."""
    return logging.getLogger("test")


@pytest.fixture
def test_config():
    """Provide a shared EMQXConfig with test values."""
    return TEST_CONFIG


@pytest.fixture
async def async_client(logger, test_config):
    """Create an EMQXClient with automatic cleanup."""
    client = EMQXClient(logger, config=test_config)
    try:
        yield client
    finally:
        await client.close()
