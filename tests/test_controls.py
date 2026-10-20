"""Switch, number and select tests, run once per charger fixture."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.rheidon.api import RheidonApiError
from custom_components.rheidon.const import MODE_MAP

from .conftest import entity_id

pytestmark = pytest.mark.usefixtures("setup_integration")


async def call(hass: HomeAssistant, domain: str, service: str, entity: str, **data: Any) -> None:
    await hass.services.async_call(domain, service, {ATTR_ENTITY_ID: entity, **data}, blocking=True)


async def test_charge_switch(hass: HomeAssistant, mock_client: AsyncMock, merged: dict[str, Any]) -> None:
    switch = entity_id(hass, "switch", merged["devId"], "charging_switch")
    assert hass.states.get(switch).state == ("on" if merged["status"] == 2 else "off")

    await call(hass, "switch", "turn_on", switch)
    delayed = str(merged.get("chargingYcModeStatus")) == "1"
    mock_client.async_start_charging.assert_awaited_once_with(merged["devId"], skip_delay=delayed)

    await call(hass, "switch", "turn_off", switch)
    mock_client.async_stop_charging.assert_awaited_once_with(merged["devId"])


async def test_charge_current(hass: HomeAssistant, mock_client: AsyncMock, merged: dict[str, Any]) -> None:
    number = entity_id(hass, "number", merged["devId"], "charge_current")
    current = hass.states.get(number)
    assert float(current.state) == merged["chargeCurrent"]
    assert current.attributes["min"] == 6
    assert current.attributes["max"] == merged["maxCurrent"]

    await call(hass, "number", "set_value", number, value=10)
    mock_client.async_set_charge_current.assert_awaited_once_with(merged["devId"], 10)


async def test_mode_select(hass: HomeAssistant, mock_client: AsyncMock, merged: dict[str, Any]) -> None:
    select = entity_id(hass, "select", merged["devId"], "mode")
    assert hass.states.get(select).state == MODE_MAP[merged["modeType"]]

    await call(hass, "select", "select_option", select, option="eco")
    mock_client.async_set_mode.assert_awaited_once_with(merged["devId"], "ECO")


async def test_command_failure_raises(
    hass: HomeAssistant, mock_client: AsyncMock, merged: dict[str, Any], config_entry: MockConfigEntry
) -> None:
    mock_client.async_stop_charging.side_effect = RheidonApiError("S5001", "nope")
    switch = entity_id(hass, "switch", merged["devId"], "charging_switch")

    with pytest.raises(HomeAssistantError):
        await call(hass, "switch", "turn_off", switch)
