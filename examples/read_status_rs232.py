from pypacontrol import PAControl

# Configure COM1 as Online Command in WINPAC before using this example.
with PAControl.rs232(model="compact", port="COM3", baudrate=9600, bytesize=7, parity="N") as pac:
    reply = pac.get_status()
    print("Controller status:", reply.status)
    print("Controller error:", reply.controller_error)
