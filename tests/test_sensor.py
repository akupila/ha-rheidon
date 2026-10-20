"""Sensor and binary sensor tests, run once per charger fixture."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant

from custom_components.rheidon.const import STATUS_MAP

from .conftest import entity_id

# Values seen on a WB500-11K-C-EU charging at about 6 A.
CHARGING = {
    "status": 2,
    "power": 1.42,
    "powerP2": 1.35,
    "powerP3": 1.42,
    "electricity": 6.07,
    "electricityP2": 5.82,
    "electricityP3": 6.05,
    "electricQuantity": 13.22,
}


def three_phase(device: dict[str, Any]) -> bool:
    if device.get("phase") in (1, 3):
        return device["phase"] == 3
    model = device.get("deviceModel") or ""
    return "7K2" not in model and "3K6" not in model


def state(hass: HomeAssistant, device: dict[str, Any], key: str, platform: str = "sensor") -> str | None:
    entity = entity_id(hass, platform, device["devId"], key)
    assert entity, f"{platform} {key} not created"
    return hass.states.get(entity).state


def number_or_unknown(value: Any) -> float | str:
    return STATE_UNKNOWN if value is None else pytest.approx(float(value))


async def setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


@pytest.mark.usefixtures("setup_integration")
async def test_sensors_match_fixture(hass: HomeAssistant, merged: dict[str, Any]) -> None:
    power = sum(float(merged.get(k) or 0) for k in ("power", "powerP2", "powerP3"))
    assert float(state(hass, merged, "power")) == pytest.approx(power)
    session = state(hass, merged, "session_energy")
    assert (session if session == STATE_UNKNOWN else float(session)) == number_or_unknown(
        merged.get("electricQuantity")
    )
    assert state(hass, merged, "status") == STATUS_MAP[merged["status"]]
    assert float(state(hass, merged, "current_l1")) == pytest.approx(merged["electricity"])
    assert float(state(hass, merged, "voltage_l1")) == pytest.approx(merged["voltage"])
    assert float(state(hass, merged, "power_l1")) == pytest.approx(merged["power"])

    started = datetime.strptime(merged["chargeStartTime"], "%Y-%m-%d %H:%M:%S")
    started = started.replace(tzinfo=ZoneInfo(merged.get("timeZone") or "UTC"))
    assert datetime.fromisoformat(state(hass, merged, "charge_start")) == started.astimezone(UTC)


@pytest.mark.usefixtures("setup_integration")
async def test_phase_entities(hass: HomeAssistant, merged: dict[str, Any]) -> None:
    for key in ("power_l2", "power_l3", "current_l2", "current_l3", "voltage_l2", "voltage_l3"):
        created = entity_id(hass, "sensor", merged["devId"], key) is not None
        assert created == three_phase(merged), key


@pytest.mark.usefixtures("setup_integration")
async def test_binary_sensors(hass: HomeAssistant, merged: dict[str, Any]) -> None:
    assert state(hass, merged, "online", "binary_sensor") == (STATE_ON if merged["online"] else STATE_OFF)
    charging = STATE_ON if merged["status"] == 2 else STATE_OFF
    assert state(hass, merged, "charging", "binary_sensor") == charging


async def test_charging(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock, device: dict[str, Any]
) -> None:
    device["detail"].update(CHARGING)
    await setup(hass, config_entry)
    detail = device["detail"]

    assert float(state(hass, detail, "power")) == pytest.approx(4.19)
    assert float(state(hass, detail, "session_energy")) == pytest.approx(13.22)
    assert state(hass, detail, "status") == "charging"
    assert state(hass, detail, "charging", "binary_sensor") == STATE_ON


async def test_offline_makes_measurements_unavailable(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock, device: dict[str, Any]
) -> None:
    device["detail"]["online"] = False
    await setup(hass, config_entry)
    detail = device["detail"]

    assert state(hass, detail, "power") == STATE_UNAVAILABLE
    assert state(hass, detail, "online", "binary_sensor") == STATE_OFF


async def test_single_phase_skips_l2_l3(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock, device: dict[str, Any]
) -> None:
    device["detail"]["phase"] = 1
    await setup(hass, config_entry)

    assert entity_id(hass, "sensor", device["detail"]["devId"], "power_l1") is not None
    assert entity_id(hass, "sensor", device["detail"]["devId"], "power_l2") is None
