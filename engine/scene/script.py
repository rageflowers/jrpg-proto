from __future__ import annotations
from dataclasses import dataclass
from typing import Literal, Dict, Any, List


SceneOpType = Literal[
    "dialogue",
    "battle",
    "set_background",
    "fade_in",
    "fade_out",
    "wait",
]


@dataclass
class SceneOp:
    """One step in a scene script.

    Examples:
      SceneOp("dialogue", {"speaker": "Setia", "text": "This place..."})
      SceneOp("battle", {"encounter_id": "tutorial"})
    """

    op: SceneOpType
    params: Dict[str, Any]


@dataclass
class SceneScript:
    """An ordered list of SceneOps."""

    id: str
    steps: List[SceneOp]
