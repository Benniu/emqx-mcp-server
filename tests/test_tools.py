"""Tests for the MCP tool handlers."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from emqx_mcp_server.tools.emqx_message_tools import EMQXMessageTools
from emqx_mcp_server.tools.emqx_client_tools import EMQXClientTools


@pytest.fixture
def mock_mcp():
    """Create a mock MCP server that captures registered tools."""
    mcp = MagicMock()
    registered = {}

    def tool_decorator(name, description):
        def decorator(func):
            registered[name] = func
            return func
        return decorator

    mcp.tool = tool_decorator
    mcp._registered = registered
    return mcp


@pytest.fixture
def message_tools(logger, mock_mcp):
    """Create EMQXMessageTools with mocked dependencies."""
    with patch("emqx_mcp_server.tools.emqx_message_tools.EMQXClient") as MockClient:
        tools = EMQXMessageTools(logger)
        tools.emqx_client = MockClient(logger)
        tools.register_tools(mock_mcp)
        return mock_mcp._registered, tools


@pytest.fixture
def client_tools(logger, mock_mcp):
    """Create EMQXClientTools with mocked dependencies."""
    with patch("emqx_mcp_server.tools.emqx_client_tools.EMQXClient") as MockClient:
        tools = EMQXClientTools(logger)
        tools.emqx_client = MockClient(logger)
        tools.register_tools(mock_mcp)
        return mock_mcp._registered, tools


class TestPublishMqttMessage:
    """Tests for the publish_mqtt_message tool."""

    async def test_publish_success(self, message_tools):
        tools, instance = message_tools
        publish = tools["publish_mqtt_message"]
        instance.emqx_client.publish_message = AsyncMock(return_value={"id": "msg-1"})

        result = await publish({"topic": "test/topic", "payload": "hello", "qos": 1})
        assert result == {"id": "msg-1"}
        instance.emqx_client.publish_message.assert_called_once_with(
            topic="test/topic", payload="hello", qos=1, retain=False
        )

    async def test_publish_missing_topic(self, message_tools):
        tools, _ = message_tools
        publish = tools["publish_mqtt_message"]

        result = await publish({"payload": "hello"})
        assert "error" in result
        assert "topic" in result["error"]

    async def test_publish_missing_payload(self, message_tools):
        tools, _ = message_tools
        publish = tools["publish_mqtt_message"]

        result = await publish({"topic": "test/topic"})
        assert "error" in result
        assert "payload" in result["error"]

    async def test_publish_invalid_qos(self, message_tools):
        tools, _ = message_tools
        publish = tools["publish_mqtt_message"]

        result = await publish({"topic": "test/topic", "payload": "hello", "qos": 3})
        assert "error" in result
        assert "QoS" in result["error"]

    async def test_publish_default_qos_and_retain(self, message_tools):
        tools, instance = message_tools
        publish = tools["publish_mqtt_message"]
        instance.emqx_client.publish_message = AsyncMock(return_value={})

        await publish({"topic": "t", "payload": "p"})
        instance.emqx_client.publish_message.assert_called_once_with(
            topic="t", payload="p", qos=0, retain=False
        )

    async def test_publish_returns_dict_on_error(self, message_tools):
        """Verify the bug fix: error returns must be dicts, not strings."""
        tools, _ = message_tools
        publish = tools["publish_mqtt_message"]

        result = await publish({})
        assert isinstance(result, dict)
        assert "error" in result


class TestListMqttClients:
    """Tests for the list_mqtt_clients tool."""

    async def test_list_defaults(self, client_tools):
        tools, instance = client_tools
        list_clients = tools["list_mqtt_clients"]
        instance.emqx_client.list_clients = AsyncMock(
            return_value={"data": [], "meta": {"count": 0}}
        )

        result = await list_clients({})
        assert result == {"data": [], "meta": {"count": 0}}
        call_params = instance.emqx_client.list_clients.call_args[0][0]
        assert call_params["page"] == 1
        assert call_params["limit"] == 100

    async def test_list_with_filters(self, client_tools):
        tools, instance = client_tools
        list_clients = tools["list_mqtt_clients"]
        instance.emqx_client.list_clients = AsyncMock(return_value={"data": []})

        await list_clients({"page": 2, "limit": 50, "username": "admin", "conn_state": "connected"})
        call_params = instance.emqx_client.list_clients.call_args[0][0]
        assert call_params["page"] == 2
        assert call_params["limit"] == 50
        assert call_params["username"] == "admin"
        assert call_params["conn_state"] == "connected"

    async def test_list_ignores_unknown_params(self, client_tools):
        tools, instance = client_tools
        list_clients = tools["list_mqtt_clients"]
        instance.emqx_client.list_clients = AsyncMock(return_value={"data": []})

        await list_clients({"page": 1, "unknown_field": "value"})
        call_params = instance.emqx_client.list_clients.call_args[0][0]
        assert "unknown_field" not in call_params


class TestGetMqttClient:
    """Tests for the get_mqtt_client tool."""

    async def test_get_success(self, client_tools):
        tools, instance = client_tools
        get_client = tools["get_mqtt_client"]
        instance.emqx_client.get_client_info = AsyncMock(
            return_value={"clientid": "c1", "connected": True}
        )

        result = await get_client({"clientid": "c1"})
        assert result["clientid"] == "c1"

    async def test_get_missing_clientid(self, client_tools):
        tools, _ = client_tools
        get_client = tools["get_mqtt_client"]

        result = await get_client({})
        assert "error" in result
        assert "Client ID" in result["error"]


class TestKickMqttClient:
    """Tests for the kick_mqtt_client tool."""

    async def test_kick_success(self, client_tools):
        tools, instance = client_tools
        kick = tools["kick_mqtt_client"]
        instance.emqx_client.kick_client = AsyncMock(
            return_value={"success": True, "message": "Client c1 has been disconnected"}
        )

        result = await kick({"clientid": "c1"})
        assert result["success"] is True

    async def test_kick_missing_clientid(self, client_tools):
        tools, _ = client_tools
        kick = tools["kick_mqtt_client"]

        result = await kick({})
        assert "error" in result
        assert "Client ID" in result["error"]
