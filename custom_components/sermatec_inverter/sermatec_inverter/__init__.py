import logging
import asyncio
from pathlib import Path
from collections.abc import Callable
from typing import Type

from . import protocol_parser
from .exceptions import *

_LOGGER = logging.getLogger(__name__)

class Sermatec:

    QUERY_WRITE_TIMEOUT     = 5
    QUERY_READ_TIMEOUT      = 5
    QUERY_ATTEMPTS          = 5

    LANG_FILES_FOLDER       = Path(__file__).parent / "translations";

    def __init__(self, host : str, port : int, protocolFilePath : str = None, language : str = "en"):
        if not protocolFilePath:
            protocolFilePath = (Path(__file__).parent / "protocol-en.json").resolve()

        if not self.LANG_FILES_FOLDER.exists():
            raise FileNotFoundError("Translation folder not found!")
        
        lang_file_path = self.LANG_FILES_FOLDER / f"{language}.csv"
        if not lang_file_path.exists():
            raise FileNotFoundError("Required translation not exists!")

        self.host = host
        self.port = port
        self.connected = False
        self.parser = protocol_parser.SermatecProtocolParser(protocolFilePath, lang_file_path)
        self.pcuVersion = 0
    
    async def __sendQueryAttempt(self, command : int, dataToSend : bytes, responsesCount : int) -> list[bytes]:
        """Send data to inverter, receive a reponse (or responses) and verify integrity.
        This should not be called anywhere except in __sendQuery.

        Args:
            command (int): A single-byte code of the command to use.
            dataToSend (bytes): Data to send.
            responsesCount (int): How many responses to expect.

        Returns:
            list[bytes]: List of raw replies. Usually contains one reply -- depends on the command.

        Raises:
            SendTimeout: If timed out during data sending.
            RecvTimeout: If no response was delivered in time.
            ConnectionResetError: If inverter aborted connection.
            FailedResponseIntegrityCheck: If the response contains errors or unexpected data.
        """
        responseData : list[bytes] = []

        try:
            self.writer.write(dataToSend)
            await asyncio.wait_for(self.writer.drain(), timeout=self.QUERY_WRITE_TIMEOUT)
        except asyncio.TimeoutError:
            raise SendTimeout()
        except ConnectionResetError:
            _LOGGER.error("Connection reset by the inverter!")
            self.connected = False
            raise ConnectionResetError()
    
        for _ in range(responsesCount):
            try:
                currentResponse = await asyncio.wait_for(self.reader.read(256), timeout=self.QUERY_READ_TIMEOUT)
            except asyncio.TimeoutError:
                raise RecvTimeout()
            except ConnectionResetError:
                _LOGGER.error("Connection reset by the inverter!")
                self.connected = False
                raise ConnectionResetError()

            _LOGGER.debug(f"Received data: { currentResponse.hex(' ', 1) }")
            responseData.append(currentResponse)

        if len(responseData) != responsesCount:
            _LOGGER.error(f"Not enough data received when issued command {command}.")
            self.connected = False
            raise ConnectionResetError()
        
        if not self.parser.checkResponseIntegrity(responseData, command):
            raise FailedResponseIntegrityCheck()
        
        return responseData

    async def __sendQuery(self, command : int, payload : bytes = bytes()) -> list[bytes]:
        """Send a query to inverter using specified command code using multiple attempts.
        The connection to the inverter must exist already.

        Args:
            command (int): A single-byte code of the command to use.

        Returns:
            list[bytes]: List of raw replies. Usually contains one reply -- depends on the command.

        Raises:
            ConnectionResetError: If the inverter disconnects.
            CommunicationError: If the inverter failed to send correct data.
            NotConnected: If the function is called when no connection to the inverter exist.
        """
        if self.isConnected():
            dataToSend      = self.parser.generateRequest(command, payload)
            responsesCount  = len(self.parser.getResponseCommands(command))
            for attempt in range(self.QUERY_ATTEMPTS):
                try:
                    _LOGGER.debug(f"Communicating with inverter, command {command:02x}, attempt {attempt + 1}/{self.QUERY_ATTEMPTS}")
                    responseData = await self.__sendQueryAttempt(command, dataToSend, responsesCount)
                except SendTimeout:
                    _LOGGER.debug(f"Timeout when sending request to inverter, command {command:02x}.")
                except RecvTimeout:
                    _LOGGER.debug(f"Timeout when waiting for response from the inverter, command {command:02x}.")
                except FailedResponseIntegrityCheck:
                    _LOGGER.debug(f"Command 0x{command:02x} data malformed.")
                except ConnectionResetError:
                    # Connection error is raised immediately.
                    raise ConnectionResetError()
                else:
                    break

                if attempt + 1 == self.QUERY_ATTEMPTS:
                    _LOGGER.error(f"Unable to receive correct response after {attempt + 1} tries.")
                    raise CommunicationError()

            return responseData
                    
        else:
            _LOGGER.error("Can't send request: not connected.")
            raise NotConnected()
        
