"""最简摄像头测试脚本：直接使用 Picamera2 捕获画面。"""
from __future__ import annotations

import cv2

from .config import config

try:  # pragma: no cover - hardware dependency
    from picamera2 import Picamera2
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("picamera2 未安装") from exc


def main() -> None:
    cfg = config.camera
    picam2 = Picamera2()
    video_config = picam2.create_preview_configuration(
        main={"size": tuple(cfg.resolution), "format": cfg.picamera_format}
    )
    picam2.configure(video_config)
    picam2.start()

    try:
        while True:
            frame = picam2.capture_array()
            if frame is None:
                raise RuntimeError("摄像头读取失败")
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            if cfg.hflip:
                frame = cv2.flip(frame, 1)
            if cfg.vflip:
                frame = cv2.flip(frame, 0)
            cv2.imshow("OpenCV Camera", frame)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
    finally:
        picam2.stop()
        picam2.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
