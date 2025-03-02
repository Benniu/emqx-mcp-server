# EMQX MCP Server
[![smithery badge](https://smithery.ai/badge/@Benniu/emqx-mcp-server)](https://smithery.ai/server/@Benniu/emqx-mcp-server)

A [Model Context Protocol (MCP)](https://www.anthropic.com/news/model-context-protocol) server implementation that provides EMQX MQTT broker interaction.
Enabling MCP clients to interact with the MQTT clusters on [EMQX Cloud](https://www.emqx.com/en/cloud/serverless-mqtt) or self-hosted clusters

## Features

### MQTT Client Management

-   Client Listing: View all connected MQTT clients with flexible filtering options
-   Client Information: Retrieve detailed information about specific clients
-   Connection Control: Disconnect problematic or stale clients from the broker
-   Flexible Filtering: Filter clients by node, username, client ID, connection state, and more

### MQTT Message Publishing

-   Topic-based Publishing: Send messages to any MQTT topics
-   QoS Control: Select Quality of Service level (0, 1, or 2) for reliable delivery
-   Message Retention: Option to persist messages for new subscribers
-   Custom Payloads: Support for any message content format

## Tools

### list_mqtt_clients
- List MQTT clients connected to your EMQX Cluster
- Inputs:
  - page (number, optional): Page number (default: 1)
  - limit (number, optional): Results per page (default: 100, max 10000)
  - node (string, optional): Filter by specific node name
  - clientid (string, optional): Filter by specific client ID
  - username (string, optional): Filter by specific username
  - ip_address (string, optional): Filter by client IP address
  - conn_state (string, optional): Filter by connection state
  - clean_start  (boolean, optional): Filter by clean start flag
  - proto_ver (string, optional): Filter by protocol version
  - like_clientid (string, optional): Fuzzy search by client ID pattern
  - like_username (string, optional): Fuzzy search by username pattern
  - like_ip_address  (string, optional): Fuzzy search by IP address pattern

### get_mqtt_client
- Get detailed information about a specific MQTT client by client ID
- Inputs:
  - clientid (string, required): The unique identifier of the client to retrieve

### kick_mqtt_client
- Disconnect a client from the MQTT broker by client ID
- Inputs:
  - clientid (string, required): The unique identifier of the client to disconnect

### publish_mqtt_message
- Publish an MQTT Message to Your EMQX Cluster on EMQX Cloud or Self-Managed Deployment
- Inputs:
  - topic (string, required): MQTT topic to publish to
  - payload (string, required): Message content to publish
  - qos (number, optional): Quality of Service level (0, 1, or 2) (default: 0)
  - retain (boolean, optional): Whether to retain the message (default: false)

## Setup EMQX Cluster

Before using the EMQX MCP Server tools, you need to set up an EMQX cluster with properly configured API Key and client authentication. There are several options:

1.  EMQX Cloud Serverless Deployment:
-   The easiest way to get started with.
-   Obtain a free serverless deployment from EMQX Cloud
-   Sign up at [EMQX Cloud Serverless](https://www.emqx.com/en/cloud/serverless-mqtt)

2. EMQX Cloud Dedicated Deployment:
-   Provides dedicated resources for production workloads
-   Offers enhanced performance, reliability, and customization options
-   Supports various cloud providers (AWS, GCP, Azure)
-   Includes professional SLA and support
-   Create a deployment at [EMQX Cloud Dedicated](https://www.emqx.com/en/cloud/dedicated)

3.  Self-hosted EMQX Platform:
-   Download and deploy EMQX Platform locally
-   Follow installation instructions at [EMQX Platform](https://www.emqx.com/en/try?tab=self-managed)

## Running locally with the Claude Desktop App

### Installing via Smithery

To install emqx-mcp-server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@Benniu/emqx-mcp-server):

```bash
npx -y @smithery/cli install @Benniu/emqx-mcp-server --client claude
```

### Manual Installation

First, ensure you have the `uv` executable installed. If not, you can install it by following the instructions [here](https://docs.astral.sh/uv/).

1. Install [Claude Desktop App](https://claude.ai/download) if you haven't done so yet.
2. Clone this repository.
3. Add the following to your `claude_desktop_config.json` file:
- On MacOS: `~/Library/Application\ Support/Claude/claude_desktop_config.json`
- On Windows: `%APPDATA%/Claude/claude_desktop_config.json`
```
{
  "mcpServers": {
    "EMQX_MCP_Server": {
      "command": "uv",
      "args": [
        "--directory",
        "path/to/repo/src/emqx_mcp_server",
        "run",
        "emqx-mcp-server"
      ],
      "env":{
        "EMQX_API_URL":"https://your-emqx-cloud-instance.com:8443/api/v5",
        "EMQX_API_KEY":"<YOUR-API-KEY>",
        "EMQX_API_SECRET":"<YOUR-API-SECRET>"
      }
    }
  }
}
```
4. Open or Restart Claude Desktop App
5. Try asking Claude to do something with the MQTT broker (e.g. ask it to publish an MQTT message to a topic). 

## Example Prompts

User: 
```
Please list the clients connected to the MQTT broker.
```

LLM: 
```
Here are the clients currently connected to your MQTT broker:
Connected Client:
  - Client ID: mqttx_2232bdb1
  - Username: test
  - Protocol: MQTT v5
  ...
There is currently 1 client connected to your MQTT broker. Would you like more detailed information about this specific client or would you like to perform another action with your MQTT broker?
```

User: 
```
Yes, please provide the detail info of this client. 
```
LLM: 
```
I'll retrieve the detailed information for this client for you.
...
Here's the detailed information for client "mqttx_2232bdb1":

**Basic Information:**
-   **Client ID:** mqttx_2232bdb1
-   **Username:** test
...
**Connection Details:**
-   **Connected:** Yes
-   **Created At:** 2025-03-02T05:29:51.103+00:00
...
Would you like to perform any actions with this client, such as publishing a message to a topic or disconnecting the client?
```

User: 
```
Please write a poem and send it to the topic '/poem' with QoS 1.
```
LLM: 
```
I'll create a poem and publish it to the topic '/poem' with QoS 1. Let me do that for you.
...
I've successfully published the poem to the topic '/poem' with QoS 1. The message has been delivered with ID: 00062F55A1EFB1156ABC481240B30000.

The poem I sent was:

- Signals in the ether,
- Invisible threads that bind,
- Devices speak in whispers,
- Across the digital divide.
- Messages like leaves falling,
- From cloud to waiting ground,
- Connected yet untethered,
- Where silence makes no sound.
- Brokers of the modern age,
- Routing dreams from here to there,
- In this web of connections,
- We find ourselves everywhere.
- Like stars in constellation,
- Each point of light has worth,
- The language of machines,
- Redefining our Earth.

Is there anything else you'd like to do with your MQTT broker?
```

User: 
```
Please kick out the client mqttx_2232bdb1
```
LLM
```
I'll disconnect the client from the MQTT broker for you.
...
The client has been successfully disconnected. The system returned:
> Client mqttx_2232bdb1 has been disconnected
The MQTT client with ID "mqttx_2232bdb1" is now disconnected from your broker. Is there anything else you would like to do with your MQTT broker?
```


## License
This project is licensed under the Apache License Version 2.0 - see the [LICENSE](https://github.com/Benniu/emqx-mcp-server/blob/main/LICENSE) file for details.
