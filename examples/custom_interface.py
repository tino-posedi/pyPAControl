from pypacontrol import PAControl, Transport

class MyGateway(Transport):
    def connect(self):
        raise NotImplementedError("Connect your tested gateway here")
    def write(self, data: bytes):
        raise NotImplementedError
    def read_frame(self) -> bytes:
        raise NotImplementedError
    def close(self):
        pass

# pac = PAControl.custom("mp", MyGateway())
