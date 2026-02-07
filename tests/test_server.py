"""Tests for the EMQXMCPServer module."""

from unittest.mock import patch, MagicMock, AsyncMock

from emqx_mcp_server.server import EMQXMCPServer


class TestEMQXMCPServer:
    """Tests for EMQXMCPServer initialization and lifecycle."""

    @patch("emqx_mcp_server.server.FastMCP")
    @patch("emqx_mcp_server.server.validate_config")
    def test_server_init(self, mock_validate, mock_fastmcp):
        """Test that server initializes and validates config."""
        server = EMQXMCPServer()
        mock_validate.assert_called_once()
        mock_fastmcp.assert_called_once()
        call_args = mock_fastmcp.call_args
        assert call_args[0][0] == "emqx_mcp_server"
        assert "lifespan" in call_args[1]

    @patch("emqx_mcp_server.server.FastMCP")
    @patch("emqx_mcp_server.server.validate_config")
    def test_shared_client_created(self, mock_validate, mock_fastmcp):
        """Test that a shared EMQXClient is created."""
        server = EMQXMCPServer()
        assert server._emqx_client is not None

    @patch("emqx_mcp_server.server.FastMCP")
    @patch("emqx_mcp_server.server.validate_config")
    def test_tool_classes_share_client(self, mock_validate, mock_fastmcp):
        """Test that both tool classes receive the same EMQXClient instance."""
        with patch("emqx_mcp_server.server.EMQXMessageTools") as MockMsgTools, \
             patch("emqx_mcp_server.server.EMQXClientTools") as MockClientTools:
            server = EMQXMCPServer()
            # Both tool classes should receive the same client instance
            msg_client = MockMsgTools.call_args[1].get("emqx_client") or MockMsgTools.call_args[0][1]
            cli_client = MockClientTools.call_args[1].get("emqx_client") or MockClientTools.call_args[0][1]
            assert msg_client is cli_client
            assert msg_client is server._emqx_client

    @patch("emqx_mcp_server.server.FastMCP")
    @patch("emqx_mcp_server.server.validate_config")
    def test_validate_config_failure_raises(self, mock_validate, mock_fastmcp):
        """Test that server raises when config validation fails."""
        mock_validate.side_effect = ValueError("Missing required environment variables")
        import pytest
        with pytest.raises(ValueError, match="Missing required"):
            EMQXMCPServer()

    @patch("emqx_mcp_server.server.FastMCP")
    @patch("emqx_mcp_server.server.validate_config")
    async def test_lifespan_cleanup(self, mock_validate, mock_fastmcp):
        """Test that lifespan context manager calls client.close()."""
        server = EMQXMCPServer()
        server._emqx_client = MagicMock()
        server._emqx_client.close = AsyncMock()

        # Extract the lifespan from the FastMCP constructor call
        # The lifespan is passed as a keyword argument
        call_kwargs = mock_fastmcp.call_args
        lifespan_arg = call_kwargs[1].get("lifespan") or call_kwargs[0][1] if len(call_kwargs[0]) > 1 else call_kwargs[1]["lifespan"]

        # We need to test the actual lifespan defined in __init__
        # Since it captures self._emqx_client at define time, we need to
        # invoke the original lifespan. Let's re-patch and test.
        # The lifespan captures server._emqx_client via closure on self.
        # Actually the lifespan is defined inline and captures self._emqx_client
        # via the instance attribute. Let's just verify close is callable.
        # To properly test the lifespan, we need to capture it before mocking.

        # Re-create server without mocking _emqx_client and capture the lifespan
        mock_fastmcp.reset_mock()
        server2 = EMQXMCPServer()
        server2._emqx_client.close = AsyncMock()

        # Get the lifespan passed to FastMCP
        lifespan_fn = mock_fastmcp.call_args[1]["lifespan"]
        async with lifespan_fn(None):
            pass
        server2._emqx_client.close.assert_called_once()
