from src.game.state import GameState
from typing import List, Dict

class Perception:
    @staticmethod
    def get_nearby_enemies(state: GameState, radius: int = 5) -> List[Dict]:
        if not state.position: return []
        my = state.position
        enemies = []
        for agent in state.visible_agents:
            if agent.get("id") == state.self_id: continue
            dist = abs(agent["position"]["x"] - my["x"]) + abs(agent["position"]["y"] - my["y"])
            if dist <= radius: enemies.append(agent)
        for monster in state.visible_monsters:
            dist = abs(monster["position"]["x"] - my["x"]) + abs(monster["position"]["y"] - my["y"])
            if dist <= radius: enemies.append(monster)
        return enemies
    
    @staticmethod
    def get_nearby_items(state: GameState, radius: int = 3) -> List[Dict]:
        if not state.position: return []
        my = state.position
        items = []
        for item in state.visible_items:
            dist = abs(item["position"]["x"] - my["x"]) + abs(item["position"]["y"] - my["y"])
            if dist <= radius: items.append(item)
        return items
    
    @staticmethod
    def get_nearby_ruins(state: GameState, radius: int = 5) -> List[Dict]:
        if not state.position: return []
        my = state.position
        ruins = []
        for ruin in state.visible_ruins:
            dist = abs(ruin["position"]["x"] - my["x"]) + abs(ruin["position"]["y"] - my["y"])
            if dist <= radius: ruins.append(ruin)
        return ruins
