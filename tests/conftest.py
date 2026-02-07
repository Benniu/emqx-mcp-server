"""Shared fixtures for EMQX MCP Server tests."""

import logging
import pytest


@pytest.fixture
def logger():
    """Provide a logger instance for tests."""
    return logging.getLogger("test")
