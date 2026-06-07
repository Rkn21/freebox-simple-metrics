"""Binary sensors for Freebox Simple Metrics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import ATTR_PORT_ID, ATTR_PORT_NAME
from .coordinator import FreeboxRuntimeData
from .entity import FreeboxBaseEntity
from .sensor import _path, _result


@dataclass(frozen=True, kw_only=True)
class FreeboxBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Describe a Freebox binary sensor."""

    value_fn: Callable[[dict[str, Any]], bool | None]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda data: True


BINARY_SENSORS: tuple[FreeboxBinarySensorEntityDescription, ...] = (
    FreeboxBinarySensorEntityDescription(
        key="connection_up",
        name="Connection",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: _result(data, "connection").get("state") == "up",
    ),
    FreeboxBinarySensorEntityDescription(
        key="ftth_link",
        name="FTTH link",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: _result(data, "ftth").get("link"),
        exists_fn=lambda data: _result(data, "ftth").get("link") is not None,
    ),
    FreeboxBinarySensorEntityDescription(
        key="ftth_sfp_present",
        name="FTTH SFP present",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: _result(data, "ftth").get("sfp_present"),
        exists_fn=lambda data: _result(data, "ftth").get("sfp_present") is not None,
    ),
    FreeboxBinarySensorEntityDescription(
        key="ftth_sfp_signal",
        name="FTTH SFP signal",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: _result(data, "ftth").get("sfp_has_signal"),
        exists_fn=lambda data: _result(data, "ftth").get("sfp_has_signal") is not None,
    ),
    FreeboxBinarySensorEntityDescription(
        key="ftth_sfp_power_report",
        name="FTTH SFP power report",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: _result(data, "ftth").get("sfp_has_power_report"),
        exists_fn=lambda data: _result(data, "ftth").get("sfp_has_power_report") is not None,
    ),
    FreeboxBinarySensorEntityDescription(
        key="ftth_sfp_power_ok",
        name="FTTH SFP power OK",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        value_fn=lambda data: _result(data, "ftth").get("sfp_alim_ok"),
        exists_fn=lambda data: _result(data, "ftth").get("sfp_alim_ok") is not None,
    ),
)

for direction in ("down", "up"):
    for metric in ("nitro", "phyr", "ginp"):
        BINARY_SENSORS += (
            FreeboxBinarySensorEntityDescription(
                key=f"xdsl_{direction}_{metric}",
                name=f"xDSL {direction} {metric.upper()}",
                device_class=BinarySensorDeviceClass.CONNECTIVITY,
                value_fn=lambda data, direction=direction, metric=metric: _path(
                    _result(data, "xdsl"), direction, metric
                ),
                exists_fn=lambda data, direction=direction, metric=metric: _path(
                    _result(data, "xdsl"), direction, metric
                )
                is not None,
            ),
        )


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox binary sensors."""
    runtime: FreeboxRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[BinarySensorEntity] = [
        FreeboxBinarySensor(coordinator, description) for description in BINARY_SENSORS
    ]

    for port in coordinator.switch_ports():
        entities.append(FreeboxPortConnectedBinarySensor(coordinator, int(port["id"])))

    async_add_entities(entities)


class FreeboxBinarySensor(FreeboxBaseEntity, BinarySensorEntity):
    """A Freebox binary sensor."""

    entity_description: FreeboxBinarySensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: FreeboxBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_uid}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.exists_fn(self.coordinator.data or {})

    @property
    def is_on(self) -> bool | None:
        """Return the binary sensor state."""
        return self.entity_description.value_fn(self.coordinator.data or {})


class FreeboxPortConnectedBinarySensor(FreeboxBaseEntity, BinarySensorEntity):
    """A Freebox switch port connected binary sensor."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY

    def __init__(self, coordinator, port_id: int) -> None:
        super().__init__(coordinator)
        port = coordinator.port_by_id(port_id) or {"name": f"Port {port_id}"}
        self.port_id = port_id
        self._attr_name = f"{port.get('name', f'Port {port_id}')} connected"
        self._attr_unique_id = f"{coordinator.device_uid}_port_{port_id}_connected"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.coordinator.port_by_id(self.port_id) is not None

    @property
    def is_on(self) -> bool | None:
        """Return whether the port link is up."""
        port = self.coordinator.port_by_id(self.port_id)
        if port is None:
            return None
        return port.get("link") == "up"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra state attributes."""
        port = self.coordinator.port_by_id(self.port_id) or {}
        return {
            ATTR_PORT_ID: self.port_id,
            ATTR_PORT_NAME: port.get("name"),
            "mode": port.get("mode"),
            "speed": port.get("speed"),
            "duplex": port.get("duplex"),
            "mac_list": port.get("mac_list", []),
        }
