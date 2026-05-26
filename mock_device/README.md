# Mock LiteVNA Device

This directory contains a mock LiteVNA‑64 TCP server that emulates the binary protocol of a real LiteVNA device. It allows students to develop and test Python drivers without physical hardware.

## Files

- `mock_litevna.py` – TCP server that accepts binary commands and returns appropriate responses.
- `__init__.py` – Makes this directory a Python package.
- `run_mock_litevna.sh` – Shell script to start the server (Linux/macOS).
- `run_mock_litevna.bat` – Batch script to start the server (Windows).
- `litevna_config.yaml` – Example YAML configuration file.

## Usage

Start the mock server (default port 12346):

```bash
python mock_litevna.py --port 12346
```

Or use the convenience scripts:

```bash
# Linux/macOS
./run_mock_litevna.sh 12346

# Windows
run_mock_litevna.bat 12346
```

The server will listen on TCP port 12346 and respond to binary commands.

### Command‑Line Options

- `--port PORT` – TCP port to listen on (default: 12346)
- `--host HOST` – Host interface to bind to (default: 0.0.0.0)
- `--config CONFIG` – Path to YAML configuration file (optional)
- `--verbose, -v` – Enable verbose logging (shows each command and response)

Example with verbose logging:

```bash
python mock_litevna.py --port 12346 --verbose
```

### Configuration

The mock server can be customized using a YAML configuration file. Create a file like `litevna_config.yaml` with the following structure:

```yaml
# Firmware version (major, minor)
firmware_major: 2
firmware_minor: 2

# Hardware revision (byte)
hardware_revision: 2

# Battery voltage in millivolts (0-65535)
battery_voltage_mv: 3700

# Default sweep parameters (used on startup)
sweep_start_hz: 1000000
sweep_step_hz: 1000000
sweep_points: 101

# Valid datapoint counts (must match device limitations)
valid_datapoints: [51, 101, 201, 401, 801, 1024, 1601, 3201, 4501, 6401, 12801, 25601]

# Maximum frequency in Hz
max_frequency_hz: 6300000000

# Screen dimensions (for screenshot generation)
screen_width: 480
screen_height: 320
screen_depth: 16  # RGB565

# Data generation parameters (for FIFO)
fifo:
  # Base amplitude for forward signal
  fwd_base: 1000
  fwd_amplitude: 500
  refl_amplitude: 200
  thru_amplitude: 300
  # Frequency variation
  fwd_freq: 0.1
  refl_freq: 0.2
  thru_freq: 0.142857

# Logging level (DEBUG, INFO, WARNING, ERROR)
logging_level: INFO
```

To use a configuration file, start the server with:

```bash
python mock_litevna.py --config litevna_config.yaml --port 12346
```

## Connecting

You can connect to the mock device using several methods:

### Raw TCP Socket (Low‑level)

```python
import socket
import struct

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.connect(('localhost', 12346))

# Read firmware version (two READ commands concatenated)
cmd = struct.pack('<BBBB', 0x10, 0xF3, 0x10, 0xF4)
s.sendall(cmd)
resp = s.recv(2)
major, minor = resp[0], resp[1]
```

### PySerial with socket:// (Recommended)

```python
import serial
import struct

ser = serial.serial_for_url('socket://localhost:12346', timeout=2)
ser.write(b'\x10\xF3\x10\xF4')
resp = ser.read(2)
major, minor = resp[0], resp[1]
ser.close()
```

### Virtual COM Port (Optional)

- **Linux/macOS**: Use `socat` to create a virtual serial port pair and forward one end to the TCP server:

  ```bash
  socat PTY,link=/dev/ttyVLNA0,raw TCP:localhost:12346
  ```
  Then connect to `/dev/ttyVLNA0` with any serial terminal.

- **Windows**: Use `com2tcp` (from com0com) to create a COM port that forwards to the TCP server:

  ```bash
  com2tcp --baud 115200 --ignore-dsr \\.\COM3 localhost 12346
  ```
  Then open `COM3` with PySerial.

## Binary Protocol Reference

