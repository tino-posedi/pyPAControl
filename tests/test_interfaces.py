import struct
import pytest
from pypacontrol import PAControl, ModbusTCPClient, ModbusError


def test_serial_aliases():
    for name in ("com", "usb", "rs232"):
        controller = getattr(PAControl, name)("compact", "COM2")
        assert controller.transport.options["port"] == "COM2"


def test_modbus_factory():
    client = PAControl.modbus_tcp("cpu4", "127.0.0.1", unit_id=2)
    assert isinstance(client, ModbusTCPClient)
    assert client.unit_id == 2


class FakeSocket:
    def __init__(self, response):
        self.response = response
        self.sent = b""
    def sendall(self, data): self.sent += data
    def recv(self, count):
        chunk, self.response = self.response[:count], self.response[count:]
        return chunk


def test_modbus_read_holding_registers():
    pdu = bytes([3, 4, 0, 42, 0, 43])
    response = struct.pack(">HHHB", 1, 0, len(pdu)+1, 1) + pdu
    client = PAControl.modbus_tcp("touch", "127.0.0.1")
    client._sock = FakeSocket(response)
    assert client.read_holding_registers(100, 2) == [42, 43]
    assert client._sock.sent == struct.pack(">HHHBBHH", 1, 0, 6, 1, 3, 100, 2)


def test_modbus_exception():
    pdu = bytes([0x83, 2])
    client = PAControl.modbus_tcp("touch", "127.0.0.1")
    client._sock = FakeSocket(struct.pack(">HHHB", 1, 0, len(pdu)+1, 1) + pdu)
    with pytest.raises(ModbusError, match="exception 2"):
        client.read_holding_registers(0)


def test_invalid_register_count():
    client = PAControl.modbus_tcp("touch", "127.0.0.1")
    client._sock = FakeSocket(b"")
    with pytest.raises(ValueError):
        client.read_holding_registers(0, 126)
