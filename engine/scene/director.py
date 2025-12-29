from __future__ import annotations
from typing import Callable, Dict, Any

from .script import SceneScript, SceneOp


class SceneDirector:
    """Very early stub of a scene runner.

    In later phases, this will:
      - own the current SceneScript
      - advance step by step
      - call into systems: dialogue UI, battle start, transitions, etc.
    """

    def __init__(self):
        # Handlers dispatch based on op type
        self.handlers: Dict[str, Callable[[SceneOp], None]] = {}

    def register_handler(self, op_type: str, func: Callable[[SceneOp], None]) -> None:
        self.handlers[op_type] = func

    def run(self, script: SceneScript) -> None:
        """Blocking, very simple runner for now (console-based)."""
        for step in script.steps:
            handler = self.handlers.get(step.op)
            if handler:
                handler(step)
            else:
                print(f"[SceneDirector] No handler for op '{step.op}', skipping.")
