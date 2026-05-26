#!/usr/bin/env python3

import socketserver
import logging
import argparse
import math
import struct
import yaml
from typing import Dict, Tuple, Optional, Union

# Command bytes 
_CMD_NOP = 0x00
_CMD_INDICATE = 0x0D
_CMD_READ = 0x10
_CMD_READ2 = 0x11
_CMD_READ4 = 0x12
_CMD_READ8 = 0x13
_CMD_READFIFO = 0x18
_CMD_WRITE = 0x20
_CMD_WRITE2 = 0x21
_CMD_WRITE4 = 0x22
_CMD_WRITE8 = 0x23
_CMD_WRITEFIFO = 0x28

# Register addresses
_ADDR_SWEEP_START = 0x00
_ADDR_SWEEP_STEP = 0x10
_ADDR_SWEEP_POINTS = 0x20
_ADDR_SWEEP_VALS_PER_FREQ = 0x22
_ADDR_RAW_SAMPLES_MODE = 0x26
_ADDR_VALUES_FIFO = 0x30
_ADDR_DEVICE_VARIANT = 0xF0
_ADDR_PROTOCOL_VERSION = 0xF1
_ADDR_HARDWARE_REVISION = 0xF2
_ADDR_FW_MAJOR = 0xF3
_ADDR_FW_MINOR = 0xF4
_ADDR_VBAT_MILIVOLTS = 0x5C
_ADDR_SCREENSHOT = 0xEE

# LiteVNA-64 specific
SCREEN_WIDTH = 480
SCREEN_HEIGHT = 320
SCREEN_DEPTH = 16  # RGB565
VALID_DATAPOINTS = (51, 101, 201, 401, 801, 1024, 1601, 3201, 4501, 6401, 12801, 25601)
SWEEP_MAX_FREQ_HZ = 6300e6
EXPECTED_HW_VERSION = (2, 2, 0)  # Version.build(2,2,0)
EXPECTED_FW_VERSION = (2, 2, 0)

# Command name mapping for logging
_CMD_NAMES = {
    _CMD_NOP: "NOP",
    _CMD_INDICATE: "INDICATE",
    _CMD_READ: "READ",
    _CMD_READ2: "READ2",
    _CMD_READ4: "READ4",
    _CMD_READ8: "READ8",
    _CMD_READFIFO: "READFIFO",
    _CMD_WRITE: "WRITE",
    _CMD_WRITE2: "WRITE2",
    _CMD_WRITE4: "WRITE4",
    _CMD_WRITE8: "WRITE8",
    _CMD_WRITEFIFO: "WRITEFIFO",
}


def _cmd_name(cmd_byte: int) -> str:
    """Return human-readable command name."""
    return _CMD_NAMES.get(cmd_byte, f"UNKNOWN(0x{cmd_byte:02x})")


def load_config(config_path: Optional[str] = None) -> Dict:
    """Load configuration from YAML file or use defaults."""
    config = {
        "firmware_major": 2,
        "firmware_minor": 2,
        "hardware_revision": 2,
        "battery_voltage_mv": 3700,
        "sweep_start_hz": 1000000,
        "sweep_step_hz": 1000000,
        "sweep_points": 101,
        "valid_datapoints": [
            51,
            101,
            201,
            401,
            801,
            1024,
            1601,
            3201,
            4501,
            6401,
            12801,
            25601,
        ],
        "max_frequency_hz": 6300000000,
        "screen_width": 480,
        "screen_height": 320,
        "screen_depth": 16,
        "fifo": {
            "fwd_base": 1000,
            "fwd_amplitude": 500,
            "refl_amplitude": 200,
            "thru_amplitude": 300,
            "fwd_freq": 0.1,
            "refl_freq": 0.2,
            "thru_freq": 0.142857,
        },
        "logging_level": "INFO",
    }

    if config_path:
        try:
            with open(config_path, "r") as f:
                user_config = yaml.safe_load(f)
                if user_config:
                    # Merge user config into defaults
                    for key, value in user_config.items():
                        if (
                            isinstance(value, dict)
                            and key in config
                            and isinstance(config[key], dict)
                        ):
                            config[key].update(value)
                        else:
                            config[key] = value
                    logging.info(f"Loaded configuration from {config_path}")
        except FileNotFoundError:
            logging.warning(f"Config file {config_path} not found, using defaults")
        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML config: {e}")
        except Exception as e:
            logging.error(f"Error loading config: {e}")

    return config


