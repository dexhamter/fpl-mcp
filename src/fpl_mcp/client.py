"""FPL HTTP client with in-memory TTL caching and optional auth."""

import logging
import os
from typing import Any, Optional

import aiohttp

from .auth import FPLAuth
from .cache import TTLCache
from .constants import ENDPOINTS, TTL

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
}


class FPLClient:
    """Async FPL API client with caching and optional session auth."""

    def __init__(self, auth: Optional[FPLAuth] = None) -> None:
        self.auth = auth
        self.cache = TTLCache()
        self._session: Optional[aiohttp.ClientSession] = None
        self._team_id: Optional[int] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        """Open the HTTP session and authenticate if credentials are set."""
        self._session = aiohttp.ClientSession(headers=DEFAULT_HEADERS)
        if self.auth:
            await self.auth.ensure_session(self._session)
            self.auth.apply_cookies(self._session)

        # Resolve team ID from env or FPL /me endpoint
        env_id = os.environ.get("FPL_TEAM_ID")
        if env_id:
            self._team_id = int(env_id)
        elif self.auth:
            try:
                me = await self._get_raw(ENDPOINTS["me"])
                self._team_id = me.get("player", {}).get("entry")
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not resolve team ID from /me: %s", exc)

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session:
            await self._session.close()
            self._session = None

    # ------------------------------------------------------------------
    # Public data fetchers
    # ------------------------------------------------------------------

    async def get_bootstrap(self) -> dict:
        return await self._cached("bootstrap", ENDPOINTS["bootstrap"], TTL["bootstrap"])

    async def get_fixtures(self, gw: Optional[int] = None) -> list:
        if gw:
            url = ENDPOINTS["fixtures_gw"].format(gw=gw)
            key = f"fixtures_gw_{gw}"
        else:
            url = ENDPOINTS["fixtures"]
            key = "fixtures_all"
        return await self._cached(key, url, TTL["fixtures"])

    async def get_element_summary(self, player_id: int) -> dict:
        url = ENDPOINTS["element_summary"].format(player_id=player_id)
        key = f"element_summary_{player_id}"
        return await self._cached(key, url, TTL["element_summary"])

    async def get_event_live(self, gw: int) -> dict:
        url = ENDPOINTS["event_live"].format(gw=gw)
        key = f"event_live_{gw}"
        return await self._cached(key, url, TTL["event_live"])

    async def get_event_status(self) -> dict:
        return await self._cached("event_status", ENDPOINTS["event_status"], TTL["event_status"])

    # ------------------------------------------------------------------
    # Authenticated data fetchers
    # ------------------------------------------------------------------

    def _require_team_id(self) -> int:
        if not self._team_id:
            env_id = os.environ.get("FPL_TEAM_ID")
            if env_id:
                self._team_id = int(env_id)
        if not self._team_id:
            raise RuntimeError(
                "Team ID not set. Add FPL_TEAM_ID to your .env file, "
                "or ensure FPL_EMAIL/FPL_PASSWORD are set so it can be resolved from /me."
            )
        return self._team_id

    async def get_my_team(self) -> dict:
        team_id = self._require_team_id()
        url = ENDPOINTS["my_team"].format(team_id=team_id)
        key = f"my_team_{team_id}"
        return await self._cached(key, url, TTL["my_team"])

    async def get_entry(self, team_id: Optional[int] = None) -> dict:
        tid = team_id or self._require_team_id()
        url = ENDPOINTS["entry"].format(team_id=tid)
        key = f"entry_{tid}"
        return await self._cached(key, url, TTL["entry"])

    async def get_entry_picks(self, gw: int, team_id: Optional[int] = None) -> dict:
        tid = team_id or self._require_team_id()
        url = ENDPOINTS["entry_picks"].format(team_id=tid, gw=gw)
        key = f"entry_picks_{tid}_{gw}"
        return await self._cached(key, url, TTL["entry_picks"])

    async def get_entry_transfers(self, team_id: Optional[int] = None) -> list:
        tid = team_id or self._require_team_id()
        url = ENDPOINTS["entry_transfers"].format(team_id=tid)
        key = f"entry_transfers_{tid}"
        return await self._cached(key, url, TTL["entry_transfers"])

    async def get_entry_history(self, team_id: Optional[int] = None) -> dict:
        tid = team_id or self._require_team_id()
        url = ENDPOINTS["entry_history"].format(team_id=tid)
        key = f"entry_history_{tid}"
        return await self._cached(key, url, TTL["entry_history"])

    async def get_classic_league(
        self, league_id: int, page: int = 1
    ) -> dict:
        url = ENDPOINTS["classic_league"].format(league_id=league_id)
        url = f"{url}?page_standings={page}"
        key = f"classic_league_{league_id}_{page}"
        return await self._cached(key, url, TTL["league"])

    async def get_h2h_league(
        self, league_id: int, page: int = 1
    ) -> dict:
        url = ENDPOINTS["h2h_league"].format(league_id=league_id)
        url = f"{url}?page_standings={page}"
        key = f"h2h_league_{league_id}_{page}"
        return await self._cached(key, url, TTL["league"])

    async def get_h2h_matches(self, league_id: int) -> dict:
        url = ENDPOINTS["h2h_matches"].format(league_id=league_id)
        key = f"h2h_matches_{league_id}"
        return await self._cached(key, url, TTL["league"])

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------

    async def _cached(self, key: str, url: str, ttl: int) -> Any:
        hit = self.cache.get(key)
        if hit is not None:
            logger.debug("Cache HIT: %s", key)
            return hit
        data = await self._get_raw(url)
        self.cache.set(key, data, ttl)
        return data

    async def _get_raw(self, url: str) -> Any:
        if self._session is None:
            raise RuntimeError("FPLClient not started. Call await client.start() first.")
        logger.debug("GET %s", url)
        async with self._session.get(url) as resp:
            resp.raise_for_status()
            return await resp.json()

    @property
    def team_id(self) -> Optional[int]:
        return self._team_id

    def cache_stats(self) -> dict:
        return self.cache.stats()

    def invalidate_cache(self, key: Optional[str] = None) -> None:
        if key:
            self.cache.invalidate(key)
        else:
            self.cache.clear()
