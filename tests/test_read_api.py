import pytest
from pypacontrol import PAControl, ModbusTCPClient, UnsupportedFeatureError
from pypacontrol.protocol import Reply

class FakeTransport:
    def connect(self): pass
    def close(self): pass
    def write(self, data): pass
    def read_frame(self): pass

@pytest.mark.parametrize('method,kwargs,code,param,result', [
    ('get_position', {'axis': 1}, '190C', 1, 12.5),
    ('get_input', {'index': 13}, '1900', 13, True),
    ('get_output', {'index': 2}, '1902', 2, True),
    ('get_register', {'index': 97}, '1906', 97, 12),
    ('get_register', {'index': 27, 'kind': 'float'}, '1907', 27, 12.5),
])
def test_online_read_mapping(method, kwargs, code, param, result):
    c = PAControl('compact', FakeTransport())
    seen = []
    def command(cmd, parameter=0, **kw):
        seen.append((cmd, parameter))
        data = '12.5' if method == 'get_position' or kwargs.get('kind') == 'float' else ('1' if method.startswith('get_in') or method.startswith('get_out') else '12')
        return Reply(0, True, 0, 0, int('.' in data), data)
    c.command = command
    assert getattr(c, method)(**kwargs) == result
    assert seen == [(code, param)]

def test_invalid_indexes():
    c = PAControl('compact', FakeTransport())
    for method, key in [('get_position','axis'),('get_input','index'),('get_output','index'),('get_register','index')]:
        with pytest.raises(ValueError):
            getattr(c, method)(**{key: 0})

def test_modbus_no_implicit_map():
    c = ModbusTCPClient('cpu4', '127.0.0.1')
    with pytest.raises(UnsupportedFeatureError):
        c.get_position(1)

def test_modbus_explicit_map():
    c = ModbusTCPClient('cpu4','127.0.0.1', register_map={('position',1): {'function': 3,'address': 15,'count': 2,'float32':True},('input',13): {'function':2,'address':12}})
    seen = []
    def request(fn, addr, count):
        seen.append((fn, addr, count))
        return [0x4148,0] if fn == 3 else [True]
    c._request = request
    assert c.get_position(1) == 12.5
    assert c.get_input(13) is True
    assert seen == [(3,15,2),(2,12,1)]
