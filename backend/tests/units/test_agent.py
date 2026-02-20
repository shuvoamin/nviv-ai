import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_core.tools import StructuredTool

# Add src to path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

from agent import ChatbotAgent

@pytest.fixture
def mock_mcp_client():
    client = AsyncMock()
    # Mock get_tools to return a dummy tool
    dummy_tool = StructuredTool.from_function(
        func=lambda x: "Tool output",
        name="test_tool",
        description="A test tool"
    )
    client.get_tools.return_value = [dummy_tool]
    return client

@pytest.mark.asyncio
async def test_agent_initialization(mock_mcp_client):
    """Test agent initialization and tool loading."""
    # Ensure Azure env vars are present to trigger Azure path, or at least pass validation
    envs = {
        "AZURE_OPENAI_API_KEY": "test-key",
        "AZURE_OPENAI_ENDPOINT": "https://test.openai.azure.com/",
        "AZURE_OPENAI_DEPLOYMENT_NAME": "test-model"
    }
    with patch.dict(os.environ, envs):
        agent = ChatbotAgent()
        agent.mcp_client = mock_mcp_client
    
        # Mock LangGraph compile
        with patch("agent.StateGraph") as mock_state_graph:
            mock_graph = mock_state_graph.return_value
            mock_graph.compile.return_value = AsyncMock()
            
            # Mock AzureChatOpenAI to avoid real connection/validation failures
            with patch("agent.AzureChatOpenAI") as mock_azure:
                await agent.initialize()
                
                mock_mcp_client.initialize.assert_awaited_once()
                mock_mcp_client.get_tools.assert_awaited_once()
                assert agent.tools is not None

@pytest.mark.asyncio
async def test_agent_should_continue():
    """Test conditional edge logic."""
    agent = ChatbotAgent()
    
    # Case End
    state_end = {"messages": [AIMessage(content="Done")]}
    assert agent.should_continue(state_end) == "end"
    
    # Case Continue (Tool Call)
    msg_with_tool = AIMessage(content="", tool_calls=[{"name": "tool", "args": {}, "id": "call_123"}])
    state_continue = {"messages": [msg_with_tool]}
    assert agent.should_continue(state_continue) == "continue"

@pytest.mark.asyncio
async def test_agent_chat_flow(mock_mcp_client):
    """Test the main chat processing flow."""
    agent = ChatbotAgent()
    agent.mcp_client = mock_mcp_client
    agent.app = AsyncMock()
    
    # Mock graph invocation response
    mock_response = {
        "messages": [
            HumanMessage(content="Hello"),
            AIMessage(content="Hi there!")
        ]
    }
    agent.app.ainvoke.return_value = mock_response
    
    response = await agent.chat("Hello", thread_id="test_thread")
    
    agent.app.ainvoke.assert_awaited_once()
    assert response == "Hi there!"

@pytest.mark.asyncio
async def test_agent_chat_error_handling(mock_mcp_client):
    """Test error handling during chat."""
    agent = ChatbotAgent()
    agent.mcp_client = mock_mcp_client
    agent.app = AsyncMock()
    
    # Simulate an error
    agent.app.ainvoke.side_effect = Exception("Graph error")
    
    response = await agent.chat("Hello", thread_id="test_thread")
    
    assert "I encountered an error" in response
    assert "Graph error" in response

    # Case Continue (Tool Call)
    msg_with_tool = AIMessage(content="", tool_calls=[{"name": "tool", "args": {}, "id": "call_123"}])

@pytest.mark.asyncio
async def test_agent_initialization_standard_openai(mock_mcp_client):
    """Test agent initialization with standard OpenAI (non-Azure)."""
    # Provide a dummy key so ChatOpenAI init doesn't fail before mock takes over or during validation
    with patch.dict(os.environ, {"OPENAI_API_KEY": "dummy"}, clear=True):
        agent = ChatbotAgent()
        agent.mcp_client = mock_mcp_client
        
        with patch("agent.ChatOpenAI") as mock_openai, \
             patch("agent.StateGraph") as mock_state_graph:
            
            mock_graph = mock_state_graph.return_value
            mock_graph.compile.return_value = AsyncMock()
            
            await agent.initialize()
            
            mock_openai.assert_called_with(model="gpt-4o")
            assert agent.model is not None

