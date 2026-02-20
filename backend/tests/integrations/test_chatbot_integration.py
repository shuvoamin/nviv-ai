import asyncio
import os
import sys
from dotenv import load_dotenv

# Add project root to path
# backend/tests/integrations -> ../../../
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
sys.path.append(project_root)
sys.path.append(os.path.join(project_root, "backend/src"))

from backend.src.chatbot import ChatBot

async def main():
    load_dotenv()
    print("Initializing ChatBot...")
    try:
        bot = ChatBot()
        await bot.initialize()
        print("ChatBot initialized.")
        
        print("\nTest: Chat")
        # this should delegate to agent.chat
        response = await bot.chat("Hello from integration test")
        print(f"Response: {response}")

        await bot.agent.cleanup() # Manually cleanup for test
        print("\nCleanup done.")

    except Exception as e:
        print(f"ERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
