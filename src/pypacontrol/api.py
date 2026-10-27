"""Common, read-only API over PA-CONTROL Online Command.

Based on IEF-Werner interface manual MAN_DE_1006913 (July 2010),
section 5.2.4 and command 190C. Actual support depends on firmware/model.
"""

class UnsupportedFeatureError(NotImplementedError):
    """The selected backend cannot safely implement this operation."""


def check_index(name, index, upper):
    if isinstance(index, bool) or not isinstance(index, int) or not 1 <= index <= upper:
        raise ValueError(f"{name} must be an integer between 1 and {upper}")
    return index


class OnlineReadAPI:
    """Mixin for read-only PA-CONTROL Online Command requests."""
    def get_position(self, axis: int) -> float:
        check_index("axis", axis, 16)
        return float(self.command("190C", parameter=axis).value)

    def get_input(self, index: int) -> bool:
        check_index("input", index, 1024)
        value = int(self.command("1900", parameter=index).value)
        if value not in (0, 1):
            raise ValueError(f"Unexpected digital input value: {value}")
        return bool(value)

    def get_output(self, index: int) -> bool:
        check_index("output", index, 1024)
        value = int(self.command("1902", parameter=index).value)
        if value not in (0, 1):
            raise ValueError(f"Unexpected digital output value: {value}")
        return bool(value)

    def get_register(self, index: int, *, kind: str = "int") -> int | float:
        check_index("register", index, 1024)
        if kind == "int":
            return int(self.command("1906", parameter=index).value)
        if kind == "float":
            return float(self.command("1907", parameter=index).value)
        raise ValueError("kind must be 'int' or 'float'")
