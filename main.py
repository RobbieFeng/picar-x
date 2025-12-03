"""Launcher script to run either the dog viewer or the pet follower."""
from __future__ import annotations

import pet_follower


def _run_dog_viewer() -> None:
    from pet_follower import dog_viewer

    dog_viewer.main()


def _run_pet_follower() -> None:
    from pet_follower import pet_follower

    pet_follower.main()

def _run_test() -> None:
    from pet_follower.motion import MotionController
    motion = MotionController()
    motion.turn90(1)

def _prompt_for_mode() -> str:
    prompt = (
        "\nSelect a mode:\n"
        "  1) Dog viewer (visualize detections only)\n"
        "  2) Pet follower (full tracking behavior)\n"
        "  3) Test\n"
        "Enter choice [1/2]: "
    )
    choice = input(prompt).strip()
    
    return "viewer" if choice == "1" else "follower" if choice == "2" else "test"

def main() -> None:
    mode = _prompt_for_mode()
    if mode == "viewer":
        _run_dog_viewer()
    elif mode == "follower":
        _run_pet_follower()
    elif mode == "test":
        _run_test()


if __name__ == "__main__":
    main()


