""""Sermatec sensor platform."""

# Generic modules.
import asyncio
from datetime import timedelta
import logging
import voluptuous as vol
from typing import Callable

# Hass modules.
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
    ConfigEntryNotReady
)
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity, SensorDeviceClass
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT
)

# API module.
from .sermatec_inverter import Sermatec
from .sermatec_inverter.exceptions import *

# Coordinator.
from .coordinator import SermatecCoordinator

# Constants.
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Configuration schema.
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_IP_ADDRESS): cv.string,
        vol.Required(CONF_PORT): cv.string
    }
)

def _smc_convert_device_class(device_class : str | None):
    if device_class:
        return SensorDeviceClass[device_class]
    else:
        return None

# Set up the sensor platform from a config entry.
async def async_setup_entry(
    hass                : HomeAssistant,
    config_entry        : ConfigEntry,
    async_add_entities  : Callable
) -> None:
    
    coordinator : SermatecCoordinator = hass.data[DOMAIN][config_entry.entry_id]["coordinator"]
    smc_api : Sermatec = hass.data[DOMAIN][config_entry.entry_id]["api"]
    pcu_version = hass.data[DOMAIN][config_entry.entry_id]["pcu_version"]

    serial_number = config_entry.data["serial"]
    
    available_sensors = smc_api.listSensors(pcuVersion=pcu_version)
    hass_sensors = []
    for key, val in available_sensors.items():
        if "device_class" in val:
            sensor_device_class = val["device_class"]
        else:
            sensor_device_class = None
        
        if "unit" in val:
            sensor_unit = val["unit"]
        else:
            sensor_unit = None

        hass_sensors.append(
            SermatecSensor(
                coordinator,
                serial_number,
                dict_key=key,
                name=val["name"],
                device_class=_smc_convert_device_class(sensor_device_class),
                unit=sensor_unit
            )
        )

    # Adding special sensors -- for convenience and usage with Energy dashboard.
    hass_sensors.extend([
        SermatecPositiveSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "grid_active_power",
            name            = "Grid export",
            id              = "grid_export",
            device_class    = "power",
            unit            = "W"   
        ),
        SermatecNegativeSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "grid_active_power",
            name            = "Grid import",
            id              = "grid_import",
            device_class    = "power",
            unit            = "W"
        ),
        SermatecBatteryDischargingPowerSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_power_key  = "dc_power",
            dict_status_key = "charge_and_discharge_status",
            name            = "Battery discharging power",
            id              = "battery_discharging_power",
            device_class    = "power",
            unit            = "W"
        ),
        SermatecBatteryChargingPowerSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_power_key  = "dc_power",
            dict_status_key = "charge_and_discharge_status",
            name            = "Battery charging power",
            id              = "battery_charging_power",
            device_class    = "power",
            unit            = "W"
        ),
        SermatecSumSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key_1      = "pv1_power",
            dict_key_2      = "pv2_power",
            name            = "PV total power",
            id              = "pv_total_power",
            device_class    = "power",
            unit            = "W"  
        )
    ])

    async_add_entities(hass_sensors, True)

class SermatecSensorBase(CoordinatorEntity, SensorEntity):
    """Standard Sermatec Inverter sensor."""
    
    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        
        super().__init__(coordinator)
        # Dict item key.
        self.dict_key                           = dict_key
        self.serial_number                      = serial_number
        self._attr_unique_id                    = serial_number + (id if id else dict_key)
        self._attr_native_unit_of_measurement   = unit
        # Not the main feature of a device = True.
        self._attr_has_entity_name              = True
        self._attr_name                         = name
        self._attr_device_class                 = device_class

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

class SermatecSensor(SermatecSensorBase):

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self.dict_key in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[self.dict_key]["value"]
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

class SermatecSerialSensor(SermatecSensorBase):
    """Special Sermatec sensor for storing serial as a main feature of the device."""
    
    def __init__(self, coordinator, serial_number):
        super().__init__(coordinator, serial_number, None, "Sermatec Solar Inverter", serial_number + "serial", None, None)
        self._attr_native_value = serial_number
        self._attr_icon = "mdi:solar-power"
        # Main feature of a device, so the value shall be False.
        self._attr_has_entity_name = False

class SermatecPositiveSensor(SermatecSensorBase):
    """
    Special Sermatec sensor for tracking only positive values.
    """
    
    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)
    
    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self.dict_key in self.coordinator.data:
            data = self.coordinator.data[self.dict_key]["value"]
            self._attr_native_value = data if data > 0 else 0
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

class SermatecNegativeSensor(SermatecSensor):
    """
    Special Sermatec sensor for tracking only negative values.
    """

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self.dict_key in self.coordinator.data:
            data = self.coordinator.data[self.dict_key]["value"]
            self._attr_native_value = abs(data) if data < 0 else 0
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

class SermatecBatteryChargingPowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for battery charging power from current and voltage,
    if actual battery_state is different "charging" return 0
    value should always be negative for charging
    ref: https://community.home-assistant.io/t/howto-fronius-integration-with-battery-into-energy-dashboard/376329
    """

    def __init__(self, coordinator, serial_number, dict_power_key, dict_status_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, None, name, id, device_class, unit)
        self.dict_power_key  = dict_power_key
        self.dict_status_key = dict_status_key

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self.dict_power_key in self.coordinator.data and self.dict_status_key in self.coordinator.data:
            data = self.coordinator.data[self.dict_power_key]["value"] if self.coordinator.data[self.dict_status_key]["value"] == "charging" else 0
            self._attr_native_value = abs(data)
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

class SermatecBatteryDischargingPowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for battery discharging power from current and voltage,
    if actual battery_state is different "discharging" return 0
    value should always be positive for discharging
    ref: https://community.home-assistant.io/t/howto-fronius-integration-with-battery-into-energy-dashboard/376329
    """

    def __init__(self, coordinator, serial_number, dict_power_key, dict_status_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, None, name, id, device_class, unit)
        self.dict_power_key  = dict_power_key
        self.dict_status_key = dict_status_key

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self.dict_power_key in self.coordinator.data and self.dict_status_key in self.coordinator.data:
            data = self.coordinator.data[self.dict_power_key]["value"] if self.coordinator.data[self.dict_status_key]["value"] == "discharging" else 0
            self._attr_native_value = abs(data)
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()

class SermatecSumSensor(SermatecSensor):
    """
    Special Sermatec sensor for calculating total PV power.
    """
    def __init__(self, coordinator, serial_number, dict_key_1, dict_key_2, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, None, name, id, device_class, unit)
        self.dict_key_1 = dict_key_1
        self.dict_key_2 = dict_key_2

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        if self.coordinator.data and self.dict_key_1 in self.coordinator.data and self.dict_key_2 in self.coordinator.data:
            self._attr_native_value = self.coordinator.data[self.dict_key_1]["value"] + self.coordinator.data[self.dict_key_2]["value"]
            self._attr_available = True
        else:
            self._attr_available = False
        self.async_write_ha_state()
