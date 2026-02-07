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


class TestAuthHeader:
    """Tests for _get_auth_header()."""

    def test_returns_basic_auth(self, async_client):
        headers = async_client._get_auth_header()
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")
        assert headers["Content-Type"] == "application/json"

    def test_auth_encoding(self, async_client):
        import base64
        headers = async_client._get_auth_header()
        token = headers["Authorization"].split(" ")[1]
        decoded = base64.b64decode(token).decode()
        assert decoded == f"{TEST_CONFIG.api_key}:{TEST_CONFIG.api_secret}"


class TestHandleResponse:
    """Tests for _handle_response()."""

    def test_success_200(self, async_client):
        response = httpx.Response(200, json={"data": "ok"})
        result = async_client._handle_response(response)
        assert result == {"data": "ok"}

    def test_success_204(self, async_client):
        response = httpx.Response(204)
        result = async_client._handle_response(response)
        assert result == {}

    def test_error_400(self, async_client):
        response = httpx.Response(400, text="Bad Request")
        result = async_client._handle_response(response)
        assert "error" in result
        assert "400" in result["error"]

    def test_error_500(self, async_client):
        response = httpx.Response(500, text="Internal Server Error")
        result = async_client._handle_response(response)
        assert "error" in result
        assert "500" in result["error"]

    def test_json_decode_error(self, async_client):
        """Test handling of response with non-JSON body."""
        response = httpx.Response(200, text="not valid json")
        result = async_client._handle_response(response)
        assert result == {}


class TestPublishMessage:
    """Tests for publish_message()."""

    @respx.mock
    async def test_publish_success(self, async_client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            return_value=httpx.Response(200, json={"id": "msg-123"})
        )
        result = await async_client.publish_message("test/topic", "hello", qos=1)
        assert result == {"id": "msg-123"}

    @respx.mock
    async def test_publish_api_error(self, async_client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            return_value=httpx.Response(401, text="Unauthorized")
        )
        result = await async_client.publish_message("test/topic", "hello")
        assert "error" in result
        assert "401" in result["error"]

    @respx.mock
    async def test_publish_timeout(self, async_client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            side_effect=httpx.ReadTimeout("timeout")
        )
        result = await async_client.publish_message("test/topic", "hello")
        assert "error" in result
        assert "timed out" in result["error"]

    @respx.mock
    async def test_publish_connection_error(self, async_client):
        respx.post(f"{TEST_CONFIG.api_url}/publish").mock(
            side_effect=httpx.ConnectError("connection refused")
        )
        result = await async_client.publish_message("test/topic", "hello")
        assert "error" in result
        assert "Connection error" in result["error"]


class TestListClients:
    """Tests for list_clients()."""

    @respx.mock
    async def test_list_default_params(self, async_client):
        route = respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": [], "meta": {"count": 0}})
        )
        result = await async_client.list_clients()
        assert result == {"data": [], "meta": {"count": 0}}
        assert route.calls[0].request.url.params["page"] == "1"
        assert route.calls[0].request.url.params["limit"] == "10"

    @respx.mock
    async def test_list_custom_params(self, async_client):
        route = respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": [{"clientid": "c1"}]})
        )
        result = await async_client.list_clients({"page": 2, "limit": 50, "username": "admin"})
        assert len(result["data"]) == 1
        assert route.calls[0].request.url.params["username"] == "admin"


class TestGetClientInfo:
    """Tests for get_client_info()."""

    @respx.mock
    async def test_get_success(self, async_client):
        respx.get(f"{TEST_CONFIG.api_url}/clients/client-1").mock(
            return_value=httpx.Response(200, json={"clientid": "client-1", "connected": True})
        )
        result = await async_client.get_client_info("client-1")
        assert result["clientid"] == "client-1"
        assert result["connected"] is True

    @respx.mock
    async def test_get_not_found(self, async_client):
        respx.get(f"{TEST_CONFIG.api_url}/clients/unknown").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        result = await async_client.get_client_info("unknown")
        assert "error" in result
        assert "404" in result["error"]

    @respx.mock
    async def test_url_encoding_special_chars(self, async_client):
        """Test that clientid with special characters is URL-encoded."""
        encoded_id = "client%2F1%23test"
        respx.get(f"{TEST_CONFIG.api_url}/clients/{encoded_id}").mock(
            return_value=httpx.Response(200, json={"clientid": "client/1#test"})
        )
        result = await async_client.get_client_info("client/1#test")
        assert result["clientid"] == "client/1#test"


class TestKickClient:
    """Tests for kick_client()."""

    @respx.mock
    async def test_kick_success(self, async_client):
        respx.delete(f"{TEST_CONFIG.api_url}/clients/client-1").mock(
            return_value=httpx.Response(204)
        )
        result = await async_client.kick_client("client-1")
        assert result["success"] is True
        assert "client-1" in result["message"]

    @respx.mock
    async def test_kick_not_found(self, async_client):
        respx.delete(f"{TEST_CONFIG.api_url}/clients/unknown").mock(
            return_value=httpx.Response(404, text="Not Found")
        )
        result = await async_client.kick_client("unknown")
        assert "error" in result


class TestClientLifecycle:
    """Tests for connection reuse and cleanup."""

    @respx.mock
    async def test_reuses_client(self, async_client):
        respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        await async_client.list_clients()
        first_client = async_client._client
        await async_client.list_clients()
        assert async_client._client is first_client

    async def test_close_idempotent(self, async_client):
        await async_client.close()  # no client created yet
        await async_client.close()  # should not error

    @respx.mock
    async def test_closed_client_reopening(self, async_client):
        """Test that a closed client creates a new httpx client on next request."""
        respx.get(f"{TEST_CONFIG.api_url}/clients").mock(
            return_value=httpx.Response(200, json={"data": []})
        )
        # Make a request to create the internal client
        await async_client.list_clients()
        first_http_client = async_client._client
        assert first_http_client is not None

        # Close the client
        await async_client.close()
        assert first_http_client.is_closed

        # Make another request - should create a new internal client
        await async_client.list_clients()
        second_http_client = async_client._client
        assert second_http_client is not None
        assert second_http_client is not first_http_client
        assert not second_http_client.is_closed
