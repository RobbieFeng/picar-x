"""Entry point tying together vision, motion, and interaction."""
from __future__ import annotations

import time

import cv2

from pet_follower.interaction import InteractionManager
from pet_follower.log import logger
from pet_follower.motion import MotionController
from pet_follower.vision import CameraStream, DogDetector, ColorDetector

WINDOW_NAME = "PetFollower"
LOOP_DELAY = 0.02


def main() -> None:
    camera = CameraStream()
    detector = DogDetector()
    motion = MotionController()
    interaction = InteractionManager(motion)

    try:
        logger.info("Pet follower starting up")
        camera.start()
        target_visible = False
        last_detection = None
        last_detection_time = 0.0
        while True:
            frame = camera.read()
            if frame is None:
                continue
            detection = detector.detect_dog(frame)

            # Create display frame with visualization
            display = frame.copy()
            now = time.monotonic()
            active_detection = detection
            holding_last = False
            if detection is not None:
                last_detection = detection
                last_detection_time = now
            elif last_detection is not None:
                age = now - last_detection_time
                if age <= motion.cfg.pursuit_hold_time:
                    active_detection = last_detection
                    holding_last = True
                    logger.debug(
                        "Holding last detection for %.2fs", motion.cfg.pursuit_hold_time - age
                    )
                else:
                    last_detection = None
                    last_detection_time = 0.0

            draw_detection = active_detection
            if draw_detection is not None:
                x1, y1, x2, y2 = [int(v) for v in draw_detection.bbox]
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = "Red"
                if draw_detection.confidence is not None:
                    label += f" {draw_detection.confidence:.2f}"
                if draw_detection.approx_distance_cm is not None:
                    label += f" {draw_detection.approx_distance_cm:.0f}cm"
                cv2.putText(
                    display,
                    label,
                    (x1, max(20, y1 - 10)),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    (0, 255, 0),
                    2,
                )
                dist = draw_detection.approx_distance_cm
                dist_str = f"{dist:.1f}cm" if dist is not None else "N/A"
                offset = draw_detection.center[0] - (draw_detection.frame_size[1] / 2)
                if not target_visible:
                    logger.info(
                        "Target acquired conf=%.2f dist=%s offset=%.1f",
                        draw_detection.confidence,
                        dist_str,
                        offset,
                    )
                    target_visible = True
                elif holding_last:
                    logger.debug(
                        "Pursuing last known direction dist=%s offset=%.1f",
                        dist_str,
                        offset,
                    )
                else:
                    logger.debug(
                        "Tracking target conf=%.2f dist=%s offset=%.1f",
                        draw_detection.confidence,
                        dist_str,
                        offset,
                    )
            else:
                if target_visible:
                    logger.info("Target lost - entering search mode")
                    target_visible = False

            cv2.imshow(WINDOW_NAME, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break

            safe_to_move = motion.update_safety()
            if not safe_to_move:
                #interaction.tick(target_visible=False)
                continue
            if active_detection is not None:
                motion.track_target(active_detection)
            else:
                logger.debug("No detection this frame - running search pattern")
                if not motion.search():
                    motion.turn90(1)
                    motion.reset_target_time()
                #motion.robot.stop()
            #interaction.tick(target_visible=detection is not None)
            time.sleep(LOOP_DELAY)
            #motion.robot.stop()
            #time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Pet follower interrupted by user")
    finally:
        motion.stop()
        camera.stop()
        cv2.destroyAllWindows()
        logger.info("Pet follower stopped")


if __name__ == "__main__":
    main()
