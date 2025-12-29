# jrpg_scenes.py

from __future__ import annotations
from typing import Iterable, Tuple

# Simple scene helper.
# Usage:
#   play_scene([
#       ("Setia", "This place... it hasn't changed."),
#       ("Nyra", "The air remembers."),
#   ])

def play_scene(lines: Iterable[Tuple[str, str]]) -> None:
    for speaker, text in lines:
        if speaker:
            print(f"{speaker}: {text}")
        else:
            print(text)
        input("(press Enter)\n")
