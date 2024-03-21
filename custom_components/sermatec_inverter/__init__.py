"""The Sermatec Inverter integration."""
from __future__ import annotations

import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .const import DOMAIN

from .sermatec_inverter import Sermatec

PLATFORMS: list[Platform] = [Platform.SENSOR]
_LOGGER = logging.getLogger(__name__)

# Name space preparation.
async def async_setup(hass: HomeAssistant, config: dict):
    # A dict is common/preferred as it allows a separate instance of the class for each
    # instance that has been created in the UI.
    hass.data.setdefault(DOMAIN, {})

    return True

# Prepare API and set up platforms.
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up sermatec from a config entry."""
    
    # Storing an API to use by platforms.
    hass.data[DOMAIN][entry.entry_id] = Sermatec(
        entry.data['host'],
        entry.data['port']
    )
    
    # This creates each HA object for each platform (sensor, button...) the integration requires.
    # It's done by calling the `async_setup_entry` function in each platform module.
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

# Unload integration instance
async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        hass.data[DOMAIN].pop(entry.entry_id)

    return unload_ok
