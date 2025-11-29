"""Motion control helpers for the pet follower behavior."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Optional

from picarx import Picarx

from .config import config
from .log import logger
from .vision import DetectionResult


@dataclass
class SafetyState:
    distance_cm: Optional[float] = None
    cliff_detected: bool = False


class MotionController:
    def __init__(self) -> None:
        self.cfg = config.motion
        self.robot = Picarx()
        self._last_distance_sample = 0.0
        self._last_cliff_sample = 0.0
        self._last_target_time = time.monotonic()
        self._last_search_toggle = time.monotonic()
        self._search_direction = 1
        self.safety = SafetyState()
        logger.info("Motion controller initialized")

    # ------------------------------------------------------------------
    # Sensors / safety
    # ------------------------------------------------------------------
    def update_safety(self) -> bool:
        now = time.monotonic()
        if now - self._last_distance_sample > self.cfg.obstacle_check_interval:
            try:
                self.safety.distance_cm = float(self.robot.get_distance())
            except Exception as exc:  # pragma: no cover - hardware
                logger.warning("Ultrasonic read failed: %s", exc)
                self.safety.distance_cm = None
            self._last_distance_sample = now

        if self.cfg.enable_cliff_detection:
            if now - self._last_cliff_sample > self.cfg.cliff_check_interval:
                try:
                    gm_values = self.robot.get_grayscale_data()
                    self.safety.cliff_detected = bool(self.robot.get_cliff_status(gm_values))
                except Exception as exc:  # pragma: no cover - hardware
                    logger.warning("Grayscale read failed: %s", exc)
                    self.safety.cliff_detected = False
                self._last_cliff_sample = now
        else:
            self.safety.cliff_detected = False

        if self.safety.cliff_detected:
            logger.warning("Cliff detected - backing up")
            self.robot.backward(self.cfg.retreat_power)
            time.sleep(0.3)
            self.robot.stop()
            return False

        distance = self.safety.distance_cm
        if distance is not None and distance < self.cfg.retreat_distance_cm:
            logger.warning("Obstacle %.1f cm ahead - backing up", distance)
            self.robot.backward(self.cfg.retreat_power)
            time.sleep(0.2)
            self.robot.stop()
            return False
        return True

    # ------------------------------------------------------------------
    # Target tracking
    # ------------------------------------------------------------------
    def track_target(self, detection: DetectionResult) -> None:
        self._last_target_time = time.monotonic()
        _, frame_width = detection.frame_size
        offset = detection.center[0] - frame_width / 2
        normalized = offset / max(frame_width / 2, 1)
        if abs(offset) <= self.cfg.center_deadband:
            steering = 0.0
        else:
            steering = normalized * self.cfg.turn_scale
        steering = max(min(steering, 30), -30)
        self.robot.set_dir_servo_angle(steering)

        desired_speed = self.cfg.forward_speed
        if detection.approx_distance_cm is not None:
            if detection.approx_distance_cm < self.cfg.stop_distance_cm:
                logger.debug(
                    "Dog %.1f cm away - holding position", detection.approx_distance_cm
                )
                self.robot.stop()
                return
            if detection.approx_distance_cm < self.cfg.safe_distance_cm:
                desired_speed = max(self.cfg.forward_speed // 2, 20)
        distance = self.safety.distance_cm
        if distance is not None and distance < self.cfg.stop_distance_cm:
            logger.debug("Ultrasonic limit reached @ %.1f cm", distance)
            self.robot.stop()
            return
        self.robot.forward(desired_speed)

    def search(self) -> None:
        now = time.monotonic()
        if now - self._last_target_time < self.cfg.lost_target_timeout:
            self.robot.stop()
            return
        if now - self._last_search_toggle > self.cfg.search_interval:
            self._search_direction *= -1
            self._last_search_toggle = now
        pan_angle = self._search_direction * self.cfg.search_pan_amplitude
        try:
            self.robot.set_cam_pan_angle(pan_angle)
        except Exception:  # pragma: no cover - servo optional
            pass
        self.robot.set_dir_servo_angle(pan_angle / 2)
        self.robot.forward(self.cfg.search_speed)

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------
    def wobble(self, angle: int, duration: float) -> None:
        end_time = time.monotonic() + duration
        while time.monotonic() < end_time:
            self.robot.set_dir_servo_angle(angle)
            time.sleep(0.2)
            self.robot.set_dir_servo_angle(-angle)
            time.sleep(0.2)
        self.robot.set_dir_servo_angle(0)

    def pause(self, duration: float) -> None:
        self.robot.stop()
        time.sleep(duration)

    def stop(self) -> None:
        self.robot.stop()
        try:
            self.robot.set_dir_servo_angle(0)
            self.robot.set_cam_pan_angle(0)
            self.robot.set_cam_tilt_angle(0)
        except Exception:  # pragma: no cover - servo optional
            pass


__all__ = ["MotionController", "SafetyState"]
