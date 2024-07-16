import logging
from typing import Any

from homeassistant.components.select import SelectEntity
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
    """Setup switch entities."""

    coordinator: SermatecCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial_number                    = config_entry.data["serial"]
    smc_api : Sermatec               = hass.data[DOMAIN][config_entry.entry_id]["api"]
    available_selects                = smc_api.listSelects()
    hass_selects                     = []

    for tag, select in available_selects.items():
        hass_selects.append(
            SermatecSelect(
                coordinator,
                serial_number,
                tag,
                select,
            )
        )

    async_add_entities(hass_selects)


class SermatecSelect(CoordinatorEntity, SelectEntity):
    """Base select entity for integration"""

    def __init__(self, coordinator : SermatecCoordinator, serial_number : str, tag : str, select_parameter : SermatecProtocolParser.SermatecSelectParameter, id = None) -> None:
        super().__init__(coordinator)
        self.serial_number          = serial_number
        self._tag                   = tag
        self._select_parameter      = select_parameter
        self._attr_unique_id        = serial_number + (id if id else select_parameter.statusTag)
        self._attr_has_entity_name  = True
        self._attr_name             = select_parameter.name
        self._attr_options          = select_parameter.converter.listFriendly()

        # This line is needed for HA to not throw AttributeError.
        self._attr_current_option   = None
        # This line is needed to make sure the entity is unavailable until it is updated
        # from the None state set above by the coordinator.
        self._attr_available        = False
        

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

    async def async_select_option(self, option: str) -> None:
        if not "parameter_data" in self.coordinator.data:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_no_data_error") 

        if not await self.coordinator.smc_api.connect(version=self.coordinator.pcuVersion) or not self.coordinator.smc_api.isConnected():
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_connection_error")

        try:
            await self.coordinator.smc_api.set(self._tag, option, self.coordinator.data["parameter_data"])
        except (CommandNotFoundInProtocol, ProtocolFileMalformed, ParsingNotImplemented, CommunicationError, MissingTaggedData, ParameterNotFound, ValueError):
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "param_set_error")
        except InverterIsNotOff:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key = "inverter_not_off")

        await self.coordinator.smc_api.disconnect()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self._select_parameter.statusTag in self.coordinator.data:
            self._attr_current_option = self.coordinator.data[self._select_parameter.statusTag]["value"]
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()
        