class LiteVNADevice:
    """Emulator for LiteVNA-64 binary protocol."""

    def __init__(self, config=None):
        if config is None:
            config = {}
        self.config = config

        # Configuration-derived constants
        self.valid_datapoints = tuple(
            config.get(
                "valid_datapoints",
                [51, 101, 201, 401, 801, 1024, 1601, 3201, 4501, 6401, 12801, 25601],
            )
        )
        self.sweep_max_freq_hz = config.get("max_frequency_hz", 6300000000)
        self.screen_width = config.get("screen_width", 480)
        self.screen_height = config.get("screen_height", 320)
        self.screen_depth = config.get("screen_depth", 16)

        # FIFO generation parameters
        self.fifo_config = config.get(
            "fifo",
            {
                "fwd_base": 1000,
                "fwd_amplitude": 500,
                "refl_amplitude": 200,
                "thru_amplitude": 300,
                "fwd_freq": 0.1,
                "refl_freq": 0.2,
                "thru_freq": 0.142857,
            },
        )

        # Sweep state from config or defaults
        self.sweep_start_hz = config.get("sweep_start_hz", 200e6)
        self.sweep_step_hz = config.get("sweep_step_hz", 1e6)
        self.datapoints = config.get("sweep_points", 201)

        # Register map: address -> (size_bytes, value_int)
        self.registers: Dict[int, Tuple[int, int]] = {}
        self._init_registers()

        # Screenshot buffer
        self._screenshot_data = None
        self._generate_screenshot()

        logging.info("LiteVNADevice initialized with config")

    def _init_registers(self):
        """Set default register values."""
        config = self.config

        # Hardware/firmware version from config
        fw_major = config.get("firmware_major", 2)
        fw_minor = config.get("firmware_minor", 2)
        hw_revision = config.get("hardware_revision", 2)
        battery_mv = config.get("battery_voltage_mv", 3700)

        self._set_register(_ADDR_DEVICE_VARIANT, 1, 1)  # device variant
        self._set_register(_ADDR_HARDWARE_REVISION, hw_revision, 1)
        self._set_register(_ADDR_FW_MAJOR, fw_major, 1)
        self._set_register(_ADDR_FW_MINOR, fw_minor, 1)
        self._set_register(_ADDR_PROTOCOL_VERSION, 1, 1)  # protocol version

        # Sweep parameters (will be updated when sweep is set)
        self._set_register(_ADDR_SWEEP_START, int(self.sweep_start_hz), 8)
        self._set_register(_ADDR_SWEEP_STEP, int(self.sweep_step_hz), 8)
        self._set_register(_ADDR_SWEEP_POINTS, self.datapoints, 2)
        self._set_register(_ADDR_SWEEP_VALS_PER_FREQ, 1, 2)
        self._set_register(_ADDR_RAW_SAMPLES_MODE, 0, 1)

        # Battery voltage
        self._set_register(_ADDR_VBAT_MILIVOLTS, battery_mv, 2)

    def _set_register(self, addr: int, value: int, size: int):
        """Store register value."""
        self.registers[addr] = (size, value)

    def _get_register(self, addr: int) -> Optional[Tuple[int, int]]:
        """Get register size and value, or None if not found."""
        return self.registers.get(addr)

    def _generate_screenshot(self):
        """Generate a dummy RGB565 screenshot."""
        # Header: width, height, depth
        header = struct.pack(
            "<HHB", self.screen_width, self.screen_height, self.screen_depth
        )

        # Generate simple gradient image
        data = bytearray()
        for y in range(self.screen_height):
            for x in range(self.screen_width):
                # Simple gradient: red increases horizontally, green vertically
                r = int((x / self.screen_width) * 31) & 0x1F
                g = int((y / self.screen_height) * 63) & 0x3F
                b = 16  # constant blue
                rgb565 = (r << 11) | (g << 5) | b
                data.extend(struct.pack(">H", rgb565))

        self._screenshot_data = header + bytes(data)

    def _generate_fifo_data(self, points: int) -> bytes:
        """Generate fake FIFO data for given number of points.

        Returns: 4-byte header (points as uint32) + points * 32 bytes of data.
        """
        # Each point: 6 int32 + int16 freq_index + 6 padding = 32 bytes
        cfg = self.fifo_config
        fwd_base = cfg.get("fwd_base", 1000)
        fwd_amp = cfg.get("fwd_amplitude", 500)
        refl_amp = cfg.get("refl_amplitude", 200)
        thru_amp = cfg.get("thru_amplitude", 300)
        fwd_freq = cfg.get("fwd_freq", 0.1)
        refl_freq = cfg.get("refl_freq", 0.2)
        thru_freq = cfg.get("thru_freq", 0.142857)

        data = bytearray()
        # Header: number of points as uint32
        data.extend(struct.pack("<I", points))

        for i in range(points):
            # Fake forward signal (some amplitude/phase)
            fwd_real = fwd_base + int(fwd_amp * math.sin(i * fwd_freq))
            fwd_imag = int(fwd_amp * math.cos(i * fwd_freq))

            # Reflection (some random complex)
            refl_real = int(refl_amp * math.sin(i * refl_freq))
            refl_imag = int(refl_amp * math.cos(i * refl_freq))

            # Transmission (another random)
            thru_real = int(thru_amp * math.sin(i * thru_freq))
            thru_imag = int(thru_amp * math.cos(i * thru_freq))

            # Frequency index (just sequential)
            freq_index = i

            # Pack as per <iiiiiihxxxxxx
            point_data = struct.pack(
                "<iiiiiihxxxxxx",
                fwd_real,
                fwd_imag,
                refl_real,
                refl_imag,
                thru_real,
                thru_imag,
                freq_index,
            )
            data.extend(point_data)
        return bytes(data)

    def process_command(
        self, cmd_byte: int, addr_byte: int, extra_data: bytes
    ) -> bytes:
        """Process a single binary command.

        Returns response bytes (empty for writes).
        """
        if cmd_byte == _CMD_NOP:
            return b""

        elif cmd_byte == _CMD_READ:
            # Read 1 byte from register
            reg = self._get_register(addr_byte)
            if reg is None:
                logging.debug(
                    f"READ addr 0x{addr_byte:02x}: register not found, returning 0"
                )
                return b"\x00"  # default zero
            size, value = reg
            if size != 1:
                logging.warning(f"READ from non-1-byte register 0x{addr_byte:02x}")
            logging.debug(f"READ addr 0x{addr_byte:02x}: value=0x{value:02x}")
            return struct.pack("<B", value & 0xFF)

        elif cmd_byte == _CMD_READ2:
            reg = self._get_register(addr_byte)
            if reg is None:
                logging.debug(
                    f"READ2 addr 0x{addr_byte:02x}: register not found, returning 0"
                )
                return b"\x00\x00"
            size, value = reg
            if size != 2:
                logging.warning(f"READ2 from non-2-byte register 0x{addr_byte:02x}")
            logging.debug(
                f"READ2 addr 0x{addr_byte:02x}: value=0x{value:04x} ({value})"
            )
            return struct.pack("<H", value & 0xFFFF)

        elif cmd_byte == _CMD_READ4:
            reg = self._get_register(addr_byte)
            if reg is None:
                logging.debug(
                    f"READ4 addr 0x{addr_byte:02x}: register not found, returning 0"
                )
                return b"\x00\x00\x00\x00"
            size, value = reg
            if size != 4:
                logging.warning(f"READ4 from non-4-byte register 0x{addr_byte:02x}")
            logging.debug(
                f"READ4 addr 0x{addr_byte:02x}: value=0x{value:08x} ({value})"
            )
            return struct.pack("<I", value & 0xFFFFFFFF)

        elif cmd_byte == _CMD_READ8:
            reg = self._get_register(addr_byte)
            if reg is None:
                logging.debug(
                    f"READ8 addr 0x{addr_byte:02x}: register not found, returning 0"
                )
                return b"\x00\x00\x00\x00\x00\x00\x00\x00"
            size, value = reg
            if size != 8:
                logging.warning(f"READ8 from non-8-byte register 0x{addr_byte:02x}")
            logging.debug(
                f"READ8 addr 0x{addr_byte:02x}: value=0x{value:016x} ({value})"
            )
            return struct.pack("<Q", value & 0xFFFFFFFFFFFFFFFF)

        elif cmd_byte == _CMD_READFIFO:
            # extra_data[0] = pointstoread (byte)
            if len(extra_data) < 1:
                logging.error("READFIFO missing pointstoread byte")
                return b""
            pointstoread = extra_data[0]
            logging.debug(
                f"READFIFO addr 0x{addr_byte:02x}: reading {pointstoread} points"
            )
            # Generate FIFO data for requested points
            fifo_data = self._generate_fifo_data(pointstoread)
            logging.debug(f"READFIFO response: {len(fifo_data)} bytes")
            return fifo_data

        elif cmd_byte == _CMD_WRITE:
            if len(extra_data) < 1:
                logging.error("WRITE missing value byte")
                return b""
            value = extra_data[0]
            logging.debug(
                f"WRITE addr 0x{addr_byte:02x}: value=0x{value:02x} ({value})"
            )
            self._set_register(addr_byte, value, 1)
            # Special handling for screenshot trigger
            if addr_byte == _ADDR_SCREENSHOT:
                logging.debug(
                    f"WRITE to screenshot trigger, returning {len(self._screenshot_data)} bytes"
                )
                return self._screenshot_data
            self._handle_register_write(addr_byte, value, 1)
            return b""

        elif cmd_byte == _CMD_WRITE2:
            if len(extra_data) < 2:
                logging.error("WRITE2 missing value bytes")
                return b""
            value = struct.unpack("<H", extra_data[:2])[0]
            logging.debug(
                f"WRITE2 addr 0x{addr_byte:02x}: value=0x{value:04x} ({value})"
            )
            self._set_register(addr_byte, value, 2)
            self._handle_register_write(addr_byte, value, 2)
            return b""

        elif cmd_byte == _CMD_WRITE4:
            if len(extra_data) < 4:
                logging.error("WRITE4 missing value bytes")
                return b""
            value = struct.unpack("<I", extra_data[:4])[0]
            logging.debug(
                f"WRITE4 addr 0x{addr_byte:02x}: value=0x{value:08x} ({value})"
            )
            self._set_register(addr_byte, value, 4)
            self._handle_register_write(addr_byte, value, 4)
            return b""

        elif cmd_byte == _CMD_WRITE8:
            if len(extra_data) < 8:
                logging.error("WRITE8 missing value bytes")
                return b""
            value = struct.unpack("<Q", extra_data[:8])[0]
            logging.debug(
                f"WRITE8 addr 0x{addr_byte:02x}: value=0x{value:016x} ({value})"
            )
            self._set_register(addr_byte, value, 8)
            self._handle_register_write(addr_byte, value, 8)
            return b""

        elif cmd_byte == _CMD_WRITEFIFO:
            # Not implemented
            logging.warning(f"WRITEFIFO not implemented")
            return b""

        elif cmd_byte == _CMD_INDICATE:
            # Some indicator command, ignore
            return b""

        else:
            logging.warning(f"Unknown command byte 0x{cmd_byte:02x}")
            return b""

    def _handle_register_write(self, addr: int, value: int, size: int):
        """Update internal state based on register write."""
        if addr == _ADDR_SWEEP_START:
            self.sweep_start_hz = float(value)
        elif addr == _ADDR_SWEEP_STEP:
            self.sweep_step_hz = float(value)
        elif addr == _ADDR_SWEEP_POINTS:
            self.datapoints = value
            # Update register (already set)
        elif addr == _ADDR_RAW_SAMPLES_MODE:
            # Mode change, ignore for mock
            pass

    def process_data_stream(self, data: bytes) -> Tuple[bytes, bytes]:
        """Process a stream of binary commands.

        Returns (response_bytes, leftover_bytes) where leftover_bytes
        are incomplete command bytes that should be kept for next call.
        """
        response = bytearray()
        i = 0
        while i < len(data):
            # Need at least 2 bytes for cmd and addr
            if i + 2 > len(data):
                break
            cmd = data[i]
            addr = data[i + 1]
            i += 2

            # Determine payload size based on command
            payload_size = 0
            if cmd in (_CMD_WRITE, _CMD_INDICATE):
                payload_size = 1
            elif cmd == _CMD_WRITE2:
                payload_size = 2
            elif cmd == _CMD_WRITE4:
                payload_size = 4
            elif cmd == _CMD_WRITE8:
                payload_size = 8
            elif cmd == _CMD_READFIFO:
                payload_size = 1  # pointstoread byte
            elif cmd == _CMD_WRITEFIFO:
                # Not implemented; assume no payload
                pass

            if i + payload_size > len(data):
                # Not enough data for payload, put back cmd and addr
                i -= 2
                break

            extra = data[i : i + payload_size] if payload_size > 0 else b""
            i += payload_size

            # Log the command being processed
            cmd_name = _cmd_name(cmd)
            extra_hex = extra.hex() if extra else ""
            logging.debug(
                f"Processing command: {cmd_name} addr=0x{addr:02x} extra={extra_hex}"
            )

            cmd_response = self.process_command(cmd, addr, extra)

            if cmd_response:
                logging.debug(f"Command response: {len(cmd_response)} bytes")
            response.extend(cmd_response)

        # i is the number of bytes consumed
        total_response = bytes(response)
        if total_response:
            logging.debug(f"Total response: {len(total_response)} bytes")
        return total_response, data[i:]


