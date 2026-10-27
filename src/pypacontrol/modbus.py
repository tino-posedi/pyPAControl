"""Minimal read-only Modbus TCP client. No PA-CONTROL register map is presumed."""
import socket
import struct
from .api import UnsupportedFeatureError, check_index
from .transports import TransportError


class ModbusError(Exception):
    """Modbus exception or invalid Modbus/TCP response."""


class ModbusTCPClient:
    def __init__(self, model, host, port=502, *, unit_id=1, timeout=2.0, register_map=None, enable_actions=False):
        if not (0 <= unit_id <= 255):
            raise ValueError("unit_id must be between 0 and 255")
        if not (1 <= port <= 65535):
            raise ValueError("invalid TCP port")
        self.model, self.host, self.port = model, host, port
        self.unit_id, self.timeout = unit_id, timeout
        self._sock = None
        self._transaction = 0
        self.register_map = dict(register_map or {})
        self.enable_actions = bool(enable_actions)

    def connect(self):
        if self._sock is None:
            self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
            self._sock.settimeout(self.timeout)
        return self

    def close(self):
        if self._sock is not None:
            self._sock.close()
            self._sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    def _recv_exact(self, n):
        buf = bytearray()
        while len(buf) < n:
            piece = self._sock.recv(n - len(buf))
            if not piece:
                raise TransportError("Modbus TCP peer closed connection")
            buf.extend(piece)
        return bytes(buf)

    def _request(self, function, address, count):
        if self._sock is None:
            raise TransportError("Modbus TCP connection not established")
        if not 0 <= address <= 65535:
            raise ValueError("address must be between 0 and 65535 (zero-based)")
        limit = 125 if function in (3, 4) else 2000
        if not 1 <= count <= limit:
            raise ValueError(f"count must be between 1 and {limit}")
        self._transaction = (self._transaction + 1) & 0xFFFF
        pdu = struct.pack(">BHH", function, address, count)
        request = struct.pack(">HHHB", self._transaction, 0, len(pdu)+1, self.unit_id) + pdu
        self._sock.sendall(request)
        header = self._recv_exact(7)
        tx, protocol, length, unit = struct.unpack(">HHHB", header)
        if tx != self._transaction or protocol != 0 or unit != self.unit_id or not 2 <= length <= 254:
            raise ModbusError("Invalid Modbus TCP MBAP header")
        response = self._recv_exact(length - 1)
        if response[0] == (function | 0x80):
            if len(response) != 2:
                raise ModbusError("Invalid Modbus exception response")
            raise ModbusError(f"Modbus exception {response[1]} on function {function}")
        if response[0] != function or len(response) < 2:
            raise ModbusError("Unexpected Modbus function code")
        expected_bytes = count * 2 if function in (3, 4) else (count + 7) // 8
        if response[1] != expected_bytes or len(response) != 2 + expected_bytes:
            raise ModbusError("Invalid byte count in Modbus response")
        data = response[2:]
        if function in (3, 4):
            return list(struct.unpack(">" + "H" * count, data))
        return [bool(data[i // 8] & (1 << (i % 8))) for i in range(count)]

    def read_holding_registers(self, address, count=1):
        return self._request(3, address, count)

    def read_input_registers(self, address, count=1):
        return self._request(4, address, count)

    def read_coils(self, address, count=1):
        return self._request(1, address, count)

    def read_discrete_inputs(self, address, count=1):
        return self._request(2, address, count)

    def _mapping(self, field: str, index: int):
        """Register map keys are ('position'/'input'/'output'/'int'/'float', 1-based index).

        Values: {'function': 1|2|3|4, 'address': zero_based,
                 'count': 1|2, 'scale': numeric, 'signed': bool,
                 'float32': bool, 'word_order': 'big'|'little'}.
        Configure from the *actual* device register map. No default addresses.
        """
        item = self.register_map.get((field, index))
        if item is None:
            raise UnsupportedFeatureError(
                f"No Modbus mapping for {field} {index}; provide register_map from device documentation"
            )
        return item

    def _mapped_value(self, field, index):
        m = self._mapping(field, index)
        fc = m['function']
        addr = m['address']
        count = m.get('count', 1)
        if fc not in (1, 2, 3, 4):
            raise ValueError('Mapping function must be 1, 2, 3 or 4')
        values = self._request(fc, addr, count)
        if fc in (1, 2):
            if count != 1:
                raise ValueError('Boolean mappings require count=1')
            return values[0]
        if m.get('float32'):
            if count != 2:
                raise ValueError('float32 mapping requires count=2')
            words = values if m.get('word_order', 'big') == 'big' else list(reversed(values))
            value = struct.unpack('>f', struct.pack('>HH', *words))[0]
        else:
            if count not in (1, 2):
                raise ValueError('Numeric mapping requires count=1 or 2')
            words = values if m.get('word_order', 'big') == 'big' else list(reversed(values))
            value = words[0] if count == 1 else (words[0] << 16) | words[1]
            if m.get('signed'):
                bits = count * 16
                if value & (1 << (bits - 1)):
                    value -= 1 << bits
        return value * m.get('scale', 1)

    def get_position(self, axis: int) -> float:
        check_index('axis', axis, 16)
        return float(self._mapped_value('position', axis))

    def get_input(self, index: int) -> bool:
        check_index('input', index, 1024)
        return bool(self._mapped_value('input', index))

    def get_output(self, index: int) -> bool:
        check_index('output', index, 1024)
        return bool(self._mapped_value('output', index))

    def get_register(self, index: int, *, kind: str = 'int') -> int | float:
        check_index('register', index, 1024)
        if kind not in ('int', 'float'):
            raise ValueError("kind must be 'int' or 'float'")
        value = self._mapped_value(kind, index)
        return float(value) if kind == 'float' else int(value)

    def _write_request(self, function, address, values):
        """Modbus FC05/06/15/16; raw zero-based addresses, explicit enable required."""
        if not self.enable_actions:
            from .actions import ActionsDisabledError
            raise ActionsDisabledError('Modbus writes require enable_actions=True')
        if self._sock is None:
            raise TransportError('Modbus TCP connection not established')
        if not isinstance(address, int) or not 0 <= address <= 65535:
            raise ValueError('invalid address')
        if function in (5, 6):
            if len(values) != 1:
                raise ValueError('single write requires one value')
            val = (0xFF00 if values[0] else 0) if function == 5 else values[0]
            if not isinstance(val, int) or not 0 <= val <= 65535:
                raise ValueError('invalid register value')
            pdu = struct.pack('>BHH', function, address, val)
        elif function in (15, 16):
            n = len(values)
            limit = 1968 if function == 15 else 123
            if not 1 <= n <= limit or address + n > 65536:
                raise ValueError('invalid count or address range')
            if function == 15:
                if not all(isinstance(v, bool) for v in values):
                    raise ValueError('coil values must be bool')
                data = bytes(sum(int(values[i+j]) << j for j in range(min(8,n-i))) for i in range(0,n,8))
            else:
                if not all(isinstance(v,int) and not isinstance(v,bool) and 0 <= v <= 65535 for v in values):
                    raise ValueError('register values must be uint16')
                data = struct.pack('>'+'H'*n,*values)
            pdu = struct.pack('>BHHB',function,address,n,len(data))+data
        else:
            raise ValueError('invalid write function')
        self._transaction = (self._transaction+1) & 0xFFFF
        self._sock.sendall(struct.pack('>HHHB',self._transaction,0,len(pdu)+1,self.unit_id)+pdu)
        tx, proto, length, unit = struct.unpack('>HHHB',self._recv_exact(7))
        if (tx,proto,unit) != (self._transaction,0,self.unit_id) or not 2 <= length <= 254:
            raise ModbusError('Invalid write response header')
        response = self._recv_exact(length-1)
        if len(response)==2 and response[0]==(function|128):
            raise ModbusError(f'Modbus exception {response[1]}')
        if len(response)!=5 or response != pdu[:5]:
            raise ModbusError('Unexpected write response')
        return True

    def write_single_register(self, address: int, value: int):
        return self._write_request(6,address,[value])

    def write_single_coil(self, address: int, value: bool):
        if not isinstance(value,bool):
            raise ValueError('coil value must be bool')
        return self._write_request(5,address,[value])

    def write_multiple_registers(self, address: int, values):
        return self._write_request(16,address,list(values))

    def write_multiple_coils(self, address: int, values):
        return self._write_request(15,address,list(values))

    def set_output(self, index: int, value: bool):
        check_index('output',index,1024)
        mapping=self._mapping('output',index)
        if mapping.get('writable') is not True or mapping.get('function') != 1:
            raise UnsupportedFeatureError('Output requires explicitly writable coil mapping')
        return self.write_single_coil(mapping['address'],value)

    def set_register(self, index: int, value: int, *, kind='int'):
        check_index('register',index,1024)
        if kind != 'int' or not isinstance(value,int) or isinstance(value,bool) or not 0 <= value <= 65535:
            raise UnsupportedFeatureError('Only mapped uint16 register writes supported')
        mapping=self._mapping('int',index)
        if mapping.get('writable') is not True or mapping.get('function') != 3 or mapping.get('count',1) != 1:
            raise UnsupportedFeatureError('Register requires explicitly writable single holding register mapping')
        return self.write_single_register(mapping['address'],value)

    def move_absolute(self,*args,**kwargs):
        raise UnsupportedFeatureError('Modbus motion requires model-specific register/coil sequence and state-machine verification')
    def move_relative(self,*args,**kwargs):
        raise UnsupportedFeatureError('Modbus motion requires model-specific register/coil sequence and state-machine verification')
    def stop_axis(self,*args,**kwargs):
        raise UnsupportedFeatureError('Modbus stop requires documented model-specific register/coil mapping')

    def start_program(self, number=None):
        raise UnsupportedFeatureError('Modbus program start requires a verified device-specific register/coil command sequence')
