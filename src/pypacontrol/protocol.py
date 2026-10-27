"""Online Command framing per IEF-Werner Schnittstellenhandbuch (2010), §3.3.

The checksum is decimal ASCII XOR of payload through ETX (excluding SOH/STX).
This follows the manual examples, which conflict with its checksum prose.
"""
from dataclasses import dataclass

SOH, STX, ETX, EOT = 1, 2, 3, 4

class ProtocolError(Exception):
    """Malformed or inconsistent telegram."""

class ControllerError(Exception):
    """PA-CONTROL reported a command or machine error."""

@dataclass(frozen=True)
class Reply:
    command_error: int
    completed: bool
    status: int
    controller_error: int
    data_type: int
    data: str

    @property
    def value(self):
        return float(self.data) if self.data_type == 1 else int(self.data)

    def raise_for_error(self):
        if self.command_error or self.controller_error:
            raise ControllerError(
                f"Command error={self.command_error}, controller error={self.controller_error}, status={self.status}"
            )


def checksum(frame_prefix: bytes) -> int:
    result = 0
    for byte in frame_prefix:
        result ^= byte
    return result


def _frame(payload: str) -> bytes:
    body = bytes((SOH, STX)) + payload.encode("ascii") + bytes((ETX,))
    return body + str(checksum(body[2:])).encode("ascii") + bytes((EOT,))


def encode_command(code: str, parameter: int = 0, data_type: int = 0, value: int | float = 0) -> bytes:
    if len(code) != 4 or not code.isascii() or not code.isalnum():
        raise ValueError("Command code must contain exactly 4 ASCII alphanumeric characters")
    if parameter < 0 or data_type not in (0, 1):
        raise ValueError("Invalid parameter or data_type")
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError("Value must be numeric")
    return _frame(f"{code};{parameter};{data_type};{value}")


def decode_reply(raw: bytes, *, verify_checksum: bool = True) -> Reply:
    if not raw.startswith(bytes((SOH, STX))) or not raw.endswith(bytes((EOT,))):
        raise ProtocolError("Invalid SOH/STX/EOT framing")
    try:
        etx_index = raw.index(bytes((ETX,)), 2)
        check_text = raw[etx_index + 1:-1].decode("ascii")
        if not check_text.isdigit() or not 1 <= len(check_text) <= 3:
            raise ProtocolError("Invalid checksum field")
        if verify_checksum and int(check_text) != checksum(raw[2:etx_index + 1]):
            raise ProtocolError("Checksum mismatch")
        fields = raw[2:etx_index].decode("ascii").split(";")
        if len(fields) != 6:
            raise ProtocolError(f"Expected six reply fields, got {len(fields)}")
        error, completed, status, machine_error, dtype = map(int, fields[:5])
        if completed not in (0, 1) or dtype not in (0, 1):
            raise ProtocolError("Invalid reply flag or data type")
        return Reply(error, bool(completed), status, machine_error, dtype, fields[5])
    except (ValueError, UnicodeDecodeError) as exc:
        raise ProtocolError("Invalid ASCII or numeric reply data") from exc
