"""Tests for the EMQXClient module."""

import json
import httpx
import pytest
import respx
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

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


def _make_sse_mock(lines, status_code=200):
    """Create a mock SSE stream context manager.

    Args:
        lines: Iterable of SSE lines to yield.
        status_code: HTTP status code for the response.

    Returns:
        An async context manager that yields a mock response with aiter_lines.
    """
    async def _aiter_lines():
        for line in lines:
            yield line

    mock_response = MagicMock()
    mock_response.status_code = status_code
    mock_response.aiter_lines = _aiter_lines
    mock_response.aread = AsyncMock(return_value=b"error body")
    mock_response.text = "error body"

    @asynccontextmanager
    async def _stream(*args, **kwargs):
        yield mock_response

    return _stream


class TestSubscribeTopic:
    """Tests for subscribe_topic()."""

    async def test_subscribe_success(self, async_client):
        """Mock SSE stream returning 2 data lines with JSON, verify messages collected."""
        lines = [
            'data: {"topic":"t/1","payload":"hello"}',
            'data: {"topic":"t/1","payload":"world"}',
        ]
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = _make_sse_mock(lines)

            result = await async_client.subscribe_topic("t/1", duration=5)

        assert result["topic"] == "t/1"
        assert result["message_count"] == 2
        assert result["messages"][0] == {"topic": "t/1", "payload": "hello"}
        assert result["messages"][1] == {"topic": "t/1", "payload": "world"}

    async def test_subscribe_non_json_data(self, async_client):
        """Mock SSE stream with non-JSON data line, verify fallback to raw."""
        lines = [
            "data: not valid json",
        ]
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = _make_sse_mock(lines)

            result = await async_client.subscribe_topic("t/1", duration=5)

        assert result["message_count"] == 1
        assert result["messages"][0] == {"raw": "not valid json"}

    async def test_subscribe_empty_data_lines_skipped(self, async_client):
        """Mock SSE stream with empty data: lines, verify they're skipped."""
        lines = [
            "data: ",
            "data:",
            'data: {"topic":"t","payload":"msg"}',
        ]
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = _make_sse_mock(lines)

            result = await async_client.subscribe_topic("t", duration=5)

        assert result["message_count"] == 1
        assert result["messages"][0] == {"topic": "t", "payload": "msg"}

    async def test_subscribe_non_data_lines_ignored(self, async_client):
        """Mock SSE stream with event:, id:, comment lines, verify only data: parsed."""
        lines = [
            "event: message",
            "id: 123",
            ": this is a comment",
            'data: {"topic":"t","payload":"hello"}',
            "retry: 3000",
        ]
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = _make_sse_mock(lines)

            result = await async_client.subscribe_topic("t", duration=5)

        assert result["message_count"] == 1
        assert result["messages"][0] == {"topic": "t", "payload": "hello"}

    async def test_subscribe_max_messages_limit(self, async_client):
        """Mock SSE stream with 10 messages, set max_messages=3, verify only 3 collected."""
        lines = [
            f'data: {{"topic":"t","payload":"msg{i}"}}'
            for i in range(10)
        ]
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = _make_sse_mock(lines)

            result = await async_client.subscribe_topic("t", duration=60, max_messages=3)

        assert result["message_count"] == 3
        assert len(result["messages"]) == 3
        assert result["messages"][2] == {"topic": "t", "payload": "msg2"}

    async def test_subscribe_connection_error(self, async_client):
        """Mock ConnectError, verify error dict returned."""
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = MagicMock(side_effect=httpx.ConnectError("connection refused"))

            result = await async_client.subscribe_topic("t/1")

        assert "error" in result
        assert "SSE connection error" in result["error"]

    async def test_subscribe_http_error(self, async_client):
        """Mock generic HTTPError, verify error dict returned."""
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = MagicMock(side_effect=httpx.HTTPError("something failed"))

            result = await async_client.subscribe_topic("t/1")

        assert "error" in result
        assert "SSE HTTP error" in result["error"]

    async def test_subscribe_non_200_status(self, async_client):
        """Mock 401 response, verify error dict with status code."""
        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = _make_sse_mock([], status_code=401)

            result = await async_client.subscribe_topic("t/1")

        assert "error" in result
        assert "401" in result["error"]

    async def test_subscribe_uses_sse_headers(self, async_client):
        """Verify the request uses Accept: text/event-stream and Cache-Control: no-cache."""
        lines = []
        captured_kwargs = {}

        @asynccontextmanager
        async def capture_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            async def _aiter_lines():
                for line in lines:
                    yield line
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.aiter_lines = _aiter_lines
            yield mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = capture_stream

            await async_client.subscribe_topic("t/1", duration=1)

        headers = captured_kwargs.get("headers", {})
        assert headers.get("Accept") == "text/event-stream"
        assert headers.get("Cache-Control") == "no-cache"
        assert "Content-Type" not in headers

    async def test_subscribe_url_encoding(self, async_client):
        """Verify topic with special chars is properly passed in query param."""
        captured_kwargs = {}

        @asynccontextmanager
        async def capture_stream(*args, **kwargs):
            captured_kwargs.update(kwargs)
            async def _aiter_lines():
                return
                yield  # make it an async generator
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.aiter_lines = _aiter_lines
            yield mock_resp

        with patch("httpx.AsyncClient") as MockClient:
            instance = MockClient.return_value
            instance.__aenter__ = AsyncMock(return_value=instance)
            instance.__aexit__ = AsyncMock(return_value=False)
            instance.stream = capture_stream

            await async_client.subscribe_topic("test/topic#special", duration=1)

        params = captured_kwargs.get("params", {})
        assert params.get("topic") == "test/topic#special"
