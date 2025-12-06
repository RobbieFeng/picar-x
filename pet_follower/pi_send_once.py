# send an image to server
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from pet_follower.utils.cloud_client import send_frame_bgr
from pet_follower.vision import CameraStream


def capture_frame(max_attempts: int = 5, retry_delay: float = 0.2):
    """Grab a single frame from the configured camera stream."""
    camera = CameraStream()
    camera.start()
    frame = None
    try:
        for _ in range(max_attempts):
            frame = camera.read()
            if frame is not None:
                break
            time.sleep(retry_delay)
    finally:
        camera.stop()
    return frame


def main():
    frame = capture_frame()
    if frame is None:
        print("Failed to read frame")
        return
    print("[pi_send_once] captured frame, sending...")
    send_frame_bgr(frame)


if __name__ == "__main__":
    main()
