from mcp.server.fastmcp import FastMCP
import sys
import os

# Ensure we can import from the tools directory and config
current_dir = os.path.dirname(os.path.abspath(__file__))
# Add tools dir
if current_dir not in sys.path:
    sys.path.append(current_dir)
# Add backend/src (parent dir) to path to import config
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

from tools.communication import send_twilio_sms, send_whatsapp_message
from tools.media import generate_image
from config import APP_NAME

# Initialize FastMCP Server
mcp = FastMCP(f"{APP_NAME} Communication Server")

# Register Tools
mcp.add_tool(send_twilio_sms)
mcp.add_tool(send_whatsapp_message)
mcp.add_tool(generate_image)

if __name__ == "__main__":
    try:
        mcp.run()
    except KeyboardInterrupt:
        # Graceful shutdown on Ctrl+C
        pass
