"""Coordinator for Freebox Simple Metrics."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FreeboxApiClient, FreeboxError
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class FreeboxRuntimeData:
    """Runtime data stored on the config entry."""

    client: FreeboxApiClient
    coordinator: "FreeboxMetricsCoordinator"


class FreeboxMetricsCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Coordinate Freebox metrics polling."""

    def __init__(
        self,
        hass: HomeAssistant,
        *,
        client: FreeboxApiClient,
        name: str,
        update_interval: timedelta,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=name,
            update_interval=update_interval,
        )
        self.client = client
        self.device_uid = client.host
        self.box_name = name

    async def _async_setup(self) -> None:
        discovery = await self.client.discover()
        self.device_uid = str(discovery.get("uid") or self.client.host)
        self.box_name = str(discovery.get("device_name") or self.box_name)

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            data = await self.client.fetch_metrics()
        except FreeboxError as err:
            raise UpdateFailed(str(err)) from err

        if not data.get("connection", {}).get("ok"):
            error = data.get("connection", {}).get("error", {})
            raise UpdateFailed(error.get("message") or "Freebox connection endpoint failed")

        return data

    @property
    def device_info(self) -> DeviceInfo:
        """Return Home Assistant device information."""
        api = (self.data or {}).get("api", {})
        model = api.get("box_model_name") or api.get("box_model") or "Freebox"
        api_version = api.get("api_version")
        return DeviceInfo(
            identifiers={(DOMAIN, self.device_uid)},
            manufacturer="Free",
            name=api.get("device_name") or self.box_name,
            model=model,
            sw_version=f"Freebox OS API {api_version}" if api_version else None,
            configuration_url=api.get("origin"),
        )

    def switch_ports(self) -> list[dict[str, Any]]:
        """Return switch port status rows."""
        ports = self.data.get("switch_status", {}).get("data", []) if self.data else []
        if not isinstance(ports, list):
            return []
        return [port for port in ports if isinstance(port, dict) and "id" in port]

    def port_by_id(self, port_id: int) -> dict[str, Any] | None:
        """Return one switch port by id."""
        return next(
            (port for port in self.switch_ports() if int(port.get("id")) == port_id),
            None,
        )

    def port_stats_by_id(self, port_id: int) -> dict[str, Any] | None:
        """Return one switch port stats result by id."""
        stats = self.data.get("switch_port_stats", {}) if self.data else {}
        result = stats.get(port_id) or stats.get(str(port_id))
        if not isinstance(result, dict) or not result.get("ok"):
            return None
        data = result.get("data")
        return data if isinstance(data, dict) else None
