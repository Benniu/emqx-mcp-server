"""
EMQX HTTP API Client Module

This module provides a client for interacting with the EMQX MQTT broker's HTTP API.
It handles authentication, request formatting, and response processing.
"""

import httpx
import base64
import logging
from urllib.parse import quote
from .config import EMQXConfig, load_config

DEFAULT_TIMEOUT = 30


class EMQXClient:
    """
    EMQX HTTP API Client

    Provides methods to interact with EMQX Cloud or self-hosted EMQX broker
    through its HTTP API. Handles authentication and error processing.
    """

    def __init__(self, logger: logging.Logger, config: EMQXConfig | None = None):
        self._config = config or load_config()
        self.logger = logger
        self._client: httpx.AsyncClient | None = None

    @property
    def api_url(self) -> str:
        return self._config.api_url

    def _get_auth_header(self) -> dict[str, str]:
        """Create authorization header for EMQX API."""
        auth_string = f"{self._config.api_key}:{self._config.api_secret}"
        encoded_auth = base64.b64encode(auth_string.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_auth}",
            "Content-Type": "application/json",
        }

    def _handle_response(self, response: httpx.Response) -> dict:
        """Process API response, extract data and handle errors."""
        if 200 <= response.status_code < 300:
            if response.status_code == 204:
                return {}
            try:
                return response.json()
            except ValueError:
                return {}
        error_msg = f"EMQX API error: {response.status_code} - {response.text}"
        self.logger.error(error_msg)
        return {"error": error_msg}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create the shared httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers=self._get_auth_header(),
                timeout=DEFAULT_TIMEOUT,
            )
        return self._client

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _request(
        self,
        method: str,
        path: str,
        json: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Send an HTTP request to the EMQX API.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            path: API endpoint path (e.g. "/publish")
            json: JSON body for POST/PUT requests
            params: Query parameters for GET requests

        Returns:
            dict: Parsed response or error dict.
        """
        url = f"{self.api_url}{path}"
        client = await self._get_client()
        try:
            response = await client.request(
                method, url, json=json, params=params,
            )
            return self._handle_response(response)
        except httpx.TimeoutException:
            error_msg = f"Request timed out: {method} {path}"
            self.logger.error(error_msg)
            return {"error": error_msg}
        except httpx.ConnectError as e:
            error_msg = f"Connection error: {e}"
            self.logger.error(error_msg)
            return {"error": error_msg}
        except httpx.HTTPError as e:
            error_msg = f"HTTP request failed: {e}"
            self.logger.error(error_msg)
            return {"error": error_msg}

    async def publish_message(
        self, topic: str, payload: str, qos: int = 0, retain: bool = False
    ) -> dict:
        """
        Publish a message to an MQTT topic.

        Args:
            topic: The MQTT topic to publish to
            payload: The message payload to publish
            qos: Quality of Service level (0, 1, or 2). Defaults to 0.
            retain: Whether to retain the message. Defaults to False.

        Returns:
            dict: Response from the EMQX API or error information
        """
        self.logger.info(f"Publishing message to topic: {topic}")
        return await self._request(
            "POST",
            "/publish",
            json={
                "topic": topic,
                "payload": payload,
                "qos": qos,
                "retain": retain,
            },
        )

    async def list_clients(self, params: dict | None = None) -> dict:
        """
        Get a list of connected MQTT clients.

        Args:
            params: Query parameters to filter results.

        Returns:
            dict: Response from the EMQX API containing client data or error information
        """
        if params is None:
            params = {"page": 1, "limit": 10}
        self.logger.info("Retrieving list of MQTT clients")
        return await self._request("GET", "/clients", params=params)

    async def get_client_info(self, clientid: str) -> dict:
        """
        Get detailed information about a specific MQTT client by client ID.

        Args:
            clientid: The unique identifier of the client to retrieve

        Returns:
            dict: Response from the EMQX API containing client data or error information
        """
        self.logger.info(f"Retrieving information for client ID: {clientid}")
        return await self._request("GET", f"/clients/{quote(clientid, safe='')}")

    async def kick_client(self, clientid: str) -> dict:
        """
        Kick out (disconnect) a client from the MQTT broker.

        Args:
            clientid: The unique identifier of the client to disconnect

        Returns:
            dict: Success confirmation or error information
        """
        self.logger.info(f"Kicking out client with ID: {clientid}")
        result = await self._request("DELETE", f"/clients/{quote(clientid, safe='')}")
        if "error" not in result:
            return {"success": True, "message": f"Client {clientid} has been disconnected"}
        return result
