"""Config flow for Freebox Simple Metrics."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import FreeboxApiClient, FreeboxAuthError, FreeboxConnectionError, FreeboxError
from .const import (
    APP_NAME,
    APP_VERSION,
    CONF_APP_ID,
    CONF_APP_TOKEN,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_TRACK_ID,
    DEFAULT_APP_ID,
    DEFAULT_HOST,
    DEFAULT_NAME,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


SCAN_INTERVAL_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=5,
        max=3600,
        step=1,
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="s",
    )
)

TIMEOUT_SELECTOR = selector.NumberSelector(
    selector.NumberSelectorConfig(
        min=2,
        max=60,
        step=1,
        mode=selector.NumberSelectorMode.BOX,
        unit_of_measurement="s",
    )
)


class FreeboxSimpleMetricsConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Freebox Simple Metrics."""

    VERSION = 1

    def __init__(self) -> None:
        self._pending_data: dict[str, Any] = {}
        self._pending_client: FreeboxApiClient | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            app_token = str(user_input.get(CONF_APP_TOKEN) or "").strip()
            app_id = str(user_input.get(CONF_APP_ID) or DEFAULT_APP_ID).strip()
            client = FreeboxApiClient(
                async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
                app_id=app_id,
                app_token=app_token or None,
                timeout=user_input[CONF_TIMEOUT],
            )

            try:
                discovery = await client.discover()
                uid = str(discovery.get("uid") or client.host)
                await self.async_set_unique_id(uid)
                self._abort_if_unique_id_configured()
            except FreeboxConnectionError:
                _LOGGER.debug("Freebox discovery failed", exc_info=True)
                errors["base"] = "cannot_connect"
            except FreeboxError:
                _LOGGER.debug("Freebox discovery failed", exc_info=True)
                errors["base"] = "unknown"
            else:
                data = {
                    CONF_HOST: user_input[CONF_HOST],
                    CONF_NAME: user_input[CONF_NAME],
                    CONF_SCAN_INTERVAL: user_input[CONF_SCAN_INTERVAL],
                    CONF_TIMEOUT: user_input[CONF_TIMEOUT],
                    CONF_APP_ID: app_id,
                }

                if app_token:
                    client.app_token = app_token
                    try:
                        await client.probe_authenticated()
                    except FreeboxAuthError:
                        _LOGGER.debug("Freebox app token rejected", exc_info=True)
                        errors["base"] = "invalid_auth"
                    except FreeboxError:
                        _LOGGER.debug("Freebox authenticated probe failed", exc_info=True)
                        errors["base"] = "cannot_connect"
                    else:
                        return self.async_create_entry(
                            title=user_input[CONF_NAME],
                            data={**data, CONF_APP_TOKEN: app_token},
                        )
                else:
                    try:
                        authorization = await client.request_authorization(
                            app_name=APP_NAME,
                            app_version=APP_VERSION,
                            device_name="Home Assistant",
                        )
                    except FreeboxAuthError:
                        _LOGGER.debug("Freebox authorization refused", exc_info=True)
                        errors["base"] = "invalid_auth"
                    except FreeboxError:
                        _LOGGER.debug("Freebox authorization request failed", exc_info=True)
                        errors["base"] = "cannot_connect"
                    else:
                        self._pending_client = client
                        self._pending_data = {
                            **data,
                            CONF_APP_TOKEN: authorization[CONF_APP_TOKEN],
                            CONF_TRACK_ID: authorization[CONF_TRACK_ID],
                        }
                        return await self.async_step_authorize()

        return self.async_show_form(
            step_id="user",
            data_schema=self._user_schema(),
            errors=errors,
        )

    async def async_step_authorize(
        self,
        user_input: dict[str, Any] | None = None,
    ) -> FlowResult:
        """Wait for physical validation on the Freebox Server."""
        errors: dict[str, str] = {}
        placeholders = {
            "track_id": self._pending_data.get(CONF_TRACK_ID, ""),
            "host": self._pending_data.get(CONF_HOST, ""),
        }

        if user_input is not None:
            client = self._pending_client
            if client is None:
                return self.async_abort(reason="reauth_required")

            try:
                status = await client.check_authorization(self._pending_data[CONF_TRACK_ID])
            except FreeboxError:
                _LOGGER.debug("Freebox authorization status check failed", exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                state = status.get("status")
                if state == "granted":
                    client.app_token = self._pending_data[CONF_APP_TOKEN]
                    try:
                        await client.probe_authenticated()
                    except FreeboxError:
                        _LOGGER.debug("Freebox session opening failed after grant", exc_info=True)
                        errors["base"] = "cannot_connect"
                    else:
                        return self.async_create_entry(
                            title=self._pending_data[CONF_NAME],
                            data=self._pending_data,
                        )
                elif state in {"denied", "timeout"}:
                    return self.async_abort(reason=state)
                else:
                    errors["base"] = "pending"

        return self.async_show_form(
            step_id="authorize",
            data_schema=vol.Schema({}),
            errors=errors,
            description_placeholders=placeholders,
        )

    def _user_schema(self) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): SCAN_INTERVAL_SELECTOR,
                vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): TIMEOUT_SELECTOR,
                vol.Optional(CONF_APP_ID, default=DEFAULT_APP_ID): str,
                vol.Optional(CONF_APP_TOKEN): str,
            }
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> "FreeboxOptionsFlow":
        """Create the options flow."""
        return FreeboxOptionsFlow()


class FreeboxOptionsFlow(config_entries.OptionsFlowWithReload):
    """Handle Freebox Simple Metrics options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            client = FreeboxApiClient(
                async_get_clientsession(self.hass),
                host=user_input[CONF_HOST],
                app_id=self.config_entry.data.get(CONF_APP_ID, DEFAULT_APP_ID),
                app_token=self.config_entry.data[CONF_APP_TOKEN],
                timeout=user_input[CONF_TIMEOUT],
            )
            try:
                await client.probe_authenticated()
            except FreeboxError:
                _LOGGER.debug("Freebox options probe failed", exc_info=True)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(data=user_input)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=DEFAULT_HOST): str,
                vol.Required(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): SCAN_INTERVAL_SELECTOR,
                vol.Required(CONF_TIMEOUT, default=DEFAULT_TIMEOUT): TIMEOUT_SELECTOR,
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=self.add_suggested_values_to_schema(
                options_schema,
                {
                    CONF_HOST: self.config_entry.options.get(
                        CONF_HOST,
                        self.config_entry.data[CONF_HOST],
                    ),
                    CONF_SCAN_INTERVAL: self.config_entry.options.get(
                        CONF_SCAN_INTERVAL,
                        self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    ),
                    CONF_TIMEOUT: self.config_entry.options.get(
                        CONF_TIMEOUT,
                        self.config_entry.data.get(CONF_TIMEOUT, DEFAULT_TIMEOUT),
                    ),
                },
            ),
            errors=errors,
        )
