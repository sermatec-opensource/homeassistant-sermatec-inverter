class NoDataReceived(BaseException):
    pass

class FailedResponseIntegrityCheck(BaseException):
    pass

class NotConnected(BaseException):
    pass

class ProtocolFileMalformed(BaseException):
    pass

class CommandNotFoundInProtocol(BaseException):
    pass

class ParsingNotImplemented(BaseException):
    pass

class PCUVersionMalformed(BaseException):
    pass

class SendTimeout(BaseException):
    pass

class RecvTimeout(BaseException):
    pass

class CommunicationError(BaseException):
    pass

class DuplicateMapValue(BaseException):
    pass

class ParameterNotFound(BaseException):
    pass

class MissingTaggedData(BaseException):
    pass

class InverterIsNotOff(BaseException):
    pass