"""Entry point tying together vision, motion, and interaction."""
from __future__ import annotations

import time

import cv2

from pet_follower.interaction import InteractionManager
from pet_follower.log import logger
from pet_follower.motion import MotionController
from pet_follower.vision import CameraStream, DogDetector, ColorDetector

WINDOW_NAME = "PetFollower"


def main() -> None:
    camera = CameraStream()
    detector = ColorDetector()
    motion = MotionController()
    interaction = InteractionManager(motion)

    try:
        logger.info("Pet follower starting up")
        camera.start()
        while True:
            frame = camera.read()
            if frame is None:
                continue
            detection = detector.detect_dog(frame)
            
            # Create display frame with visualization
            display = frame.copy()
            if detection is not None:
                x1, y1, x2, y2 = [int(v) for v in detection.bbox]
                cv2.rectangle(display, (x1, y1), (x2, y2), (0, 255, 0), 2)
                label = "Blue"
                if detection.confidence is not None:
                    label += f" {detection.confidence:.2f}"
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
                dist = detection.approx_distance_cm
                dist_str = f"{dist:.1f}cm" if dist is not None else "N/A"
                print(f"Blue detected! Pos: {detection.center}, Dist: {dist_str}")
            
            cv2.imshow(WINDOW_NAME, display)
            key = cv2.waitKey(1) & 0xFF
            if key in (27, ord("q"), ord("Q")):
                break
            
            #safe_to_move = motion.update_safety()
            safe_to_move = True
            if not safe_to_move:
                #interaction.tick(target_visible=False)
                continue
            if detection is not None:
                motion.track_target(detection)
            else:
                #motion.search()
                motion.robot.stop()
            #interaction.tick(target_visible=detection is not None)
            time.sleep(0.1)
            motion.robot.stop()
            time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Pet follower interrupted by user")
    finally:
        motion.stop()
        camera.stop()
        cv2.destroyAllWindows()
        logger.info("Pet follower stopped")


if __name__ == "__main__":
    main()
