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
    
    async def __sendQuery(self, command : int) -> bytes:
        if self.isConnected():
            dataToSend = self.parser.generateRequest(command)
            self.writer.write(dataToSend)

            for attempt in range(self.QUERY_ATTEMPTS):
                _LOGGER.debug(f"Sending query, attempt {attempt + 1}/{self.QUERY_ATTEMPTS}")
                try:
                    await asyncio.wait_for(self.writer.drain(), timeout=self.QUERY_WRITE_TIMEOUT)
                except asyncio.TimeoutError:
                    _LOGGER.debug(f"[{attempt + 1}/{self.QUERY_ATTEMPTS}] Timeout when sending request to inverter.")
                    if attempt + 1 == self.QUERY_ATTEMPTS:
                        _LOGGER.error(f"Timeout when sending request to inverter after {self.QUERY_ATTEMPS} tries.")
                        raise NoDataReceived()
                    continue
                except ConnectionResetError:
                    _LOGGER.error("Connection reset by the inverter!")
                    self.connected = False
                    raise ConnectionResetError()
            
                try:
                    data = await asyncio.wait_for(self.reader.read(256), timeout=self.QUERY_READ_TIMEOUT)
                except asyncio.TimeoutError:
                    _LOGGER.debug(f"[{attempt + 1}/{self.QUERY_ATTEMPTS}] Timeout when waiting for response from the inverter.")
                    if attempt + 1 == self.QUERY_ATTEMPTS:
                        _LOGGER.error(f"Timeout when waiting for response from the inverter after {self.QUERY_ATTEMPS} tries.")
                        raise NoDataReceived()
                    continue
                except ConnectionResetError:
                    _LOGGER.error("Connection reset by the inverter!")
                    self.connected = False
                    raise ConnectionResetError()         

                _LOGGER.debug(f"Received data: { data.hex(' ', 1) }")

                if len(data) == 0:
                    _LOGGER.error(f"No data received when issued command {command}: connection closed by the inverter.")
                    self.connected = False
                    raise ConnectionResetError()
                
                if not self.parser.checkResponseIntegrity(data, command):
                    _LOGGER.debug(f"[{attempt + 1}/{self.QUERY_ATTEMPTS}] Command 0x{command:02x} response data malformed.")
                    if attempt + 1 == self.QUERY_ATTEMPTS:
                        _LOGGER.error(f"Got malformed response after {self.QUERY_ATTEMPS} tries, command 0x{command:02x}.")
                        raise FailedResponseIntegrityCheck()
                else:
                    break

            return data
                    
        else:
            _LOGGER.error("Can't send request: not connected.")
            raise NotConnected()

    async def __sendQueryByName(self, commandName : str) -> bytes:
        command : int = self.parser.getCommandCodeFromName(commandName)
        return await self.__sendQuery(command)

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
                    except (NoDataReceived, FailedResponseIntegrityCheck, PCUVersionMalformed):
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
        for cmd in self.parser.getQueryCommands(pcuVersion):
            sensorList.update(self.parser.parseReply(cmd, pcuVersion, bytearray(), dryrun=True))

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
        data : bytes = await self.__sendQuery(command)
        parsedData : dict = self.parser.parseReply(command, self.pcuVersion, data)
        return parsedData
    
    async def getCustomRaw(self, command : int) -> bytes:
        return await self.__sendQuery(command)

    async def get(self, commandName : str) -> dict:
        data : bytes = await self.__sendQueryByName(commandName)
        parsedData : dict = self.parser.parseReply(self.parser.getCommandCodeFromName(commandName), self.pcuVersion, data)
        return parsedData

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