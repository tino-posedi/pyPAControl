import pytest
from pypacontrol import PAControl, ProtocolError, encode_command, decode_reply
from pypacontrol.protocol import _frame
from pypacontrol.transports import Transport


def test_status_packet_matches_manual():
    assert encode_command("1F00") == b"\x01\x021F00;0;0;0\x03127\x04"


def test_reply_from_manual():
    result = decode_reply(b"\x01\x020;1;1;0;0;0\x0356\x04")
    assert result.status == 1 and result.completed and result.value == 0


def test_checksum_rejected():
    with pytest.raises(ProtocolError):
        decode_reply(b"\x01\x020;1;1;0;0;0\x0399\x04")


def test_roundtrip():
    result = decode_reply(_frame("0;1;31;0;1;12.5"))
    assert result.status == 31 and result.value == 12.5


class FakeTransport(Transport):
    def __init__(self): self.sent = []
    def connect(self): pass
    def write(self, data): self.sent.append(data)
    def read_frame(self): return _frame("0;1;1;0;0;0")
    def close(self): pass


def test_mock_controller():
    fake = FakeTransport()
    with PAControl.custom("compact", fake) as controller:
        assert controller.get_status().status == 1
    assert fake.sent == [encode_command("1F00")]


def test_tcp_requires_explicit_confirmation():
    with pytest.raises(ValueError):
        PAControl.ethernet("touch", "192.0.2.1", 1234)
