"""Standalone Picamera2 + OpenCV test, mirroring the working sample code."""
from __future__ import annotations

import time

import cv2

from .config import config

try:  # pragma: no cover - hardware dependency
    from picamera2 import Picamera2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("picamera2 package not available") from exc


WINDOW_TITLE = "PetFollower Camera Test"


def main() -> None:
    camera_cfg = config.camera
    picam2 = Picamera2()
    video_config = picam2.create_preview_configuration(
        main={"size": tuple(camera_cfg.resolution), "format": camera_cfg.picamera_format}
    )
    picam2.configure(video_config)
    picam2.start()
    print("Camera started. Press ESC or Q to exit.")

    last_time = time.time()
    frame_counter = 0
    fps = 0.0

    try:
        while True:
            frame = picam2.capture_array()
            if frame is None:
                print("Failed to read from camera device")
                break
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            if camera_cfg.hflip:
                frame = cv2.flip(frame, 1)
            if camera_cfg.vflip:
                frame = cv2.flip(frame, 0)

            frame_counter += 1
            now = time.time()
            if now - last_time >= 1.0:
                fps = frame_counter / (now - last_time)
                frame_counter = 0
                last_time = now
            cv2.putText(
                frame,
                f"{fps:4.1f} fps",
                (10, 24),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2,
            )
            cv2.putText(
                frame,
                "Press Q or ESC to exit",
                (10, camera_cfg.resolution[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2,
            )

            cv2.imshow(WINDOW_TITLE, frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
    finally:
        picam2.stop()
        picam2.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
