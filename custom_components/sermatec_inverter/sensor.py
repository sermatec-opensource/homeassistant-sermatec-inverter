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
)
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
import homeassistant.helpers.config_validation as cv
from homeassistant.const import (
    CONF_IP_ADDRESS,
    CONF_PORT
)

# API module.
from sermatec_inverter import Sermatec

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

    sensors = [
        SermatecSerialSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_SOC",
            name            = "Battery SOC",
            device_class    = "battery",
            unit            = "%"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_SOH",
            name            = "Battery SOH",
            device_class    = "battery",
            unit            = "%"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_voltage",
            name            = "Battery voltage",
            device_class    = "voltage",
            unit            = "V"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_current",
            name            = "Battery current",
            device_class    = "current",
            unit            = "A"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_temperature",
            name            = "Battery temperature",
            device_class    = "temperature",
            unit            = "°C"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_state",
            name            = "Battery state",
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_max_charging_current",
            name            = "Battery max charging current",
            device_class    = "current",
            unit            = "A"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "battery_max_discharging_current",
            name            = "Battery max discharging current",
            device_class    = "current",
            unit            = "A"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "pv1_voltage",
            name            = "PV1 voltage",
            device_class    = "voltage",
            unit            = "V"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "pv1_current",
            name            = "PV1 current",
            device_class    = "current",
            unit            = "A"
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "pv1_power",
            name            = "PV1 power",
            device_class    = "power",
            unit            = "W" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "pv2_voltage",
            name            = "PV2 voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "pv2_current",
            name            = "PV2 current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "pv2_power",
            name            = "PV2 power",
            device_class    = "power",
            unit            = "W" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "ab_line_voltage",
            name            = "AB line voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "a_phase_current",
            name            = "A phase current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "a_phase_voltage",
            name            = "A phase voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "bc_line_voltage",
            name            = "BC line voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "b_phase_current",
            name            = "B phase current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "b_phase_voltage",
            name            = "B phase voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "c_phase_voltage",
            name            = "C phase voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "ca_line_voltage",
            name            = "CA line voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "c_phase_current",
            name            = "C phase current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "grid_frequency",
            name            = "Grid frequency",
            device_class    = "frequency",
            unit            = "Hz" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "grid_active_power",
            name            = "Grid active power",
            device_class    = "power",
            unit            = "W" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "grid_reactive_power",
            name            = "Grid reactive power",
            device_class    = "reactive_power",
            unit            = "var" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "grid_apparent_power",
            name            = "Grid apparent power",
            device_class    = "apparent_power",
            unit            = "VA" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_frequency",
            name            = "Backup frequency",
            device_class    = "frequency",
            unit            = "Hz" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_active_power",
            name            = "Backup active power",
            device_class    = "power",
            unit            = "W" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_reactive_power",
            name            = "Backup reactive power",
            device_class    = "reactive_power",
            unit            = "var" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_apparent_power",
            name            = "Backup apparent power",
            device_class    = "apparent_power",
            unit            = "VA" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_a_phase_voltage",
            name            = "Backup A phase voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_b_phase_voltage",
            name            = "Backup B phase voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_c_phase_voltage",
            name            = "Backup C phase voltage",
            device_class    = "voltage",
            unit            = "V" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_a_phase_current",
            name            = "Backup A phase current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_b_phase_current",
            name            = "Backup B phase current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "backup_c_phase_current",
            name            = "Backup C phase current",
            device_class    = "current",
            unit            = "A" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "upper_limit_ongrid_power",
            name            = "Upper limit of on-grid power",
            device_class    = "power",
            unit            = "W" 
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "working_mode",
            name            = "Inverter working mode",
        ),
        SermatecSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = "lower_limit_ongrid_soc",
            name            = "Battery on-grid min. SOC",
            device_class    = "battery",
            unit            = "%"
        ),
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
            dict_key        = {"voltage":"battery_voltage", "current":"battery_current"},
            name            = "Battery discharging power",
            id              = "battery_discharging_power",
            device_class    = "power",
            unit            = "W"
        ),
        SermatecBatteryChargingPowerSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = {"voltage":"battery_voltage", "current":"battery_current"},
            name            = "Battery charging power",
            id              = "battery_charging_power",
            device_class    = "power",
            unit            = "W"
        ),
        SermatecPVTotalPowerSensor(
            coordinator     = coordinator,
            serial_number   = serial_number,
            dict_key        = {"pv1":"pv1_power", "pv2":"pv2_power"},
            name            = "PV total power",
            id              = "pv_total_power",
            device_class    = "power",
            unit            = "W"  
        )
    ]

    async_add_entities(sensors, True)

   
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

        retries = 3
        while not (serial := await self.smc_api.getSerial()) and retries > 0:
            await asyncio.sleep(0.5)
            retries -= 1

        if not serial:
            raise UpdateFailed(f"Can't retrieve battery information.")

        retries = 3
        while not (battery := await self.smc_api.getBatteryInfo()) and retries > 0:
            await asyncio.sleep(0.5)
            retries -= 1

        if not battery:
            raise UpdateFailed(f"Can't retrieve battery information.")
        
        retries = 3
        while not (pvgrid := await self.smc_api.getGridPVInfo()) and retries > 0:
            await asyncio.sleep(0.5)
            retries -= 1

        if not pvgrid:
            raise UpdateFailed(f"Can't retrieve PV/grid information.")

        retries = 3
        while not (wpams := await self.smc_api.getWorkingParameters()) and retries > 0:
            await asyncio.sleep(0.5)
            retries -= 1

        if not wpams:
            raise UpdateFailed(f"Can't retrieve working parameters.")

        await self.smc_api.disconnect()

        return {
            "serial": serial,
            **battery,
            **pvgrid,
            **wpams
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
