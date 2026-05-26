#!/usr/bin/env python3
"""
Skeleton driver for LiteVNA using PySerial.

Students should implement the missing methods.
"""

import serial
import struct
from typing import Tuple, List, Optional

# Command bytes
CMD_READ = 0x10
CMD_READ2 = 0x11
CMD_READ4 = 0x12
CMD_READ8 = 0x13
CMD_READFIFO = 0x18
CMD_WRITE = 0x20
CMD_WRITE2 = 0x21
CMD_WRITE4 = 0x22
CMD_WRITE8 = 0x23

# Register addresses (add more as needed)
ADDR_FW_MAJOR = 0xF3
ADDR_FW_MINOR = 0xF4
ADDR_HARDWARE_REVISION = 0xF2
ADDR_VBAT_MILIVOLTS = 0x5C
ADDR_SWEEP_START = 0x00
ADDR_SWEEP_STEP = 0x10
ADDR_SWEEP_POINTS = 0x20
ADDR_VALUES_FIFO = 0x30


class LiteVNASerial:
    """PySerial-based driver for LiteVNA-64."""

    def __init__(self, host="localhost", port=12346):
        """Initialize driver.

        Args:
            host: Server hostname or IP
            port: TCP port number
        """
        self.host = host
        self.port = port
        self.ser = None

    def connect(self):
        """Establish connection to the device."""
        # TODO: Implement connection using PySerial's serial_for_url
        # Use socket:// URL: f"socket://{self.host}:{self.port}"
        raise NotImplementedError("Implement connect method")

    def disconnect(self):
        """Close connection."""
        # TODO: Close serial connection if open
        raise NotImplementedError("Implement disconnect method")

    def _send_command(
        self, cmd: int, addr: int, value: int = 0, extra: bytes = b""
    ) -> Optional[bytes]:
        """Send a binary command and return response.

        Args:
            cmd: Command byte
            addr: Register address
            value: Integer value for WRITE commands
            extra: Extra bytes (e.g., point count for READFIFO)

        Returns:
            Response bytes, or None for WRITE commands.
        """
        # TODO: Implement command sending and response reading
        # Hint: Use self.ser.write() and self.ser.read()
        raise NotImplementedError("Implement _send_command method")

    def get_firmware_version(self) -> Tuple[int, int]:
        """Return firmware major and minor version."""
        # TODO: Use _send_command with READ commands
        raise NotImplementedError("Implement get_firmware_version")

    def get_hardware_revision(self) -> int:
        """Return hardware revision byte."""
        raise NotImplementedError("Implement get_hardware_revision")

    def get_battery_voltage(self) -> float:
        """Return battery voltage in volts."""
        raise NotImplementedError("Implement get_battery_voltage")

    def set_sweep(self, start_hz: int, step_hz: int, points: int):
        """Configure frequency sweep.

        Args:
            start_hz: Start frequency in Hz
            step_hz: Step frequency in Hz
            points: Number of sweep points
        """
        # TODO: Use WRITE8 for start and step, WRITE2 for points
        raise NotImplementedError("Implement set_sweep")

    def read_measurement(self, points: int) -> List[Tuple]:
        """Read measurement data for given number of points.

        Args:
            points: Number of measurement points to read

        Returns:
            List of tuples (fwd_real, fwd_imag, refl_real, refl_imag,
                            thru_real, thru_imag, freq_index)
        """
        # TODO: Use READFIFO command
        # Remember: response includes 4‑byte header with point count
        raise NotImplementedError("Implement read_measurement")

    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()


# Example usage
if __name__ == "__main__":
    # Simple test (requires mock server running)
    try:
        with LiteVNASerial() as vna:
            print("Connected")
            # Uncomment and implement:
            # version = vna.get_firmware_version()
            # print(f"Firmware: {version[0]}.{version[1]}")
    except NotImplementedError as e:
        print(f"Driver not yet implemented: {e}")
