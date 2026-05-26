# Developing Drivers with the Mock LiteVNA

This guide walks you through developing Python drivers for the LiteVNA‑64 device using the mock TCP server.

## Why Use a Mock?

- No physical hardware required
- Consistent, predictable behavior
- Ability to test error handling
- Fast iteration without cable connections
- Can run automated tests in CI/CD

## Getting Started

1. **Start the mock server** in a terminal:

   ```bash
   python mock_device/mock_litevna.py --port 12346 --verbose
   ```

   The `--verbose` flag shows every command and response, which is invaluable for debugging.

2. **Write a simple connection test** using raw sockets:

   ```python
   import socket
   import struct

   sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   sock.connect(('localhost', 12346))
   sock.send(b'\x10\xF3\x10\xF4')  # Read firmware version
   response = sock.recv(2)
   print(f"Firmware: {response[0]}.{response[1]}")
   sock.close()
   ```

3. **Graduate to PySerial** for a more serial‑port‑like interface:

   ```python
   import serial
   ser = serial.serial_for_url('socket://localhost:12346', timeout=2)
   ser.write(b'\x10\xF3\x10\xF4')
   response = ser.read(2)
   print(f"Firmware: {response[0]}.{response[1]}")
   ser.close()
   ```

## Understanding the Binary Protocol

The LiteVNA uses a register‑based binary protocol:

- **Commands**: One byte (`0x10` = READ, `0x20` = WRITE, etc.)
- **Address**: One byte (register address)
- **Data**: Optional bytes depending on command

Example: `WRITE8` command (`0x23`) followed by address `0x00` and an 8‑byte little‑endian frequency value.

### Common Operations

#### Read Firmware Version

```python
cmd = b'\x10\xF3\x10\xF4'  # READ major, READ minor
ser.write(cmd)
major, minor = ser.read(2)
```

#### Set Sweep Start Frequency

```python
import struct
start_hz = 100_000_000  # 100 MHz
cmd = struct.pack('<BBQ', 0x23, 0x00, start_hz)
ser.write(cmd)
```

#### Read FIFO Data

```python
points = 10
cmd = struct.pack('<BBB', 0x18, 0x30, points)
ser.write(cmd)
header = ser.read(4)  # 4‑byte point count
num_points = struct.unpack('<I', header)[0]
data = ser.read(num_points * 32)  # 32 bytes per point
```

## Advanced Topics

### Customizing the Mock Behavior

Create a YAML configuration file to change:

- Firmware/hardware version
- Battery voltage
- Default sweep parameters
- FIFO data generation

See `mock_device/litevna_config.yaml` for the full schema.

### Simulating Real‑World Conditions

Modify `mock_litevna.py` to:

- Add random delays (simulate slow USB)
- Introduce bit errors (test error recovery)
- Simulate device disconnections
- Vary measurement noise

### Integrating with PyMeasure

PyMeasure expects an `Instrument` subclass with a specific adapter. Study the PyMeasure documentation to wrap your driver in the PyMeasure framework.

## Troubleshooting

**"Connection refused"** – The mock server isn't running. Start it first.

**No response / timeout** – Check command format. Use `--verbose` to see if the server received your command.

**Incorrect data** – Verify endianness and data sizes. The mock expects little‑endian.

**PyVISA errors** – Ensure `pyvisa‑py` backend is installed and configured.

## Next Steps

1. Implement all LiteVNA commands in your driver
2. Add S‑parameter calculations (convert raw I/Q to S11, S21)
3. Create a GUI front‑end using PyQt or Tkinter
4. Package your driver as a Python library

Remember: The mock is a learning tool. Once your driver works with the mock, test it with a real LiteVNA device.