class LiteVNAServer(socketserver.TCPServer):
    def __init__(self, server_address, RequestHandlerClass, config=None):
        super().__init__(server_address, RequestHandlerClass)
        self.config = config or {}


class LiteVNAHandler(socketserver.BaseRequestHandler):
    def handle(self):
        client_ip, client_port = self.client_address
        logging.info(f"Client connected from {client_ip}:{client_port}")
        device = LiteVNADevice(self.server.config)
        buffer = bytearray()

        while True:
            try:
                # Read available data
                data = self.request.recv(4096)
                if not data:
                    logging.info(
                        f"Client {client_ip}:{client_port} disconnected (no data)"
                    )
                    break

                logging.debug(
                    f"Received {len(data)} bytes from {client_ip}:{client_port}"
                )
                buffer.extend(data)
                # Process as much as possible
                response, leftover = device.process_data_stream(buffer)
                if response:
                    logging.debug(
                        f"Sending {len(response)} bytes to {client_ip}:{client_port}"
                    )
                    self.request.sendall(response)
                # Keep leftover for next iteration
                buffer = bytearray(leftover)

            except (ConnectionResetError, BrokenPipeError):
                logging.info(f"Client {client_ip}:{client_port} disconnected abruptly")
                break
            except Exception as e:
                logging.error(f"Handler error for {client_ip}:{client_port}: {e}")
                break


def run_server(port=12346, host="0.0.0.0", config=None):
    with LiteVNAServer((host, port), LiteVNAHandler, config) as server:
        logging.info(f"Mock LiteVNA listening on {host}:{port}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            logging.info("Server stopped")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Mock LiteVNA TCP server")
    parser.add_argument("--port", type=int, default=12346)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--config", help="Path to YAML configuration file")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
    )

    # Load configuration
    config = load_config(args.config)

    run_server(args.port, args.host, config)
