import os
import sys
from typing import TypedDict, Annotated, Sequence
import operator
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, AIMessage
from langchain_openai import AzureChatOpenAI, ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from config import APP_NAME
try:
    from backend.src.utils.mcp_client import MCPClient
except ImportError:
    from utils.mcp_client import MCPClient

# Add local path for imports if run directly
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

from langgraph.checkpoint.sqlite import SqliteSaver
import sqlite3
import uuid

# ... imports ...

class ChatbotAgent:
    def __init__(self):
        self.mcp_client = MCPClient(
            command=sys.executable,
            args=[os.path.join(os.path.dirname(__file__), "utils/mcp_server.py")],
            env=os.environ.copy()
        )
        self.tools = []
        self.model = None
        self.workflow = None
        self.app = None
        
        # Ensure data directory exists
        self.data_dir = os.path.join(os.path.dirname(__file__), "..", "data")
        os.makedirs(self.data_dir, exist_ok=True)
        self.db_path = os.path.join(self.data_dir, "chat_history.sqlite")
        
        # We need to keep the connection open for the lifetime of the agent
        # check_same_thread=False allows async calls to reuse it
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.memory = SqliteSaver(self.conn)
        
        self.system_message = self._load_system_message()


    def _load_system_message(self) -> str:
        try:
            kb_path = os.path.join(os.path.dirname(__file__), "..", "training", "knowledge_base.md")
            if os.path.exists(kb_path):
                with open(kb_path, "r") as f:
                    return f"You are {APP_NAME}, a helpful AI assistant.\n\n{f.read()}\n\nUse this knowledge to answer questions accurately.\n\nIMPORTANT: When you generate an image using the `generate_image` tool, the tool will return a markdown link (e.g. `![Generated Image](...)`). You MUST include this EXACT markdown link in your final response to the user. Do not just describe the image; show it by including the link."
        except Exception:
            pass
        return f"You are {APP_NAME}, a helpful AI assistant.\n\nIMPORTANT: When you generate an image using the `generate_image` tool, the tool will return a markdown link (e.g. `![Generated Image](...)`). You MUST include this EXACT markdown link in your final response to the user. Do not just describe the image; show it by including the link."
        
    async def initialize(self):
        # 1. Initialize MCP Connection
        await self.mcp_client.initialize()
        self.tools = await self.mcp_client.get_tools()
        
        # 2. Setup Model
        if os.getenv("AZURE_OPENAI_API_KEY"):
            self.model = AzureChatOpenAI(
                azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
                api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-02-15-preview")
            )
        else:
            self.model = ChatOpenAI(model="gpt-4o")
            
        self.model = self.model.bind_tools(self.tools)
        
        # 3. Define Graph
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            self.should_continue,
            {"continue": "tools", "end": END}
        )
        workflow.add_edge("tools", "agent")
        
        self.app = workflow.compile(checkpointer=self.memory)
        print("Agent Initialized with Tools:", [t.name for t in self.tools])

    async def call_model(self, state):
        messages = state['messages']
        # Ensure system message is first if not present
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=self.system_message)] + list(messages)
            
        response = await self.model.ainvoke(messages)
        return {"messages": [response]}

    def should_continue(self, state):
        messages = state['messages']
        last_message = messages[-1]
        if last_message.tool_calls:
            return "continue"
        return "end"

    async def chat(self, message: str, thread_id: str):
        if not self.app:
            await self.initialize()
            
        config = {"configurable": {"thread_id": thread_id}}
        inputs = {"messages": [HumanMessage(content=message)]}
        
        try:
            # Invoke gets the final state of the graph
            final_state = await self.app.ainvoke(inputs, config=config)
            return final_state["messages"][-1].content
        except Exception as e:
            return f"I encountered an error: {str(e)}"

    def reset_history(self, thread_id: str):
        # We could delete the rows manually, or just let users generate a new thread.
        # But if we must clear a specific thread ID's state:
        if self.conn:
            try:
                # Remove checkpoints associated with this thread to 'reset' it
                self.conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
                self.conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id = ?", (thread_id,))
                self.conn.execute("DELETE FROM checkpoint_writes WHERE thread_id = ?", (thread_id,))
                self.conn.commit()
            except Exception as e:
                print(f"Failed to reset history for {thread_id}: {e}")

    async def cleanup(self):
        await self.mcp_client.close()
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
