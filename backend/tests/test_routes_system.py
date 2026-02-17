import pytest

def test_health_check(client):
    """Verify that the /health endpoint returns a 200 OK"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}

def test_debug_logs_endpoint(client):
    """Verify that the /debug-logs endpoint returns HTML content"""
    response = client.get("/debug-logs")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "System Diagnostic Logs" in response.text
