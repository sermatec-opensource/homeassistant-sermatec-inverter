import logging
import asyncio
from . import protocol_parser
from .exceptions import *
from pathlib import Path

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
    
    async def __sendQueryAttempt(self, command : int, dataToSend : bytes, responsesCount : int) -> bytes:        
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

    async def __sendQuery(self, command : int) -> bytes:
        if self.isConnected():
            dataToSend      = self.parser.generateRequest(command)
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
                    raise ConnectionError()
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
                    except (CommunicationError, FailedResponseIntegrityCheck, PCUVersionMalformed):
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

    def getQueryCommands(self, pcuVersion : int = None) -> dict:
        # If no specific pcuVersion specified, use (possibly) previously discovered.
        if not pcuVersion:
            pcuVersion = self.pcuVersion
        
        return self.parser.getQueryCommands(pcuVersion)
# ========================================================================
# Query methods
# ========================================================================   
    async def getCustom(self, command : int) -> dict:
        responses = await self.__sendQuery(command)
        
        responseCodes = self.parser.getResponseCommands(command)
        
        parsedResponse = {}
        for response, responseCode in zip(responses, responseCodes):
            parsedResponse.update(self.parser.parseReply(responseCode, self.pcuVersion, response))
        
        return parsedResponse
    
    async def getCustomRaw(self, command : int) -> list[bytes]:
        return await self.__sendQuery(command)

    async def get(self, commandName : str) -> dict:
        command = self.parser.getCommandCodeFromName(commandName)
        return await self.getCustom(command)

    async def getPCUVersion(self) -> int:
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
        parsedData : dict = await self.get("systemInformation")
        serial : str = parsedData["product_sn"]["value"]
        return serial