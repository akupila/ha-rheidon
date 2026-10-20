"""Charging current limit for Rheidon+ chargers."""

from __future__ import annotations

from homeassistant.components.number import NumberDeviceClass, NumberEntity, NumberMode
from homeassistant.const import UnitOfElectricCurrent
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RheidonConfigEntry
from .const import MIN_CHARGE_CURRENT
from .coordinator import RheidonCoordinator
from .entity import RheidonEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RheidonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rheidon+ numbers."""
    coordinator = entry.runtime_data
    async_add_entities(RheidonChargeCurrent(coordinator, dev_id) for dev_id in coordinator.data)


class RheidonChargeCurrent(RheidonEntity, NumberEntity):
    """The maximum current the charger offers the car."""

    _attr_translation_key = "charge_current"
    _attr_device_class = NumberDeviceClass.CURRENT
    _attr_native_unit_of_measurement = UnitOfElectricCurrent.AMPERE
    _attr_native_min_value = MIN_CHARGE_CURRENT
    _attr_native_step = 1
    _attr_mode = NumberMode.SLIDER

    def __init__(self, coordinator: RheidonCoordinator, dev_id: str) -> None:
        super().__init__(coordinator, dev_id, "charge_current")

    @property
    def native_max_value(self) -> float:
        # Same fallback as the app's calculateMaxCurrent.
        if self.device.get("maxCurrent"):
            return float(self.device["maxCurrent"])
        model = self.device.get("deviceModel") or ""
        return 16 if "11K" in model or "3K" in model else 32

    @property
    def native_value(self) -> float | None:
        value = self.device.get("chargeCurrent")
        return float(value) if value not in (None, "") else None

    async def async_set_native_value(self, value: float) -> None:
        await self.async_command(
            self.coordinator.client.async_set_charge_current(self.api_dev_id, int(value))
        )
