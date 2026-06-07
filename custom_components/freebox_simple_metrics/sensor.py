"""Sensors for Freebox Simple Metrics."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfDataRate, UnitOfInformation, UnitOfTime
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import StateType

from .const import ATTR_PORT_ID, ATTR_PORT_NAME
from .coordinator import FreeboxRuntimeData
from .entity import FreeboxBaseEntity


def _result(data: dict[str, Any], key: str) -> dict[str, Any]:
    value = data.get(key, {})
    if not isinstance(value, dict) or not value.get("ok"):
        return {}
    result = value.get("data", {})
    return result if isinstance(result, dict) else {}


def _path(data: dict[str, Any], *keys: str) -> Any:
    value: Any = data
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _mbit_from_bytes_per_second(value: Any) -> float | None:
    return round(float(value) * 8 / 1_000_000, 3) if value is not None else None


def _mbit_from_bits_per_second(value: Any) -> float | None:
    return round(float(value) / 1_000_000, 3) if value is not None else None


def _dbm_from_centidbm(value: Any) -> float | None:
    return round(float(value) / 100, 2) if value is not None else None


def _mac_count(port: dict[str, Any]) -> int:
    mac_list = port.get("mac_list")
    return len(mac_list) if isinstance(mac_list, list) else 0


def _tx_error_count(stats: dict[str, Any] | None) -> int | None:
    if stats is None:
        return None
    return sum(
        int(stats.get(key) or 0)
        for key in ("tx_collisions", "tx_late", "tx_fcs", "tx_excessive")
    )


@dataclass(frozen=True, kw_only=True)
class FreeboxSensorEntityDescription(SensorEntityDescription):
    """Describe a Freebox metric sensor."""

    value_fn: Callable[[dict[str, Any]], StateType]
    exists_fn: Callable[[dict[str, Any]], bool] = lambda data: True
    attrs_fn: Callable[[dict[str, Any]], dict[str, Any] | None] = lambda data: None


@dataclass(frozen=True, kw_only=True)
class FreeboxPortSensorEntityDescription(SensorEntityDescription):
    """Describe a Freebox switch port sensor."""

    value_fn: Callable[[dict[str, Any], dict[str, Any] | None], StateType]
    attrs_fn: Callable[[dict[str, Any], dict[str, Any] | None], dict[str, Any] | None] = (
        lambda port, stats: None
    )


CONNECTION_SENSORS: tuple[FreeboxSensorEntityDescription, ...] = (
    FreeboxSensorEntityDescription(
        key="connection_state",
        name="Connection state",
        icon="mdi:wan",
        value_fn=lambda data: _result(data, "connection").get("state"),
    ),
    FreeboxSensorEntityDescription(
        key="connection_media",
        name="Connection media",
        icon="mdi:connection",
        value_fn=lambda data: _result(data, "connection").get("media"),
    ),
    FreeboxSensorEntityDescription(
        key="connection_type",
        name="Connection type",
        icon="mdi:transit-connection",
        value_fn=lambda data: _result(data, "connection").get("type"),
    ),
    FreeboxSensorEntityDescription(
        key="ipv4",
        name="IPv4",
        icon="mdi:ip-network",
        value_fn=lambda data: _result(data, "connection").get("ipv4"),
        attrs_fn=lambda data: {
            "port_range": _result(data, "connection").get("ipv4_port_range"),
        },
    ),
    FreeboxSensorEntityDescription(
        key="ipv6",
        name="IPv6",
        icon="mdi:ip-network-outline",
        value_fn=lambda data: _result(data, "connection").get("ipv6"),
    ),
    FreeboxSensorEntityDescription(
        key="download_rate",
        name="Download rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: _mbit_from_bytes_per_second(
            _result(data, "connection").get("rate_down")
        ),
    ),
    FreeboxSensorEntityDescription(
        key="upload_rate",
        name="Upload rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda data: _mbit_from_bytes_per_second(
            _result(data, "connection").get("rate_up")
        ),
    ),
    FreeboxSensorEntityDescription(
        key="download_bandwidth",
        name="Download bandwidth",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _mbit_from_bits_per_second(
            _result(data, "connection").get("bandwidth_down")
        ),
    ),
    FreeboxSensorEntityDescription(
        key="upload_bandwidth",
        name="Upload bandwidth",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=lambda data: _mbit_from_bits_per_second(
            _result(data, "connection").get("bandwidth_up")
        ),
    ),
    FreeboxSensorEntityDescription(
        key="downloaded_data",
        name="Downloaded data",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: _result(data, "connection").get("bytes_down"),
    ),
    FreeboxSensorEntityDescription(
        key="uploaded_data",
        name="Uploaded data",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda data: _result(data, "connection").get("bytes_up"),
    ),
    FreeboxSensorEntityDescription(
        key="connected_ports",
        name="Connected ports",
        icon="mdi:ethernet",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _path(data, "summary", "connected_ports"),
    ),
    FreeboxSensorEntityDescription(
        key="total_ports",
        name="Total ports",
        icon="mdi:ethernet",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _path(data, "summary", "total_ports"),
    ),
)

FTTH_SENSORS: tuple[FreeboxSensorEntityDescription, ...] = (
    FreeboxSensorEntityDescription(
        key="ftth_link_type",
        name="FTTH link type",
        icon="mdi:fiber-optic",
        value_fn=lambda data: _result(data, "ftth").get("link_type"),
        exists_fn=lambda data: bool(_result(data, "ftth")),
    ),
    FreeboxSensorEntityDescription(
        key="ftth_sfp_vendor",
        name="FTTH SFP vendor",
        icon="mdi:factory",
        value_fn=lambda data: _result(data, "ftth").get("sfp_vendor"),
        exists_fn=lambda data: bool(_result(data, "ftth")),
    ),
    FreeboxSensorEntityDescription(
        key="ftth_sfp_model",
        name="FTTH SFP model",
        icon="mdi:identifier",
        value_fn=lambda data: _result(data, "ftth").get("sfp_model"),
        exists_fn=lambda data: bool(_result(data, "ftth")),
    ),
    FreeboxSensorEntityDescription(
        key="ftth_sfp_serial",
        name="FTTH SFP serial",
        icon="mdi:barcode",
        value_fn=lambda data: _result(data, "ftth").get("sfp_serial"),
        exists_fn=lambda data: bool(_result(data, "ftth")),
    ),
    FreeboxSensorEntityDescription(
        key="ftth_rx_power",
        name="FTTH RX power",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _dbm_from_centidbm(_result(data, "ftth").get("sfp_pwr_rx")),
        exists_fn=lambda data: _result(data, "ftth").get("sfp_pwr_rx") is not None,
    ),
    FreeboxSensorEntityDescription(
        key="ftth_tx_power",
        name="FTTH TX power",
        native_unit_of_measurement="dBm",
        device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=2,
        value_fn=lambda data: _dbm_from_centidbm(_result(data, "ftth").get("sfp_pwr_tx")),
        exists_fn=lambda data: _result(data, "ftth").get("sfp_pwr_tx") is not None,
    ),
)

XDSL_SENSORS: tuple[FreeboxSensorEntityDescription, ...] = (
    FreeboxSensorEntityDescription(
        key="xdsl_status",
        name="xDSL status",
        icon="mdi:phone-outline",
        value_fn=lambda data: _path(_result(data, "xdsl"), "status", "status"),
        exists_fn=lambda data: bool(_result(data, "xdsl")),
    ),
    FreeboxSensorEntityDescription(
        key="xdsl_protocol",
        name="xDSL protocol",
        icon="mdi:protocol",
        value_fn=lambda data: _path(_result(data, "xdsl"), "status", "protocol"),
        exists_fn=lambda data: bool(_result(data, "xdsl")),
    ),
    FreeboxSensorEntityDescription(
        key="xdsl_uptime",
        name="xDSL uptime",
        native_unit_of_measurement=UnitOfTime.SECONDS,
        device_class=SensorDeviceClass.DURATION,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda data: _path(_result(data, "xdsl"), "status", "uptime"),
        exists_fn=lambda data: _path(_result(data, "xdsl"), "status", "uptime") is not None,
    ),
)

for direction in ("down", "up"):
    XDSL_SENSORS += (
        FreeboxSensorEntityDescription(
            key=f"xdsl_{direction}_rate",
            name=f"xDSL {direction} rate",
            native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "rate"
            ),
            exists_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "rate"
            )
            is not None,
        ),
        FreeboxSensorEntityDescription(
            key=f"xdsl_{direction}_max_rate",
            name=f"xDSL {direction} max rate",
            native_unit_of_measurement=UnitOfDataRate.KILOBITS_PER_SECOND,
            device_class=SensorDeviceClass.DATA_RATE,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "maxrate"
            ),
            exists_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "maxrate"
            )
            is not None,
        ),
        FreeboxSensorEntityDescription(
            key=f"xdsl_{direction}_snr",
            name=f"xDSL {direction} SNR",
            native_unit_of_measurement="dB",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "snr"
            ),
            exists_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "snr"
            )
            is not None,
        ),
        FreeboxSensorEntityDescription(
            key=f"xdsl_{direction}_attenuation",
            name=f"xDSL {direction} attenuation",
            native_unit_of_measurement="dB",
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
            state_class=SensorStateClass.MEASUREMENT,
            value_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "attn"
            ),
            exists_fn=lambda data, direction=direction: _path(
                _result(data, "xdsl"), direction, "attn"
            )
            is not None,
        ),
    )
    for metric in ("fec", "crc", "hec", "es", "ses", "rxmt", "rxmt_corr", "rxmt_uncorr"):
        XDSL_SENSORS += (
            FreeboxSensorEntityDescription(
                key=f"xdsl_{direction}_{metric}",
                name=f"xDSL {direction} {metric.replace('_', ' ').upper()}",
                icon="mdi:counter",
                state_class=SensorStateClass.MEASUREMENT,
                value_fn=lambda data, direction=direction, metric=metric: _path(
                    _result(data, "xdsl"), direction, metric
                ),
                exists_fn=lambda data, direction=direction, metric=metric: _path(
                    _result(data, "xdsl"), direction, metric
                )
                is not None,
            ),
        )

PORT_SENSOR_TYPES: tuple[FreeboxPortSensorEntityDescription, ...] = (
    FreeboxPortSensorEntityDescription(
        key="speed",
        name="speed",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda port, stats: int(port["speed"]) if port.get("speed") else None,
    ),
    FreeboxPortSensorEntityDescription(
        key="mode",
        name="mode",
        icon="mdi:ethernet-cable",
        value_fn=lambda port, stats: port.get("mode"),
    ),
    FreeboxPortSensorEntityDescription(
        key="duplex",
        name="duplex",
        icon="mdi:swap-horizontal",
        value_fn=lambda port, stats: port.get("duplex"),
    ),
    FreeboxPortSensorEntityDescription(
        key="learned_mac_count",
        name="learned MAC count",
        icon="mdi:counter",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda port, stats: _mac_count(port),
        attrs_fn=lambda port, stats: {
            "mac_list": port.get("mac_list", []),
        },
    ),
    FreeboxPortSensorEntityDescription(
        key="rx_rate",
        name="RX rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda port, stats: _mbit_from_bytes_per_second(
            (stats or {}).get("rx_bytes_rate")
        ),
    ),
    FreeboxPortSensorEntityDescription(
        key="tx_rate",
        name="TX rate",
        native_unit_of_measurement=UnitOfDataRate.MEGABITS_PER_SECOND,
        device_class=SensorDeviceClass.DATA_RATE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=3,
        value_fn=lambda port, stats: _mbit_from_bytes_per_second(
            (stats or {}).get("tx_bytes_rate")
        ),
    ),
    FreeboxPortSensorEntityDescription(
        key="rx_bytes",
        name="RX bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda port, stats: (stats or {}).get("rx_good_bytes"),
    ),
    FreeboxPortSensorEntityDescription(
        key="tx_bytes",
        name="TX bytes",
        native_unit_of_measurement=UnitOfInformation.BYTES,
        device_class=SensorDeviceClass.DATA_SIZE,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda port, stats: (stats or {}).get("tx_bytes"),
    ),
    FreeboxPortSensorEntityDescription(
        key="rx_packets",
        name="RX packets",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda port, stats: (stats or {}).get("rx_good_packets"),
    ),
    FreeboxPortSensorEntityDescription(
        key="tx_packets",
        name="TX packets",
        icon="mdi:counter",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda port, stats: (stats or {}).get("tx_packets"),
    ),
    FreeboxPortSensorEntityDescription(
        key="rx_errors",
        name="RX errors",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda port, stats: (stats or {}).get("rx_err_packets"),
    ),
    FreeboxPortSensorEntityDescription(
        key="tx_errors",
        name="TX errors",
        icon="mdi:alert-circle-outline",
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda port, stats: _tx_error_count(stats),
    ),
)

PORT_STAT_COUNTERS: tuple[tuple[str, str], ...] = (
    ("rx_bad_bytes", "RX bad bytes"),
    ("rx_discard_packets", "RX discard packets"),
    ("rx_jabber_packets", "RX jabber packets"),
    ("rx_fragments_packets", "RX fragments packets"),
    ("rx_filtered_packets", "RX filtered packets"),
    ("rx_oversize_packets", "RX oversize packets"),
    ("rx_undersize_packets", "RX undersize packets"),
    ("rx_unicast_packets", "RX unicast packets"),
    ("rx_multicast_packets", "RX multicast packets"),
    ("rx_broadcast_packets", "RX broadcast packets"),
    ("rx_fcs_packets", "RX FCS packets"),
    ("rx_pause", "RX pause frames"),
    ("tx_unicast_packets", "TX unicast packets"),
    ("tx_multicast_packets", "TX multicast packets"),
    ("tx_broadcast_packets", "TX broadcast packets"),
    ("tx_collisions", "TX collisions"),
    ("tx_late", "TX late collisions"),
    ("tx_filtered_packets", "TX filtered packets"),
    ("tx_multiple", "TX multiple collisions"),
    ("tx_fcs", "TX FCS errors"),
    ("tx_single", "TX single collisions"),
    ("tx_excessive", "TX excessive collisions"),
    ("tx_deferred", "TX deferred packets"),
    ("tx_pause", "TX pause frames"),
)

for stat_key, stat_name in PORT_STAT_COUNTERS:
    PORT_SENSOR_TYPES += (
        FreeboxPortSensorEntityDescription(
            key=stat_key,
            name=stat_name,
            icon="mdi:counter",
            state_class=SensorStateClass.TOTAL_INCREASING,
            value_fn=lambda port, stats, stat_key=stat_key: (stats or {}).get(stat_key),
        ),
    )

PORT_SENSOR_TYPES += (
    FreeboxPortSensorEntityDescription(
        key="rx_packets_rate",
        name="RX packets rate",
        native_unit_of_measurement="packets/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda port, stats: (stats or {}).get("rx_packets_rate"),
    ),
    FreeboxPortSensorEntityDescription(
        key="tx_packets_rate",
        name="TX packets rate",
        native_unit_of_measurement="packets/s",
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda port, stats: (stats or {}).get("tx_packets_rate"),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Freebox sensors."""
    runtime: FreeboxRuntimeData = entry.runtime_data
    coordinator = runtime.coordinator
    entities: list[SensorEntity] = [
        FreeboxSensor(coordinator, description)
        for description in (*CONNECTION_SENSORS, *FTTH_SENSORS, *XDSL_SENSORS)
    ]

    for port in coordinator.switch_ports():
        port_id = int(port["id"])
        for description in PORT_SENSOR_TYPES:
            entities.append(FreeboxPortSensor(coordinator, port_id, description))

    async_add_entities(entities)


