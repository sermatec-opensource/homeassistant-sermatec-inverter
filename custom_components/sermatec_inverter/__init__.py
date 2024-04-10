"""The Sermatec Inverter integration."""
from __future__ import annotations

import asyncio
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import (
    ConfigEntryNotReady
)

from .const import DOMAIN
from .coordinator import SermatecCoordinator
from .sermatec_inverter import Sermatec

PLATFORMS: list[Platform] = [Platform.SENSOR, Platform.SWITCH, Platform.BINARY_SENSOR]
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
    
    smc_api = Sermatec(
        entry.data['host'],
        entry.data['port'],
        language=entry.data["language"]
    )

    _LOGGER.info("Getting inverter version...")
    retries : int = 3
    while not await smc_api.connect() and retries > 0:
        await asyncio.sleep(2)
        retries -= 1

    if not smc_api.isConnected():
        raise ConfigEntryNotReady(f"Can't get inverter version - can't connect to the inverter.")
    elif smc_api.pcuVersion == 0:
        raise ConfigEntryNotReady(f"Inverted did not return version.")

    await smc_api.disconnect()

    # Storing a coordinator, API and PCU version to be used by platforms.
    hass.data[DOMAIN][entry.entry_id]                = {}
    hass.data[DOMAIN][entry.entry_id]["coordinator"] = SermatecCoordinator(hass, smc_api, smc_api.pcuVersion)
    hass.data[DOMAIN][entry.entry_id]["api"]         = smc_api
    hass.data[DOMAIN][entry.entry_id]["pcu_version"] = smc_api.pcuVersion
    
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
