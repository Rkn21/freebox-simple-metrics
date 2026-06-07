"""Entity helpers for Freebox Simple Metrics."""

from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import FreeboxMetricsCoordinator


class FreeboxBaseEntity(CoordinatorEntity[FreeboxMetricsCoordinator]):
    """Base entity for Freebox Simple Metrics."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FreeboxMetricsCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
