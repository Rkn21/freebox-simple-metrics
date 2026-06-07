"""Constants for Freebox Simple Metrics."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "freebox_simple_metrics"
PLATFORMS = [Platform.SENSOR, Platform.BINARY_SENSOR]

DEFAULT_NAME = "Freebox Simple Metrics"
DEFAULT_HOST = "192.168.1.254"
DEFAULT_SCAN_INTERVAL = 30
DEFAULT_TIMEOUT = 10
DEFAULT_APP_ID = "fr.rkn21.freebox_simple_metrics"
APP_NAME = "Freebox Simple Metrics"
APP_VERSION = "1.0.4"

CONF_APP_ID = "app_id"
CONF_APP_TOKEN = "app_token"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_TIMEOUT = "timeout"
CONF_TRACK_ID = "track_id"

ATTR_PORT_ID = "port_id"
ATTR_PORT_NAME = "port_name"
