class BaseValidator():
    """Validate values."""
    def __init__(self):
        pass

    def validate(self, value) -> bool: # type: ignore
        pass

class EnumValidator(BaseValidator):
    """Validate whether the value is in defined list."""

    def __init__(self, allowed_values : list):
        """
        Args:
            allowed_values (list): List of allowed values.
        """

        self.__allowed_values = allowed_values

    def validate(self, value) -> bool:
        return (value in self.__allowed_values)
    
class IntRangeValidator(BaseValidator):
    """Validate whether the int value is in defined range."""

    def __init__(self, min_value : int, max_value : int):
        """
        Args:
            min_value (int): Minimal allowed value.
            max_value (int): Maximal allowed value.
        """

        self.__min_val = min_value
        self.__max_val = max_value

    def validate(self, value : int) -> bool:
        if type(value) is int:
            return self.__min_val <= int(value) <= self.__max_val
        else:
            return False