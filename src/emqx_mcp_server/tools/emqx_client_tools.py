"""
EMQX Client Tools Module

This module provides tools for managing MQTT clients connected to an EMQX broker.
It registers these tools with the MCP server, making them available for clients
to use through the MCP protocol.
"""

import logging
from mcp.server.fastmcp import FastMCP
from ..emqx_client import EMQXClient

_LIST_OPTIONAL_PARAMS = (
    "node", "clientid", "username", "ip_address", "conn_state",
    "clean_start", "proto_ver", "like_clientid", "like_username",
    "like_ip_address",
)


class EMQXClientTools:

    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.emqx_client = EMQXClient(logger)

    def register_tools(self, mcp: FastMCP) -> None:
        """Register EMQX Client management tools."""

        @mcp.tool(
            name="list_mqtt_clients",
            description="List MQTT clients connected to your EMQX Cluster",
        )
        async def list_clients(request: dict) -> dict:
            """Handle list clients request.

            Args:
                request: Dict containing optional filter parameters:
                    - page (int): Page number (default: 1)
                    - limit (int): Results per page, max 10000 (default: 100)
                    - node, clientid, username, ip_address, conn_state,
                      clean_start, proto_ver, like_clientid, like_username,
                      like_ip_address: Optional filters.
            """
            self.logger.info("Handling list clients request")

            params: dict = {
                "page": request.get("page", 1),
                "limit": request.get("limit", 100),
            }
            for key in _LIST_OPTIONAL_PARAMS:
                if key in request:
                    params[key] = request[key]

            result = await self.emqx_client.list_clients(params)
            self.logger.info("Client list retrieved successfully")
            return result

        @mcp.tool(
            name="get_mqtt_client",
            description="Get detailed information about a specific MQTT client by client ID",
        )
        async def get_client_info(request: dict) -> dict:
            """Handle get client info request.

            Args:
                request: Dict containing:
                    - clientid (str): Client ID (required)
            """
            self.logger.info("Handling get client info request")

            clientid = request.get("clientid")
            if not clientid:
                self.logger.error("Client ID is required but was not provided")
                return {"error": "Client ID is required"}

            result = await self.emqx_client.get_client_info(clientid)
            self.logger.info(f"Client info for '{clientid}' retrieved successfully")
            return result

        @mcp.tool(
            name="kick_mqtt_client",
            description="Disconnect a client from the MQTT broker by client ID",
        )
        async def kick_client(request: dict) -> dict:
            """Handle kick client request.

            Args:
                request: Dict containing:
                    - clientid (str): Client ID (required)
            """
            self.logger.info("Handling kick client request")

            clientid = request.get("clientid")
            if not clientid:
                self.logger.error("Client ID is required but was not provided")
                return {"error": "Client ID is required"}

            result = await self.emqx_client.kick_client(clientid)
            self.logger.info(f"Client '{clientid}' disconnect request processed")
            return result
