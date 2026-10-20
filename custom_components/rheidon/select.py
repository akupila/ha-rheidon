"""Charging mode select for Rheidon+ chargers."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import RheidonConfigEntry
from .const import MODE_MAP
from .coordinator import RheidonCoordinator
from .entity import RheidonEntity

_API_MODES = {option: mode for mode, option in MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RheidonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rheidon+ selects."""
    coordinator = entry.runtime_data
    async_add_entities(RheidonModeSelect(coordinator, dev_id) for dev_id in coordinator.data)


class RheidonModeSelect(RheidonEntity, SelectEntity):
    """The charging mode."""

    _attr_translation_key = "mode"
    _attr_options = list(MODE_MAP.values())

    def __init__(self, coordinator: RheidonCoordinator, dev_id: str) -> None:
        super().__init__(coordinator, dev_id, "mode")

    @property
    def current_option(self) -> str | None:
        return MODE_MAP.get(self.device.get("modeType") or "")

    async def async_select_option(self, option: str) -> None:
        await self.async_command(
            self.coordinator.client.async_set_mode(self.api_dev_id, _API_MODES[option])
        )
