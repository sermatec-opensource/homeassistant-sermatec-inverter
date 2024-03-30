import asyncio
from datetime import timedelta
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
    ConfigEntryNotReady
)

# API module.
from .sermatec_inverter import Sermatec
from .sermatec_inverter.exceptions import *

_LOGGER = logging.getLogger(__name__)

class SermatecCoordinator(DataUpdateCoordinator):
    """Inverter data coordinator."""

    def __init__(self, hass : HomeAssistant, smc_api : Sermatec, pcuVersion : int):
        """Coordinator initialization."""
        super().__init__(
            hass,
            _LOGGER,
            name = "Sermatec",
            update_interval = timedelta(seconds = 30),
        )
        self.smc_api = smc_api
        self.pcuVersion = pcuVersion
        self.first_time_update = True

    async def _async_update_data(self):
        """Fetch data from inverter."""

        # Because loading data from the inverter takes a very long time,
        # skipping the update on integration load -> to not obstruct Home Assistant from loading.
        if self.first_time_update:
            self.first_time_update = False
            return {}
        
        _LOGGER.info("Fetching data from inverter...")
        retries : int = 3
        while not await self.smc_api.connect(version=self.pcuVersion) and retries > 0:
            await asyncio.sleep(2)
            retries -= 1

        if not self.smc_api.isConnected():
            raise UpdateFailed(f"Can't connect to the inverter.")

        query_cmds = self.smc_api.getQueryCommands()
        coordinator_data = {}
        # Here we don't attempt to retry -- the API script has
        # retry mechanism built-in.
        for cmd in query_cmds:
            try:
                response = await self.smc_api.getCustom(cmd)
            except (NoDataReceived, FailedResponseIntegrityCheck):
                pass
            except (NotConnected, ConnectionResetError):
                await asyncio.sleep(5)
                await self.smc_api.connect(version=self.pcuVersion)
            else:
                coordinator_data.update(response)

        await self.smc_api.disconnect()

        if not coordinator_data:
            raise UpdateFailed(f"Can't update any values.")

        _LOGGER.info("Data fetched!")

        return coordinator_data
    
    async def async_config_entry_first_refresh(self) -> None:
        return