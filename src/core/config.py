import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    API_KEY = os.getenv("CLAW_API_KEY")
    AUTH_TOKEN = os.getenv("CLAW_AUTH_TOKEN")
    STRATEGY_MODE = os.getenv("STRATEGY_MODE", "super_hybrid")
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    HEALTH_PORT = int(os.getenv("HEALTH_PORT", 8080))
    FREE_ONLY = os.getenv("FREE_ONLY", "true").lower() == "true"  # default true

    BASE_URL = "https://cdn.clawroyale.ai/api"
    WS_JOIN_URL = "wss://cdn.clawroyale.ai/ws/join"
    WS_AGENT_URL = "wss://cdn.clawroyale.ai/ws/agent"

    ETAG_CACHE = {}
    CURRENT_VERSION = None

    @classmethod
    def has_credentials(cls):
        return bool(cls.API_KEY or cls.AUTH_TOKEN)