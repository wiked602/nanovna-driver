import socket
import struct
import serial

try:
    import pyvisa as pv

    PYVISA_AVAILABLE = True
except ImportError:
    PYVISA_AVAILABLE = False

# LiteVNA protocol constants
_CMD_READ = 0x10
_CMD_READ2 = 0x11
_ADDR_FW_MAJOR = 0xF3
_ADDR_FW_MINOR = 0xF4
_ADDR_VBAT = 0x5C


def raw_socket(host, port):
    """Example 1: raw TCP socket (no extra libraries)."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((host, port))
    sock.settimeout(2.0)

    try:
        # Read firmware version (two READ commands concatenated)
        cmd = struct.pack("<BBBB", _CMD_READ, _ADDR_FW_MAJOR, _CMD_READ, _ADDR_FW_MINOR)
        sock.sendall(cmd)
        major, minor = sock.recv(2)
        print(f"Firmware: {major}.{minor}")

        # Read battery voltage (READ2 = 2‑byte read)
        cmd = struct.pack("<BB", _CMD_READ2, _ADDR_VBAT)
        sock.sendall(cmd)
        millivolts = struct.unpack("<H", sock.recv(2))[0]
        print(f"Battery: {millivolts / 1000:.3f} V")
    finally:
        sock.close()
        print("Socket closed.")


def pyserial_socket(host, port):
    """Example 2: PySerial with socket:// (feels like a serial port)."""

    ser = serial.serial_for_url(f"socket://{host}:{port}", timeout=2)
    try:
        cmd = struct.pack("<BBBB", _CMD_READ, _ADDR_FW_MAJOR, _CMD_READ, _ADDR_FW_MINOR)
        ser.write(cmd)
        major, minor = ser.read(2)
        print(f"Firmware: {major}.{minor}")

        cmd = struct.pack("<BB", _CMD_READ2, _ADDR_VBAT)
        ser.write(cmd)
        millivolts = struct.unpack("<H", ser.read(2))[0]
        print(f"Battery: {millivolts / 1000:.3f} V")
    finally:
        ser.close()
        print("Serial connection closed.")


if PYVISA_AVAILABLE:

    def pyvisa_ex(host, port):
        """Example 3: PyVISA with TCPIP socket."""
        rm = pv.ResourceManager()
        device = rm.open_resource(f"TCPIP::{host}::{port}::SOCKET")
        device.timeout = 2000  # milliseconds

        try:
            # Read firmware version (two READ commands concatenated)
            cmd = struct.pack(
                "<BBBB", _CMD_READ, _ADDR_FW_MAJOR, _CMD_READ, _ADDR_FW_MINOR
            )
            device.write_raw(cmd)
            response = device.read_bytes(2)
            major, minor = response[0], response[1]
            print(f"Firmware: {major}.{minor}")

            # Read battery voltage (READ2 = 2‑byte read)
            cmd = struct.pack("<BB", _CMD_READ2, _ADDR_VBAT)
            device.write_raw(cmd)
            response = device.read_bytes(2)
            millivolts = struct.unpack("<H", response)[0]
            print(f"Battery: {millivolts / 1000:.3f} V")
        finally:
            device.close()
            print("PyVISA connection closed.")
else:

    def pyvisa_ex(host, port):
        raise ImportError("PyVISA is not installed")


def main():
    host = "localhost"
    port = 12346

    raw_socket(host, port)
    pyserial_socket(host, port)

    # Try PyVISA example (optional)
    try:
        pyvisa_ex(host, port)
    except Exception as e:
        print(f"PyVISA example skipped: {e}")


if __name__ == "__main__":
    main()
