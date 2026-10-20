"""Base entity for Rheidon+ chargers."""

from __future__ import annotations

from collections.abc import Awaitable
from typing import Any

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .api import RheidonError
from .const import DOMAIN
from .coordinator import RheidonCoordinator


def is_three_phase(device: dict[str, Any]) -> bool:
    """Whether the charger reports L2/L3 values."""
    if device.get("phase") in (1, 3):
        return device["phase"] == 3
    # Fall back to the app's model-name check.
    model = device.get("deviceModel") or ""
    return "7K2" not in model and "3K6" not in model


def is_online(device: dict[str, Any]) -> bool | None:
    """Return the online flag, or None if the API did not report one."""
    online = device.get("online")
    if online is None:
        return None
    return online in (True, 1, "1")


class RheidonEntity(CoordinatorEntity[RheidonCoordinator]):
    """A Rheidon+ charger entity."""

    _attr_has_entity_name = True
    # Measurements are stale while the charger is offline.
    _requires_online = True

    def __init__(self, coordinator: RheidonCoordinator, dev_id: str, key: str) -> None:
        super().__init__(coordinator)
        self._dev_id = dev_id
        self._attr_unique_id = f"{dev_id}_{key}"
        device = self.device
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, dev_id)},
            manufacturer="Rheidon",
            model=device.get("deviceModel"),
            name=device.get("devName") or device.get("deviceModel") or "Rheidon+ charger",
            serial_number=device.get("deviceNo"),
            sw_version=device.get("devVersion"),
        )

    @property
    def device(self) -> dict[str, Any]:
        """The latest data for this charger."""
        return self.coordinator.data.get(self._dev_id, {})

    @property
    def available(self) -> bool:
        if not super().available or self._dev_id not in self.coordinator.data:
            return False
        return not self._requires_online or is_online(self.device) is not False

    @property
    def api_dev_id(self) -> Any:
        """The devId as the API returned it, for command payloads."""
        return self.device.get("devId", self._dev_id)

    async def async_command(self, command: Awaitable[None]) -> None:
        """Send a command, then refresh so the new state shows up."""
        try:
            await command
        except RheidonError as err:
            raise HomeAssistantError(f"Rheidon+ command failed: {err}") from err
        await self.coordinator.async_request_refresh()
