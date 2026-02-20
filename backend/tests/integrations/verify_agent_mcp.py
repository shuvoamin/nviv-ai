import asyncio
import os
import sys
# Add project root to path
# backend/tests/integrations -> ../../../
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../../..")))

from backend.src.agent import ChatbotAgent
from dotenv import load_dotenv

async def main():
    load_dotenv()
    print("Initializing Agent...")
    try:
        agent = ChatbotAgent()
        await agent.initialize()
        print("Agent initialized.")
        
        # Test 1: General Chat
        print("\nTest 1: General Chat")
        response = await agent.chat("Hello, who are you?")
        print(f"Agent Response: {response}")
        
        # Test 2: Tool Call Experiment
        # Note: If keys are missing, the tool will return an error string, which the agent will describe.
        print("\nTest 2: Tool Call Experiment (SMS)")
        response = await agent.chat("Send a text to +15550000000 saying 'Testing MCP'.")
        print(f"Agent Response (SMS): {response}")

        # Test 3: Image Generation
        print("\nTest 3: Image Generation")
        response = await agent.chat("Generate an image of a cute robot.")
        print(f"Agent Response (Image): {response}")

        await agent.cleanup()
        print("\nCleanup done.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
