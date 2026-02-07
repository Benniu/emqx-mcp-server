"""Tests for the EMQXClient module."""

import httpx
import pytest
import respx

from emqx_mcp_server.config import EMQXConfig
from emqx_mcp_server.emqx_client import EMQXClient


TEST_CONFIG = EMQXConfig(
    api_url="https://emqx.example.com/api/v5",
    api_key="test-key",
    api_secret="test-secret",
)


@pytest.fixture
def client(logger):
    """Create an EMQXClient with test configuration."""
    return EMQXClient(logger, config=TEST_CONFIG)


class TestAuthHeader:
    """Tests for _get_auth_header()."""

    def test_returns_basic_auth(self, client):
        headers = client._get_auth_header()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    def test_auth_encoding(self, client):
        import base64
        headers = client._get_auth_header()
        token = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(token).decode()
        assert decoded == f"{TEST_CONFIG.api_key}:{TEST_CONFIG.api_secret}"


class TestHandleResponse:
    """Tests for _handle_response()."""

    def test_success_200(self, client):
        response = httpx.Response(200, json={"data": "ok"})
        result = client._handle_response(response)
        assert result == {"data": "ok"}

    def test_success_204(self, client):
        response = httpx.Response(204)
        result = client._handle_response(response)
        assert result == {}

    def test_error_400(self, client):
        response = httpx.Response(400, text="Bad Request")
        result = client._handle_response(response)
        assert "error" in result
        assert "400" in result["error"]

    def test_error_500(self, client):
        response = httpx.Response(500, text="Internal Server Error")
        result = client._handle_response(response)
        assert "error" in result
        assert "500" in result["error"]


class TestPublishMessage:
    """Tests for publish_message()."""

    @respx.mock
    async def test_publish_success(self, client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            return_value=httpx.Response(200, json={"id": "msg-123"})
        )
        result = await client.publish_message("test/topic", "hello", qos=1)
        assert result == {"id": "msg-123"}
        await client.close()

    @respx.mock
    async def test_publish_api_error(self, client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        result = await client.publish_message("test/topic", "hello")
        assert "error" in result
        assert "401" in result["error"]
        await client.close()

    @respx.mock
    async def test_publish_timeout(self, client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            side_effect=httpx.ReadTimeout("timeout")
        )
        result = await client.publish_message("test/topic", "hello")
        assert "error" in result
        assert "timed out" in result["error"]
        await client.close()

    @respx.mock
    async def test_publish_connection_error(self, client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = await client.publish_message("test/topic", "hello")
        assert "error" in result
        assert "Connection error" in result["error"]
        await client.close()


class TestListClients:
    """Tests for list_clients()."""

    @respx.mock
    async def test_list_default_params(self, client):
        route = respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": [], "meta": {"count": 0}})
        )
        result = await client.list_clients()
        assert result == {"data": [], "meta": {"count": 0}}
        assert route.calls[0].request.url.params["page"] == "1"
        assert route.calls[0].request.url.params["limit"] == "10"
        await client.close()

    @respx.mock
    async def test_list_custom_params(self, client):
        route = respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": [{"clientid": "c1"}]})
        )
        result = await client.list_clients({"page": 2, "limit": 50, "username": "admin"})
        assert len(result["data"]) == 1
        assert route.calls[0].request.url.params["username"] == "admin"
        await client.close()


class TestGetClientInfo:
    """Tests for get_client_info()."""

    @respx.mock
    async def test_get_success(self, client):
        respx.get(f"{TEST_CONFIG.api_url}/clients/client-1").mock(
            return_value=httpx.Response(200, json={"clientid": "client-1", "connected": True})
        )
        result = await client.get_client_info("client-1")
        assert result["clientid"] == "client-1"
        assert result["connected"] is True
        await client.close()

    @respx.mock
    async def test_get_not_found(self, client):
        respx.get(f"{TEST_CONFIG.api_url}/clients/unknown").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        result = await client.get_client_info("unknown")
        assert "error" in result
        assert "404" in result["error"]
        await client.close()


class TestKickClient:
    """Tests for kick_client()."""

    @respx.mock
    async def test_kick_success(self, client):
        respx.delete(f"{TEST_CONFIG.api_url}/clients/client-1").mock(
            return_value=httpx.Response(204)
        )
        result = await client.kick_client("client-1")
        assert result["success"] is True
        assert "client-1" in result["message"]
        await client.close()

    @respx.mock
    async def test_kick_not_found(self, client):
        respx.delete(f"{TEST_CONFIG.api_url}/clients/unknown").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        result = await client.kick_client("unknown")
        assert "error" in result
        await client.close()


class TestClientLifecycle:
    """Tests for connection reuse and cleanup."""

    @respx.mock
    async def test_reuses_client(self, client):
        respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        await client.list_clients()
        first_client = client._client
        await client.list_clients()
        assert client._client is first_client
        await client.close()

    async def test_close_idempotent(self, client):
        await client.close()  # no client created yet
        await client.close()  # should not error
