"""Sensors for Rheidon+ chargers."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    UnitOfElectricCurrent,
    UnitOfElectricPotential,
    UnitOfEnergy,
    UnitOfPower,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import RheidonConfigEntry
from .const import STATUS_MAP
from .coordinator import RheidonCoordinator
from .entity import RheidonEntity, is_three_phase


def _number(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _device_time(key: str) -> Callable[[dict[str, Any]], datetime | None]:
    """Parse a "YYYY-MM-DD HH:MM:SS" field given in the charger's own time zone."""

    def value(device: dict[str, Any]) -> datetime | None:
        try:
            parsed = datetime.strptime(device.get(key) or "", "%Y-%m-%d %H:%M:%S")
        except ValueError:
            return None
        tz = dt_util.get_time_zone(device.get("timeZone") or "") or dt_util.get_default_time_zone()
        return parsed.replace(tzinfo=tz)

    return value


def _total_power(device: dict[str, Any]) -> float | None:
    phases = [_number(device.get(key)) for key in ("power", "powerP2", "powerP3")]
    if all(value is None for value in phases):
        return None
    return round(sum(value or 0 for value in phases), 3)


@dataclass(frozen=True, kw_only=True)
class RheidonSensorEntityDescription(SensorEntityDescription):
    """Describes a Rheidon+ sensor."""

    value_fn: Callable[[dict[str, Any]], Any]
    three_phase_only: bool = False


def _field(key: str) -> Callable[[dict[str, Any]], float | None]:
    return lambda device: _number(device.get(key))


def _phase_sensors(
    name: str, fields: tuple[str, str, str], **kwargs: Any
) -> list[RheidonSensorEntityDescription]:
    return [
        RheidonSensorEntityDescription(
            key=f"{name}_l{phase}",
            translation_key=f"{name}_l{phase}",
            value_fn=_field(field),
            three_phase_only=phase > 1,
            state_class=SensorStateClass.MEASUREMENT,
            **kwargs,
        )
        for phase, field in enumerate(fields, start=1)
    ]


SENSORS: list[RheidonSensorEntityDescription] = [
    RheidonSensorEntityDescription(
        key="status",
        translation_key="status",
        device_class=SensorDeviceClass.ENUM,
        options=list(STATUS_MAP.values()),
        value_fn=lambda device: STATUS_MAP.get(int(_number(device.get("status")) or 0)),
    ),
    RheidonSensorEntityDescription(
        key="power",
        translation_key="power",
        device_class=SensorDeviceClass.POWER,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
        value_fn=_total_power,
    ),
    RheidonSensorEntityDescription(
        key="session_energy",
        translation_key="session_energy",
        device_class=SensorDeviceClass.ENERGY,
        # Resets at the start of each session, which total_increasing handles.
        state_class=SensorStateClass.TOTAL_INCREASING,
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        suggested_display_precision=2,
        value_fn=_field("electricQuantity"),
    ),
    RheidonSensorEntityDescription(
        key="charge_start",
        translation_key="charge_start",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_device_time("chargeStartTime"),
    ),
    RheidonSensorEntityDescription(
        key="charge_end",
        translation_key="charge_end",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=_device_time("chargeEndTime"),
    ),
    *_phase_sensors(
        "power",
        ("power", "powerP2", "powerP3"),
        device_class=SensorDeviceClass.POWER,
        native_unit_of_measurement=UnitOfPower.KILO_WATT,
        suggested_display_precision=2,
    ),
    *_phase_sensors(
        "current",
        ("electricity", "electricityP2", "electricityP3"),
        device_class=SensorDeviceClass.CURRENT,
        native_unit_of_measurement=UnitOfElectricCurrent.AMPERE,
        suggested_display_precision=1,
    ),
    *_phase_sensors(
        "voltage",
        ("voltage", "voltageP2", "voltageP3"),
        device_class=SensorDeviceClass.VOLTAGE,
        native_unit_of_measurement=UnitOfElectricPotential.VOLT,
        suggested_display_precision=0,
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: RheidonConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Rheidon+ sensors."""
    coordinator = entry.runtime_data
    async_add_entities(
        RheidonSensor(coordinator, dev_id, description)
        for dev_id, device in coordinator.data.items()
        for description in SENSORS
        if not description.three_phase_only or is_three_phase(device)
    )


class RheidonSensor(RheidonEntity, SensorEntity):
    """A Rheidon+ sensor."""

    entity_description: RheidonSensorEntityDescription

    def __init__(
        self,
        coordinator: RheidonCoordinator,
        dev_id: str,
        description: RheidonSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, dev_id, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.device)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.key != "status":
            return None
        return {"fault": self.device.get("faultType")}
