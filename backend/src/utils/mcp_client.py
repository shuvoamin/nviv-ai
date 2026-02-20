import logging
import asyncio
from contextlib import AsyncExitStack
from typing import List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, Field, create_model

class MCPClient:
    def __init__(self, command: str, args: List[str], env: Optional[dict] = None):
        self.command = command
        self.args = args
        self.env = env
        self.session: Optional[ClientSession] = None
        self.exit_stack = AsyncExitStack()

    async def initialize(self):
        server_params = StdioServerParameters(
            command=self.command,
            args=self.args,
            env=self.env
        )
        
        # Connect to server
        read, write = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(read, write)
        )
        await self.session.initialize()
    
    async def get_tools(self) -> List[StructuredTool]:
        if not self.session:
            await self.initialize()
            
        mcp_tools = await self.session.list_tools()
        langchain_tools = []

        for tool in mcp_tools.tools:
            async def call_tool(tool_name=tool.name, **kwargs):
                result = await self.session.call_tool(tool_name, arguments=kwargs)
                if result.isError:
                    return f"Error: {result.content}"
                return result.content[0].text

            # Create Pydantic model for args dynamically
            fields = {
                k: (str, Field(description=v.get("description", ""))) 
                for k, v in tool.inputSchema.get("properties", {}).items()
            }
            ArgsModel = create_model(f"{tool.name}Args", **fields)

            langchain_tools.append(StructuredTool.from_function(
                coroutine=call_tool,
                name=tool.name,
                description=tool.description,
                args_schema=ArgsModel
            ))
            
        return langchain_tools

    async def close(self):
        try:
            await self.exit_stack.aclose()
        except RuntimeError as e:
            # Ignore "Attempted to exit cancel scope in a different task" error during shutdown
            logging.debug(f"Ignored RuntimeError during MCP client close: {e}")
        except Exception as e:
            logging.debug(f"Ignored generic Exception during MCP client close: {e}")