The mock LiteVNA server implements a subset of the binary register‑based protocol used by LiteVNA‑64 devices. The protocol uses command bytes followed by address bytes and optional data.

### Command Bytes

- `0x10` – READ (1 byte)
- `0x11` – READ2 (2 bytes)
- `0x12` – READ4 (4 bytes)
- `0x13` – READ8 (8 bytes)
- `0x18` – READFIFO (4‑byte header + N × 32 bytes per point)
- `0x20` – WRITE (1 byte)
- `0x21` – WRITE2 (2 bytes)
- `0x22` – WRITE4 (4 bytes)
- `0x23` – WRITE8 (8 bytes)
- `0x28` – WRITEFIFO (not implemented in mock)

### Important Register Addresses

- `0x00` – Sweep start frequency (8 bytes, Hz)
- `0x10` – Sweep step frequency (8 bytes, Hz)
- `0x20` – Number of sweep points (2 bytes)
- `0x22` – Values per frequency (2 bytes, usually 1)
- `0x26` – Raw samples mode (1 byte)
- `0x30` – Values FIFO (read via READFIFO)
- `0x5C` – Battery voltage in millivolts (2 bytes)
- `0xEE` – Screenshot capture (write 0 to trigger, then read header + data)
- `0xF0` – Device variant (1 byte)
- `0xF1` – Protocol version (1 byte)
- `0xF2` – Hardware revision (1 byte)
- `0xF3` – Firmware major version (1 byte)
- `0xF4` – Firmware minor version (1 byte)

### Example Operations

**Read firmware version:**
```python
# Send two READ commands for major and minor version
cmd = b'\x10\xF3\x10\xF4'
ser.write(cmd)
resp = ser.read(2)
major, minor = resp[0], resp[1]
```

**Set sweep start frequency:**
```python
import struct
start_hz = 100_000_000
cmd = struct.pack('<BBQ', 0x23, 0x00, start_hz)
ser.write(cmd)
```

**Read FIFO data (1 point):**
```python
cmd = b'\x18\x30\x01'  # READFIFO, address 0x30, 1 point ser.write(cmd)
# First 4 bytes are number of points (uint32)
header = ser.read(4)
num_points = struct.unpack('<I', header)[0]
# Each point is 32 bytes
resp = ser.read(num_points * 32)
```

**Capture screenshot:**
```python
# Trigger capture
ser.write(b'\x20\xEE\x00')
# Read header (5 bytes)
header = ser.read(5)
width, height, depth = struct.unpack('<HHB', header)
data_size = width * height * (depth // 8)
# Read image data
image_data = ser.read(data_size)
```

## Testing the Connection

### Simple Socket Test

```python
import socket
import struct

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect(('localhost', 12346))
    s.send(b'\x10\xF3\x10\xF4')
    response = s.recv(2)
    print(f"Firmware version: {response[0]}.{response[1]}")
```

### PySerial Test

```python
import serial

try:
    ser = serial.serial_for_url('socket://localhost:12346', timeout=2)
    ser.write(b'\x10\xF3\x10\xF4')
    response = ser.read(2)
    print(f"Firmware version: {response[0]}.{response[1]}")
    ser.close()
except Exception as e:
    print(f"Connection error: {e}")
```

## Logging

When started with `--verbose`, the server logs each command received, the register address, the value (for writes), and the response size. This is extremely helpful for debugging your driver.

Example log output:
```
2026-04-09 16:14:04,248 - DEBUG - Processing command: READ addr=0xf3 extra=
2026-04-09 16:14:04,248 - DEBUG - READ addr 0xf3: value=0x02
2026-04-09 16:14:04,248 - DEBUG - Command response: 1 bytes
2026-04-09 16:14:04,248 - DEBUG - Sending 2 bytes to 127.0.0.1:41940
```

## Development

Use the mock server to develop and test your LiteVNA driver without hardware. The mock implements the core protocol commands needed for basic VNA operations.

For more details on the real LiteVNA protocol, refer to the LiteVNA documentation and the NanoVNASaver source code.
