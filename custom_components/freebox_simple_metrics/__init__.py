"""Freebox Simple Metrics integration."""

from __future__ import annotations

from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FreeboxApiClient, FreeboxError
from .const import (
    CONF_APP_ID,
    CONF_APP_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    DEFAULT_APP_ID,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    PLATFORMS,
)
from .coordinator import FreeboxMetricsCoordinator, FreeboxRuntimeData


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Freebox Simple Metrics from a config entry."""
    client = FreeboxApiClient(
        async_get_clientsession(hass),
        host=entry.options.get(CONF_HOST, entry.data[CONF_HOST]),
        app_id=entry.data.get(CONF_APP_ID, DEFAULT_APP_ID),
        app_token=entry.data[CONF_APP_TOKEN],
        timeout=entry.options.get(CONF_TIMEOUT, entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)),
    )
    coordinator = FreeboxMetricsCoordinator(
        hass,
        client=client,
        name=entry.data.get(CONF_NAME, DEFAULT_NAME),
        update_interval=timedelta(
            seconds=entry.options.get(
                CONF_SCAN_INTERVAL,
                entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
            )
        ),
    )

    try:
        await coordinator.async_config_entry_first_refresh()
    except FreeboxError as err:
        raise ConfigEntryNotReady(str(err)) from err

    entry.runtime_data = FreeboxRuntimeData(client=client, coordinator=coordinator)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    runtime = entry.runtime_data
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        await runtime.client.close_session()
    return unload_ok
