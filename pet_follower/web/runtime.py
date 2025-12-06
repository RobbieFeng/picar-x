"""Runtime helpers powering the pet follower web API."""
from __future__ import annotations

import asyncio
import json
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional

import cv2

from pet_follower.interaction import InteractionManager
from pet_follower.log import logger
from pet_follower.motion import MotionController
from pet_follower.vision import CameraStream, DetectionResult, DogDetector
from pet_follower.utils.cloud_client import send_frame_bgr

LOOP_DELAY = 0.02


class EventBus:
    """Fan out runtime events (status/log) to async listeners."""

    def __init__(self) -> None:
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._listeners: List[asyncio.Queue] = []
        self._lock = threading.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def register(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        with self._lock:
            self._listeners.append(queue)
        return queue

    def unregister(self, queue: asyncio.Queue) -> None:
        with self._lock:
            if queue in self._listeners:
                self._listeners.remove(queue)

    def emit(self, payload: Dict[str, Any]) -> None:
        loop = self._loop
        if loop is None:
            return
        with self._lock:
            queues = list(self._listeners)
        for queue in queues:
            try:
                asyncio.run_coroutine_threadsafe(queue.put(payload), loop)
            except RuntimeError:
                # Loop might be closed during shutdown.
                pass


class CameraManager:
    """Background thread that keeps a single camera instance warm."""

    def __init__(self) -> None:
        self._camera = CameraStream()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._frame_lock = threading.Lock()
        self._frame_ready = threading.Condition(self._frame_lock)
        self._latest_frame: Optional[Any] = None  # OpenCV ndarray

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        logger.info("Camera manager starting up")
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, name="camera-manager", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self._thread = None

    def _run(self) -> None:
        self._camera.start()
        try:
            while not self._stop.is_set():
                frame = self._camera.read()
                if frame is None:
                    time.sleep(0.05)
                    continue
                with self._frame_ready:
                    self._latest_frame = frame
                    self._frame_ready.notify_all()
        finally:
            self._camera.stop()
            with self._frame_ready:
                self._latest_frame = None
                self._frame_ready.notify_all()

    def get_frame(self, *, wait: bool = True, timeout: float = 1.0, copy_frame: bool = True):
        """Return the latest frame, waiting if requested."""
        with self._frame_ready:
            if wait and self._latest_frame is None:
                self._frame_ready.wait(timeout)
            frame = self._latest_frame
        if frame is None:
            return None
        return frame.copy() if copy_frame else frame

    def mjpeg_generator(self) -> Iterable[bytes]:
        boundary = b"--frame"
        while True:
            frame = self.get_frame(wait=True, timeout=1.0, copy_frame=True)
            if frame is None:
                continue
            ok, buf = cv2.imencode(".jpg", frame)
            if not ok:
                continue
            payload = buf.tobytes()
            yield boundary + b"\r\nContent-Type: image/jpeg\r\n\r\n" + payload + b"\r\n"


@dataclass
class RuntimeState:
    mode: str = "idle"
    message: str = "Idle"
    target_visible: bool = False
    detection: Dict[str, Any] = field(default_factory=dict)
    safety: Dict[str, Any] = field(default_factory=dict)
    motion: Dict[str, Any] = field(default_factory=dict)
    fps: float = 0.0
    last_log: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "message": self.message,
            "target_visible": self.target_visible,
            "detection": self.detection,
            "safety": self.safety,
            "motion": self.motion,
            "fps": self.fps,
            "last_log": self.last_log,
        }


