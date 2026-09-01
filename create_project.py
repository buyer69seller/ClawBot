import os
import shutil

# ---------- DEFINISI KONTEN FILE ----------

files = {
    # root files
    "requirements.txt": """requests
websocket-client
python-dotenv
pyjwt
cryptography
""",
    "Dockerfile": """FROM python:3.10-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD ["python", "-m", "src.main"]
""",
    "railway.json": """{
  "build": {
    "builder": "DOCKERFILE"
  },
  "deploy": {
    "startCommand": "python -m src.main",
    "healthcheckPath": "/health",
    "healthcheckTimeout": 100
  }
}
""",
    ".dockerignore": "__pycache__\n*.pyc\n.env\ntests/\n",
    ".gitignore": "__pycache__\n*.pyc\n.env\n*.log\n",
    "LICENSE": "MIT License ... (silakan isi)",
    "README.md": """# Claw Royale Bot

Bot otomatis untuk Claw Royale berdasarkan `skill.md`. Menggunakan strategi hybrid 4 mode.

## Setup
- Buat file `.env` dari `config/.env.example`, isi `CLAW_API_KEY`.
- Jalankan `pip install -r requirements.txt`
- Jalankan `python -m src.main`

## Struktur
- `src/lifecycle/`: state router dan driver utama
- `src/strategy/`: logika keputusan
- `src/ai/`: persepsi dan analisis
- `src/client/`: REST dan WebSocket
- `src/game/`: state dan action

## Catatan
- Mendukung deteksi kematian via `meta.youDied`
- Handle resume target dead (1013)
- Menggunakan ETag cache untuk REST
""",

    # config
    "config/.env.example": """CLAW_API_KEY=your_api_key_here
CLAW_AUTH_TOKEN=your_jwt_or_apikey
STRATEGY_MODE=super_hybrid
LOG_LEVEL=INFO
HEALTH_PORT=8080
""",

    # src/__init__.py
    "src/__init__.py": "",
    "src/main.py": """from src.lifecycle.driver import GameDriver

def main():
    driver = GameDriver()
    driver.run()

if __name__ == "__main__":
    main()
""",

    # src/core/__init__.py
    "src/core/__init__.py": "# Export STRATEGY_MODE",
    "src/core/config.py": """import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_KEY = os.getenv("CLAW_API_KEY")
    AUTH_TOKEN = os.getenv("CLAW_AUTH_TOKEN")
    STRATEGY_MODE = os.getenv("STRATEGY_MODE", "super_hybrid")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    HEALTH_PORT = int(os.getenv("HEALTH_PORT", 8080))
    
    BASE_URL = "https://cdn.clawroyale.ai/api"
    WS_JOIN_URL = "wss://cdn.clawroyale.ai/ws/join"
    WS_AGENT_URL = "wss://cdn.clawroyale.ai/ws/agent"
    
    ETAG_CACHE = {}
    CURRENT_VERSION = None
""",
    "src/core/constants.py": "# Pack/Relic data (placeholder)",
    "src/core/exceptions.py": """class ClawError(Exception):
    pass

class AuthError(ClawError):
    pass

class VersionMismatch(ClawError):
    pass

class GameEnded(ClawError):
    pass

class AgentDead(ClawError):
    pass

class ResumeTargetDead(ClawError):
    pass
""",

    # src/client/
    "src/client/__init__.py": "",
    "src/client/rest_client.py": """import requests
import json
from typing import Optional, Dict, Any
from src.utils.logger import logger
from src.core.config import Config
from src.core.exceptions import VersionMismatch, AuthError

class RestClient:
    def __init__(self):
        self.base_url = Config.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({
            "X-API-Key": Config.API_KEY,
            "Accept": "application/json"
        })
        self._version = None
        self._etag_cache = Config.ETAG_CACHE
    
    def _ensure_version(self):
        if self._version is None:
            resp = self.session.get(f"{self.base_url}/version")
            resp.raise_for_status()
            self._version = resp.json().get("version")
            self.session.headers["X-Version"] = self._version
        return self._version
    
    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path}"
        self._ensure_version()
        
        if method.lower() == "get" and path in self._etag_cache:
            etag = self._etag_cache[path].get("etag")
            if etag:
                kwargs.setdefault("headers", {})["If-None-Match"] = etag
        
        resp = self.session.request(method, url, **kwargs)
        
        if resp.status_code == 304:
            return self._etag_cache[path]["data"]
        if resp.status_code == 426:
            raise VersionMismatch("API version outdated")
        if resp.status_code == 403:
            raise AuthError("Authentication failed")
        resp.raise_for_status()
        data = resp.json()
        
        if method.lower() == "get" and "etag" in resp.headers:
            self._etag_cache[path] = {
                "etag": resp.headers["etag"],
                "data": data
            }
        return data
    
    def get(self, path: str, params=None) -> Dict:
        return self._request("GET", path, params=params)
    def post(self, path: str, json_data=None) -> Dict:
        return self._request("POST", path, json=json_data)
    def put(self, path: str, json_data=None) -> Dict:
        return self._request("PUT", path, json=json_data)
    def delete(self, path: str) -> Dict:
        return self._request("DELETE", path)
""",
    "src/client/ws_client.py": """import websocket
import json
import threading
import time
from typing import Callable, Optional, Dict, Any
from src.utils.logger import logger
from src.core.config import Config
from src.core.exceptions import AuthError, VersionMismatch, ResumeTargetDead

class WSClient:
    def __init__(self, on_message: Callable, on_close: Callable):
        self.on_message_cb = on_message
        self.on_close_cb = on_close
        self.ws = None
        self.thread = None
        self.running = False
    
    def connect(self, url: str, headers: dict = None):
        if not headers:
            headers = {}
        headers["X-API-Key"] = Config.API_KEY
        headers["X-Version"] = Config.CURRENT_VERSION or "1.0.0"
        
        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error
        )
        self.running = True
        self.thread = threading.Thread(target=self.ws.run_forever, daemon=True)
        self.thread.start()
    
    def _on_open(self, ws):
        logger.info("WebSocket connected")
    
    def _on_message(self, ws, message):
        try:
            data = json.loads(message)
            self.on_message_cb(data)
        except Exception as e:
            logger.error(f"Error parsing WS message: {e}")
    
    def _on_error(self, ws, error):
        logger.error(f"WebSocket error: {error}")
        if "426" in str(error):
            raise VersionMismatch("Version mismatch on WS")
        if "403" in str(error):
            raise AuthError("Auth failed on WS")
    
    def _on_close(self, ws, close_status_code, close_msg):
        logger.warning(f"WebSocket closed: {close_status_code} - {close_msg}")
        self.running = False
        if close_status_code == 1013 and "RESUME_TARGET_DEAD" in (close_msg or ""):
            raise ResumeTargetDead("Resume target dead, re-dial")
        self.on_close_cb(close_status_code, close_msg)
    
    def send(self, data: dict):
        if self.ws and self.running:
            self.ws.send(json.dumps(data))
        else:
            logger.error("Cannot send, WS not connected")
    
    def close(self):
        self.running = False
        if self.ws:
            self.ws.close()
        if self.thread:
            self.thread.join(timeout=2)
""",

    # src/game/
    "src/game/__init__.py": "",
    "src/game/state.py": """from typing import Dict, Any, List, Optional

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
""",
    "src/game/actions.py": """from typing import Dict, Any

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
""",

    # src/strategy/
    "src/strategy/__init__.py": "# Export all strategies",
    "src/strategy/engine.py": "# Heuristic (fallback)",
    "src/strategy/evaluators.py": "# Score evaluators",
    "src/strategy/scan_clear.py": "# Scan & Clear",
    "src/strategy/hybrid_strategy.py": "# Hybrid v7 (3 Mode)",
    "src/strategy/super_hybrid.py": """from src.game.state import GameState
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
""",

    # src/ai/
    "src/ai/__init__.py": "",
    "src/ai/perception.py": """from src.game.state import GameState
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
""",
    "src/ai/analyzer.py": "# Game analysis",
    "src/ai/decision.py": """from src.game.state import GameState
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
""",
    "src/ai/risk.py": "# Risk assessment",
    "src/ai/knowledge.py": "# Knowledge base",
    "src/ai/hybrid_engine.py": "# Hybrid AI + RL",
    "src/ai/rl_agent.py": "# Q-Learning",

    # src/lifecycle/
    "src/lifecycle/__init__.py": "",
    "src/lifecycle/driver.py": """import time
from src.client.rest_client import RestClient
from src.client.ws_client import WSClient
from src.game.state import GameState
from src.ai.decision import DecisionMaker
from src.lifecycle.router import StateRouter
from src.lifecycle.version_manager import VersionManager
from src.utils.logger import logger
from src.core.exceptions import AgentDead, ResumeTargetDead, VersionMismatch
from src.game.actions import ActionBuilder
from src.core.config import Config

class GameDriver:
    def __init__(self):
        self.rest = RestClient()
        self.router = StateRouter(self.rest)
        self.version_mgr = VersionManager(self.rest)
        self.state = GameState()
        self.decision_maker = DecisionMaker()
        self.ws = None
        self.game_type = None
        self.running = True
        self.last_action_result = None
    
    def run(self):
        logger.info("Claw Royale Bot starting...")
        self.version_mgr.ensure_version()
        while self.running:
            try:
                state_name, err = self.router.determine_state()
                logger.info(f"Current state: {state_name}")
                if state_name == "NO_ACCOUNT":
                    logger.error("No account, please set up credentials")
                    break
                elif state_name in ("IN_GAME_FREE", "IN_GAME_PAID"):
                    self.game_type = "free" if state_name == "IN_GAME_FREE" else "paid"
                    self._play_game()
                elif state_name in ("READY_FREE", "READY_PAID"):
                    self.game_type = "free" if state_name == "READY_FREE" else "paid"
                    self._play_game()
                elif state_name == "IDLE":
                    logger.info("Idle, waiting...")
                    time.sleep(5)
                elif state_name == "ERROR":
                    logger.error(f"Error state: {err}")
                    time.sleep(10)
            except VersionMismatch:
                logger.info("Version mismatch, fetching new skill...")
                self.version_mgr.ensure_version(force=True)
            except AgentDead:
                logger.info("Agent died, exiting game loop and reconnecting...")
                self._cleanup_game()
                continue
            except ResumeTargetDead:
                logger.info("Resume target dead, re-dial once")
                self._cleanup_game()
                continue
            except Exception as e:
                logger.error(f"Unhandled exception: {e}", exc_info=True)
                self._cleanup_game()
                time.sleep(5)
    
    def _play_game(self):
        logger.info(f"Playing {self.game_type} game")
        self._connect_and_hello()
        while self.running and not self.state.you_died and not self.state.game_ended:
            time.sleep(0.05)
            self._process_turn()
        if self.state.you_died:
            raise AgentDead("Agent died")
        elif self.state.game_ended:
            logger.info("Game ended normally")
            self._cleanup_game()
        else:
            self._cleanup_game()
    
    def _connect_and_hello(self):
        self.ws = WSClient(on_message=self._on_ws_message, on_close=self._on_ws_close)
        self.ws.connect(Config.WS_JOIN_URL, headers={"X-Version": Config.CURRENT_VERSION})
        self.ws.send({"type": "hello", "entryType": self.game_type})
        timeout = 30
        while timeout > 0 and not self.state.agent_view and not self.state.game_ended:
            time.sleep(0.1)
            timeout -= 0.1
        if timeout <= 0:
            logger.error("Timeout waiting for game start")
            raise Exception("Game start timeout")
    
    def _process_turn(self):
        if self.state.can_act and self.state.alive:
            action = self.decision_maker.decide(self.state, self.last_action_result)
            if action:
                logger.info(f"Sending action: {action}")
                self.ws.send(action)
                self.last_action_result = None
    
    def _on_ws_message(self, data):
        frame_type = data.get("type")
        logger.debug(f"WS received: {frame_type}")
        if frame_type == "welcome":
            logger.info(f"Welcome: {data}")
        elif frame_type == "assigned":
            logger.info(f"Assigned to game: {data}")
        elif frame_type == "agent_view":
            self.state.update_from_agent_view(data)
            if self.state.reason == "action_rejected":
                logger.warning("Action rejected, will retry on next turn")
        elif frame_type == "turn_advanced":
            self.state.turn = data.get("turn", self.state.turn)
        elif frame_type == "agent_died":
            self.state.update_from_agent_died(data)
            if self.state.you_died:
                logger.info("We died! (youDied=true)")
        elif frame_type == "game_ended":
            self.state.update_from_game_ended(data)
            logger.info(f"Game ended: {data}")
        elif frame_type == "action_result":
            self.state.update_from_action_result(data)
            self.last_action_result = data
            if not data.get("success"):
                error = data.get("error", {})
                if error.get("code") == "TARGET_DEAD":
                    logger.warning("Target dead, retry in same turn?")
                elif error.get("code") == "AGENT_DEAD":
                    logger.error("AGENT_DEAD from action_result")
                    self.state.alive = False
                    self.state.you_died = True
        elif frame_type == "log":
            pass
        else:
            logger.warning(f"Unknown frame type: {frame_type}")
    
    def _on_ws_close(self, close_code, close_msg):
        logger.info(f"WS closed: {close_code} - {close_msg}")
        if close_code == 1013 and "RESUME_TARGET_DEAD" in (close_msg or ""):
            raise ResumeTargetDead("Resume target dead")
        if close_code == 1000:
            self.state.game_ended = True
    
    def _cleanup_game(self):
        if self.ws:
            self.ws.close()
            self.ws = None
        self.state.reset()
        self.game_type = None
        self.last_action_result = None
""",
    "src/lifecycle/router.py": """from src.client.rest_client import RestClient
from src.utils.logger import logger

class StateRouter:
    def __init__(self, rest_client: RestClient):
        self.rest = rest_client
    
    def determine_state(self):
        try:
            me = self.rest.get("/accounts/me")
            if "error" in me:
                return "ERROR", me.get("error")
            data = me.get("data", {})
            current_games = data.get("currentGames", [])
            readiness = data.get("readiness", {})
            free_live = any(g.get("entryType")=="free" and g.get("isAlive") and g.get("gameStatus")!="finished" for g in current_games)
            paid_live = any(g.get("entryType")=="paid" and g.get("isAlive") and g.get("gameStatus")!="finished" for g in current_games)
            if free_live: return "IN_GAME_FREE", None
            if paid_live: return "IN_GAME_PAID", None
            if readiness.get("freeReady"): return "READY_FREE", None
            if readiness.get("paidReady"): return "READY_PAID", None
            return "IDLE", None
        except Exception as e:
            logger.error(f"Router error: {e}")
            return "ERROR", str(e)
""",
    "src/lifecycle/version_manager.py": """from src.client.rest_client import RestClient
from src.core.config import Config
from src.utils.logger import logger

class VersionManager:
    def __init__(self, rest: RestClient):
        self.rest = rest
        self.current_version = None
    
    def ensure_version(self, force=False):
        if force or self.current_version is None:
            try:
                resp = self.rest.get("/version")
                self.current_version = resp.get("version")
                Config.CURRENT_VERSION = self.current_version
                logger.info(f"API version: {self.current_version}")
            except Exception as e:
                logger.error(f"Failed to fetch version: {e}")
                raise
        return self.current_version
""",

    # src/services/
    "src/services/__init__.py": "",
    "src/services/auth_service.py": "# Authentication",
    "src/services/reward_service.py": "# Rewards",
    "src/services/loadout_service.py": "# Loadout optimization",
    "src/services/inventory_service.py": "# Inventory management",
    "src/services/marketplace_service.py": "# Marketplace",

    # src/utils/
    "src/utils/__init__.py": "",
    "src/utils/logger.py": """import logging
from src.core.config import Config

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("claw-bot")
""",
    "src/utils/health.py": """from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import threading
from src.core.config import Config

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"status": "ok"}).encode())
        else:
            self.send_response(404)

def start_health_server():
    port = Config.HEALTH_PORT
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
""",

    # tests/
    "tests/__init__.py": "",
    "tests/test_strategy.py": "",
    "tests/test_ai.py": "",
}

# ---------- BUAT FOLDER DAN FILE ----------
def create_project():
    base = os.getcwd()
    for rel_path, content in files.items():
        full_path = os.path.join(base, rel_path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created {rel_path}")
    print("\n✅ All files created. You can now run:")
    print("    python -m src.main")
    print("(Don't forget to set your API key in config/.env)")

if __name__ == "__main__":
    create_project()