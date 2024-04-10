import logging
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorEntity, BinarySensorDeviceClass
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
from .sermatec_inverter import Sermatec

_LOGGER = logging.getLogger(__name__)

def _smc_convert_binary_device_class(device_class : str | None):
    if device_class:
        return BinarySensorDeviceClass[device_class]
    else:
        return None
    
async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities: AddEntitiesCallback) -> None:
    """Setup switch entities."""

    coordinator : SermatecCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    serial_number                     = config_entry.data["serial"]
    smc_api     : Sermatec            = hass.data[DOMAIN][config_entry.entry_id]["api"]
    pcu_version : int                 = hass.data[DOMAIN][config_entry.entry_id]["pcu_version"]
    
    hass_binary_sensors = []

    for key, val in smc_api.listBinarySensors(pcuVersion=pcu_version).items():
        if "device_class" in val:
            sensor_device_class = val["device_class"]
        else:
            sensor_device_class = None

        hass_binary_sensors.append(
            SermatecBinarySensor(
                coordinator,
                serial_number,
                key,
                val["name"],
                _smc_convert_binary_device_class(sensor_device_class)
            )
        )

    async_add_entities(hass_binary_sensors)

class SermatecBinarySensor(CoordinatorEntity, BinarySensorEntity):
    
    def __init__(self, coordinator : SermatecCoordinator, serial_number : str, dict_status_key : str, name : str, device_class : BinarySensorDeviceClass, id = None) -> None:
        super().__init__(coordinator)
        self.dict_status_key        = dict_status_key
        self.serial_number          = serial_number
        self._attr_unique_id        = serial_number + (id if id else dict_status_key)
        self._attr_has_entity_name  = True
        self._attr_name             = name
        self._attr_device_class     = device_class

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
    def is_on(self) -> bool:
        if self.coordinator.data and self.dict_status_key in self.coordinator.data:
            self._attr_available = True
            return self.coordinator.data[self.dict_status_key]["value"] == 1
        else:
            self._attr_available = True
            return False
