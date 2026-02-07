"""
EMQX Message Tools Module

This module provides tools for publishing MQTT messages to an EMQX broker.
It registers these tools with the MCP server, making them available for clients
to use through the MCP protocol.
"""

import logging
from mcp.server.fastmcp import FastMCP
from ..emqx_client import EMQXClient


class EMQXMessageTools:

    def __init__(self, logger: logging.Logger, emqx_client: EMQXClient | None = None):
        self.logger = logger
        self.emqx_client = emqx_client or EMQXClient(logger)

    def register_tools(self, mcp: FastMCP) -> None:
        """Register EMQX Publish tools."""

        @mcp.tool(
            name="publish_mqtt_message",
            description="Publish an MQTT Message to Your EMQX Cluster on EMQX Cloud or Self-Managed Deployment",
        )
        async def publish(request: dict) -> dict:
            """Handle publish message request.

            Args:
                request: Dict containing:
                    - topic (str): MQTT topic (required)
                    - payload (str): Message content (required)
                    - qos (int): Quality of Service 0, 1, or 2 (default: 0)
                    - retain (bool): Whether to retain the message (default: False)

            Returns:
                dict: Publish result or error information.
            """
            self.logger.info("Handling publish request")

            topic = request.get("topic")
            payload = request.get("payload")
            qos = request.get("qos", 0)
            retain = request.get("retain", False)

            if not topic:
                self.logger.error("Missing required parameter: topic")
                return {"error": "Missing required parameter: topic"}

            if payload is None:
                self.logger.error("Missing required parameter: payload")
                return {"error": "Missing required parameter: payload"}

            if qos not in (0, 1, 2):
                self.logger.error(f"Invalid QoS value: {qos}. Must be 0, 1, or 2")
                return {"error": f"Invalid QoS value: {qos}. Must be 0, 1, or 2"}

            result = await self.emqx_client.publish_message(
                topic=topic, payload=payload, qos=qos, retain=retain,
            )

            if "error" not in result:
                self.logger.info(f"Message published successfully to topic: {topic}")
            return result