@pytest.mark.asyncio
async def test_agent_cleanup(mock_mcp_client):
    """Test cleanup calls close on mcp client"""
    agent = ChatbotAgent()
    agent.mcp_client = mock_mcp_client
    await agent.cleanup()
    mock_mcp_client.close.assert_awaited_once()

@pytest.mark.asyncio
async def test_agent_load_system_message_file():
    """Test loading system message from file."""
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", new_callable=MagicMock) as mock_open:
        mock_file = MagicMock()
        mock_file.__enter__.return_value.read.return_value = "Knowledge content"
        mock_open.return_value = mock_file
        
        agent = ChatbotAgent()
        assert "Knowledge content" in agent.system_message

@pytest.mark.asyncio
async def test_agent_load_system_message_failure():
    """Test fallback when loading fails."""
    from config import APP_NAME
    image_instruction = (
        "\n\nIMPORTANT: When you generate an image using the `generate_image` tool, "
        "the tool will return a markdown link (e.g. `![Generated Image](...)`). "
        "You MUST include this EXACT markdown link in your final response to the user. "
        "Do not just describe the image; show it by including the link."
    )
    expected = f"You are {APP_NAME}, a helpful AI assistant.{image_instruction}"
    with patch("os.path.exists", return_value=True), \
         patch("builtins.open", side_effect=Exception("Read Error")):
        agent = ChatbotAgent()
        assert agent.system_message == expected

@pytest.mark.asyncio
async def test_agent_call_model_adds_system_message(mock_mcp_client):
    """Test that call_model adds system message if missing."""
    agent = ChatbotAgent()
    agent.mcp_client = mock_mcp_client
    agent.model = AsyncMock()
    agent.model.ainvoke.return_value = AIMessage(content="Response")
    
    # Case 1: No messages
    state = {"messages": []}
    await agent.call_model(state)
    
    # Verify model called with system message prepended
    call_args = agent.model.ainvoke.call_args[0][0]
    assert isinstance(call_args[0], SystemMessage)
    assert call_args[0].content == agent.system_message

    # Case 2: Messages exist but no system message
    state = {"messages": [HumanMessage(content="Hi")]}
    await agent.call_model(state)
    
    call_args = agent.model.ainvoke.call_args[0][0]
    assert isinstance(call_args[0], SystemMessage)
    assert isinstance(call_args[1], HumanMessage)

@pytest.mark.asyncio
async def test_agent_call_model_preserves_system_message(mock_mcp_client):
    """Test that call_model keeps existing system message."""
    agent = ChatbotAgent()
    agent.mcp_client = mock_mcp_client
    agent.model = AsyncMock()
    
    sys_msg = SystemMessage(content="Custom system prompt")
    state = {"messages": [sys_msg, HumanMessage(content="Hi")]}
    
    await agent.call_model(state)
    
    call_args = agent.model.ainvoke.call_args[0][0]
    assert call_args[0] == sys_msg # Should be the exact same object/content
    assert len(call_args) == 2

@pytest.mark.asyncio
async def test_agent_reset_history():
    """Test history reset attempts to clear records."""
    agent = ChatbotAgent()
    agent.conn = MagicMock()
    
    agent.reset_history("test_thread")
    
    assert agent.conn.execute.called

@pytest.mark.asyncio
async def test_agent_chat_auto_initialize(mock_mcp_client):
    """Test that chat() calls initialize() if app is None."""
    agent = ChatbotAgent()
    agent.mcp_client = mock_mcp_client
    
    # Mock app that will be set during initialize
    mock_app = AsyncMock()
    mock_app.ainvoke.return_value = {"messages": [AIMessage(content="Response")]}

    # Mock initialize to set the app
    async def mock_init_side_effect():
        agent.app = mock_app

    agent.initialize = AsyncMock(side_effect=mock_init_side_effect)
    
    # Ensure app is None initially
    agent.app = None
    
    await agent.chat("Hello", thread_id="test_thread")
    
    agent.initialize.assert_awaited_once()
