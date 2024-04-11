import logging
from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
    ConfigEntryNotReady
)

from .const import (
    DOMAIN
)
from .coordinator import SermatecCoordinator

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup switch entities."""

    coordinator: SermatecCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial_number                    = config_entry.data["serial"]

    hass_switches = [
        SermatecSwitch(
            coordinator,
            serial_number,
            "inverter_switched_on",
            "Power"
        )
    ]

    async_add_entities(hass_switches)


class SermatecSwitch(CoordinatorEntity, SwitchEntity):
    """Base switch entity for integration"""

    def __init__(self, coordinator : SermatecCoordinator, serial_number : str, dict_status_key : str, name : str, id = None) -> None:
        super().__init__(coordinator)
        self.dict_status_key        = dict_status_key
        self.serial_number          = serial_number
        self._attr_unique_id        = serial_number + (id if id else dict_status_key)
        self._attr_has_entity_name  = True
        self._attr_name             = name

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
    
    @property
    def is_on(self):
        """Return true if the switch is on."""
        if self.coordinator.data and self.dict_status_key in self.coordinator.data:
            self._attr_available = True
            return self.coordinator.data[self.dict_status_key]["value"] == 1
        else:
            self._attr_available = True
            return False
        
    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        # TODO implement

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the entity on."""
        # TODO implement
        