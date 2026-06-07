"""Diagnostics for Freebox Simple Metrics."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_APP_TOKEN


TO_REDACT = {CONF_APP_TOKEN}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    data = dict(config_entry.data)
    for key in TO_REDACT:
        if key in data:
            data[key] = "**REDACTED**"

    runtime = config_entry.runtime_data
    coordinator_data = runtime.coordinator.data or {}
    return {
        "entry": {
            "title": config_entry.title,
            "data": data,
            "options": dict(config_entry.options),
        },
        "api": coordinator_data.get("api"),
        "endpoint_status": {
            key: {
                "ok": value.get("ok"),
                "error": value.get("error"),
            }
            for key, value in coordinator_data.items()
            if isinstance(value, dict) and "ok" in value
        },
        "summary": coordinator_data.get("summary"),
    }
