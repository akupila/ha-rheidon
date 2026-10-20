"""The Rheidon+ EV charger integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import RheidonClient
from .const import CONF_BASE_URL, DEFAULT_BASE_URL
from .coordinator import RheidonCoordinator

PLATFORMS: list[Platform] = [
    Platform.BINARY_SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

RheidonConfigEntry = ConfigEntry[RheidonCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: RheidonConfigEntry) -> bool:
    """Set up Rheidon+ from a config entry."""
    client = RheidonClient(
        async_get_clientsession(hass),
        entry.data[CONF_EMAIL],
        entry.data[CONF_PASSWORD],
        entry.data.get(CONF_BASE_URL, DEFAULT_BASE_URL),
    )
    coordinator = RheidonCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: RheidonConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
