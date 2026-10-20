"""Constants for the Rheidon+ integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "rheidon"

CONF_BASE_URL = "base_url"

# The app hardcodes this host. https://api.rheidon-tech.com appears in the app as
# a fallback but does not respond, so plain HTTP is the only working option.
DEFAULT_BASE_URL = "http://8.211.24.170:7074"

SCAN_INTERVAL = timedelta(seconds=30)

# Device `status` values, from mapChargeRunStatus in the app.
STATUS_MAP: dict[int, str] = {
    1: "plugged",
    2: "charging",
    3: "unplugged",
    4: "fault",
    5: "emergency_stop",
    6: "discharging",
    7: "paused",
}
STATUS_CHARGING = 2

# Values accepted by /set/charge/modeType, mapped to translation keys.
MODE_MAP: dict[str, str] = {
    "Plug Now": "plug_now",
    "ECO": "eco",
    "MAX": "max",
    "Manual": "manual",
}

MIN_CHARGE_CURRENT = 6
