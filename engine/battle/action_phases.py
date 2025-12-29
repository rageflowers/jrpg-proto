# engine/battle/action_phases.py  (or inside battle_runtime.py)

class ActionPhase:
    WAIT_CTB = "wait_ctb"
    PREPARE_ACTOR = "prepare_actor"
    PLAYER_COMMAND = "player_command"
    ENEMY_COMMAND = "enemy_command"
    RESOLVE_ACTION = "resolve_action"
    POST_RESOLVE = "post_resolve"
    BATTLE_END = "battle_end"
