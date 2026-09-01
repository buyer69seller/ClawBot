import asyncio
import json
import logging
from typing import Optional

import websockets
from websockets.exceptions import ConnectionClosed

from src.client.rest_client import RestClient
from src.game.state import GameState
from src.ai.decision import DecisionMaker
from src.lifecycle.router import StateRouter
from src.lifecycle.version_manager import VersionManager
from src.core.exceptions import AgentDead, ResumeTargetDead
from src.core.config import Config
from src.utils.logger import logger

class GameDriver:
    def __init__(self):
        self.rest = RestClient()
        self.router = StateRouter(self.rest)
        self.version_mgr = VersionManager(self.rest)
        self.state = GameState()
        self.decision_maker = DecisionMaker()
        self.game_type = "free"
        self.running = True
        self.last_action_result = None
        self.current_game_id = None
        self.ws = None
        self._last_action_time = 0
        self._min_action_interval = 1.0  # 1 detik antar aksi

    def run(self):
        asyncio.run(self._async_run())

    async def _async_run(self):
        logger.info("🚀 Claw Royale Bot starting (FREE ONLY)")

        if not Config.has_credentials():
            logger.error("❌ No credentials found. Set CLAW_API_KEY or CLAW_AUTH_TOKEN in .env")
            return

        try:
            self.version_mgr.ensure_version()
        except Exception as e:
            logger.error(f"Failed to get API version: {e}")
            return

        while self.running:
            try:
                state_name, err = self.router.determine_state()
                logger.info(f"📊 Current state: {state_name}")

                if state_name == "IN_GAME_FREE":
                    logger.info("🔄 Found live free game, resuming...")
                    await self._play_game(resume=True)
                elif state_name in ("READY_FREE", "IDLE"):
                    logger.info("🎮 No live game, starting new free game...")
                    await self._play_game(resume=False)
                elif state_name == "ERROR":
                    logger.error(f"Error state: {err}")
                    if "401" in str(err) or "Unauthorized" in str(err):
                        logger.error("🔑 Auth error – stopping.")
                        break
                    await asyncio.sleep(10)
                else:
                    logger.warning(f"Unknown state: {state_name}, waiting...")
                    await asyncio.sleep(5)

            except AgentDead:
                logger.info("💀 Agent died – restarting game loop")
                self._cleanup()
                await asyncio.sleep(2)
                continue

            except ResumeTargetDead:
                logger.info("🔄 Resume target dead – starting new game")
                self._cleanup()
                await asyncio.sleep(2)
                continue

            except Exception as e:
                logger.exception(f"💥 Unhandled error: {e}")
                self._cleanup()
                await asyncio.sleep(5)

    async def _play_game(self, resume: bool):
        """Main game loop – connect, join, play until death/game ended."""
        self.state.reset()
        self.last_action_result = None
        self._last_action_time = 0

        headers = {
            "X-API-Key": Config.API_KEY,
            "X-Version": Config.CURRENT_VERSION or "1.0.0"
        }
        if Config.AUTH_TOKEN:
            headers["Authorization"] = f"Bearer {Config.AUTH_TOKEN}"

        try:
            logger.info(f"🔗 Connecting to {Config.WS_JOIN_URL}...")
            self.ws = await websockets.connect(
                Config.WS_JOIN_URL,
                additional_headers=headers,
                ping_interval=20,
                ping_timeout=20,
                close_timeout=5,
                max_size=2**20
            )
            logger.info("✅ WebSocket connected!")

            # Baca welcome
            welcome_raw = await self.ws.recv()
            welcome = json.loads(welcome_raw)
            decision = welcome.get("decision")
            logger.info(f"📨 Welcome decision: {decision}")

            # Kirim hello
            hello = {"type": "hello", "entryType": "free"}
            await self.ws.send(json.dumps(hello))
            logger.info("📤 Sent hello (free)")

            # ===== LOOP UTAMA =====
            while self.running:
                try:
                    raw = await self.ws.recv()  # blocking, no timeout
                    msg = json.loads(raw)
                    await self._handle_frame(msg)

                    if self.state.game_ended or self.state.you_died:
                        break

                except ConnectionClosed as e:
                    logger.warning(f"🔌 Connection closed: {e.code} - {e.reason}")
                    if e.code == 1013 and "RESUME_TARGET_DEAD" in str(e.reason):
                        raise ResumeTargetDead("Resume target dead")
                    if e.code == 1000:
                        logger.info("Game ended normally (close 1000)")
                        self.state.game_ended = True
                        break
                    if e.code == 4008:
                        # Rate limit – backoff
                        logger.warning("⏳ Rate limit (4008), waiting 10s before reconnect...")
                        await asyncio.sleep(10)
                        raise  # re-raise to restart game loop
                    # Untuk kode lain, kita coba reconnect di loop utama
                    raise

            logger.info("🔚 Game loop ended")

        except Exception as e:
            logger.error(f"❌ Game error: {e}")
            raise
        finally:
            self._cleanup()

    async def _handle_frame(self, msg: dict):
        """Handle semua frame dari server."""
        msg_type = msg.get("type")
        logger.debug(f"📨 Frame: {msg_type}")

        if msg_type == "assigned":
            self.current_game_id = msg.get("gameId")
            logger.info(f"✅ Assigned to game {self.current_game_id}")

        elif msg_type == "agent_view":
            self.state.update_from_agent_view(msg)
            if self.state.reason == "action_rejected":
                logger.warning("⚠️ Action rejected, will retry")
            if self.state.can_act and self.state.alive:
                await self._act()

        elif msg_type == "turn_advanced":
            self.state.turn = msg.get("turn", self.state.turn)

        elif msg_type == "agent_died":
            self.state.update_from_agent_died(msg)
            if self.state.you_died:
                logger.info("💀 YOU DIED! (meta.youDied=true)")
                raise AgentDead("Agent died")

        elif msg_type == "game_ended":
            self.state.update_from_game_ended(msg)
            placement = msg.get("placement")
            logger.info(f"🏆 Game ended! Placement: {placement}")

        elif msg_type == "action_result":
            self.state.update_from_action_result(msg)
            self.last_action_result = msg
            if not msg.get("success"):
                error = msg.get("error", {})
                code = error.get("code")
                if code == "AGENT_DEAD":
                    logger.error("💀 AGENT_DEAD from action_result")
                    self.state.alive = False
                    self.state.you_died = True
                    raise AgentDead("Agent dead from action_result")
                elif code == "TARGET_DEAD":
                    logger.warning("🎯 Target dead, retrying...")
                elif code == "ACTION_FAILED":
                    logger.warning(f"❌ Action failed: {error.get('message')}")
                elif code == "RATE_LIMITED":
                    logger.warning("⏳ Rate limited by server, waiting...")
                    await asyncio.sleep(5)
            else:
                logger.info("✅ Action succeeded")

        elif msg_type == "queued":
            logger.info("⏳ Queued, waiting for match...")

        elif msg_type == "waiting":
            logger.info("⏳ Waiting for game...")

        elif msg_type == "error":
            error = msg.get("error", {})
            code = error.get("code")
            message = error.get("message", "")
            logger.error(f"❌ Server error: {code} - {message}")
            if code == "BLOCKED":
                logger.warning("⛔ Blocked – check readiness")

        elif msg_type == "log":
            pass

        else:
            logger.debug(f"📨 Unhandled frame type: {msg_type}")

    async def _act(self):
        """Ambil keputusan dan kirim action dengan rate limit."""
        if not self.state.can_act or not self.state.alive:
            return

        # Rate limit – minimal 1 detik antar aksi
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_action_time
        if elapsed < self._min_action_interval:
            wait = self._min_action_interval - elapsed
            logger.debug(f"⏳ Rate limit: waiting {wait:.2f}s")
            await asyncio.sleep(wait)

        action = self.decision_maker.decide(self.state, self.last_action_result)
        if action:
            logger.info(f"📤 Sending action: {action}")
            await self.ws.send(json.dumps(action))
            self._last_action_time = asyncio.get_event_loop().time()
            self.last_action_result = None
        else:
            logger.warning("⚠️ No action decided, waiting...")

    def _cleanup(self):
        if self.ws:
            try:
                asyncio.create_task(self.ws.close())
            except:
                pass
            self.ws = None
        self.state.reset()
        self.current_game_id = None
        self.last_action_result = None