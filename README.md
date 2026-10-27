<img alt="ief" src="https://github.com/user-attachments/assets/da4b0204-954b-4ca8-b3b0-5c70d55bcaeb" />

## Implemented

- Explicit device selection: `single`, `compact`, `cpu4`, `steuergeraet`, `mp`, `servotec`, `smart`, `touch`.
- `com`, `rs232` and `usb` (USB-to-serial / USB CDC) via pyserial, with configurable serial parameters.
- Modbus TCP read-only client (FC 01, 02, 03, 04) with separate binary MBAP framing; user supplies device-specific register addresses.
- Experimental TCP byte transport behind explicit `protocol_confirmed=True` safeguard.
- Pluggable `Transport` abstract base class for gateways and other physical interfaces.
- Legacy PA-CONTROL Online Command framing and decimal ASCII XOR checksum.
- `get_status()` command (`1F00`); `command()` for documented manual command codes; one-shot `poll()` for incomplete operations.
- Deterministic mocked unit tests and CLI.

## Installation

```bash
pip install -e '.[serial,dev]'
pytest -q
pypacontrol models
```

## Safe, read-only serial example

In WINPAC, configure the intended COM1 as Online Command, then confirm cable pinout and serial parameters with the actual controller manual.

```python
from pypacontrol import PAControl

with PAControl.rs232(model="compact", port="COM3", baudrate=9600,
                     bytesize=7, parity="N") as pac:
    print(pac.get_status())
```

**Note:** The 2010 interfaces manual describes 9600 baud, 7N1 as a standard setting, while some newer CPU4 documentation says 8N1. Match your actual device configuration; don't assume.

## CLI

```bash
pypacontrol models
pypacontrol status --model compact --interface rs232 --port COM3 --bytesize 7
```

## Ethernet / TCP (EXPERIMENTAL)

A TCP socket is **not** evidence that PA-CONTROL Online Command is supported over TCP. Do not make assumptions about the destination port or encapsulation. Only use when the exact controller/gateway documentation confirms raw Online Command over TCP.

```python
from pypacontrol import PAControl

# Example only: host and TCP port MUST come from your verified gateway configuration.
with PAControl.ethernet("touch", host="192.0.2.10", port=12345,
                        protocol_confirmed=True) as pac:
    print(pac.get_status())
```

`Touch` is an identifier here; native Ethernet communication is **not verified** by this example.

## Choose the interface

```python
from pypacontrol import PAControl

# COM (Windows serial port)
pac = PAControl.com("compact", port="COM3", baudrate=9600)

# RS232 (e.g. Linux native serial port)
pac = PAControl.rs232("cpu4", port="/dev/ttyS0", baudrate=9600)

# USB serial adapter / USB CDC device (does NOT imply a native USB protocol)
pac = PAControl.usb("single", port="/dev/ttyUSB0", baudrate=9600)

# Raw Online Command over Ethernet (only if verified for device/gateway)
pac = PAControl.ethernet("touch", host="192.0.2.10", port=12345,
                         protocol_confirmed=True)

# Modbus TCP (separate protocol; requires verified device support/register map)
mb = PAControl.modbus_tcp("cpu4", host="192.0.2.20", port=502, unit_id=1)
with mb:
    values = mb.read_holding_registers(address=0, count=2)  # example address only
```

**Important:** An RJ45/Ethernet port does not establish Modbus TCP support. Not every PA-CONTROL model speaks Modbus TCP. Never assume specific register addresses, especially for motion/safety functions. USB here means a virtual serial port or USB-RS232 adapter, not an undocumented native USB interface. `ModbusTCPClient` does not provide `get_status()` because no vendor-specific register map has been confirmed. All methods only read; they do not write coils/registers.

## Other interfaces

Implement `Transport.connect()`, `.write(bytes)`, `.read_frame()`, and `.close()`; pass instance with `PAControl.custom(model, transport)`. Profibus and CANopen have separate application protocols and cannot simply use raw serial framing. No CANopen/Profibus drivers are claimed as implemented.

## Protocol basis

IEF-Werner PA-CONTROL *Schnittstellenhandbuch*, July 2010, art. 1006913, sections 3.1–3.4:

https://www.ief.de/fileadmin/Download-Explorer/DE/2_Komponenten/6_Steuerungstechnik/1_Steuerungen/3_PA-CONTROL_CPU4/Weitere_Dokumente/MAN_DE_1006913_PAC_Schnittstellen.pdf

Request telegram: `SOH STX CMD;PAR_1;TYP_PAR_2;PAR_2 ETX CHECK EOT`.

Response telegram: `SOH STX QUIT;BE;STATUS;ERROR;TYP_QUIT;Q_PAR ETX CHECK EOT`.

`CHECK` uses decimal ASCII XOR of the payload through ETX, **excluding SOH/STX**. This reproduces the official examples (`1F00` → `127`; sample reply → `56`). The manual prose claims XOR begins at SOH, which contradicts its own examples; this needs verification on real hardware. One-shot polling of asynchronous command completion sends only EOT. The read-only `1F00` status request is demonstrated in the official manual.

## Important industrial safety notes

- **Not a certified safety component.** Never use this library for emergency stop, protective functions or safety interlocks.
- Test initially on a disconnected or safely simulated machine; secure physical axes before trying any motion commands.
- Read the machine manual and determine authorized machine modes before sending commands.
- `command()` can send arbitrary documented commands (including potentially hazardous ones). Use only after risk assessment.
- No automatic reconnect, motion control, software limits, reference travel, or production-ready error recovery in v0.1.0.

## Development roadmap

1. Validate actual RS232 telegram exchanges against Single, Compact, CPU4, MP and servoTEC devices.
2. Add typed read-only axis position and I/O commands after confirming codes/parameters in specific firmware manuals.
3. Add a documented feature matrix per firmware and model.
4. Validate Modbus TCP availability and register maps per model; implement CANopen and Profibus gateways where applicable.
5. Add motion control with explicit machine-state validation, operator control and acceptance tests.

## License

MIT. Trademark and product names belong to their respective owners.
