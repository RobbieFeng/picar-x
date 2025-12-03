"""仅进行狗检测并在画面上绘制框选的可视化脚本。"""
from __future__ import annotations

import cv2

from .log import logger
from .vision import CameraStream, ColorDetector, DetectionResult, DogDetector

WINDOW_NAME = "PetFollower Dog Viewer"


def main() -> None:  # pragma: no cover - 需真实硬件
    camera = CameraStream()
    detector = DogDetector()
    camera.start()

    if detector.model is None:
        raise RuntimeError("未能加载 YOLO 模型，请先安装 ultralytics 并提供模型文件")

    try:
        while True:
            frame = camera.read()
            if frame is None:
                continue
            detection = detector.detect_dog(frame)
            display = frame.copy()
            if detection is not None:
                x1, y1, x2, y2 = [int(v) for v in detection.bbox]
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = f"dog {detection.confidence:.2f}"
                if detection.approx_distance_cm is not None:
                    label += f" {detection.approx_distance_cm:.0f}cm"
                cv2.putText(
                    display,
                    label,
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
            cv2.imshow(WINDOW_NAME, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
    finally:
        camera.stop()
        cv2.destroyAllWindows()
        logger.info("Dog viewer stopped")


if __name__ == "__main__":
    main()
