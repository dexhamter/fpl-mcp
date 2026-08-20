"""FPL authentication — session cookie login."""

import json
import logging
import os
from pathlib import Path
from typing import Optional

import aiohttp

from .constants import FPL_LOGIN_URL

logger = logging.getLogger(__name__)

LOGIN_HEADERS = {
    "User-Agent": "Mozilla/5.0",
    "Content-Type": "application/x-www-form-urlencoded",
    "Origin": "https://users.premierleague.com",
    "Referer": "https://users.premierleague.com/accounts/login/",
}


class FPLAuth:
    """Manages FPL session cookie authentication."""

    def __init__(
        self,
        email: str = "",
        password: str = "",
        session_file: Optional[str] = None,
        cookie: Optional[str] = None,
        api_token: Optional[str] = None,
    ) -> None:
        self.email = email
        self.password = password
        self.session_file = Path(session_file or "fpl_session.json")
        self.raw_cookie = cookie or os.environ.get("FPL_COOKIE", "")
        self.api_token = (api_token or os.environ.get("FPL_API_TOKEN", "")).strip()
        if self.api_token.lower().startswith("bearer "):
            self.api_token = self.api_token[7:].strip()
        self._cookies: dict[str, str] = {}
        if self.raw_cookie:
            self._parse_raw_cookie(self.raw_cookie)

    def _parse_raw_cookie(self, raw: str) -> None:
        """Parse 'key=value; key2=value2' cookie string."""
        for part in raw.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                self._cookies[k.strip()] = v.strip()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    @classmethod
    def from_env(cls) -> "FPLAuth":
        """Construct from environment variables (loaded from .env)."""
        email = os.environ.get("FPL_EMAIL", "")
        password = os.environ.get("FPL_PASSWORD", "")
        session_file = os.environ.get("FPL_SESSION_FILE", "fpl_session.json")
        cookie = os.environ.get("FPL_COOKIE", "")
        return cls(email=email, password=password, session_file=session_file, cookie=cookie)

    async def ensure_session(self, session: aiohttp.ClientSession) -> None:
        """Ensure we have a valid session cookie, refreshing if necessary."""
        # Bearer token auth needs no cookies or login
        if self.api_token:
            return
        # Try raw cookie or persisted cookies first
        if not self._cookies:
            self._load_cookies()

        # If still empty and credentials provided, attempt login
        if not self._cookies and self.email and self.password:
            try:
                await self._login(session)
            except Exception as exc:  # noqa: BLE001
                logger.warning("FPL login could not be completed automatically (%s). Public endpoints will still work.", exc)

    def apply_cookies(self, session: aiohttp.ClientSession) -> None:
        """Apply stored cookies to the aiohttp session."""
        for name, value in self._cookies.items():
            session.cookie_jar.update_cookies({name: value})

    async def refresh(self, session: aiohttp.ClientSession) -> None:
        """Force a fresh login, discarding any cached cookies."""
        self._cookies = {}
        if self.email and self.password:
            await self._login(session)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _login(self, session: aiohttp.ClientSession) -> None:
        """Authenticate with FPL and cache the session cookie."""
        payload = {
            "login": self.email,
            "password": self.password,
            "app": "plfpl-web",
            "redirect_uri": "https://fantasy.premierleague.com/a/login",
        }
        logger.info("Attempting login to FPL as %s", self.email)
        try:
            async with session.post(
                FPL_LOGIN_URL, data=payload, headers=LOGIN_HEADERS, allow_redirects=True, timeout=10
            ) as resp:
                if resp.status in (200, 302):
                    self._cookies = {
                        c.key: c.value
                        for c in session.cookie_jar
                        if "premierleague.com" in (c.get("domain") or "")
                    }
                    if self._cookies:
                        self._persist_cookies()
                        logger.info("FPL login successful, %d cookies stored", len(self._cookies))
                else:
                    text = await resp.text()
                    logger.warning("FPL login returned HTTP %s: %s", resp.status, text[:150])
        except Exception as exc:
            logger.warning("FPL login request failed: %s", exc)

    def _load_cookies(self) -> None:
        """Load cookies from the session file if it exists."""
        if self.session_file.exists():
            try:
                data = json.loads(self.session_file.read_text())
                self._cookies = data.get("cookies", {})
                logger.debug("Loaded %d cookies from %s", len(self._cookies), self.session_file)
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load session file: %s", exc)
                self._cookies = {}

    def _persist_cookies(self) -> None:
        """Persist cookies to disk."""
        try:
            self.session_file.write_text(
                json.dumps({"cookies": self._cookies}, indent=2)
            )
            logger.debug("Session cookies persisted to %s", self.session_file)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Could not persist session: %s", exc)
