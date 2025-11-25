# Mermaid MCP Pydantic Example

This is an example of using the MCP Pydantic library to create a Mermaid chart.

## Requirements

This does require a running terraform MCP server.

`docker run -p 8080:8080 --rm -e TRANSPORT_MODE=streamable-http -e TRANSPORT_HOST=0.0.0.0 hashicorp/terraform-mcp-server`

To use the google models you'll need `GEMINI_API_KEY` set in your environment.

