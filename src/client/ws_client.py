import websocket
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
