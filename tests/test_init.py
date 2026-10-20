"""Setup, unload and error handling."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.rheidon.api import RheidonAuthError, RheidonConnectionError


async def test_setup_and_unload(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_connection_error_retries_setup(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    mock_client.async_get_devices.side_effect = RheidonConnectionError("down")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_auth_error_starts_reauth(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> None:
    mock_client.async_get_devices.side_effect = RheidonAuthError("expired")
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]
