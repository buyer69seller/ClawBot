from typing import Dict, Any

class ActionBuilder:
    @staticmethod
    def move(direction: str) -> Dict[str, Any]:
        return {"action": "move", "direction": direction}
    @staticmethod
    def attack(target_id: str) -> Dict[str, Any]:
        return {"action": "attack", "targetId": target_id}
    @staticmethod
    def interact(interactable_id: str) -> Dict[str, Any]:
        return {"action": "interact", "interactableId": interactable_id}
    @staticmethod
    def explore(ruin_id: str) -> Dict[str, Any]:
        return {"action": "explore", "ruinId": ruin_id}
    @staticmethod
    def curse(target_id: str) -> Dict[str, Any]:
        return {"action": "curse", "targetId": target_id}
    @staticmethod
    def use_item(item_id: str) -> Dict[str, Any]:
        return {"action": "useItem", "itemId": item_id}
    @staticmethod
    def wait() -> Dict[str, Any]:
        return {"action": "wait"}
