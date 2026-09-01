import time
from src.client.rest_client import RestClient
from src.core.config import Config
from src.utils.logger import logger
from src.core.exceptions import VersionMismatch

class VersionManager:
    def __init__(self, rest: RestClient):
        self.rest = rest
        self.current_version = None

    def ensure_version(self, force=False, retries=3):
        if force or self.current_version is None:
            attempt = 0
            while attempt < retries:
                try:
                    resp = self.rest.get("/version")
                    self.current_version = resp.get("version")
                    Config.CURRENT_VERSION = self.current_version
                    logger.info(f"API version: {self.current_version}")
                    return self.current_version
                except Exception as e:
                    attempt += 1
                    logger.warning(f"Version fetch attempt {attempt}/{retries} failed: {e}")
                    if attempt >= retries:
                        logger.error("All retries failed. Check your network or domain.")
                        raise
                    # Backoff: 2, 4, 6 detik
                    wait = attempt * 2
                    logger.info(f"Retrying in {wait}s...")
                    time.sleep(wait)
                    # Jika gagal karena DNS, coba domain alternatif (moltyroyale.com)
                    if attempt == 2:  # percobaan kedua gagal, coba domain lain
                        alt_url = "https://cdn.moltyroyale.com/api"
                        if Config.BASE_URL != alt_url:
                            logger.info(f"Switching to alt domain: {alt_url}")
                            Config.BASE_URL = alt_url
                            self.rest.base_url = alt_url
                            # update session header? tidak perlu karena rest_client pakai self.base_url
        return self.current_version