class FreeboxSensor(FreeboxBaseEntity, SensorEntity):
    """A Freebox metric sensor."""

    entity_description: FreeboxSensorEntityDescription

    def __init__(
        self,
        coordinator,
        description: FreeboxSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{coordinator.device_uid}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return super().available and self.entity_description.exists_fn(self.coordinator.data or {})

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        return self.entity_description.value_fn(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        return self.entity_description.attrs_fn(self.coordinator.data or {})


class FreeboxPortSensor(FreeboxBaseEntity, SensorEntity):
    """A Freebox switch port metric sensor."""

    entity_description: FreeboxPortSensorEntityDescription

    def __init__(
        self,
        coordinator,
        port_id: int,
        description: FreeboxPortSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator)
        port = coordinator.port_by_id(port_id) or {"name": f"Port {port_id}"}
        self.port_id = port_id
        self.entity_description = description
        self._attr_name = f"{port.get('name', f'Port {port_id}')} {description.name}"
        self._attr_unique_id = f"{coordinator.device_uid}_port_{port_id}_{description.key}"

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        port = self.coordinator.port_by_id(self.port_id)
        return super().available and port is not None

    @property
    def native_value(self) -> StateType:
        """Return the sensor value."""
        port = self.coordinator.port_by_id(self.port_id)
        if port is None:
            return None
        return self.entity_description.value_fn(
            port,
            self.coordinator.port_stats_by_id(self.port_id),
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes."""
        port = self.coordinator.port_by_id(self.port_id)
        if port is None:
            return None
        attrs = self.entity_description.attrs_fn(
            port,
            self.coordinator.port_stats_by_id(self.port_id),
        )
        return {
            ATTR_PORT_ID: self.port_id,
            ATTR_PORT_NAME: port.get("name"),
            **(attrs or {}),
        }
