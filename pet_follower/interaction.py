"""Sound and behavioral interaction layer."""
from __future__ import annotations

import random
import time
from pathlib import Path
from typing import Optional

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
        self._schedule_next()

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


__all__ = ["InteractionManager"]
