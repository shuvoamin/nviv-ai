from fastapi import APIRouter, Response
from app_state import LOG_BUFFER, APP_NAME

router = APIRouter()

@router.get("/health")
async def health_check():
    """Basic health check endpoint"""
    return {"status": "ok"}

@router.get("/debug-logs")
async def debug_logs():
    """Serves the in-memory diagnostic logs as HTML"""
    logs_html = f"<html><head><title>{APP_NAME} Debug Logs</title><style>body{{font-family:monospace;background:#1e1e1e;color:#d4d4d4;padding:20px;}} li{{margin-bottom:5px;border-bottom:1px solid #333;padding-bottom:5px;}}</style></head><body>"
    logs_html += "<h1>System Diagnostic Logs (Last 100)</h1><ul>"
    for entry in reversed(list(LOG_BUFFER)):
        color = "#ff4444" if "ERROR" in entry else "#ffbb33" if "WARNING" in entry else "#d4d4d4"
        logs_html += f"<li style='color:{color}'>{entry}</li>"
    return Response(content=logs_html + "</ul></body></html>", media_type="text/html")
