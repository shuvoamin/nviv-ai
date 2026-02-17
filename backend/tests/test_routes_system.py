import pytest
from unittest.mock import patch

def test_health_check(client):
    """Verify that the /health endpoint returns a 200 OK"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_diag_logger_warning():
    """Verify diagnostic logger warning method"""
    from app_state import diag_logger, LOG_BUFFER
    diag_logger.warning("Test Warning")
    assert any("WARNING: Test Warning" in log for log in LOG_BUFFER)

def test_app_state_init_failure():
    """Verify app startup when ChatBot fails to init"""
    # We must patch the SOURCE class so that when app_state re-imports it during reload, it gets the mock
    with patch("chatbot.ChatBot", side_effect=Exception("Init Failed")):
        import app_state
        from importlib import reload
        
        reload(app_state)
        
        assert app_state.chatbot is None
        # Verify log buffer contains error
        assert any("Failed to initialize ChatBot: Init Failed" in log for log in app_state.LOG_BUFFER)
        
        # Cleanup: Reload again with real ChatBot but we need to stop patching first
        # use a new block to verify recovery or just let the test end (patch exits)
        
    # Restore app_state to normal
    reload(app_state)

def test_debug_logs_endpoint(client):
    """Verify that the /debug-logs endpoint returns HTML content"""
    response = client.get("/debug-logs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "System Diagnostic Logs" in response.text
