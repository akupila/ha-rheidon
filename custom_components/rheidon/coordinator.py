"""Polling coordinator for Rheidon+ chargers."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import RheidonApiError, RheidonAuthError, RheidonClient, RheidonError
from .const import DOMAIN, SCAN_INTERVAL

_LOGGER = logging.getLogger(__name__)


class RheidonCoordinator(DataUpdateCoordinator[dict[str, dict[str, Any]]]):
    """Fetches the state of every charger on the account, keyed by devId."""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, client: RheidonClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=SCAN_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, dict[str, Any]]:
        try:
            devices = await self.client.async_get_devices()
            data: dict[str, dict[str, Any]] = {}
            for device in devices:
                dev_id = device.get("devId")
                if dev_id is None:
                    continue
                try:
                    detail = await self.client.async_get_device_detail(dev_id)
                except RheidonApiError as err:
                    _LOGGER.debug("Detail for %s failed, using list data: %s", dev_id, err)
                    detail = {}
                data[str(dev_id)] = {**device, **detail}
        except RheidonAuthError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except RheidonError as err:
            raise UpdateFailed(str(err)) from err
        return data
