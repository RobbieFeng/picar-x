"""Interaction layer implementing celebratory behaviors."""
from __future__ import annotations

import random
import time
from typing import Callable, List

from .config import config
from .log import logger
from .motion import MotionController


class InteractionManager:
    """Provides celebration behaviors triggered by the motion controller."""

    def __init__(self, motion: MotionController) -> None:
        self.motion = motion
        self.cfg = config.interaction
        self._celebrations: List[Callable[[], None]] = [
            self._celebration_spin,
            self._celebration_bounce,
        ]
        self.motion.register_celebration_handler(self.perform_celebration)
        logger.info("Interaction ready with %s celebration behaviors", len(self._celebrations))

    def tick(self, target_visible: bool) -> None:  # pragma: no cover - unused hook
        return

    # ------------------------------------------------------------------
    def perform_celebration(self) -> None:
        behavior = random.choice(self._celebrations)
        logger.info("Starting celebration: %s", behavior.__name__)
        behavior()

    def _celebration_spin(self) -> None:
        robot = self.motion.robot
        duration = self.motion.cfg.celebration_duration
        speed = max(self.motion.cfg.forward_speed, 40)
        try:
            robot.set_dir_servo_angle(60)
        except Exception:
            pass
        robot.forward(speed)
        time.sleep(duration)
        robot.stop()
        try:
            robot.set_dir_servo_angle(0)
            robot.set_cam_tilt_angle(0)
        except Exception:
            pass
        self.motion.reset_target_time()

    def _celebration_bounce(self) -> None:
        robot = self.motion.robot
        duration = 5.0
        speed = max(self.motion.cfg.forward_speed, 20)
        end_time = time.monotonic() + duration
        try:
            robot.set_dir_servo_angle(0)
        except Exception:
            pass
        while time.monotonic() < end_time:
            try:
                robot.set_cam_tilt_angle(15)
            except Exception:
                pass
            robot.forward(speed)
            time.sleep(0.6)
            try:
                robot.set_cam_tilt_angle(-10)
            except Exception:
                pass
            robot.backward(speed)
            time.sleep(0.6)
        robot.stop()
        try:
            robot.set_cam_tilt_angle(0)
        except Exception:
            pass
        self.motion.reset_target_time()


__all__ = ["InteractionManager"]
