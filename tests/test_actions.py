import pytest
from pypacontrol import PAControl, ActionsDisabledError, UnsupportedFeatureError
from pypacontrol.protocol import _frame

class FakeTransport:
    def __init__(self, completed=True):
        self.sent=[]
        self.completed=completed
    def connect(self): return self
    def write(self, data): self.sent.append(data)
    def read_frame(self): return _frame(f'0;{int(self.completed)};31;0;0;0')
    def close(self): pass

def test_actions_disabled_by_default():
    f=FakeTransport()
    pac=PAControl.custom('compact',f)
    with pytest.raises(ActionsDisabledError): pac.move_absolute(1,100)
    assert not f.sent

def test_online_actions_codes():
    f=FakeTransport()
    pac=PAControl.custom('compact',f,enable_actions=True)
    pac.move_absolute(1,100.5)
    pac.move_relative(2,-2,asynchronous=True)
    pac.stop_axis(1)
    pac.stop()
    assert b'0A87;1;1;100.5' in f.sent[0]
    assert b'0A95;2;1;-2.0' in f.sent[1]
    assert b'0A9A;1;0;0' in f.sent[2]
    assert b'0600;0;0;0' in f.sent[3]

def test_pending_uses_poll():
    f=FakeTransport(completed=False)
    pac=PAControl.custom('compact',f,enable_actions=True)
    pac.move_absolute(1,5)
    with pytest.raises(RuntimeError): pac.get_status()
    f.completed=True
    pac.wait_until_complete()
    assert f.sent[-1]==b'\x04'
    pac.get_status()

def test_online_writes_and_program_start():
    f=FakeTransport()
    pac=PAControl.custom('compact',f,enable_actions=True)
    pac.set_output(13,True)
    pac.set_register(97,12589)
    pac.set_register(27,10.0,kind='float')
    pac.start_program()
    assert b'0902;13;0;1' in f.sent[0]
    assert b'0906;97;0;12589' in f.sent[1]
    assert b'0907;27;1;10.0' in f.sent[2]
    assert b'0602;0;0;0' in f.sent[3]

def test_numbered_program_requires_explicit_selection_mapping():
    f=FakeTransport()
    pac=PAControl.custom('compact',f,enable_actions=True)
    with pytest.raises(UnsupportedFeatureError): pac.start_program(12)
    assert not f.sent
    pac=PAControl.custom('compact',f,enable_actions=True,program_select_register=99)
    pac.start_program(12)
    assert b'0906;99;0;12' in f.sent[0]
    assert b'0602;0;0;0' in f.sent[1]

def test_write_guards():
    f=FakeTransport()
    pac=PAControl.custom('compact',f)
    with pytest.raises(ActionsDisabledError): pac.start_program()
    with pytest.raises(ActionsDisabledError): pac.set_output(1,True)
    with pytest.raises(ActionsDisabledError): pac.set_register(1,1)
    assert not f.sent
    pac=PAControl.custom('compact',f,enable_actions=True)
    with pytest.raises(ValueError): pac.set_output(1,1)
    with pytest.raises(ValueError): pac.set_register(1,2**40)
    with pytest.raises(ValueError): pac.set_register(1,float('inf'),kind='float')
    with pytest.raises(ValueError): pac.start_program(0)
    assert not f.sent

class FakeSocket:
    def __init__(self): self.sent=[]; self.buf=b''
    def sendall(self,data):
        import struct
        self.sent.append(data)
        tx,_,_,unit=struct.unpack('>HHHB',data[:7]); pdu=data[7:]
        resp=pdu[:5]
        self.buf=struct.pack('>HHHB',tx,0,len(resp)+1,unit)+resp
    def recv(self,n):
        v,self.buf=self.buf[:n],self.buf[n:]
        return v

def test_modbus_write_and_mapping():
    from pypacontrol.modbus import ModbusTCPClient
    c=ModbusTCPClient('compact','localhost',enable_actions=True,register_map={('output',1):{'function':1,'address':12,'writable':True},('int',9):{'function':3,'address':42,'writable':True}})
    sock=FakeSocket();c._sock=sock
    assert c.set_output(1,True)
    assert sock.sent[0][7:]==b'\x05\x00\x0c\xff\x00'
    assert c.set_register(9,47)
    assert sock.sent[1][7:]==b'\x06\x00*\x00/'
    assert c.write_multiple_registers(4,[1,2])
    assert c.write_multiple_coils(20,[True,False,True])

def test_modbus_write_not_enabled():
    from pypacontrol.modbus import ModbusTCPClient
    c=ModbusTCPClient('compact','localhost')
    with pytest.raises(ActionsDisabledError): c.write_single_register(1,2)
