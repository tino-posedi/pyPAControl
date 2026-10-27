import argparse
from . import Model, PAControl

def main():
    parser = argparse.ArgumentParser(prog="pypacontrol", description="IEF PA-CONTROL interface client")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("models", help="List supported model identifiers")
    status = sub.add_parser("status", help="Read status (non-motion command)")
    status.add_argument("--model", required=True, choices=[m.value for m in Model])
    status.add_argument("--interface", required=True, choices=["rs232", "com", "usb", "ethernet"])
    status.add_argument("--port", help="Serial port (e.g. COM3, /dev/ttyUSB0)")
    status.add_argument("--baudrate", type=int, default=9600)
    status.add_argument("--bytesize", type=int, choices=[7, 8], default=7)
    status.add_argument("--parity", choices=["N", "E", "O"], default="N")
    status.add_argument("--host")
    status.add_argument("--tcp-port", type=int)
    status.add_argument("--protocol-confirmed", action="store_true")
    args = parser.parse_args()
    if args.cmd == "models":
        print("\n".join(m.value for m in Model))
        return
    if args.interface in ("rs232", "com", "usb"):
        if not args.port:
            parser.error("--port required for RS232")
        device = getattr(PAControl, args.interface)(args.model, args.port, baudrate=args.baudrate,
                                 bytesize=args.bytesize, parity=args.parity)
    else:
        if not args.host or args.tcp_port is None:
            parser.error("--host and --tcp-port required for Ethernet")
        device = PAControl.ethernet(args.model, args.host, args.tcp_port,
                                    protocol_confirmed=args.protocol_confirmed)
    with device:
        print(device.get_status())

if __name__ == "__main__":
    main()
