import logging
import json
import re
from typing import Any, Callable
from .exceptions import *
from pathlib import Path
from enum import Enum, auto

from .converters import *
from .validators import *

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
            # Parameter query commands have two responses.
            0x95: [0x95, 0x9D],

            # Set commands have no response.
            0x64: [],
            0x66: [],
            0x6A: []
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

    ALL_PARAMETER_QUERY_COMMANDS = [0x0c, 0x95]

    __CONVERTER_BATTERY_STATUS = MapConverter({
        0x0011 : "charging",
        0x0022 : "discharging",
        0x0033 : "stand-by",
    }, 0x0000, "unknown")

    __CONVERTER_OPERATING_MODE = MapConverter({
        0x0001 : "General Mode",
        0x0002 : "Energy Storage Mode",
        0x0003 : "Micro-grid",
        0x0004 : "Peak-Valley",
        0x0005 : "AC Coupling"
    }, 0x0000, "unknown")

    __CONVERTER_EE_BINARY = MapConverter({
        0xee00 : True,
        0x00ee : False
    }, 0x0000, False)

    # This converter is used for flags represented in protocol as int (instead bits as usual).
    __CONVERTER_SIMPLE_BINARY = MapConverter({
        1: True,
        0: False
    }, 1, True)
    
    # This converter is used for flags represented in protocol as int but with inverted meaning.
    __CONVERTER_INVERTED_BINARY = MapConverter({
        1: False,
        0: True
    }, 1, True)

    # Use only for converting from friendly value to set value in 0x64 command.
    __CONVERTER_ON_OFF = MapConverter({
        0x55 : True,
        0xaa : False
    }, 0x00, False)

    __CONVERTER_MODEL_CODE = MapConverter({
        0x0001: "10 kW",
        0x0002: "5 kW",
        0x0003: "6 kW",
        0x0005: "3 kW"
    }, 0x0000, "unknown")

    __CONVERTER_BATTERY_MANUFACTURER = MapConverter({
        1:  "No battery",
        2:  "PylonTech High Voltage Battery",
        3:  "PylonTech Low Voltage Battery",
        4:  "BYD",
        5:  "Chaowei",
        6:  "HDXN",
        7:  "YWLN",
        9:  "XPGY",
        10: "WOTAI",
        11: "RuiPu",
        12: "Cairi High Voltage",
        13: "Cairi Low Voltage",
        14: "Dyness High Voltage",
        15: "Dyness Low Voltage",
        16: "DLG Low Voltage",
        17: "Wotai Low Voltage",
        18: "SHDL",
        19: "GuangYu",
        20: "FeiBo",
        21: "NJSG",
        22: "BYD High Voltage",
        23: "BYD Low Voltage",
        24: "METERBOOST",
        25: "AOBO",
        26: "DLG High Voltage",
        27: "Soluna Low Voltage",
        28: "Soluna 3K"
    }, 0, "unknown")

    __CONVERTER_BATTERY_TYPE = MapConverter({
        1: "Lithium battery",
        2: "Lead-acid battery",
        3: "Flow battery"
    }, 0, "unknown")

    __CONVERTER_METER_PROTOCOL = MapConverter({
        1: "Not installed",
        2: "Acrel Three-phase meter",
        3: "Acrel Single-phase meter",
        4: "Eastron Three-phase meter",
        5: "Eastron Single-phase meter"
    }, 0, "unknown")
        
    __CONVERTER_AC_OP_STATUS = MapConverter({
        0: "not running",
        1: "self-check",
        2: "standby",
        3: "on-grid",
        4: "off-grid",
        5: "backup mode"
    }, 0, "unknown")

    __CONVERTER_AC_OP_MODE = MapConverter({
        1: "MPPT mode",
        2: "Constant current mode",
        3: "PV constant voltage mode",
        4: "AC rectification mode",
        5: "Secondary constant current mode",
        6: "Constant DC power mode",
        7: "Constant AC power mode",
        0: "unknown mode"
    }, 0, "unknown mode")

    # Using original name from name tag in protocol.json, not translated/converted one!
    NAME_BASED_FIELD_PARSERS : dict[str, BaseConverter] = {
        "Charge and discharge status" : __CONVERTER_BATTERY_STATUS,
        "Operating mode" : __CONVERTER_OPERATING_MODE,
        "model code": __CONVERTER_MODEL_CODE,
        "Battery manufacturer number (code list)": __CONVERTER_BATTERY_MANUFACTURER,
        "Battery communication protocol selection": __CONVERTER_BATTERY_MANUFACTURER,
        "DC side battery type": __CONVERTER_BATTERY_TYPE,
        "Meter communication protocol selection": __CONVERTER_METER_PROTOCOL,
        "Three-phase unbalanced output": __CONVERTER_EE_BINARY,
        "Meter detection function": __CONVERTER_EE_BINARY,
        "battery warning": __CONVERTER_SIMPLE_BINARY,
        "battery error": __CONVERTER_SIMPLE_BINARY,
        "Battery communication connection status": __CONVERTER_INVERTED_BINARY,
        "AC side operation mode": __CONVERTER_AC_OP_STATUS,
        "AC side running status": __CONVERTER_AC_OP_MODE
    }


    class SermatecParameter:      
        def __init__(self, command : int, byteLength : int, converter : BaseConverter, validator : BaseValidator, friendlyType : type, shouldBeOff : bool):
            # Parameter friendlyType is used to signalize in what type the friendly value is expected, useful mainly for terminal UI,
            # where everything is passed as string by default
            self.command        = command
            self.byteLength     = byteLength
            self.converter      = converter
            self.validator      = validator
            self.friendlyType   = friendlyType
            self.shouldBeOff    = shouldBeOff

    class SermatecSwitchParameter(SermatecParameter):
        def __init__(self, command : int, byteLength : int, converter : BaseConverter, validator : BaseValidator, friendlyType : type, shouldBeOff : bool):
            super().__init__(command, byteLength, converter, validator, friendlyType, shouldBeOff)

    class SermatecSelectParameter(SermatecParameter):
        def __init__(self, command : int, byteLength : int, converter : BaseConverter, validator : BaseValidator, friendlyType : type, shouldBeOff : bool):
            super().__init__(command, byteLength, converter, validator, friendlyType, shouldBeOff)

    class SermatecNumberParamter(SermatecParameter):
        def __init__(self, command : int, byteLength : int, converter : BaseConverter, validator : BaseValidator, friendlyType : type, shouldBeOff : bool, min : int, max : int):
            super().__init__(command, byteLength, converter, validator, friendlyType, shouldBeOff)
            self.min = min
            self.max = max

    SERMATEC_PARAMETERS = {
        "onOff" : SermatecSwitchParameter(
            command      = 0x64,
            byteLength   = 1,
            converter    = __CONVERTER_ON_OFF,
            validator    = EnumValidator([0x55, 0xaa]),
            friendlyType = int,
            shouldBeOff  = False
        ),
        "operatingMode" : SermatecSelectParameter(
            command      = 0x66,
            byteLength   = 2,
            converter    = __CONVERTER_OPERATING_MODE,
            validator    = EnumValidator([0x1, 0x2, 0x3, 0x4, 0x5]),
            friendlyType = str,
            shouldBeOff  = False,
        ),
        "antiBackflow" : SermatecSwitchParameter(
            command      = 0x66,
            byteLength   = 2,
            converter    = __CONVERTER_EE_BINARY,
            validator    = EnumValidator([0xee00, 0x00ee]),
            friendlyType = int,
            shouldBeOff  = True,
        ),
        "soc": SermatecNumberParamter(
            command      = 0x66,
            byteLength   = 2,
            converter    = DummyConverter(),
            validator    = IntRangeValidator(10, 100),
            friendlyType = int,
            shouldBeOff  = False,
            min          = 10,
            max          = 100
        )
    }

    def getParameterInfo(self,parameterTag : str) -> SermatecParameter:
        """Get information about parameter by tag.

        Returns:
            SermatecParameter: Parameter information.

        Raises:
            ParameterNotFound: Parameter was not found.
        """
        if not parameterTag in self.SERMATEC_PARAMETERS:
            raise ParameterNotFound()
        else:
            return self.SERMATEC_PARAMETERS[parameterTag]

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

    def parseParameterReply(self, command : int, version : int, reply : bytes) -> dict:
        """Parse a command reply, leaving raw values and using tag as keys. Usable mainly
           for parameter setting.

        Args:
            command (int): A single-byte code of the command to parse.
            version (int): A PCU version (used to look up a correct response format).
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
            ignoreField = False

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

            fieldType = field["type"]                           
            rawFieldData = reply[ replyPosition : (replyPosition + fieldLength) ]

            # This is used only for the onOff tag. Others are integers.
            if fieldType == "bit":
                if "bitPosition" in field:
                    fieldBitPosition = field["bitPosition"]
                else:
                    logger.error("Field is of a type 'bit', but is missing key 'bitPosition'.")
                    raise ProtocolFileMalformed()
                convertedBytes = int.from_bytes(rawFieldData, byteorder = "big", signed = False)
                extractedBit   = bool(convertedBytes & (1 << fieldBitPosition))
                
                if "tag" in field and field["tag"] == "onOff":
                    logger.debug("Detected type bit, tag onOff. Converting.")
                    rawFieldData = self.__CONVERTER_ON_OFF.fromFriendly(extractedBit).to_bytes(byteorder = "big", signed = False)
                
            logger.debug(f"Storing raw field data: {rawFieldData}")

            # Fields with "repeat" are not supported for now, skipping.
            if "repeat" in field:
                fieldLength *= int(field["repeat"])
                ignoreField = True
                logger.debug("Fields with 'repeat' are not supported, skipping...")

            # Skipping reserved fields.
            if fieldType == "preserve":
                ignoreField = True
                logger.debug("Skipping unused value (type preserved)...")

            if not ignoreField and "tag" in field:
                parsedData[field["tag"]] =  rawFieldData
                logger.debug(f"Stored data to tag {field["tag"]}.")

            prevReplyPosition = replyPosition
            replyPosition += fieldLength
        
        return parsedData

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
                    convertedBytes = int.from_bytes(currentFieldData, byteorder = "big", signed = False)                    
                    newField["value"] = bool(convertedBytes & (1 << fieldBitPosition))
                elif fieldType == "bitRange":
                    convertedBytes = int.from_bytes(currentFieldData, byteorder = "big", signed = False)
                    binLength = fieldEndBit - fieldFromBit
                    binaryMask = (1 << (binLength)) - 1
                    convertedBytes = (convertedBytes >> fieldFromBit) & binaryMask
                    logger.debug(f"Masked value: {convertedBytes}")
                    newField["value"] = convertedBytes
                elif fieldType == "hex":
                    newField["value"] =  int.from_bytes(currentFieldData, byteorder = "big", signed = False)
                elif fieldType == "preserve":
                    pass
                elif fieldType == "long":
                    newField["value"] = round(int.from_bytes(currentFieldData, byteorder = "big", signed = True) * fieldMultiplier, self.__getMultiplierDecimalPlaces(fieldMultiplier))
                else:
                    ignoreField = True
                    logger.info(f"The provided field is of an unsuported type '{fieldType}'.")

                # Some field have a meaning encoded: trying to parse.
                # Using names for identification.
                if field["name"] in self.NAME_BASED_FIELD_PARSERS:
                    logger.debug("This field has an name-based parser available, parsing.")
                    newField["value"] = self.NAME_BASED_FIELD_PARSERS[field["name"]].toFriendly(newField["value"])

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

    def checkResponseIntegrity(self, responses : list[bytes], command : int) -> bool:

        reponseCommands = self.getResponseCommands(command)

        if len(responses) != len(reponseCommands):
            logger.debug(f"Invalid count of response packets. Expected {len(response)}, got {len(reponseCommands)}.")
            return False

        for response, commandCode in zip(responses, reponseCommands):
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
            if int.from_bytes(response[0x04:0x05], byteorder = "little", signed = False) != commandCode:
                logger.debug(f"Bad response expected command. Expected: {commandCode:02x}, got: {response[0x04:0x05].hex()}.")
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

    def generateRequest(self, command : int, payload : bytes = bytes()) -> bytes:
        request : bytearray = bytearray([*self.REQ_SIGNATURE, *self.REQ_APP_ADDRESS, *self.REQ_INVERTER_ADDRESS, command, 0x00, len(payload)]) + payload
        request += self.__calculateChecksum(request)
        request += self.REQ_FOOTER

        logger.debug(f"Built command: {[hex(x) for x in request]}")

        return request

    def build66Payload(self, taggedData : dict) -> bytes:
        """Generate 0x66 command payload from specified data.

        Args:
            taggedData (dict): Data to build payload from.

        Returns:
            bytes: Payload.

        Raises:
            MissingTaggedData: If not enough data was supplied to build payload.
        """      
        payload = bytearray();

        try:
            payload.extend(taggedData["price1"])
            payload.extend(taggedData["price2"])
            payload.extend(taggedData["price3"])
            payload.extend(taggedData["price4"])
            payload.extend(taggedData["con"])
            payload.extend(taggedData["chargePower"])
            payload.extend(taggedData["operatingMode"])
            payload.extend(taggedData["gridSwitch"])
            payload.extend(taggedData["adjustMethod"])
            payload.extend(taggedData["antiBackflow"])
            payload.extend(taggedData["batteryCharge"])
            payload.extend(taggedData["soc"])
            # Zeroes for "How many sets of data are there" field.
            payload.extend(b'\x00\x00')
        except KeyError:
            raise MissingTaggedData()
        
        return payload
        
    def build64Payload(self, taggedData : dict) -> bytes:
        """Generate 0x64 command payload from specified data.

        Args:
            taggedData (dict): Data to build payload from.

        Returns:
            bytes: Payload.

        Raises:
            MissingTaggedData: If not enough data was supplied to build payload.
        """      
        payload = bytearray();

        try:
            payload.extend(taggedData["onOff"])
        except KeyError:
            raise MissingTaggedData()
        
        return payload
    
    def isInverterOff(self, value : bytes) -> bool:
        """Check whether the provided value corresponds to off state."""
        return value == bytes([0xaa])

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