"""Tests for the API client, against a fake Rheidon cloud."""

from __future__ import annotations

from typing import Any

import aiohttp
import pytest

from custom_components.rheidon.api import (
    RheidonApiError,
    RheidonAuthError,
    RheidonClient,
    RheidonConnectionError,
)

BASE_URL = "http://rheidon.test"
DEVICES = [{"devId": "1000000000000000002", "deviceModel": "WB500-11K-C-EU"}]


class FakeResponse:
    def __init__(self, status: int, body: Any) -> None:
        self.status = status
        self._body = body

    async def __aenter__(self) -> FakeResponse:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    def raise_for_status(self) -> None:
        if self.status >= 400:
            raise aiohttp.ClientResponseError(None, (), status=self.status)  # type: ignore[arg-type]

    async def json(self, content_type: str | None = None) -> Any:
        return self._body


class FakeCloud:
    """Mimics the Rheidon cloud: envelopes, tokens and the login error."""

    def __init__(self, password: str) -> None:
        self.password = password
        self.valid_tokens: set[str] = set()
        self.logins: list[str] = []
        self.requests: list[dict[str, Any]] = []
        self.unreachable = False

    def request(self, method: str, url: str, **kwargs: Any) -> FakeResponse:
        if self.unreachable:
            raise aiohttp.ClientConnectionError("unreachable")
        path = url.removeprefix(BASE_URL)
        self.requests.append({"method": method, "path": path, **kwargs})
        headers = kwargs.get("headers") or {}
        if path == "/app-api/user/login":
            password = kwargs["json"]["password"]
            self.logins.append(password)
            if password != self.password:
                return self._error("S5004", "Incorrect account or password")
            token = f"token-{len(self.logins)}"
            self.valid_tokens.add(token)
            return self._ok({"token": token, "userInfo": {"userId": "1"}})
        if headers.get("Authorization", "").removeprefix("Bearer ") not in self.valid_tokens:
            return self._error("U0230", "login expired")
        if path == "/app-api/rt/rt-device-bind-user/list":
            return self._ok(DEVICES)
        if path == "/app-api/rt/rt-device/set/charge/current" and kwargs["json"]["chargeCurrent"] > 32:
            return self._error("S5001", "current out of range")
        return self._ok(None)

    @staticmethod
    def _ok(data: Any) -> FakeResponse:
        return FakeResponse(200, {"code": "20001", "success": True, "message": "成功.", "data": data})

    @staticmethod
    def _error(code: str, message: str) -> FakeResponse:
        return FakeResponse(200, {"code": code, "success": False, "message": message, "status": 500})


def make_client(cloud: FakeCloud, password: str) -> RheidonClient:
    return RheidonClient(cloud, "user@example.com", password, BASE_URL)  # type: ignore[arg-type]


async def test_login_and_list_devices() -> None:
    cloud = FakeCloud("secret")
    client = make_client(cloud, "secret")

    assert await client.async_get_devices() == DEVICES

    login, listing = cloud.requests
    assert login["json"] == {"loginType": "PHONE_EMAIL", "userName": "user@example.com", "password": "secret"}
    assert "Authorization" not in login["headers"]
    assert listing["headers"]["Authorization"] == "Bearer token-1"
    assert listing["headers"]["timeutc"].startswith("UTC")


async def test_wrong_password_raises_auth_error() -> None:
    cloud = FakeCloud("secret")
    with pytest.raises(RheidonAuthError):
        await make_client(cloud, "wrong").login()
    assert cloud.logins == ["wrong"]


async def test_long_password_retried_truncated_to_16() -> None:
    cloud = FakeCloud("0123456789abcdef")
    client = make_client(cloud, "0123456789abcdefXYZ")

    await client.login()
    await client.login()

    # The first login falls back once; later logins use the truncated password.
    assert cloud.logins == ["0123456789abcdefXYZ", "0123456789abcdef", "0123456789abcdef"]


async def test_expired_token_logs_in_again() -> None:
    cloud = FakeCloud("secret")
    client = make_client(cloud, "secret")
    await client.async_get_devices()

    cloud.valid_tokens.clear()

    assert await client.async_get_devices() == DEVICES
    assert len(cloud.logins) == 2


async def test_api_error_is_raised() -> None:
    client = make_client(FakeCloud("secret"), "secret")
    with pytest.raises(RheidonApiError) as err:
        await client.async_set_charge_current("1", 40)
    assert err.value.code == "S5001"


async def test_connection_error_is_raised() -> None:
    cloud = FakeCloud("secret")
    cloud.unreachable = True
    with pytest.raises(RheidonConnectionError):
        await make_client(cloud, "secret").login()


@pytest.mark.parametrize(
    ("call", "path", "body"),
    [
        (lambda c: c.async_start_charging("7"), "/app-api/rt/rt-device/start/charging", {"devId": "7"}),
        (
            lambda c: c.async_start_charging("7", skip_delay=True),
            "/app-api/rt/rt-device/start/charging/hold",
            {"devId": "7"},
        ),
        (lambda c: c.async_stop_charging("7"), "/app-api/rt/rt-device/end/charging", {"devId": "7"}),
        (
            lambda c: c.async_set_charge_current("7", 10),
            "/app-api/rt/rt-device/set/charge/current",
            {"devId": "7", "chargeCurrent": 10},
        ),
        (
            lambda c: c.async_set_mode("7", "ECO"),
            "/app-api/rt/rt-device/set/charge/modeType",
            {"devId": "7", "modeType": "ECO"},
        ),
    ],
)
async def test_commands(call: Any, path: str, body: dict[str, Any]) -> None:
    cloud = FakeCloud("secret")
    await call(make_client(cloud, "secret"))
    command = cloud.requests[-1]
    assert (command["method"], command["path"], command["json"]) == ("POST", path, body)
