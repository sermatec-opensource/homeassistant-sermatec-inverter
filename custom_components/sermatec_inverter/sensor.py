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
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT
)

# API module.
from .sermatec_inverter import Sermatec

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

# Set up the sensor platform from a config entry.
async def async_setup_entry(
    hass                : HomeAssistant,
    config_entry        : ConfigEntry,
    async_add_entities  : Callable
) -> None:
    
    smc_api = hass.data[DOMAIN][config_entry.entry_id]
    coordinator = SermatecCoordinator(hass, smc_api)
    
    # await coordinator.async_config_entry_first_refresh()
    serial_number = config_entry.data["serial"]
    
    for i in range(3):
        connection_status = await smc_api.connect()
        if connection_status:
            break
    
    if not connection_status:
        raise ConfigEntryNotReady("Timeout setting up inverter!")

    available_sensors = await smc_api.listSensors()

    hass_sensors = []
    for key, val in available_sensors.items():
        if "device_class" in val:
            sensor_device_class = val["device_class"]
        else:
            sensor_device_class = ""
        
        if "unit" in val:
            sensor_unit = val["unit"]
        else:
            sensor_unit = ""

        hass_sensors.append(
            SermatecSensor(
                coordinator,
                serial_number,
                dict_key=key,
                name=key,
                device_class=sensor_device_class,
                unit=sensor_unit
            )
        )

    async_add_entities(hass_sensors, True)

   
class SermatecCoordinator(DataUpdateCoordinator):
    """Inverter data coordinator."""

    def __init__(self, hass : HomeAssistant, smc_api : Sermatec):
        """Coordinator initialization."""
        super().__init__(
            hass,
            _LOGGER,
            name = "Sermatec",
            update_interval = timedelta(seconds = 30),
        )
        self.smc_api = smc_api

    async def _async_update_data(self):
        """Fetch data from inverter."""

        retries : int = 3
        while not await self.smc_api.connect() and retries > 0:
            await asyncio.sleep(0.5)
            retries -= 1

        if not self.smc_api.isConnected():
            raise UpdateFailed(f"Can't connect to the inverter.")

        await self.smc_api.disconnect()

        return {
            "serial": ":)"
        }

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
        self._attr_native_value = self.coordinator.data[self.dict_key]
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
        data = self.coordinator.data[self.dict_key]
        self._attr_native_value = data if data > 0 else 0
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
        data = self.coordinator.data[self.dict_key]
        self._attr_native_value = abs(data) if data < 0 else 0
        self.async_write_ha_state()

class SermatecPositivePowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for calculating power from voltage
    and current and tracking only positive value.
    """

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        data = self.coordinator.data[self.dict_key["voltage"]] * self.coordinator.data[self.dict_key["current"]]
        self._attr_native_value = data if data > 0 else 0
        self.async_write_ha_state()

class SermatecNegativePowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for calculating power from voltage
    and current and tracking only positive value.
    """

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        data = self.coordinator.data[self.dict_key["voltage"]] * self.coordinator.data[self.dict_key["current"]]
        self._attr_native_value = abs(data) if data < 0 else 0
        self.async_write_ha_state()

class SermatecBatteryChargingPowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for battery charging power from current and voltage,
    if actual battery_state is different "charging" return 0
    value should always be negative for charging
    ref: https://community.home-assistant.io/t/howto-fronius-integration-with-battery-into-energy-dashboard/376329
    """

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        data = self.coordinator.data[self.dict_key["voltage"]] * self.coordinator.data[self.dict_key["current"]] if self.coordinator.data["battery_state"] == "charging" else 0
        self._attr_native_value = abs(data)
        self.async_write_ha_state()

class SermatecBatteryDischargingPowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for battery discharging power from current and voltage,
    if actual battery_state is different "discharging" return 0
    value should always be positive for discharging
    ref: https://community.home-assistant.io/t/howto-fronius-integration-with-battery-into-energy-dashboard/376329
    """

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        data = self.coordinator.data[self.dict_key["voltage"]] * self.coordinator.data[self.dict_key["current"]] if self.coordinator.data["battery_state"] == "discharging" else 0
        self._attr_native_value = abs(data)
        self.async_write_ha_state()

class SermatecPVTotalPowerSensor(SermatecSensor):
    """
    Special Sermatec sensor for calculating total PV power.
    """

    def __init__(self, coordinator, serial_number, dict_key, name, id = None, device_class = None, unit = None):
        super().__init__(coordinator, serial_number, dict_key, name, id, device_class, unit)

    @callback
    def _handle_coordinator_update(self) -> None:
        """Handle data from the coordinator."""
        self._attr_native_value = self.coordinator.data[self.dict_key["pv1"]] + self.coordinator.data[self.dict_key["pv2"]]
        self.async_write_ha_state()
