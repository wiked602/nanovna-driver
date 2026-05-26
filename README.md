# LiteVNA Driver Development Repository

This repository is designed for students to develop drivers for the LiteVNA‑64 (Vector Network Analyzer) device. Students will learn to write drivers using three different libraries: **PySerial**, **PyVISA-py**, and **PyMeasure**.

A **mock LiteVNA TCP server** is included to allow development and testing without physical hardware. The mock emulates the binary register‑based protocol of a real LiteVNA‑64 device, providing realistic responses for firmware version, battery voltage, frequency sweeps, and measurement data.

## Prerequisites

- **Python 3.11** (or later) installed on your system
- Basic knowledge of Python and serial communication

## Setting Up the Development Environment

### 1. Create a Virtual Environment

It is recommended to use a virtual environment to isolate project dependencies.

```bash
python -m venv .venv
```

### 2. Activate the Virtual Environment

- **Windows (Command Prompt)**:
  ```cmd
  .venv\Scripts\activate
  ```

- **Windows (PowerShell)**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```

- **Linux / macOS**:
  ```bash
  source .venv/bin/activate
  ```

### 3. Install Required Libraries

With the virtual environment activated, install the dependencies:

```bash
pip install pyserial pyvisa pyvisa-py pymeasure pytest
```

Alternatively, you can use the `requirements.txt` file:

```bash
pip install -r requirements.txt
```

## Repository Structure

```
nanovna-driver-py/
├── README.md                          ← This file
├── requirements.txt                   ← Project dependencies
├── main.py                           ← Example connection code
├── mock_device/                      ← Mock LiteVNA TCP server
│   ├── __init__.py
│   ├── mock_litevna.py               # TCP server emulating LiteVNA
│   ├── run_mock_litevna.sh           # Linux/macOS start script
│   ├── run_mock_litevna.bat          # Windows start script
│   ├── litevna_config.yaml           # Example configuration
│   └── README.md                     # Detailed mock documentation
├── src/                              # Source code (student drivers go here)
│   ├── __init__.py
│   └── driver.py                     # Placeholder for student driver
└── docs/                             # Documentation
    └── ...                           # Additional guides
```

## Using the Mock LiteVNA

The repository includes a **mock LiteVNA TCP server** that emulates the binary protocol of a real LiteVNA‑64 device. This allows you to develop and test drivers without needing physical hardware.

### Starting the Mock Server

Run the mock server in a terminal:

```bash
python mock_device/mock_litevna.py --port 12346
```

The server will listen on TCP port 12346.

You can customize the mock device behavior using a YAML configuration file (see `mock_device/litevna_config.yaml` for an example):

```bash
python mock_device/mock_litevna.py --config mock_device/litevna_config.yaml --port 12346
```

### Connecting to the Mock

You can connect to the mock device in several ways:

1. **PySerial with socket:// URL (Recommended)**:
   ```python
   import serial
   ser = serial.serial_for_url('socket://localhost:12346', timeout=1)
   ser.write(b'\x10\xF3\x10\xF4')  # Read firmware version
   response = ser.read(2)
   ```

2. **Raw TCP socket**:
   ```python
   import socket
   s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
   s.connect(('localhost', 12346))
   s.send(b'\x10\xF3\x10\xF4')
   response = s.recv(1024)
   ```

3. **PyVISA with TCPIP socket**:
   ```python
   import pyvisa
   rm = pyvisa.ResourceManager()
   inst = rm.open_resource('TCPIP::localhost::12346::SOCKET')
   inst.write_raw(b'\x10\xF3\x10\xF4')
   response = inst.read_bytes(2)
   ```

4. **Virtual COM port** (optional):
   - On Linux/macOS: Use `socat` to create a virtual serial port:
     ```bash
     socat PTY,link=/dev/ttyVLNA0,raw TCP:localhost:12346
     ```
   - On Windows: Use `com2tcp` (from com0com) to create a COM port that forwards to the TCP server.

For detailed protocol documentation and more examples, see [mock_device/README.md](mock_device/README.md).

## Learning Path

1. **Understand the LiteVNA protocol**:
   - Read the mock device documentation in `mock_device/README.md`
   - Study the example driver `mock_device/example_litevna_driver.py`
   - Examine the binary command set and register map

2. **Learn PySerial**:
   - Connect to the mock device using PySerial with the `socket://` URL (recommended)
   - Implement a `LiteVNASerial` class with methods like `get_firmware_version()`, `set_sweep()`, `read_measurement()`

3. **Learn PyVISA**:
   - Study how PyVISA works with the pyvisa‑py backend
   - Configure PyVISA to use the mock device via a TCPIP socket connection
   - Implement a `LiteVNAVisa` class that uses the same binary command set

4. **Learn PyMeasure**:
   - Understand PyMeasure’s `Instrument` class and adapter system
   - Configure an adapter that connects to the mock device
   - Implement a `LiteVNAPyMeasure` class that subclasses `Instrument`

5. **Compare and Contrast**:
   - Write a demo that uses all three drivers interchangeably with the mock
   - Reflect on the advantages and disadvantages of each library

## Skeleton Drivers

Skeleton driver implementations should be placed in `src/drivers/` (create this directory if needed):

- `litevna_serial.py` – PySerial‑based driver
- `litevna_visa.py` – PyVISA‑based driver  
- `litevna_pymeasure.py` – PyMeasure‑based driver

These skeletons should implement basic connection handling and a few example commands. Students should extend them with the full LiteVNA command set.

## Running Tests

A test suite is provided to verify the mock server connection:

```bash
python mock_device/test_mock_litevna.py
```

See `mock_device/README.md` for detailed testing instructions.

## Useful Links

- [LiteVNA Hardware Documentation](https://github.com/erikkaashoek/liteVNA)
- [NanoVNASaver Project](https://github.com/NanoVNA-Saver/nanovna-saver) (includes LiteVNA driver code)
- [PySerial Documentation](https://pyserial.readthedocs.io/)
- [PyVISA Documentation](https://pyvisa.readthedocs.io/)
- [PyMeasure Documentation](https://pymeasure.readthedocs.io/)

## License

This educational project is provided under the MIT License.
