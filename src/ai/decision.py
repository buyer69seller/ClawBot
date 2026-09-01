from src.game.state import GameState
from src.game.actions import ActionBuilder
from src.strategy.super_hybrid import SuperHybridStrategy
from src.ai.perception import Perception
from src.utils.logger import logger

class DecisionMaker:
    def __init__(self, strategy_mode="super_hybrid"):
        self.strategy = SuperHybridStrategy()
        self.pending_action = None
        self.last_target_id = None
    
    def decide(self, state: GameState, last_action_result: dict = None) -> dict:
        if last_action_result and not last_action_result.get("success"):
            error = last_action_result.get("error", {})
            if error.get("code") == "TARGET_DEAD":
                logger.warning("Target already dead, mencari target lain...")
                return self._retry_target(state)
        
        if not state.alive or state.you_died:
            return None
        if not state.can_act:
            return ActionBuilder.wait()
        
        action = self.strategy.decide(state)
        if action is None:
            action = ActionBuilder.wait()
        if action.get("action") in ("attack", "curse"):
            self.last_target_id = action.get("targetId")
        else:
            self.last_target_id = None
        return action
    
    def _retry_target(self, state: GameState) -> dict:
        enemies = Perception.get_nearby_enemies(state, radius=5)
        if not enemies:
            return ActionBuilder.wait()
        target = min(enemies, key=lambda e: e.get("hp", 999))
        if target.get("id") == self.last_target_id:
            enemies = [e for e in enemies if e.get("id") != self.last_target_id]
            if enemies:
                target = min(enemies, key=lambda e: e.get("hp", 999))
            else:
                return ActionBuilder.wait()
        return ActionBuilder.attack(target["id"])
