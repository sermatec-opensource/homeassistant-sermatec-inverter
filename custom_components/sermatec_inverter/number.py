import logging
from typing import Any

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity
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
    """Setup number entities."""

    coordinator: SermatecCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial_number                    = config_entry.data["serial"]
    smc_api : Sermatec               = hass.data[DOMAIN][config_entry.entry_id]["api"]
    available_numbers                = smc_api.listNumbers()
    hass_numbers                     = []

    for tag, switch in available_numbers.items():
        hass_numbers.append(
            SermatecNumber(
                coordinator,
                serial_number,
                tag,
                switch,
            )
        )

    async_add_entities(hass_numbers)


class SermatecNumber(CoordinatorEntity, NumberEntity):
    """Base number entity for integration"""

    def __init__(self, coordinator : SermatecCoordinator, serial_number : str, tag : str, number_parameter : SermatecProtocolParser.SermatecNumberParamter, id = None) -> None:
        super().__init__(coordinator)
        self.serial_number          = serial_number
        self._tag                   = tag
        self._switch_parameter      = number_parameter
        self._attr_unique_id        = serial_number + (id if id else number_parameter.statusTag)
        self._attr_has_entity_name  = True
        self._attr_name             = number_parameter.name
        self._attr_native_min_value = number_parameter.min
        self._attr_native_max_value = number_parameter.max
        self._attr_native_step      = 1

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
            self._attr_native_value = self.coordinator.data[self._switch_parameter.statusTag]["value"]
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        if not "parameter_data" in self.coordinator.data:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_no_data_error") 
        
        if not await self.coordinator.smc_api.connect(version=self.coordinator.pcuVersion) or not self.coordinator.smc_api.isConnected():
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_connection_error")
        
        try:
            # WARNING, TODO: here I always convert to int. This is because no configurable float
            # parameters exists as of now, but this would need to be changed if there will be any.
            await self.coordinator.smc_api.set(self._tag, int(value), self.coordinator.data["parameter_data"])
        except (CommandNotFoundInProtocol, ProtocolFileMalformed, ParsingNotImplemented, CommunicationError, MissingTaggedData, ParameterNotFound, ValueError):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_set_error")
        except InverterIsNotOff:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "inverter_not_off")
        
        await self.coordinator.smc_api.disconnect()
