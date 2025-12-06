"""FastAPI server exposing pet_follower controls for the web dashboard."""
from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pet_follower.log import logger
from pet_follower.web.runtime import CameraManager, EventBus, PetFollowerRuntime

app = FastAPI(title="Pet Follower Controller", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

camera_manager = CameraManager()
events = EventBus()
runtime = PetFollowerRuntime(camera_manager, events)


# execute once when starting
@app.on_event("startup")
async def startup_event() -> None:
    events.bind_loop(asyncio.get_running_loop())
    camera_manager.start()
    logger.info("Web API server started")


@app.get("/api/status")
def api_status() -> Dict[str, Any]:
    return runtime.get_status()


@app.post("/api/commands")
def api_commands(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    action = (payload.get("action") or "").lower()
    try:
        if action == "start":
            message = runtime.start_following()
        elif action == "stop":
            message = runtime.stop_following()
        elif action == "reset":
            message = runtime.reset()
        elif action == "celebrate":
            message = runtime.celebrate()
        elif action == "force_search":
            message = runtime.force_search()
        elif action == "capture_frame":
            message = runtime.capture_snapshot()
        elif action == "manual_drive":
            message = runtime.manual_drive(
                payload.get("direction", ""), payload.get("speed", 40), payload.get("duration", 0.8)
            )
        elif action == "mark_event":
            message = runtime.mark_event(payload.get("note"))
        else:
            raise ValueError("Unknown action")
    except Exception as exc:  # pragma: no cover - runtime safety
        logger.warning("Command failed: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {"status": message, "state": runtime.get_status()}


@app.get("/stream.mjpg")
def mjpeg_stream() -> StreamingResponse:
    generator = camera_manager.mjpeg_generator()
    return StreamingResponse(
        generator,
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/api/events")
async def sse_events() -> StreamingResponse:
    queue = events.register()

    async def event_generator():
        try:
            while True:
                payload = await queue.get()
                yield f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            events.unregister(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser(description="Pet Follower web API server")
    parser.add_argument("--host", default="0.0.0.0", help="Bind address")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument(
        "--reload", action="store_true", help="Enable uvicorn reload (development only)"
    )
    args = parser.parse_args()

    uvicorn.run(app, host=args.host, port=args.port, reload=args.reload)
