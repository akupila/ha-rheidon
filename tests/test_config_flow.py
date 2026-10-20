"""Tests for the config flow."""

from __future__ import annotations

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.rheidon.api import RheidonAuthError, RheidonConnectionError
from custom_components.rheidon.const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN

USER_INPUT = {CONF_EMAIL: "User@Example.com", CONF_PASSWORD: "password123"}


@pytest.fixture
def login() -> Generator[AsyncMock]:
    """Patch the client used by the flow; returns its login mock."""
    with patch("custom_components.rheidon.config_flow.RheidonClient", autospec=True) as client_cls:
        yield client_cls.return_value.login


@pytest.fixture(autouse=True)
def no_setup() -> Generator[None]:
    """Don't set up the integration when the flow creates an entry."""
    with patch("custom_components.rheidon.async_setup_entry", return_value=True):
        yield


async def test_user_flow(hass: HomeAssistant, login: AsyncMock) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "User@Example.com"
    assert result["data"] == {**USER_INPUT, CONF_BASE_URL: DEFAULT_BASE_URL}
    assert result["result"].unique_id == "user@example.com"
    login.assert_awaited_once()


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (RheidonAuthError("bad"), "invalid_auth"),
        (RheidonConnectionError("down"), "cannot_connect"),
        (ValueError("boom"), "unknown"),
    ],
)
async def test_user_flow_errors_then_recovers(
    hass: HomeAssistant, login: AsyncMock, error: Exception, expected: str
) -> None:
    login.side_effect = error
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}

    login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_duplicate_account_aborts(hass: HomeAssistant, login: AsyncMock) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id="user@example.com").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reauth(hass: HomeAssistant, login: AsyncMock) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="user@example.com",
        data={CONF_EMAIL: "user@example.com", CONF_PASSWORD: "old", CONF_BASE_URL: DEFAULT_BASE_URL},
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["step_id"] == "reauth_confirm"

    login.side_effect = RheidonAuthError("bad")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "wrong"})
    assert result["errors"] == {"base": "invalid_auth"}

    login.side_effect = None
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new"