# ========================================================================
# Communications
# ========================================================================
    async def connect(self, version = -1) -> bool:
        if not self.isConnected():

            confut = asyncio.open_connection(host = self.host, port = self.port)
            try:
                self.reader, self.writer = await asyncio.wait_for(confut, timeout = 3)
            except (asyncio.TimeoutError, OSError):
                _LOGGER.error("Couldn't connect to the inverter.")
                self.connected = False
                return False
            else:
                self.connected = True

                # Get version only if not explicitly stated
                if version == -1:
                    try:
                        version = await self.getPCUVersion()
                    except (CommunicationError, ConnectionResetError, PCUVersionMalformed):
                        _LOGGER.warning("Can't get PCU version! Using version 0, available parameters will be limited.")
                        self.pcuVersion = 0
                    else:
                        self.pcuVersion = version
                        _LOGGER.info(f"Inverter's PCU version: {version}")
                else:
                    self.pcuVersion = version
                
                return True
        else:
            return True
    
    def isConnected(self) -> bool:
        return self.connected

    async def disconnect(self) -> None:
        if self.connected:
            self.writer.close()
            await self.writer.wait_closed()
            self.connected = False

# ========================================================================
# Feature discovery methods
# These methods do not communicate with inverter nor handle real data,
# they are used to discover abilities, sensors and controls.
# However, connection to the inverter is required to find out correct
# PCU version!
# This is useful for Home Assistant integration.
# ========================================================================
    def listSensors(self, pcuVersion : int = None) -> dict:
        # If no specific pcuVersion specified, use (possibly) previously discovered.
        if not pcuVersion:
            pcuVersion = self.pcuVersion
        
        sensorList : dict = {}
        for cmd in self.parser.getResponseCodes(pcuVersion):
            for key, field in self.parser.parseReply(cmd, pcuVersion, bytearray(), dryrun=True).items():
                if "listIgnore" in field and field["listIgnore"]:
                    continue
                elif "unit" in field and field["unit"] == "binary":
                    continue
                else:
                    sensorList.update({key: field})

        return sensorList
    
    def listBinarySensors(self, pcuVersion : int = None) -> dict:
        # If no specific pcuVersion specified, use (possibly) previously discovered.
        if not pcuVersion:
            pcuVersion = self.pcuVersion
        
        sensorList : dict = {}
        for cmd in self.parser.getResponseCodes(pcuVersion):
            for key, field in self.parser.parseReply(cmd, pcuVersion, bytearray(), dryrun=True).items():
                if "listIgnore" in field and field["listIgnore"]:
                    continue
                elif "unit" in field and field["unit"] == "binary":
                    sensorList.update({key: field})

        return sensorList
    
    def __listParams(self, paramType : Type[protocol_parser.SermatecProtocolParser.SermatecParameter], pcuVersion : int = None) -> dict:
        # If no specific pcuVersion specified, use (possibly) previously discovered.
        if not pcuVersion:
            pcuVersion = self.pcuVersion

        paramList : dict = {}
        for name, param in self.parser.SERMATEC_PARAMETERS.items():
            if isinstance(param, paramType):
                paramList.update({name:param})
        
        return paramList

    def listSwitches(self, pcuVersion : int = None) -> dict:
        return self.__listParams(self.parser.SermatecSwitchParameter, pcuVersion)
    
    def listNumbers(self, pcuVersion : int = None) -> dict:
        return self.__listParams(self.parser.SermatecNumberParamter, pcuVersion)
    
    def listSelects(self, pcuVersion : int = None) -> dict:
        return self.__listParams(self.parser.SermatecSelectParameter, pcuVersion)

    def getQueryCommands(self, pcuVersion : int = None) -> dict:
        # If no specific pcuVersion specified, use (possibly) previously discovered.
        if not pcuVersion:
            pcuVersion = self.pcuVersion
        
        return self.parser.getQueryCommands(pcuVersion)

