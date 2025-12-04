"""Sound and behavioral interaction layer."""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Callable, List, Optional

from robot_hat import Music, TTS

from .config import PROJECT_ROOT, config
from .log import logger
from .motion import MotionController

DEFAULT_SOUNDS = [
    PROJECT_ROOT / "picar-x" / "sounds" / "car-double-horn.wav",
    PROJECT_ROOT / "picar-x" / "sounds" / "car-start-engine.wav",
]


class InteractionManager:
    def __init__(self, motion: MotionController) -> None:
        self.motion = motion
        self.cfg = config.interaction
        self.music: Optional[Music] = None
        self.tts: Optional[TTS] = None
        self._next_event = time.monotonic()
        self._celebrations: List[Callable[[], None]] = [
            self._celebration_spin,
            self._celebration_bounce,
        ]
        self._schedule_next()
        # Register celebration handler so motion controller can trigger it
        try:
            self.motion.register_celebration_handler(self._perform_celebration)
        except AttributeError:
            logger.info("Motion controller does not support celebrations yet")

    # ------------------------------------------------------------------
    def tick(self, target_visible: bool) -> None:
        now = time.monotonic()
        if now < self._next_event:
            return
        self._trigger_behavior(target_visible)
        self._schedule_next()

    def _schedule_next(self) -> None:
        interval = random.uniform(*self.cfg.random_interval_range)
        self._next_event = time.monotonic() + interval

    def _trigger_behavior(self, target_visible: bool) -> None:
        behaviors = [self._wobble_behavior, self._pause_behavior]
        if self.cfg.enable_sound:
            behaviors.append(self._sound_behavior)
        if self.cfg.greeting_lines:
            behaviors.append(self._tts_behavior)
        behavior = random.choice(behaviors)
        try:
            behavior(target_visible)
        except Exception as exc:  # pragma: no cover - hardware
            logger.warning("Interaction behavior failed: %s", exc)

    # ------------------------------------------------------------------
    def _ensure_music(self) -> None:
        if self.music is None:
            self.music = Music()
            self.music.music_set_volume(self.cfg.sound_volume)

    def _ensure_tts(self) -> None:
        if self.tts is None:
            self.tts = TTS()
            self.tts.lang(self.cfg.tts_language)

    def _wobble_behavior(self, _: bool) -> None:
        logger.debug("Interaction: wobble head")
        self.motion.wobble(self.cfg.wobble_angle, duration=1.2)

    def _pause_behavior(self, target_visible: bool) -> None:
        if target_visible:
            logger.debug("Interaction: short pause")
            duration = random.uniform(*self.cfg.pause_duration_range)
            self.motion.pause(duration)

    def _sound_behavior(self, _: bool) -> None:
        self._ensure_music()
        sound_pool = [
            Path(p) for p in (self.cfg.sound_files or DEFAULT_SOUNDS) if Path(p).exists()
        ]
        if not sound_pool or self.music is None:
            return
        sound = str(random.choice(sound_pool))
        logger.debug("Interaction: playing %s", sound)
        self.music.sound_play(sound)

    def _tts_behavior(self, _: bool) -> None:
        if random.random() > self.cfg.tts_probability:
            return
        self._ensure_tts()
        if not self.tts:
            return
        line = random.choice(tuple(self.cfg.greeting_lines))
        logger.debug("Interaction: speaking '%s'", line)
        self.tts.say(line)

    # ------------------------------------------------------------------
    # Celebrations triggered when the car approaches the pet
    # ------------------------------------------------------------------
    def _perform_celebration(self) -> None:
        behavior = random.choice(self._celebrations)
        logger.info("Celebration: starting %s", behavior.__name__)
        behavior()

    def _celebration_spin(self) -> None:
        """Oscillate steering and camera pan while staying in place."""
        robot = self.motion.robot
        robot.stop()
        try:
            robot.set_motor_speed(1, 0)
            robot.set_motor_speed(2, 0)
        except Exception:
            pass
        end_time = time.monotonic() + 5.0
        angles = (50, -50)
        idx = 0
        while time.monotonic() < end_time:
            angle = angles[idx]
            try:
                robot.set_dir_servo_angle(angle)
            except Exception:
                pass
            try:
                robot.set_cam_pan_angle(angle)
            except Exception:
                pass
            idx = 1 - idx
            time.sleep(0.4)
        try:
            robot.set_dir_servo_angle(0)
            robot.set_cam_pan_angle(0)
        except Exception:
            pass

    def _celebration_bounce(self) -> None:
        """Alternate short forward/back motions while nodding the camera."""
        robot = self.motion.robot
        duration = 5.0
        end_time = time.monotonic() + duration
        speed = max(self.motion.cfg.forward_speed // 2, 20)
        while time.monotonic() < end_time:
            try:
                robot.set_cam_tilt_angle(15)
            except Exception:
                pass
            robot.forward(speed)
            time.sleep(0.5)
            try:
                robot.set_cam_tilt_angle(-10)
            except Exception:
                pass
            robot.backward(speed)
            time.sleep(0.5)
        robot.stop()
        try:
            robot.set_cam_tilt_angle(0)
        except Exception:
            pass


__all__ = ["InteractionManager"]
