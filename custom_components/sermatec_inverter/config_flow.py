"""Config flow for sermatec integration."""
from __future__ import annotations
import logging
from typing import Any
import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.selector import selector

from .sermatec_inverter import Sermatec
from .sermatec_inverter.exceptions import *

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# TODO adjust the data schema to the data that you need
STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required("host"): str,
        vol.Optional("port", default="8899"): str,
        vol.Required("language"): selector({
            "select":{
                "options":["en", "cs", "fr"],
                "mode": "dropdown"
            }
        })
    }
)

# Try connect to the inverter and get its serial number.
async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """
    Validate the user input allows us to connect.
    Data has the keys from STEP_USER_DATA_SCHEMA with values provided by the user.
    """

    smc_api : Sermatec = Sermatec(
        data["host"],
        data["port"]
    )

    if not await smc_api.connect():
        raise CannotConnect
    
    try:
        serial = await smc_api.getSerial()
    except (ParsingNotImplemented, ProtocolFileMalformed, CommandNotFoundInProtocol):
        _LOGGER.error("Can't parse serial number. This error should not happen, please contact developer.")
        await smc_api.disconnect()
        raise CannotConnect
    except ConnectionResetError:
        _LOGGER.error("Inverter reset connnection!")
        await smc_api.disconnect()
        raise CannotConnect
    except CommunicationError:
        _LOGGER.error("Can't communicate with inverter!")
        await smc_api.disconnect()
        raise CannotConnect
    except NotConnected:
        _LOGGER.error("No connection to the inverter was made.")
        await smc_api.disconnect()
        raise CannotConnect

    await smc_api.disconnect()
    # Return info that you want to store in the config entry.
    return {
        "title": "Sermatec Inverter",
        "serial": serial
    }

# Configuration flow.
class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Sermatec Inverter."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=STEP_USER_DATA_SCHEMA
            )

        errors = {}

        try:
            info = await validate_input(self.hass, user_input)
        except CannotConnect:
            errors["base"] = "cannot_connect"
        except Exception:  # pylint: disable=broad-except
            _LOGGER.exception("Unexpected exception")
            errors["base"] = "unknown"
        else:
            return self.async_create_entry(title=info["title"], data={**user_input, "serial": info["serial"]})

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
