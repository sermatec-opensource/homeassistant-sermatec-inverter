import sys
import argparse
import logging
import asyncio
from pathlib import Path
from . import Sermatec
from .protocol_parser import SermatecProtocolParser
from .exceptions import *

async def customgetFunc(**kwargs):
    """Query the inverter with a custom command.

    Keyword Args:
        command (int): The command's single-byte code. 
        ip (str): Inverter's IP.
        port (str): Inverter's API port.
        protocolFilePath (str): Path to the protocol JSON.
        raw (bool): True = parse the response, otherwise return raw bytes.
    """

    # Parsing command - it can be hex, dec or whathever base integer.
    try:
        parsedCmd = int(kwargs["command"], 0)
        if parsedCmd not in range(0, 255):
            raise ValueError
    except:
        print("The command has to be an integer in range [0, 255] (single byte).")
        return

    smc = Sermatec(kwargs["ip"], kwargs["port"], kwargs["protocolFilePath"])
    print(f"Connecting to Sermatec at {kwargs['ip']}:{kwargs['port']}...", end = "")
    if await smc.connect():
        print("OK")
    else:
        print("Can't connect.")
        return

    print("Getting data...")
    data : str | dict = {}

    if kwargs["raw"]:
        data = (await smc.getCustomRaw(parsedCmd)).hex(' ')
    else:
        try:
            data = await smc.getCustom(parsedCmd)
        except CommandNotFoundInProtocol:
            print("The command was not found in protocol for inverter's version, unable to parse. Try --raw to get raw bytes.")
        except (ProtocolFileMalformed, ParsingNotImplemented):
            print("There was an error parsing the command. Refer to logs.")
        except (NoDataReceived):
            print("Inverter sent no data.")
        except (FailedResponseIntegrityCheck):
            print("The response was malformed.")

    if data: print(data)

    print("Disconnecting...", end = "")
    await smc.disconnect()
    print("OK")

async def getFunc(**kwargs):
    
    smc = Sermatec(kwargs["ip"], kwargs["port"], kwargs["protocolFilePath"])
    print(f"Connecting to Sermatec at {kwargs['ip']}:{kwargs['port']}...", end = "")
    if await smc.connect():
        print("OK")
    else:
        print("Can't connect.")
        return

    print("Getting data...")
    pass

    data : dict = {}

    try:
        data = await smc.get(kwargs["command"])
    except CommandNotFoundInProtocol:
        print("The command was not found in protocol for inverter's version, unable to parse. Try --raw to get raw bytes.")
    except (ProtocolFileMalformed, ParsingNotImplemented):
        print("There was an error parsing the command. Refer to logs.")
    except (NoDataReceived):
        print("Inverter sent no data.")
    except (FailedResponseIntegrityCheck):
        print("The response was malformed.")
        
    if data: print(data)

    print("Disconnecting...", end = "")
    await smc.disconnect()
    print("OK")

async def setFunc(**kwargs):
    pass

async def listFunc(**kwargs):
    smc = Sermatec(kwargs["ip"], kwargs["port"], kwargs["protocolFilePath"])
    print(f"Connecting to Sermatec at {kwargs['ip']}:{kwargs['port']}...", end = "")
    if await smc.connect():
        print("OK")
    else:
        print("Can't connect.")
        return

    if kwargs["type"] == "sensors":
        print(smc.listSensors())
    elif kwargs["type"] == "binarysensors":
        print(smc.listBinarySensors())
    
    print("Disconnecting...", end = "")
    await smc.disconnect()
    print("OK")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog = "sermatec_inverter",
        description = "Sermatec Inverter communication script.",
    )
    parser.add_argument(
        "ip",
        help = "IP address of the inverter."
    )
    
    subparsers = parser.add_subparsers(dest = "cmd")
    getParser = subparsers.add_parser("get", help = "Get data from the inverter.")
    getParser.set_defaults(cmdFunc = getFunc)

    cmdShortNames = SermatecProtocolParser.COMMAND_SHORT_NAMES.keys()
    getParser.add_argument(
        "command",
        help = "A type of data to query.",
        choices = cmdShortNames,
    )

    setParser = subparsers.add_parser("set", help = "Configure a value in the inverter.")
    setParser.set_defaults(cmdFunc = setFunc)

    listParser = subparsers.add_parser("list", help = "List supported sensors and other features.")
    listParser.set_defaults(cmdFunc = listFunc)
    listParser.add_argument(
        "type",
        help = "What type of features to list.",
        choices = ["sensors", "binarysensors"]
    )

    customgetParser = subparsers.add_parser("customget", help = "Query the inverter using custom command.")
    customgetParser.set_defaults(cmdFunc = customgetFunc)
    customgetParser.add_argument(
        "command",
        help = "A single-byte command to send.",
    )
    customgetParser.add_argument(
        "--raw",
        help = "Do not parse the response.",
        action = "store_true"
    )
    
    parser.add_argument(
        "--port",
        help = "API port. Defaults to 8899.",
        default = 8899
    )
    parser.add_argument(
        "-v",
        help = "Print debug data.",
        action = "store_true"
    )
    parser.add_argument(
        "--protocolFilePath",
        help = "JSON with the OSIM protocol description.",
        default = (Path(__file__).parent / "protocol-en.json").resolve()
    )

    args = parser.parse_args()

    if args.v:
        logging.basicConfig(level = "DEBUG")

    if not args.cmd:
        print("Error: No command specified.")
        parser.print_help()
        sys.exit()
    else:
        asyncio.run(args.cmdFunc(**vars(args)))
