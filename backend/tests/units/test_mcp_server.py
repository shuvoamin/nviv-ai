import pytest
from unittest.mock import MagicMock, patch
import sys
import os

# Add src to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) + "/src")

def test_mcp_server_initialization():
    """Test that the MCP server initializes and registers tools correctly."""
    
    # Mock FastMCP and the tools to prevent side effects/imports
    with patch("mcp.server.fastmcp.FastMCP") as MockFastMCP, \
         patch("utils.tools.communication.send_twilio_sms") as mock_sms, \
         patch("utils.tools.communication.send_whatsapp_message") as mock_whatsapp, \
         patch("utils.tools.media.generate_image") as mock_image:
        
        mock_mcp_instance = MockFastMCP.return_value
        
        # Ensure clean state by removing from sys.modules if present
        if "utils.mcp_server" in sys.modules:
            del sys.modules["utils.mcp_server"]
            
        import utils.mcp_server
        
        from config import APP_NAME
        # Verify initialization
        # It should be called once upon import
        MockFastMCP.assert_called_once_with(f"{APP_NAME} Communication Server")
        
        # Verify tool registration
        assert mock_mcp_instance.add_tool.call_count >= 3
        
        # Check that specific tools were added. 
        # We need to access the function objects from the imported module to compare
        mock_mcp_instance.add_tool.assert_any_call(utils.mcp_server.send_twilio_sms)
        mock_mcp_instance.add_tool.assert_any_call(utils.mcp_server.send_whatsapp_message)
        mock_mcp_instance.add_tool.assert_any_call(utils.mcp_server.generate_image)

def test_mcp_server_path_configuration():
    """Test that mcp_server adds directories to sys.path if missing."""
    import sys
    import os
    
    # Calculate paths that mcp_server tries to add
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    src_utils_dir = os.path.join(base_dir, "src/utils")
    src_dir = os.path.join(base_dir, "src")
    
    # Create a copy of sys.path without these directories
    clean_path = [p for p in sys.path if p != src_utils_dir and p != src_dir]
    
    with patch("sys.path", clean_path), \
         patch("mcp.server.fastmcp.FastMCP"), \
         patch("utils.tools.communication.send_twilio_sms"), \
         patch("utils.tools.communication.send_whatsapp_message"), \
         patch("utils.tools.media.generate_image"):
        
        # Force re-import
        if "utils.mcp_server" in sys.modules:
            del sys.modules["utils.mcp_server"]
            
        import utils.mcp_server
        
        # Verify paths were added
        # Note: We rely on the side effect of the import modifying the patched list
        # Since we passed a list object to patch, it modifies that object in place if it's mutable?
        # No, patch("sys.path", new_list) replaces the sys.path object. 
        # The module code does `sys.path.append`.
        # So `sys.path` inside the with block should contain the new paths.
        
        assert src_utils_dir in sys.path
        assert src_dir in sys.path

def test_mcp_server_main_keyboard_interrupt():
    """Test that KeyboardInterrupt is caught gracefully in the __main__ block."""
    import runpy

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    mcp_server_path = os.path.join(base_dir, "src/utils/mcp_server.py")

    with patch("mcp.server.fastmcp.FastMCP") as MockFastMCP:
        mock_instance = MockFastMCP.return_value
        # Make run() raise KeyboardInterrupt to hit the except branch
        mock_instance.run.side_effect = KeyboardInterrupt

        with patch("utils.tools.communication.send_twilio_sms"), \
             patch("utils.tools.communication.send_whatsapp_message"), \
             patch("utils.tools.media.generate_image"):
            # Should NOT raise — KeyboardInterrupt must be caught inside the module
            runpy.run_path(mcp_server_path, run_name="__main__")

        mock_instance.run.assert_called_once()


def test_mcp_server_main_execution():
    """Test the __name__ == '__main__' block (simulated)."""
    with patch("mcp.server.fastmcp.FastMCP") as MockFastMCP:
        mock_instance = MockFastMCP.return_value
        
        # We can't easily trigger __name__ == "__main__" by importing.
        # We can simulate it by reading the file and executing it.
        
        import utils.mcp_server
        
        # Manually invoke run if we can't trigger main, OR:
        # executing the file logic:
        # We can just verify mcp.run() is called if we executed the block.
        # But for coverage, we often just need to ensure the file is valid.
        
        # To hit the `if __name__ == "__main__":` block for coverage:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        mcp_server_path = os.path.join(base_dir, "src/utils/mcp_server.py")
        
        with patch("sys.path", sys.path): # Protect sys.path
             # We need to mock the tools again because exec will re-import
            with patch("utils.tools.communication.send_twilio_sms"), \
                 patch("utils.tools.communication.send_whatsapp_message"), \
                 patch("utils.tools.media.generate_image"):
                     
                import runpy
                # This executes the file as __main__
                runpy.run_path(mcp_server_path, run_name="__main__")
                
                # We can't easily assert on the *internal* mcp object created during runpy
                # unless we patch FastMCP again and check the return value behavior.
                pass
        
        # The MockFastMCP from the decorator/context manager *should* catch the instantiation inside runpy
        # because it patches the class in the module where it's defined (mcp.server.fastmcp).
        MockFastMCP.return_value.run.assert_called()
