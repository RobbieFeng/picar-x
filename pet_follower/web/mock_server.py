"""Mock server for local development - serves dashboard with dummy data."""
from __future__ import annotations

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles

# Get the directory where this file is located
BASE_DIR = Path(__file__).parent
ASSETS_DIR = BASE_DIR / "assets"

app = FastAPI(title="Pet Follower Dashboard (Mock)", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mock state
mock_state = {
    "mode": "idle",
    "state": "idle",
    "detection": {
        "target_visible": True,
        "confidence": 0.85,
        "approx_distance_cm": 120.5,
        "updated_at": time.time() - 2,
    },
    "safety": {
        "distance_cm": 45.0,
        "cliff_detected": False,
    },
    "motion": {
        "safe_to_move": True,
    },
    "fps": 15.3,
    "camera_fps": 15.3,
    "message": "System ready - Mock mode",
    "last_log": "Mock server running",
    "target_visible": True,
    "distance_cm": 120.5,
    "obstacle_distance": 45.0,
    "last_detection": time.time() - 2,
}


@app.get("/")
async def serve_dashboard():
    """Serve the main dashboard HTML file."""
    return FileResponse(BASE_DIR / "dashboard.html")


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    """Return mock status data."""
    # Update timestamps to make it look live
    mock_state["detection"]["updated_at"] = time.time() - 2
    mock_state["last_detection"] = time.time() - 2
    return mock_state


@app.post("/api/commands")
def api_commands(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Handle mock commands."""
    action = (payload.get("action") or "").lower()
    
    # Update mock state based on action
    if action == "start":
        mock_state["mode"] = "following"
        mock_state["state"] = "following"
        mock_state["message"] = "Started following - Mock mode"
    elif action == "stop":
        mock_state["mode"] = "idle"
        mock_state["state"] = "idle"
        mock_state["message"] = "Stopped - Mock mode"
    elif action == "reset":
        mock_state["mode"] = "idle"
        mock_state["state"] = "idle"
        mock_state["message"] = "State reset - Mock mode"
    elif action == "celebrate":
        mock_state["message"] = "Celebrating! 🎉 - Mock mode"
    elif action == "force_search":
        mock_state["mode"] = "searching"
        mock_state["message"] = "Searching for target - Mock mode"
    elif action == "capture_frame":
        mock_state["message"] = "Snapshot captured - Mock mode"
    elif action == "manual_drive":
        direction = payload.get("direction", "unknown")
        mock_state["message"] = f"Manual drive: {direction} - Mock mode"
    elif action == "mark_event":
        note = payload.get("note", "")
        mock_state["message"] = f"Event marked: {note} - Mock mode"
    
    return {
        "status": mock_state["message"],
        "state": mock_state,
    }


@app.get("/stream.mjpg")
def mjpeg_stream():
    """Return a dummy video stream (placeholder image)."""
    # Create a simple placeholder image response
    # Using a 1x1 transparent PNG as a placeholder
    placeholder = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00"
        b"\x01\x00\x00\x05\x00\x01\r\n-\xdb\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    
    async def generate_frames():
        while True:
            # Send a frame every 100ms to simulate video stream
            yield (
                b"--frame\r\n"
                b"Content-Type: image/png\r\n\r\n" + placeholder + b"\r\n"
            )
            await asyncio.sleep(0.1)
    
    return StreamingResponse(
        generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/events")
async def sse_events():
    """Mock Server-Sent Events stream."""
    async def event_generator():
        # Send initial status
        yield f"data: {json.dumps({'type': 'status', 'data': mock_state}, ensure_ascii=False)}\n\n"
        
        # Periodically send updates
        while True:
            await asyncio.sleep(2)
            # Update some values to make it look dynamic
            if mock_state["detection"]["target_visible"]:
                mock_state["detection"]["confidence"] = min(0.99, mock_state["detection"]["confidence"] + 0.01)
            else:
                mock_state["detection"]["confidence"] = max(0.5, mock_state["detection"]["confidence"] - 0.01)
            
            yield f"data: {json.dumps({'type': 'status', 'data': mock_state}, ensure_ascii=False)}\n\n"
    
    return StreamingResponse(event_generator(), media_type="text/event-stream")


# Mount static assets directory
app.mount("/assets", StaticFiles(directory=str(ASSETS_DIR)), name="assets")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Pet Follower mock web server")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument(
        "--reload", action="store_true", help="Enable uvicorn reload (development only)"
    )
    args = parser.parse_args()

    print(f"\n🚀 Mock server starting at http://{args.host}:{args.port}")
    print("📱 Open the dashboard in your browser!")
    print("⚠️  This is a mock server - no actual hardware control\n")
    
    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)

