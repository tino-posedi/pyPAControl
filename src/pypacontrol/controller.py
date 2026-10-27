"""PA-CONTROL communication facade; commands are opt-in rather than guessed."""
from dataclasses import dataclass
from enum import Enum
from .protocol import Reply, decode_reply, encode_command
from .api import OnlineReadAPI
from .actions import OnlineActions, ActionsDisabledError
from .transports import SerialTransport, TCPTransport, Transport

class Model(str, Enum):
    SINGLE = "single"
    COMPACT = "compact"
    CPU4 = "cpu4"
    STEUERGERAET = "steuergeraet"
    MP = "mp"
    SERVOTEC = "servotec"
    SMART = "smart"
    TOUCH = "touch"

@dataclass(frozen=True)
class DeviceConfig:
    model: Model
    interface: str

class PAControl(OnlineReadAPI, OnlineActions):
    def __init__(self, model: Model | str, transport: Transport, *, enable_actions: bool = False, program_select_register: int | None = None):
        if program_select_register is not None:
            from .api import check_index
            check_index("program_select_register", program_select_register, 1024)
        self.program_select_register = program_select_register
        self.model = Model(model)
        self.transport = transport
        self.enable_actions = bool(enable_actions)
        self._pending = False

    @classmethod
    def rs232(cls, model: Model | str, port: str, *, enable_actions=False, program_select_register=None, **kwargs):
        return cls(model, SerialTransport(port, **kwargs), enable_actions=enable_actions, program_select_register=program_select_register)

    @classmethod
    def com(cls, model: Model | str, port: str, **kwargs):
        """Windows COM port, using serial communication (same as rs232)."""
        return cls.rs232(model, port, **kwargs)

    @classmethod
    def usb(cls, model: Model | str, port: str, **kwargs):
        """USB-to-serial adapter / USB CDC exposed as COM or tty device."""
        return cls.rs232(model, port, **kwargs)

    @classmethod
    def modbus_tcp(cls, model: Model | str, host: str, port: int = 502,
                   *, unit_id: int = 1, timeout: float = 2.0, register_map=None, enable_actions=False):
        """Create a separate Modbus/TCP client (not PA-CONTROL Online Command).

        Requires model-specific register map for meaningful addresses.
        """
        from .modbus import ModbusTCPClient
        return ModbusTCPClient(model=Model(model), host=host, port=port,
                               unit_id=unit_id, timeout=timeout, register_map=register_map, enable_actions=enable_actions)

    @classmethod
    def ethernet(cls, model: Model | str, host: str, port: int, *, protocol_confirmed=False, enable_actions=False, program_select_register=None, **kwargs):
        if not protocol_confirmed:
            raise ValueError("TCP framing is not verified for this PA-CONTROL model. "
                             "Set protocol_confirmed=True only after consulting its documentation.")
        return cls(model, TCPTransport(host, port, **kwargs), enable_actions=enable_actions, program_select_register=program_select_register)

    @classmethod
    def custom(cls, model: Model | str, transport: Transport, *, enable_actions=False, program_select_register=None):
        return cls(model, transport, enable_actions=enable_actions, program_select_register=program_select_register)

    def connect(self):
        self.transport.connect()
        return self

    def close(self):
        self.transport.close()

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    def command(self, code: str, parameter=0, data_type=0, value=0, *, check_errors=True) -> Reply:
        """Send an explicit, documented command. No automatic polling or motion."""
        if self._pending:
            raise RuntimeError("A previous long-running command is pending; call wait_until_complete()")
        self.transport.write(encode_command(code, parameter, data_type, value))
        result = decode_reply(self.transport.read_frame())
        if check_errors:
            result.raise_for_error()
        self._pending = not result.completed
        return result

    def get_status(self) -> Reply:
        """Request CMD_GET_STATUS (1F00) according to the 2010 interface manual."""
        return self.command("1F00")

    def poll(self) -> Reply:
        """Poll completion of previously accepted long-running command (single EOT)."""
        self.transport.write(b"\x04")
        reply = decode_reply(self.transport.read_frame())
        reply.raise_for_error()
        self._pending = not reply.completed
        return reply

    def wait_until_complete(self, *, max_polls: int = 100):
        """Poll pending command; polling is bounded, no unbounded waiting."""
        if not isinstance(max_polls, int) or not 1 <= max_polls <= 100000:
            raise ValueError("max_polls must be between 1 and 100000")
        for _ in range(max_polls):
            if not self._pending:
                return None
            last = self.poll()
            if last.completed:
                return last
        raise TimeoutError("Command still running after max_polls; controller may still be moving")
