"""Shared fixtures.

Every file in tests/fixtures/ is one charger, captured with
`scripts/probe.py --save-fixture tests/fixtures`. Device tests run once per
file, so supporting a new model starts with adding its fixture.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator, Generator
import json
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.rheidon.const import CONF_BASE_URL, DEFAULT_BASE_URL, DOMAIN

FIXTURES = sorted((Path(__file__).parent / "fixtures").glob("*.json"))


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Allow Home Assistant to load custom_components/rheidon."""


@pytest.fixture(params=FIXTURES, ids=[path.stem for path in FIXTURES])
def device(request: pytest.FixtureRequest) -> dict[str, Any]:
    """One captured charger: {"list": <list item>, "detail": <detail>}."""
    return json.loads(request.param.read_text())


@pytest.fixture
def merged(device: dict[str, Any]) -> dict[str, Any]:
    """The charger data as the coordinator sees it (detail overrides list)."""
    return {**device["list"], **device["detail"]}


@pytest.fixture
def mock_client(device: dict[str, Any]) -> Generator[AsyncMock]:
    """A RheidonClient that returns the captured charger."""
    with patch("custom_components.rheidon.RheidonClient", autospec=True) as client_cls:
        client = client_cls.return_value
        client.async_get_devices.return_value = [device["list"]]
        client.async_get_device_detail.return_value = device["detail"]
        yield client


@pytest.fixture
def config_entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="user@example.com",
        unique_id="user@example.com",
        data={
            CONF_EMAIL: "user@example.com",
            CONF_PASSWORD: "password123",
            CONF_BASE_URL: DEFAULT_BASE_URL,
        },
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
async def setup_integration(
    hass: HomeAssistant, config_entry: MockConfigEntry, mock_client: AsyncMock
) -> AsyncGenerator[MockConfigEntry]:
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    yield config_entry


def entity_id(hass: HomeAssistant, platform: str, dev_id: str, key: str) -> str | None:
    """Look up an entity by its unique id, which is "<devId>_<key>"."""
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{dev_id}_{key}")
