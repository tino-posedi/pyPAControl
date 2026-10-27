"""Read ONLY a register confirmed by the device-specific register map."""
from pypacontrol import PAControl

# Replace IP and address with values from your device's Modbus/TCP documentation.
with PAControl.modbus_tcp("touch", host="192.0.2.10", unit_id=1) as device:
    print(device.read_holding_registers(address=0, count=1))
