"""Binary sensors for Rheidon+ chargers."""

from __future__ import annotations

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RheidonConfigEntry
from .const import STATUS_CHARGING
from .coordinator import RheidonCoordinator
from .entity import RheidonEntity, is_online


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RheidonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rheidon+ binary sensors."""
    coordinator = entry.runtime_data
    entities: list[BinarySensorEntity] = []
    for dev_id in coordinator.data:
        entities.append(RheidonOnlineSensor(coordinator, dev_id))
        entities.append(RheidonChargingSensor(coordinator, dev_id))
    async_add_entities(entities)


class RheidonOnlineSensor(RheidonEntity, BinarySensorEntity):
    """Whether the charger is connected to the Rheidon+ cloud."""

    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _requires_online = False

    def __init__(self, coordinator: RheidonCoordinator, dev_id: str) -> None:
        super().__init__(coordinator, dev_id, "online")

    @property
    def is_on(self) -> bool | None:
        return is_online(self.device)


class RheidonChargingSensor(RheidonEntity, BinarySensorEntity):
    """Whether the charger is charging."""

    _attr_translation_key = "charging"
    _attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    def __init__(self, coordinator: RheidonCoordinator, dev_id: str) -> None:
        super().__init__(coordinator, dev_id, "charging")

    @property
    def is_on(self) -> bool:
        return str(self.device.get("status")) == str(STATUS_CHARGING)
