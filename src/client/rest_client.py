import requests
import json
from typing import Optional, Dict, Any
from src.utils.logger import logger
from src.core.config import Config
from src.core.exceptions import VersionMismatch, AuthError

class RestClient:
    def __init__(self):
        self.base_url = Config.BASE_URL
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

        if Config.AUTH_TOKEN:
            self.session.headers["Authorization"] = f"Bearer {Config.AUTH_TOKEN}"
        elif Config.API_KEY:
            self.session.headers["X-API-Key"] = Config.API_KEY
        else:
            raise AuthError("No credentials provided (API_KEY or AUTH_TOKEN)")

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
            raise AuthError("Authentication failed (403)")
        if resp.status_code == 401:
            raise AuthError("Unauthorized (401) – check API key / token")
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