"""End-to-end protocol tests for the stdio MCP server (mcp SDK v2 handlers)."""

import pytest
from mcp.client import Client

from hopper.mcp.config import MCPServerConfig
from hopper.mcp.server import HopperMCPServer


@pytest.fixture
def hopper_server():
    return HopperMCPServer(MCPServerConfig(api_base_url="http://127.0.0.1:9"))


@pytest.mark.asyncio
async def test_list_tools_and_resources_over_protocol(hopper_server):
    async with Client(hopper_server.server) as client:
        tools = await client.list_tools()
        names = {t.name for t in tools.tools}
        assert "hopper_create_task" in names
        create = next(t for t in tools.tools if t.name == "hopper_create_task")
        assert "title" in create.input_schema["required"]

        resources = await client.list_resources()
        assert resources.resources
        assert all(r.mime_type == "application/json" for r in resources.resources)


@pytest.mark.asyncio
async def test_call_tool_error_is_reported_as_error_result(hopper_server):
    """An unreachable API must surface as is_error, not crash the server."""
    async with Client(hopper_server.server) as client:
        result = await client.call_tool("hopper_create_task", {"title": "x"})
        assert result.is_error is True
        assert result.content[0].text.startswith("Error")
    await hopper_server.cleanup()
