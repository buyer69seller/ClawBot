from typing import Dict, Any, List, Optional

class GameState:
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.self_id = None
        self.self_name = None
        self.in_cave = False
        self.position = None
        self.hp = 0
        self.max_hp = 0
        self.ep = 0
        self.max_ep = 0
        self.atk = 0
        self.defense = 0
        self.explore = 0
        self.item_atk = 0
        self.can_act = False
        self.turn = 0
        self.alive = True
        self.you_died = False
        self.visible_agents = []
        self.visible_monsters = []
        self.visible_items = []
        self.visible_ruins = []
        self.agent_view = None
        self.game_ended = False
        self.game_result = None
        self.last_action_result = None
        self.reason = None
    
    def update_from_agent_view(self, data: Dict[str, Any]):
        self.agent_view = data
        self.reason = data.get("reason")
        view = data.get("view", {})
        self.self_id = data.get("agentId")
        self.can_act = data.get("canAct", False)
        self.turn = data.get("turn", 0)
        self_obj = view.get("self", {})
        self.self_name = self_obj.get("name")
        self.in_cave = self_obj.get("inCave", False)
        self.position = self_obj.get("position")
        self.hp = self_obj.get("hp", 0)
        self.max_hp = self_obj.get("maxHp", 0)
        self.ep = self_obj.get("ep", 0)
        self.max_ep = self_obj.get("maxEp", 0)
        self.atk = self_obj.get("atk", 0)
        self.defense = self_obj.get("def", 0)
        self.explore = self_obj.get("explore", 0)
        self.item_atk = self_obj.get("itemAtk", 0)
        self.visible_agents = view.get("visibleAgents", [])
        self.visible_monsters = view.get("visibleMonsters", [])
        self.visible_items = view.get("visibleItems", [])
        self.visible_ruins = view.get("visibleRuins", [])
    
    def update_from_agent_died(self, data: Dict[str, Any]):
        if data.get("meta", {}).get("youDied") is True:
            self.you_died = True
            self.alive = False
            self.can_act = False
    
    def update_from_game_ended(self, data: Dict[str, Any]):
        self.game_ended = True
        self.game_result = data
        self.can_act = False
        self.alive = False
    
    def update_from_action_result(self, data: Dict[str, Any]):
        self.last_action_result = data