class PetFollowerRuntime:
    """Orchestrates the pet follower behavior for the web API."""

    def __init__(self, camera: CameraManager, events: EventBus) -> None:
        self._camera = camera
        self._events = events
        self._motion = MotionController()
        self._interaction = InteractionManager(self._motion)
        self._detector = DogDetector()
        self._state = RuntimeState()
        self._state_lock = threading.Lock()
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._fps_samples: Deque[float] = deque(maxlen=60)
        self._last_detection: Optional[DetectionResult] = None
        self._last_detection_time = 0.0
        self._target_visible = False
        self._force_search = threading.Event()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def get_status(self) -> Dict[str, Any]:
        with self._state_lock:
            return json.loads(json.dumps(self._state.to_dict()))

    def start_following(self) -> str:
        if self._detector.model is None:
            raise RuntimeError("YOLO model not loaded; cannot start follow mode")
        if self._thread and self._thread.is_alive():
            return "Follow mode already running"
        self._stop_event.clear()
        self._camera.start()
        self._thread = threading.Thread(target=self._loop, name="pet-follower", daemon=True)
        self._thread.start()
        self._update_state(mode="auto", message="Entering follow mode")
        return "Pet follower started"

    def stop_following(self) -> str:
        if self._thread and self._thread.is_alive():
            self._stop_event.set()
            self._thread.join(timeout=2.0)
        self._thread = None
        self._motion.stop()
        self._update_state(mode="idle", message="Stopped", target_visible=False)
        return "Pet follower stopped"

    def reset(self) -> str:
        self._motion.stop()
        self._motion.reset_target_time()
        self._force_search.clear()
        self._update_state(message="State reset", target_visible=False)
        return "State reset"

    def celebrate(self) -> str:
        self._interaction.perform_celebration()
        self._update_state(message="Celebration requested")
        return "Celebration triggered"

    def force_search(self) -> str:
        self._force_search.set()
        self._update_state(message="Search command queued")
        return "Search triggered"

    def capture_snapshot(self) -> str:
        frame = self._camera.get_frame(wait=True, timeout=1.0, copy_frame=True)
        if frame is None:
            raise RuntimeError("Unable to capture frame right now")
        send_frame_bgr(frame)
        self._update_state(message="Snapshot uploaded to cloud")
        return "Snapshot sent"

    def manual_drive(self, direction: str, speed: int, duration: float) -> str:
        if self._thread and self._thread.is_alive():
            raise RuntimeError("Follower is active; stop it before manual drive")
        robot = self._motion.robot
        speed = max(0, min(100, int(speed)))
        duration = max(0.1, min(3.0, float(duration)))
        direction = (direction or "").lower()
        logger.info("Manual drive direction=%s speed=%s duration=%s", direction, speed, duration)
        if direction == "forward":
            robot.forward(speed)
        elif direction == "backward":
            robot.backward(speed)
        elif direction == "left":
            robot.set_dir_servo_angle(-30)
            robot.forward(speed)
        elif direction == "right":
            robot.set_dir_servo_angle(30)
            robot.forward(speed)
        elif direction == "stop":
            robot.stop()
            robot.set_dir_servo_angle(0)
            return "Stopped"
        else:
            raise RuntimeError("Unknown direction; allowed forward/backward/left/right/stop")
        time.sleep(duration)
        robot.stop()
        robot.set_dir_servo_angle(0)
        self._update_state(message=f"Manual drive {direction}")
        return "Manual drive complete"

    def mark_event(self, note: str | None) -> str:
        msg = note or "Untitled event"
        logger.info("Mark event: %s", msg)
        self._update_state(message=f"Event: {msg}")
        return "Event recorded"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _loop(self) -> None:
        logger.info("Pet follower loop starting")
        self._motion.reset_target_time()
        last_loop = time.monotonic()
        try:
            while not self._stop_event.is_set():
                frame = self._camera.get_frame(wait=True, timeout=1.0, copy_frame=False)
                if frame is None:
                    continue
                now = time.monotonic()
                elapsed = now - last_loop
                last_loop = now
                if elapsed > 0:
                    self._fps_samples.append(1.0 / elapsed)

                detection = self._detector.detect_dog(frame)
                active_detection, holding_last = self._resolve_detection(detection)
                target_visible = detection is not None
                safe_to_move = self._motion.update_safety()

                if self._force_search.is_set():
                    self._force_search.clear()
                    self._motion.reset_target_time()
                    self._motion.turn90(1)
                    self._log("Executing forced search")

                if not safe_to_move:
                    self._log("Movement blocked by safety check", level="warning")
                else:
                    if active_detection is not None:
                        self._motion.track_target(active_detection)
                        if target_visible:
                            self._log("Target acquired; following")
                        elif holding_last:
                            self._log("Holding last heading, continuing search")
                    else:
                        self._log("No detection; running search pattern", verbose=True)
                        if not self._motion.search():
                            self._motion.turn90(1)
                            self._motion.reset_target_time()

                self._publish_state(active_detection, target_visible, safe_to_move)
                time.sleep(LOOP_DELAY)
        except Exception as exc:  # pragma: no cover - safety
            logger.exception("Follower loop crashed: %s", exc)
            self._update_state(message=f"Loop error: {exc}")
        finally:
            self._motion.stop()
            self._update_state(mode="idle", message="Automatic mode exited", target_visible=False)
            logger.info("Pet follower loop stopped")

    def _resolve_detection(self, detection: Optional[DetectionResult]):
        active = detection
        holding = False
        now = time.monotonic()
        if detection is not None:
            self._last_detection = detection
            self._last_detection_time = now
            self._target_visible = True
        elif self._last_detection is not None:
            age = now - self._last_detection_time
            if age <= self._motion.cfg.pursuit_hold_time:
                active = self._last_detection
                holding = True
            else:
                self._last_detection = None
                self._last_detection_time = 0.0
                self._target_visible = False
        return active, holding

    def _publish_state(self, detection: Optional[DetectionResult], target_visible: bool, safe: bool) -> None:
        detection_payload = self._serialize_detection(detection)
        safety = {
            "distance_cm": self._motion.safety.distance_cm,
            "cliff_detected": self._motion.safety.cliff_detected,
        }
        motion = {"safe_to_move": safe}
        fps = sum(self._fps_samples) / len(self._fps_samples) if self._fps_samples else 0.0
        self._update_state(
            detection=detection_payload or {},
            safety=safety,
            motion=motion,
            target_visible=target_visible,
            fps=round(fps, 2),
        )

    def _serialize_detection(self, detection: Optional[DetectionResult]) -> Optional[Dict[str, Any]]:
        if detection is None:
            return None
        return {
            "center": [detection.center[0], detection.center[1]],
            "bbox": [float(v) for v in detection.bbox],
            "confidence": float(detection.confidence),
            "approx_distance_cm": detection.approx_distance_cm,
            "updated_at": time.time(),
        }

    def _log(self, message: str, *, level: str = "info", verbose: bool = False) -> None:
        if verbose:
            logger.debug(message)
        else:
            getattr(logger, level, logger.info)(message)
        self._update_state(message=message, last_log=message)
        self._events.emit({"type": "log", "level": level, "message": message})

    def _update_state(
        self,
        *,
        mode: Optional[str] = None,
        message: Optional[str] = None,
        target_visible: Optional[bool] = None,
        detection: Optional[Dict[str, Any]] = None,
        safety: Optional[Dict[str, Any]] = None,
        motion: Optional[Dict[str, Any]] = None,
        fps: Optional[float] = None,
        last_log: Optional[str] = None,
    ) -> None:
        with self._state_lock:
            if mode is not None:
                self._state.mode = mode
            if message is not None:
                self._state.message = message
            if target_visible is not None:
                self._state.target_visible = target_visible
            if detection is not None:
                self._state.detection = detection
            if safety is not None:
                self._state.safety = safety
            if motion is not None:
                self._state.motion = motion
            if fps is not None:
                self._state.fps = fps
            if last_log is not None:
                self._state.last_log = last_log
            snapshot = self._state.to_dict()
        self._events.emit({"type": "status", "data": snapshot})
