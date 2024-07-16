import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
    ConfigEntryNotReady
)
from homeassistant.exceptions import HomeAssistantError

from .const import (
    DOMAIN
)
from .coordinator                       import SermatecCoordinator
from .sermatec_inverter                 import Sermatec
from .sermatec_inverter.protocol_parser import SermatecProtocolParser
from .sermatec_inverter.exceptions      import *

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup switch entities."""

    coordinator: SermatecCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial_number                    = config_entry.data["serial"]
    smc_api : Sermatec               = hass.data[DOMAIN][config_entry.entry_id]["api"]
    available_switches               = smc_api.listSwitches()
    hass_switches                    = []

    for tag, switch in available_switches.items():
        hass_switches.append(
            SermatecSwitch(
                coordinator,
                serial_number,
                tag,
                switch,
            )
        )

    async_add_entities(hass_switches)


class SermatecSwitch(CoordinatorEntity, SwitchEntity):
    """Base switch entity for integration"""

    def __init__(self, coordinator : SermatecCoordinator, serial_number : str, tag : str, switch_parameter : SermatecProtocolParser.SermatecSwitchParameter, id = None) -> None:
        super().__init__(coordinator)
        self.serial_number          = serial_number
        self._tag                   = tag
        self._switch_parameter      = switch_parameter
        self._attr_unique_id        = serial_number + (id if id else switch_parameter.statusTag)
        self._attr_has_entity_name  = True
        self._attr_name             = switch_parameter.name

    @property
    def device_info(self):
        return {
            "identifiers":{
                ("Sermatec", self.serial_number)
            },
            "name": "Solar Inverter",
            "manufacturer": "Sermatec",
            "model": "Residential Hybrid Inverter 5-10 kW"
        }
           
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self._switch_parameter.statusTag in self.coordinator.data:
            self._attr_available = True
            self._attr_is_on = self.coordinator.data[self._switch_parameter.statusTag]["value"] == 1
        else:
            self._attr_available = False
        self.async_write_ha_state()

    
    async def _set_switch(self, state : bool) -> None:
        if not "parameter_data" in self.coordinator.data:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_no_data_error") 
        
        if not await self.coordinator.smc_api.connect(version=self.coordinator.pcuVersion) or not self.coordinator.smc_api.isConnected():
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_connection_error")
        
        try:
            await self.coordinator.smc_api.set(self._tag, state, self.coordinator.data["parameter_data"])
        except (CommandNotFoundInProtocol, ProtocolFileMalformed, ParsingNotImplemented, CommunicationError, MissingTaggedData, ParameterNotFound, ValueError):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_set_error")
        except InverterIsNotOff:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "inverter_not_off")
        
        await self.coordinator.smc_api.disconnect()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._set_switch(False)
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._set_switch(True)
        