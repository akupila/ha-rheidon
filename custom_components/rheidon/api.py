"""Async client for the Rheidon+ cloud API.

Reverse engineered from the Rheidon+ Android app (2.1.4). See FLOW.md for the
protocol description. This module has no Home Assistant dependencies.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import DEFAULT_BASE_URL

_LOGGER = logging.getLogger(__name__)

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)

# Response envelope codes, from the app's request wrapper.
SUCCESS_CODES = {"200", "20001"}
AUTH_ERROR_CODES = {"A00004", "A00006", "A00007", "U0230"}

APP_PASSWORD_MAX_LENGTH = 16


class RheidonError(Exception):
    """Base error for the Rheidon+ API."""


class RheidonConnectionError(RheidonError):
    """The API could not be reached."""


class RheidonAuthError(RheidonError):
    """Credentials or token were rejected."""


class RheidonApiError(RheidonError):
    """The API returned an error envelope."""

    def __init__(self, code: str | None, message: str) -> None:
        super().__init__(f"{message} ({code})" if code else message)
        self.code = code


def _timeutc_header() -> str:
    """Format the local UTC offset the way the app does, e.g. "UTC+2"."""
    offset = time.localtime().tm_gmtoff / 3600
    value = int(offset) if offset.is_integer() else offset
    return f"UTC{'+' if offset >= 0 else ''}{value}"


class RheidonClient:
    """Client for the Rheidon+ cloud API."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        email: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._token: str | None = None
        self._login_lock = asyncio.Lock()

    async def login(self) -> dict[str, Any]:
        """Log in and store the bearer token. Returns the login payload."""
        async with self._login_lock:
            try:
                data = await self._login(self._password)
            except RheidonAuthError:
                # The iOS app's password field silently cuts input off at 16
                # characters, so accounts created there have the truncated
                # password. Remember it so later logins skip the failed attempt.
                if len(self._password) <= APP_PASSWORD_MAX_LENGTH:
                    raise
                _LOGGER.debug("Login failed, retrying with the password truncated like the app")
                data = await self._login(self._password[:APP_PASSWORD_MAX_LENGTH])
                self._password = self._password[:APP_PASSWORD_MAX_LENGTH]
            self._token = data["token"]
            return data

    async def _login(self, password: str) -> dict[str, Any]:
        try:
            data = await self._request(
                "POST",
                "/app-api/user/login",
                json={"loginType": "PHONE_EMAIL", "userName": self._email, "password": password},
                auth=False,
            )
        except RheidonApiError as err:
            raise RheidonAuthError(str(err)) from err
        if not isinstance(data, dict) or not data.get("token"):
            raise RheidonAuthError("Login response did not contain a token")
        return data

    async def async_get_devices(self) -> list[dict[str, Any]]:
        """Return the devices bound to the account."""
        data = await self._call("GET", "/app-api/rt/rt-device-bind-user/list")
        return data if isinstance(data, list) else []

    async def async_get_device_detail(self, dev_id: Any) -> dict[str, Any]:
        """Return the full state of one device."""
        data = await self._call(
            "GET",
            "/app-api/rt/rt-device-bind-user/detail",
            params={"devId": str(dev_id)},
        )
        return data if isinstance(data, dict) else {}

    async def async_start_charging(self, dev_id: Any, *, skip_delay: bool = False) -> None:
        """Start charging. skip_delay starts now even if a delayed start is set."""
        path = "/start/charging/hold" if skip_delay else "/start/charging"
        await self._call("POST", f"/app-api/rt/rt-device{path}", json={"devId": dev_id})

    async def async_stop_charging(self, dev_id: Any) -> None:
        """Stop charging."""
        await self._call("POST", "/app-api/rt/rt-device/end/charging", json={"devId": dev_id})

    async def async_set_charge_current(self, dev_id: Any, amps: int) -> None:
        """Set the charging current limit in amps."""
        await self._call(
            "POST",
            "/app-api/rt/rt-device/set/charge/current",
            json={"devId": dev_id, "chargeCurrent": amps},
        )

    async def async_set_mode(self, dev_id: Any, mode: str) -> None:
        """Set the charging mode ("Plug Now", "ECO", "MAX" or "Manual")."""
        await self._call(
            "POST",
            "/app-api/rt/rt-device/set/charge/modeType",
            json={"devId": dev_id, "modeType": mode},
        )

    async def _call(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        """Make an authenticated request, logging in again if the token expired."""
        if self._token is None:
            await self.login()
        try:
            return await self._request(method, path, params=params, json=json)
        except RheidonAuthError:
            _LOGGER.debug("Token rejected, logging in again")
            self._token = None
            await self.login()
            return await self._request(method, path, params=params, json=json)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str] | None = None,
        json: dict[str, Any] | None = None,
        auth: bool = True,
    ) -> Any:
        headers = {"Accept-Language": "en", "timeutc": _timeutc_header()}
        if auth:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.request(
                method,
                self._base_url + path,
                params=params,
                json=json,
                headers=headers,
                timeout=REQUEST_TIMEOUT,
            ) as resp:
                if resp.status == 401:
                    raise RheidonAuthError("Unauthorized")
                resp.raise_for_status()
                body = await resp.json(content_type=None)
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise RheidonConnectionError(f"{method} {path} failed: {err}") from err

        if not isinstance(body, dict):
            raise RheidonApiError(None, f"Unexpected response from {path}: {body!r}")
        code = str(body.get("code"))
        if code in SUCCESS_CODES or body.get("success") is True:
            return body.get("data")
        message = body.get("message") or body.get("msg") or "Unknown error"
        if code in AUTH_ERROR_CODES:
            raise RheidonAuthError(message)
        raise RheidonApiError(code, message)
