from src.client.rest_client import RestClient
from src.utils.logger import logger
from src.core.config import Config

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

            # Hanya perhatikan free
            free_live = any(
                g.get("entryType") == "free"
                and g.get("isAlive")
                and g.get("gameStatus") != "finished"
                for g in current_games
            )

            if free_live:
                return "IN_GAME_FREE", None

            # Cek readiness free
            if readiness.get("freeReady"):
                return "READY_FREE", None

            # Jika free tidak tersedia, idle
            return "IDLE", None

        except Exception as e:
            logger.error(f"Router error: {e}")
            return "ERROR", str(e)