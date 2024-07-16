from .exceptions import *

class BaseConverter():
    """Convert to and from friendly names.
    """
    def __init__(self):
        pass

    def toFriendly(self, value : int):
        pass

    def fromFriendly(self, value) -> int: # type: ignore
        pass

    def listFriendly(self) -> list:
        pass

class MapConverter(BaseConverter):
    """Convert to and from friendly names using map.
    """

    def __init__(self, map : dict, defaultNotFriendly, defaultFriendly):
        """
        Args:
            map (dict): Translation map, bijective function (no duplicate values).
            defaultNotFriendly: default system ("not friendly") value to return if no record in map is found
            defaultFriendly: default friendly value to return if no record in map is found

        Raises:
            DuplicateMapValue: If there are duplicate values.
        """

        self.__map = map
        self.__def_notFriendly = defaultNotFriendly
        self.__def_friendly = defaultFriendly

        self.__inv_map = {}
        for key, value in self.__map.items():
            if value in self.__inv_map:
                raise DuplicateMapValue()
            self.__inv_map[value] = key
    
    def toFriendly(self, value):
        if value not in self.__map:
            return self.__def_friendly
        else:
            return self.__map[value]
    
    def fromFriendly(self, value):
        if value not in self.__inv_map:
            return self.__def_notFriendly
        else:
            return self.__inv_map[value]
        
    def listFriendly(self) -> list:
        return list(self.__map.values())
        
class DummyConverter(BaseConverter):
    """This converter passes through the value without conversion."""
    def __init__(self):
        pass
    
    def toFriendly(self, value):
        return value
    
    def fromFriendly(self, value):
        return value
    
    def listFriendly(self) -> list:
        return []