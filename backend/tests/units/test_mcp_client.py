import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from mcp import ClientSession, StdioServerParameters
from mcp.types import CallToolResult, TextContent, Tool

# Add src to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

from utils.mcp_client import MCPClient

@pytest.mark.asyncio
async def test_mcp_client_initialization():
    """Test that MCPClient initializes correctly and connects to the server."""
    with patch("utils.mcp_client.stdio_client") as mock_stdio_client, \
         patch("utils.mcp_client.ClientSession") as mock_client_session:
        
        # Setup mocks
        mock_read_stream = AsyncMock()
        mock_write_stream = AsyncMock()
        
        # Mock the context manager behavior of stdio_client
        mock_context_manager = AsyncMock()
        mock_context_manager.__aenter__.return_value = (mock_read_stream, mock_write_stream)
        mock_context_manager.__aexit__.return_value = None
        mock_stdio_client.return_value = mock_context_manager

        # Mock ClientSession
        session_instance = AsyncMock(spec=ClientSession)
        # ClientSession is used as an async context manager
        mock_client_session.return_value.__aenter__.return_value = session_instance
        mock_client_session.return_value.__aexit__.return_value = None
        
        # Initialize client
        client = MCPClient("python", ["server.py"])
        await client.initialize()

        # Verification
        mock_stdio_client.assert_called_once()
        mock_client_session.assert_called_once_with(mock_read_stream, mock_write_stream)
        session_instance.initialize.assert_awaited_once()
        
        await client.close()

@pytest.mark.asyncio
async def test_get_tools():
    """Test retrieval and conversion of tools to LangChain format."""
    with patch("utils.mcp_client.stdio_client"), \
         patch("utils.mcp_client.ClientSession") as mock_client_session:
        
        session_instance = AsyncMock(spec=ClientSession)
        mock_client_session.return_value = session_instance
        
        # Mock list_tools response
        mock_tool = Tool(name="test_tool", description="A test tool", inputSchema={"type": "object", "properties": {"arg": {"type": "string", "description": "An argument"}}})
        session_instance.list_tools.return_value.tools = [mock_tool]
        
        # Mock call_tool response for the generated tool
        mock_result = CallToolResult(content=[TextContent(type="text", text="Tool output")])
        session_instance.call_tool.return_value = mock_result

        client = MCPClient("python", ["server.py"])
        # Inject session to bypass init
        client.session = session_instance
    
        tools = await client.get_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        assert tools[0].description == "A test tool"
        
        # Verify the generated tool calls the session
        # We need to run the tool's coroutine
        result = await tools[0].ainvoke({"arg": "value"})
        
        session_instance.call_tool.assert_awaited_once_with("test_tool", arguments={"arg": "value"})
        assert result == "Tool output"



@pytest.mark.asyncio
async def test_mcp_client_close_error_handling():
    """Test that close() handles RuntimeError gracefully."""
    client = MCPClient("python", ["server.py"])
    client.exit_stack = AsyncMock()
    
    # Simulate the specific RuntimeError we want to catch
    error_msg = "Attempted to exit cancel scope in a different task than it was entered in"
    client.exit_stack.aclose.side_effect = RuntimeError(error_msg)
    
    with patch("utils.mcp_client.logging") as mock_logging:
        # Should not raise exception
        await client.close()
        
        client.exit_stack.aclose.assert_awaited_once()
        mock_logging.debug.assert_called_with(f"Ignored RuntimeError during MCP client close: {error_msg}")

@pytest.mark.asyncio
async def test_mcp_client_close_generic_error():
    """Test that close() handles generic Exception gracefully."""
    client = MCPClient("python", ["server.py"])
    client.exit_stack = AsyncMock()
    
    # Simulate a generic exception
    error_msg = "Generic error"
    client.exit_stack.aclose.side_effect = Exception(error_msg)
    
    with patch("utils.mcp_client.logging") as mock_logging:
        # Should not raise exception
        await client.close()
        
        client.exit_stack.aclose.assert_awaited_once()
        mock_logging.debug.assert_called_with(f"Ignored generic Exception during MCP client close: {error_msg}")

@pytest.mark.asyncio
async def test_get_tools_auto_initialization():
    """Test that get_tools initializes the session if not already done."""
    with patch("utils.mcp_client.stdio_client"), \
         patch("utils.mcp_client.ClientSession") as mock_client_session:
        
        session_instance = AsyncMock(spec=ClientSession)
        mock_client_session.return_value = session_instance
        session_instance.list_tools.return_value.tools = []
        
        client = MCPClient("python", ["server.py"])
        # We do NOT inject session here, so it is None
        
        # Mock the context managers for initialization
        client.exit_stack.enter_async_context = AsyncMock()
        client.exit_stack.enter_async_context.side_effect = [
            (AsyncMock(), AsyncMock()), # read, write
            session_instance # session
        ]
        
        await client.get_tools()
        
        # Verify initialize was called (via checking side effects or session state)
        assert client.session is not None
        session_instance.initialize.assert_awaited_once()

@pytest.mark.asyncio
async def test_tool_execution_error():
    """Test tool execution when the tool returns an error."""
    with patch("utils.mcp_client.stdio_client"), \
         patch("utils.mcp_client.ClientSession") as mock_client_session:
        
        session_instance = AsyncMock(spec=ClientSession)
        mock_client_session.return_value = session_instance
        
        # Mock list_tools with one tool
        mock_tool = Tool(name="error_tool", description="Fails", inputSchema={"type": "object", "properties": {}})
        session_instance.list_tools.return_value.tools = [mock_tool]
        
        # Mock call_tool response with error
        mock_result = CallToolResult(content=[TextContent(type="text", text="Failure reason")], isError=True)
        session_instance.call_tool.return_value = mock_result
        
        client = MCPClient("python", ["server.py"])
        client.session = session_instance
        
        tools = await client.get_tools()
        result = await tools[0].ainvoke({})
        
        assert "Error:" in result
        assert "Failure reason" in result
