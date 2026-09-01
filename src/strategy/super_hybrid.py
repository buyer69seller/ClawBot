from src.game.state import GameState
from src.game.actions import ActionBuilder
from src.ai.perception import Perception
import random

class SuperHybridStrategy:
    def __init__(self):
        self.mode = 0
    
    def decide(self, state: GameState) -> dict:
        self._select_mode(state)
        if self.mode == 0:
            return self._safe_mode(state)
        elif self.mode == 1:
            return self._aggressive_mode(state)
        elif self.mode == 2:
            return self._explorer_mode(state)
        else:
            return self._survival_mode(state)
    
    def _select_mode(self, state: GameState):
        if state.hp < state.max_hp * 0.3:
            self.mode = 3
        elif len(Perception.get_nearby_enemies(state, 3)) > 0:
            self.mode = 1 if state.hp > state.max_hp * 0.6 else 3
        elif len(Perception.get_nearby_ruins(state, 4)) > 0:
            self.mode = 2 if state.explore > 2 else 0
        else:
            self.mode = 0
    
    def _safe_mode(self, state: GameState) -> dict:
        items = Perception.get_nearby_items(state, 2)
        if items:
            return ActionBuilder.interact(items[0]["id"])
        return self._move_random_safe(state)
    
    def _aggressive_mode(self, state: GameState) -> dict:
        enemies = Perception.get_nearby_enemies(state, 2)
        if enemies:
            target = min(enemies, key=lambda e: e.get("hp", 999))
            return ActionBuilder.attack(target["id"])
        enemies = Perception.get_nearby_enemies(state, 5)
        if enemies:
            target = min(enemies, key=lambda e: e.get("hp", 999))
            return self._move_towards(state, target["position"])
        return ActionBuilder.wait()
    
    def _explorer_mode(self, state: GameState) -> dict:
        ruins = Perception.get_nearby_ruins(state, 3)
        if ruins:
            ruin = ruins[0]
            if ruin.get("progress", 0) < 3:
                return ActionBuilder.explore(ruin["id"])
            else:
                return self._move_towards(state, ruin["position"])
        return ActionBuilder.wait()
    
    def _survival_mode(self, state: GameState) -> dict:
        items = Perception.get_nearby_items(state, 2)
        for item in items:
            if "heal" in item.get("effect", "").lower():
                return ActionBuilder.interact(item["id"])
        enemies = Perception.get_nearby_enemies(state, 3)
        if enemies:
            return self._move_away(state, enemies[0]["position"])
        return self._move_random_safe(state)
    
    def _move_random_safe(self, state: GameState) -> dict:
        return ActionBuilder.move(random.choice(["up","down","left","right"]))
    
    def _move_towards(self, state: GameState, target_pos: dict) -> dict:
        my = state.position
        if not my: return ActionBuilder.wait()
        dx = target_pos["x"] - my["x"]
        dy = target_pos["y"] - my["y"]
        if abs(dx) > abs(dy):
            return ActionBuilder.move("right" if dx > 0 else "left")
        else:
            return ActionBuilder.move("down" if dy > 0 else "up")
    
    def _move_away(self, state: GameState, threat_pos: dict) -> dict:
        my = state.position
        if not my: return ActionBuilder.wait()
        dx = threat_pos["x"] - my["x"]
        dy = threat_pos["y"] - my["y"]
        if abs(dx) > abs(dy):
            return ActionBuilder.move("left" if dx > 0 else "right")
        else:
            return ActionBuilder.move("up" if dy > 0 else "down")
