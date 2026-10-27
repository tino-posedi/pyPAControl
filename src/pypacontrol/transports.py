"""Replaceable byte transports. TCP is a raw stream, NOT a claim of protocol support."""
from abc import ABC, abstractmethod
import socket

class TransportError(OSError):
    pass

class Transport(ABC):
    @abstractmethod
    def connect(self): ...
    @abstractmethod
    def write(self, data: bytes): ...
    @abstractmethod
    def read_frame(self) -> bytes: ...
    @abstractmethod
    def close(self): ...

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *_):
        self.close()


def _read_frame(read_byte, max_size=4096):
    result = bytearray()
    while len(result) < max_size:
        byte = read_byte()
        if not byte:
            raise TransportError("Timeout or connection closed while awaiting EOT")
        result.extend(byte)
        if byte == b"\x04":
            return bytes(result)
    raise TransportError("Response exceeds maximum telegram length")

class SerialTransport(Transport):
    def __init__(self, port: str, baudrate=9600, bytesize=7, parity="N", stopbits=1, timeout=2.0):
        self.options = dict(port=port, baudrate=baudrate, bytesize=bytesize,
                            parity=parity, stopbits=stopbits, timeout=timeout,
                            write_timeout=timeout)
        self._serial = None

    def connect(self):
        if self._serial is None:
            try:
                import serial
            except ImportError as exc:
                raise ImportError('RS232 requires: pip install "pypacontrol[serial]"') from exc
            self._serial = serial.Serial(**self.options)

    def write(self, data):
        if self._serial is None:
            raise TransportError("Serial interface not connected")
        self._serial.write(data)
        self._serial.flush()

    def read_frame(self):
        if self._serial is None:
            raise TransportError("Serial interface not connected")
        return _read_frame(lambda: self._serial.read(1))

    def close(self):
        if self._serial is not None:
            self._serial.close()
            self._serial = None

class TCPTransport(Transport):
    """Experimental byte transport: only use if TCP-protocol compatibility is confirmed."""
    def __init__(self, host: str, port: int, timeout=2.0):
        self.host, self.port, self.timeout = host, port, timeout
        self._sock = None

    def connect(self):
        if self._sock is None:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._sock.settimeout(self.timeout)

    def write(self, data):
        if self._sock is None:
            raise TransportError("TCP interface not connected")
        self._sock.sendall(data)

    def read_frame(self):
        if self._sock is None:
            raise TransportError("TCP interface not connected")
        return _read_frame(lambda: self._sock.recv(1))

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None