# ========================================================================
# Query methods
# ========================================================================   
    async def getCustom(self, command : int) -> dict:
        """Get data from the inverter using specified command code.

        Args:
            command (int): A single-byte code of the command to use.

        Returns:
            dict: Parsed reply.

        Raises:
            ConnectionResetError: If the inverter disconnects.
            CommunicationError: If the inverter failed to send correct data.
            NotConnected: If the function is called when no connection to the inverter exist.
            CommandNotFoundInProtocol: The specified command is not found in the protocol (thus can't be parsed).
            ProtocolFileMalformed: There was an unexpected error in the protocol file.
            ParsingNotImplemented: There is a field in command reply which is not supported.
        """
        responses = await self.__sendQuery(command)
        
        responseCodes = self.parser.getResponseCommands(command)
        
        parsedResponse = {}
        for response, responseCode in zip(responses, responseCodes):
            parsedResponse.update(self.parser.parseReply(responseCode, self.pcuVersion, response))
        
        return parsedResponse
    
    async def getCustomRaw(self, command : int) -> list[bytes]:
        return await self.__sendQuery(command)

    async def get(self, commandName : str) -> dict:
        """Get data from the inverter from the specified dataset.

        Args:
            command (str): A dataset to get data from.

        Returns:
            dict: Parsed reply.

        Raises:
            ConnectionResetError: If the inverter disconnects.
            CommunicationError: If the inverter failed to send correct data.
            NotConnected: If the function is called when no connection to the inverter exist.
            CommandNotFoundInProtocol: The specified command is not found in the protocol (thus can't be parsed).
            ProtocolFileMalformed: There was an unexpected error in the protocol file.
            ParsingNotImplemented: There is a field in command reply which is not supported.
        """
        command = self.parser.getCommandCodeFromName(commandName)
        return await self.getCustom(command)

    async def getPCUVersion(self) -> int:
        """Get inverter's PCU version.

        Returns:
            int: PCU version.

        Raises:
            ConnectionResetError: If the inverter disconnects.
            CommunicationError: If the inverter failed to send correct data.
            NotConnected: If the function is called when no connection to the inverter exist.
            CommandNotFoundInProtocol: The specified command is not found in the protocol (thus can't be parsed).
            ProtocolFileMalformed: There was an unexpected error in the protocol file.
            ParsingNotImplemented: There is a field in command reply which is not supported.
            PCUVersionMalformed: The inverter returned invalid PCU version.
        """
        parsedData : dict = await self.get("systemInformation")

        if not "protocol_version_number" in parsedData:
            _LOGGER.error("PCU version is missing!")
            raise PCUVersionMalformed()
        else:
            version : int = 0

            try:
                version = int(parsedData["protocol_version_number"]["value"])
            except ValueError:
                _LOGGER.error("Can't parse PCU version!")
                raise PCUVersionMalformed()
            
            return version

    async def getSerial(self) -> str:
        """Get inverter's serial number.

        Returns:
            int: Serial number.

        Raises:
            ConnectionResetError: If the inverter disconnects.
            CommunicationError: If the inverter failed to send correct data.
            NotConnected: If the function is called when no connection to the inverter exist.
            CommandNotFoundInProtocol: The specified command is not found in the protocol (thus can't be parsed).
            ProtocolFileMalformed: There was an unexpected error in the protocol file.
            ParsingNotImplemented: There is a field in command reply which is not supported.
        """
        parsedData : dict = await self.get("systemInformation")
        serial : str = parsedData["product_sn"]["value"]
        return serial
    
    async def getParameterData(self) -> dict:
        parsedResponse = {}
        for commandCode in self.parser.ALL_PARAMETER_QUERY_COMMANDS:
            responses      = await self.__sendQuery(commandCode)
            responseCodes  = self.parser.getResponseCommands(commandCode)
            for response, responseCode in zip(responses, responseCodes):
                parsedResponse.update(self.parser.parseParameterReply(responseCode, self.pcuVersion, response))
            
        return parsedResponse

# ========================================================================
# Set methods
# ========================================================================
    async def set(self, tag : str, value : bool | int | str, previousData : dict = {}) -> None:
        """

        Args:
            
        Returns:
            
        Raises:
            MissingTaggedData: If not enough data was supplied to build payload.
            CommandNotFoundInProtocol: The requested command is not available.
            ParameterNotFound: This parameter is not supported.
            ValueError: If supplied value is invalid.
            InverterIsNotOff: If the inverter should be off to set this value.
        """
        
        taggedDataToSend = previousData
        _LOGGER.debug(f"Provided previous data: {taggedDataToSend}")

        # This may throw ParameterNotFound.    
        parameterInfo = self.parser.getParameterInfo(tag)
        
        convertedValue = parameterInfo.converter.fromFriendly(value)
        _LOGGER.debug(f"Setting up tag '{tag}' with converted value '{hex(convertedValue)}'")

        if not parameterInfo.validator.validate(convertedValue):
            raise ValueError

        taggedDataToSend[tag] = int.to_bytes(convertedValue, byteorder="big", signed=False, length = parameterInfo.byteLength)

        if parameterInfo.shouldBeOff:
            if "onOff" not in previousData:
                _LOGGER.debug("The inverter should be off to set the value, but no 'onOff' state supplied!")
                raise MissingTaggedData()
            elif not self.parser.isInverterOff(previousData["onOff"]):
                _LOGGER.debug("The inverter has to be off to set this value, but it is on.")
                raise InverterIsNotOff()

        if parameterInfo.command == 0x66:
            payload = self.parser.build66Payload(taggedDataToSend)
        elif parameterInfo.command == 0x64:
            payload = self.parser.build64Payload(taggedDataToSend)
        else:
            raise CommandNotFoundInProtocol
        
        _LOGGER.debug(f"Query payload: {payload.hex(' ')}")

        await self.__sendQuery(parameterInfo.command, payload)
        