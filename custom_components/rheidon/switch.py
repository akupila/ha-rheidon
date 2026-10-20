"""Charging switch for Rheidon+ chargers."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RheidonConfigEntry
from .const import STATUS_CHARGING
from .coordinator import RheidonCoordinator
from .entity import RheidonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RheidonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rheidon+ switches."""
    coordinator = entry.runtime_data
    async_add_entities(RheidonChargingSwitch(coordinator, dev_id) for dev_id in coordinator.data)


class RheidonChargingSwitch(RheidonEntity, SwitchEntity):
    """Starts and stops charging."""

    _attr_translation_key = "charging"

    def __init__(self, coordinator: RheidonCoordinator, dev_id: str) -> None:
        super().__init__(coordinator, dev_id, "charging_switch")

    @property
    def is_on(self) -> bool:
        return str(self.device.get("status")) == str(STATUS_CHARGING)

    async def async_turn_on(self, **kwargs: Any) -> None:
        # With a delayed start pending, the app uses the "hold" endpoint to
        # cancel the delay and start immediately.
        delayed = str(self.device.get("chargingYcModeStatus")) == "1"
        await self.async_command(
            self.coordinator.client.async_start_charging(self.api_dev_id, skip_delay=delayed)
        )

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self.async_command(self.coordinator.client.async_stop_charging(self.api_dev_id))
