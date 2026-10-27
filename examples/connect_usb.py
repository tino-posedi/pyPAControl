from pypacontrol import PAControl

# USB-RS232 dongle / USB CDC: COM5 on Windows, /dev/ttyUSB0 or /dev/ttyACM0 on Linux.
with PAControl.usb("compact", port="COM5", baudrate=9600, bytesize=7) as device:
    print(device.get_status())
