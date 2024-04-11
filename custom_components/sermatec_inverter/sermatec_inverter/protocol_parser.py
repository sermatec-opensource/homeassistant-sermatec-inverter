import logging
import json
import re
from typing import Any, Callable
from .exceptions import *
from pathlib import Path

# Local module logger.
logger = logging.getLogger(__name__)

class SermatecProtocolParser:

    REPLY_OFFSET_DATA = 7
    
    REQ_SIGNATURE           = bytes([0xfe, 0x55])
    REQ_APP_ADDRESS         = bytes([0x64])
    REQ_INVERTER_ADDRESS    = bytes([0x14])
    REQ_FOOTER              = bytes([0xae])

    @staticmethod
    def getResponseCommands(command : int) -> list[int]:
        responseCommands = {
            0x95: [0x95, 0x9D]
        }

        # Usually a single response is returned to a command,
        # hence the default value.
        return responseCommands.get(command, [command])


    COMMAND_SHORT_NAMES : dict = {
        "systemInformation"   : 0x98,
        "batteryStatus"       : 0x0a,
        "gridPVStatus"        : 0x0b,
        "runningStatus"       : 0x0c,
        "workingParameters"   : 0x95,
        "load"                : 0x0d, # Same as bmsStatus, keeping for backwards compatibility.
        "bmsStatus"           : 0x0d
    }

    ALL_QUERY_COMMANDS = [0x98, 0x0a, 0x0b, 0x0c, 0x95, 0x0d]
    # Some codes are not meant to be sent, just received via another code.
    ALL_RESPONSE_CODES = [0x98, 0x0a, 0x0b, 0x0c, 0x95, 0x0d, 0x9d]

    def __parseBatteryStatus(self, value : int) -> str:
        if value == 0x0011:
            return "charging"
        elif value == 0x0022:
            return "discharging"
        elif value == 0x0033:
            return "stand-by"
        else:
            return "unknown"

    def __parseOperatingMode(self, value : int) -> str:
        if value == 0x0001:
            return "General Mode"
        elif value == 0x0002:
            return "Energy Storage Mode"
        elif value == 0x0003:
            return "Micro-grid"
        elif value == 0x0004:
            return "Peak-Valley"
        elif value == 0x0005:
            return "AC Coupling"
        else:
            return "unknown"

    def __parseBatteryComStatus(self, value : int) -> str:
        if value == 0x0000:
            return "OK"
        elif value == 0x0001:
            return "Disconnected"
        else:
            return "Unknown"

    def __parseModelCode(self, value : int) -> str:
        if value == 0x0001:
            return "10 kW"
        elif value == 0x0002:
            return "5 kW"
        elif value == 0x0003:
            return "6 kW"
        elif value == 0x0005:
            return "3 kW"
    
    def __parseBatteryManufacturer(self, value : int) -> str:
        if value == 1:
            return "No battery"
        elif value == 2:
            return "PylonTech High Voltage Battery"
        elif value == 3:
            return "PylonTech Low Voltage Battery"
        elif value == 9:
            return "Nelumbo HV Battery"
        elif value == 12:
            return "Generic High Voltage Battery"
        elif value == 13:
            return "Generic Low Voltage Battery"
        elif value == 14:
            return "Dyness High Voltage Battery"
        elif value == 22:
            return "BYD High Voltage Battery"
        elif value == 23:
            return "BYD Low Voltage Battery"
        elif value == 25:
            return "AOBO Battery"
        elif value == 26:
            return "Soluna 15K Pack HV"
        elif value == 27:
            return "Soluna 4K LV"
        elif value == 28:
            return "Soluna 3K LV"
        elif value == 30:
            return "Pylon Low Voltage Battery 485"
        else:
            return "Unknown"

    def __parseBatteryType(self, value : int) -> str:
        if value == 1:
            return "Lithium Battery"
        elif value == 2:
            return "Lead-acid Battery"
        else:
            return "Unknown battery type"

    def __parseMeterProtocol(self, value : int) -> str:
        if value == 1:
            return "Not installed"
        elif value == 2:
            return "Acrel Three-phase meter"
        elif value == 3:
            return "Acrel Single-phase meter"
        elif value == 4:
            return "Three-phase Eastron meter"
        elif value == 5:
            return "Single-phase Eastron meter"
        else:
            return "Unknown meter"

    def __parseEEBinarySensor(self, value : int) -> bool:
        if value == 0xee00:
            return True
        else:
            return False
        
    def __parseProtocolVersion(self, value : int) -> str:
        return f"{int(value / 100)}.{int((value / 10) % 10)}.{value % 10}"

    # Enquoting the SermatecProtocolParser type because it is a forward declaration (PEP 484).
    FIELD_PARSERS : dict[str, Callable[["SermatecProtocolParser", Any], Any]] = {
        "batteryStatus" : __parseBatteryStatus,
        "operatingMode" : __parseOperatingMode,
    }

    NAME_BASED_FIELD_PARSERS : dict[str, Callable[["SermatecProtocolParser", Any], Any]] = {
        "battery_communication_connection_status" : __parseBatteryComStatus,
        "model_code": __parseModelCode,
        "battery_manufacturer_number__code_list_": __parseBatteryManufacturer,
        "battery_communication_protocol_selection": __parseBatteryManufacturer,
        "dc_side_battery_type": __parseBatteryType,
        "meter_communication_protocol_selection": __parseMeterProtocol,
        "meter_detection_function": __parseEEBinarySensor,
        "three_phase_unbalanced_output": __parseEEBinarySensor
    }


    def __init__(self, protocolPath : str, languageFilePath : Path):
        with open(protocolPath, "r") as protocolFile:
            protocolData = json.load(protocolFile)
            try:
                self.osim = protocolData["osim"]
            except KeyError:
                logger.error("Protocol file malformed, 'osim' key not found.")
                raise ProtocolFileMalformed()
        self.translations = {}
        with languageFilePath.open("r") as langFile:
            for line in langFile.readlines():
                splitLine = line.replace("\"", "").replace("\n", "").split(";")
                original_name = splitLine[0]
                translated_name = splitLine[1]
                self.translations[original_name] = translated_name
            
    def getCommandCodeFromName(self, commandName : str) -> int:
        if commandName in self.COMMAND_SHORT_NAMES:
            return self.COMMAND_SHORT_NAMES[commandName]
        else:
            logger.error(f"Specified command '{commandName}' not found.")
            raise CommandNotFoundInProtocol()

    # Get all available query commands in the specified version.
    # TODO: Use queryCommands from protocol.json instead of hardcoded array.
    def getQueryCommands(self, version : int) -> list:
        return self.ALL_QUERY_COMMANDS

        cmds = set()
        for ver in self.osim["versions"]:
            cmds |= {int(cmd, base=16) for cmd in ver["queryCommands"] if ver["version"] <= version}
        
        listCmds = list(cmds)
        listCmds.sort()
        print(type(listCmds[0]))
        return listCmds
    
    def getResponseCodes(self, version : int) -> list:
        return self.ALL_RESPONSE_CODES

    def __getCommandByVersion(self, command : int, version : int) -> dict:
        """Get a newest version of a reply to a command specified.

        Args:
            command (int): Command to get a reply structure for.
            version (int): Version of the MCU.

        Raises:
            CommandNotFoundInProtocol: The command was not found in protocol.

        Returns:
            dict: Structure of the reply.
        """

        allSupportedVersions = [ver for ver in self.osim["versions"] if ver["version"] <= version]
        cmd = {}

        for ver in allSupportedVersions:
            cmd = next((cmd for cmd in ver["commands"] if int(cmd["type"],base=16) == command), cmd)

        if not cmd:
            raise CommandNotFoundInProtocol(f"Specified command 0x'{command:02x}' not found.")

        return cmd
    
    def __getMultiplierDecimalPlaces(self, multiplier : float) -> int:
        if "." in str(multiplier):
            return len(str(multiplier).split(".")[1])
        else:
            return 0
        

    def parseReply(self, command : int, version : int, reply : bytes, dryrun : bool = False) -> dict:
        """Parse a command reply using a specified version definition.

        Args:
            command (int): A single-byte code of the command to parse.
            version (int): A MCU version (used to look up a correct response format).
            reply (bytes): A reply to parse.

        Returns:
            dict: Parsed reply.

        Raises:
            CommandNotFoundInProtocol: The specified command is not found in the protocol (thus can't be parsed).
            ProtocolFileMalformed: There was an unexpected error in the protocol file.
            ParsingNotImplemented: There is a field in command reply which is not supported.
        """      
        
        logger.debug(f"Reply to parse: {reply[self.REPLY_OFFSET_DATA:].hex(' ')}")
        
        logger.debug("Looking for the command in protocol.")
        # This may throw CommandNotFoundInProtocol.
        cmd : dict = self.__getCommandByVersion(command, version)

        try:
            cmdType     : dict = cmd["type"]
            cmdName     : dict = cmd["comment"]
            cmdFields   : dict = cmd["fields"]
        except KeyError:
            logger.error(f"Protocol file malformed, can't process command 0x'{command:02x}'")
            raise ProtocolFileMalformed()
        
        logger.debug(f"It is command 0x{cmdType}: {cmdName} with {len(cmdFields)} fields")

        parsedData : dict       = {}
        replyPosition : int     = self.REPLY_OFFSET_DATA
        prevReplyPosition : int = 0

        for idx, field in enumerate(cmdFields):

            # Whether to ignore this field (unknown type, reserved field...)
            ignoreField : bool = False

            if ("same" in field and field["same"]):
                logger.debug(f"Staying at the same byte.")
                replyPosition = prevReplyPosition

            logger.debug(f"== Field #{idx} (reply byte #{replyPosition})")

            if not (("name" or "byteLen" or "type") in field):
                logger.error(f"Field has a 'name', 'byteLen' or 'type' missing: {field}.")
                raise ProtocolFileMalformed()

            fieldLength = int(field["byteLen"])
            if fieldLength < 1:
                logger.error("Field length is zero or negative.")
                raise ProtocolFileMalformed()

            newField = {}

            fieldType = field["type"]
            if fieldType == "bit":
                if "bitPosition" in field:
                    fieldBitPosition = field["bitPosition"]
                else:
                    logger.error("Field is of a type 'bit', but is missing key 'bitPosition'.")
                    raise ProtocolFileMalformed()
                newField["unit"] = "binary"

            if fieldType == "bitRange":
                if "fromBit" and "endBit":
                    fieldFromBit = field["fromBit"]
                    fieldEndBit = field["endBit"]
                else:
                    logger.error("Field is of a type 'bitRange' but is missing key 'fromBit' or 'endBit'.")
                    raise ProtocolFileMalformed()
            

            fieldTag = re.sub(r"[^A-Za-z0-9]", "_", field["name"]).lower()
            logger.debug(f"Created tag from name: {fieldTag}")

            if field["name"] in self.translations:
                fieldName = self.translations[field["name"]]
            else:
                fieldName = field["name"]

            newField["name"] = fieldName

            if "unitValue" in field:
                try:
                    fieldMultiplier : float = float(field["unitValue"])
                except:
                    logger.error("Can't convert field's unitValue to float.")
                    raise ProtocolFileMalformed()
            else:
                fieldMultiplier : float = 1
                logger.debug(f"Field {fieldName} has not 'unitValue' key, using 1 as a default multiplier.")          
            

            if "unitType" in field:
                logger.debug(f"Field has a unit: {field['unitType']}")
                newField["unit"] = field['unitType']

                if newField["unit"] == "V":
                    newField["device_class"] = "VOLTAGE"
                elif newField["unit"] == "W":
                    newField["device_class"] = "POWER"
                elif newField["unit"] == "VA":
                    newField["device_class"] = "APPARENT_POWER"
                elif newField["unit"] == "A":
                    newField["device_class"] = "CURRENT"
                elif newField["unit"] == "var":
                    newField["device_class"] = "REACTIVE_POWER"
                elif newField["unit"] == "°C":
                    newField["device_class"] = "TEMPERATURE"
                elif newField["unit"] == "Hz":
                    newField["device_class"] = "FREQUENCY"
            
            if "deviceClass" in field:
                logger.debug(f"Field has an explicit device class: {field['deviceClass']}")
                newField["device_class"] = field['deviceClass']
                                  
            # Do not parse when no data are supplied (dry run) -> checking out list of available sensors,
            # useful e.g. for Home Assistant.
            if not dryrun:
                currentFieldData = reply[ replyPosition : (replyPosition + fieldLength) ]
                logger.debug(f"Parsing field data: {currentFieldData.hex(' ')}")
                
                if fieldType == "int":
                    newField["value"] = round(int.from_bytes(currentFieldData, byteorder = "big", signed = True) * fieldMultiplier, self.__getMultiplierDecimalPlaces(fieldMultiplier))
                elif fieldType == "uInt":
                    newField["value"] = round(int.from_bytes(currentFieldData, byteorder = "big", signed = False) * fieldMultiplier, self.__getMultiplierDecimalPlaces(fieldMultiplier))
                elif fieldType == "string":
                    # The string is null-terminated, trimming everything after first occurence of '\0'.
                    trimmedString = currentFieldData.split(b"\x00", 1)[0]
                    newField["value"] = trimmedString.decode('ascii')
                elif fieldType == "bit":
                    binString : str = bin(int.from_bytes(currentFieldData, byteorder = "little", signed = False)).removeprefix("0b")
                    newField["value"] = bool(binString[fieldBitPosition])
                elif fieldType == "bitRange":
                    binString : str = bin(int.from_bytes(currentFieldData, byteorder = "little", signed = False)).removeprefix("0b")
                    newField["value"] = binString[fieldFromBit:fieldEndBit]
                elif fieldType == "hex":
                    newField["value"] =  int.from_bytes(currentFieldData, byteorder = "big", signed = False)
                elif fieldType == "preserve":
                    pass
                elif fieldType == "long":
                    newField["value"] = round(int.from_bytes(currentFieldData, byteorder = "big", signed = True) * fieldMultiplier, self.__getMultiplierDecimalPlaces(fieldMultiplier))
                else:
                    ignoreField = True
                    logger.info(f"The provided field is of an unsuported type '{fieldType}'.")

                # Some field have a meaning encoded to integers: trying to parse.
                if "parser" in field and field["parser"] in self.FIELD_PARSERS:
                    logger.debug("This field has an explicit parser available, parsing.")
                    newField["value"] = self.FIELD_PARSERS[field["parser"]](self, newField["value"])

                # On some fields the parse key is missing, so using names for identification.
                if fieldTag in self.NAME_BASED_FIELD_PARSERS:
                    logger.debug("This field has an name-based parser available, parsing.")
                    newField["value"] = self.NAME_BASED_FIELD_PARSERS[fieldTag](self, newField["value"])

            # Fields with "repeat" are not supported for now, skipping.
            if "repeat" in field:
                fieldLength *= int(field["repeat"])
                ignoreField = True
                logger.debug("Fields with 'repeat' are not supported, skipping...")

            if fieldType == "preserve":
                ignoreField = True

            newField["listIgnore"] = field.get("listIgnore", False)

            if not ignoreField:
                parsedData[fieldTag] = newField
                logger.debug(f"Parsed: {parsedData[fieldTag]}")

            prevReplyPosition = replyPosition
            replyPosition += fieldLength
        
        return parsedData
    
    def __calculateChecksum(self, data : bytes) -> bytes:
        checksum : int = 0x0f
        
        for byte in data:
            checksum = (checksum & 0xff) ^ byte
        
        logger.debug(f"Calculated checksum: {hex(checksum)}")

        return checksum.to_bytes(1, byteorder="little")

    def checkResponseIntegrity(self, response : bytes, expectedCommandByte : int) -> bool:
        # Length check.
        if len(response) < 8: return False

        # Signature check.
        if response[0x00:0x02] != self.REQ_SIGNATURE:
            logger.debug("Bad response signature.")
            return False
        # Sender + receiver check.
        if response[0x02:0x03] != self.REQ_INVERTER_ADDRESS:
            logger.debug("Bad response sender address.")
            return False
        if response[0x03:0x04] != self.REQ_APP_ADDRESS:
            logger.debug("Bad response recipient address.")
            return False
        # Response command check.
        if int.from_bytes(response[0x04:0x05], byteorder = "little", signed = False) != expectedCommandByte:
            logger.debug(f"Bad response expected command. Expected: {expectedCommandByte}, got: {response[0x04:0x05]}.")
            return False
        # Zero.
        if response[0x05] != 0:
            logger.debug("No zero at response position 0x00.")
            return False
        # Checksum verification.
        if response[-0x02:-0x01] != self.__calculateChecksum(response[:len(response) - 2]):
            logger.debug(f"Bad response checksum: {response[-0x03:-0x02].hex()}")
            return False
        # Footer check.
        if response[-0x01] != int.from_bytes(self.REQ_FOOTER, byteorder="big"):
            logger.debug("Bad response footer.")
            return False

        return True

    def generateRequest(self, command : int) -> bytes:  
        request : bytearray = bytearray([*self.REQ_SIGNATURE, *self.REQ_APP_ADDRESS, *self.REQ_INVERTER_ADDRESS, command, 0x00, 0x00])
        request += self.__calculateChecksum(request)
        request += self.REQ_FOOTER

        logger.debug(f"Built command: {[hex(x) for x in request]}")

        return request

if __name__ == "__main__":
    logging.basicConfig(level = "DEBUG")
    smc : SermatecProtocolParser = SermatecProtocolParser("protocol-en.json")
    #print(smc.getQueryCommands(0))
    binfile98 = open("../../dumps/98", "rb")
    c98 = binfile98.read()
    binfile0a = open("../../dumps/0a", "rb")
    c0a = binfile0a.read()
    binfile0b = open("../../dumps/0b", "rb")
    c0b = binfile0b.read()
    binfile0c = open("../../dumps/0c_ongrid", "rb")
    c0c = binfile0c.read()
    binfile0d = open("../../dumps/0d", "rb")
    c0d = binfile0d.read()

    print(smc.parseReply(0x98, 400, c98))
    # print(smc.parseReply(0x0c, 400, c0c))