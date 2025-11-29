"""Entry point tying together vision, motion, and interaction."""
from __future__ import annotations

import time

from pet_follower.interaction import InteractionManager
from pet_follower.log import logger
from pet_follower.motion import MotionController
from pet_follower.vision import CameraStream, DogDetector


def main() -> None:
    camera = CameraStream()
    detector = DogDetector()
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
            safe_to_move = motion.update_safety()
            if not safe_to_move:
                interaction.tick(target_visible=False)
                continue
            if detection is not None:
                motion.track_target(detection)
            else:
                motion.search()
            interaction.tick(target_visible=detection is not None)
            time.sleep(0.05)
    except KeyboardInterrupt:
        logger.info("Pet follower interrupted by user")
    finally:
        motion.stop()
        camera.stop()
        logger.info("Pet follower stopped")


if __name__ == "__main__":
    main()
