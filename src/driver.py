import struct
from typing import Tuple, List, Optional

try:
    from pymeasure.instruments import Instrument
    from pymeasure.adapters import Adapter
except ImportError:
    Instrument = None
    Adapter = None

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


# Register addresses
ADDR_FW_MAJOR = 0xF3
ADDR_FW_MINOR = 0xF4
ADDR_HARDWARE_REVISION = 0xF2
ADDR_VBAT_MILIVOLTS = 0x5C
ADDR_SWEEP_START = 0x00
ADDR_SWEEP_STEP = 0x10
ADDR_SWEEP_POINTS = 0x20
ADDR_VALUES_FIFO = 0x30
ADDR_DEVICE_VARIANT = 0xF0          
ADDR_PROTOCOL_VERSION = 0xF1              

MAX_FREQ = 6300000000
VALID_POINTS = [51, 101, 201, 401, 801, 1024, 1601, 3201, 4501, 6401, 12801, 25601]


class LiteVNAPyMeasure(Instrument):
    """PyMeasure-based driver for LiteVNA-64."""

    def __init__(self, adapter, name="LiteVNA", **kwargs):
        super().__init__(adapter, name, includeSCPI=False, **kwargs)

    def _send_command(self, cmd: int, addr: int, value: int = 0, extra: bytes = b"") -> bytes:
        """Send a binary command and return response.

        Args:
            cmd: Command byte
            addr: Register address
            value: Integer value for WRITE commands
            extra: Extra bytes (e.g., point count for READFIFO)

        Returns:
            Response bytes, or None for WRITE commands.
        """
        payload = b""
        if cmd in [CMD_WRITE, CMD_WRITE2, CMD_WRITE4, CMD_WRITE8]:
            fmt = {CMD_WRITE: "<B", CMD_WRITE2: "<H", CMD_WRITE4: "<I", CMD_WRITE8: "<Q"}[cmd]
            payload = struct.pack(fmt, value)
        
        packet = struct.pack("<BB", cmd, addr) + payload + extra
        self.adapter.write_bytes(packet)
        
        # Если команда чтения — ждем ответ
        if cmd in [CMD_READ, CMD_READ2, CMD_READ4, CMD_READ8]:
            size = {CMD_READ: 1, CMD_READ2: 2, CMD_READ4: 4, CMD_READ8: 8}[cmd]
            return self.adapter.read_bytes(size)
        return b""
    
    def write(self, command: str):
        """Парсит строку и отправляет байты"""
        if not command.startswith("hex:"):
            return super().write(command)
        
        parts = command.replace("hex:", "").split()
        cmd = int(parts[0])
        addr = int(parts[1])
        val = int(parts[2]) if len(parts) > 2 else 0
        self._send_command(cmd, addr, val)

    def values(self, command: str, **kwargs):
        """Читает данные и возвращает их как список"""
        if not command.startswith("hex:"):
            return super().values(command, **kwargs)
            
        parts = command.replace("hex:", "").split()
        cmd = int(parts[0])
        addr = int(parts[1])
        
        raw = self._send_command(cmd, addr)
        
        fmt_map = {CMD_READ: "<B", CMD_READ2: "<H", CMD_READ4: "<I", CMD_READ8: "<Q"}
        if cmd in fmt_map:
            return [struct.unpack(fmt_map[cmd], raw)[0]]
        return [raw]

    def validate_freq(value, target):
        if not (0 <= value <= MAX_FREQ):
            raise ValueError(f"Частота {value} больше допустимого (0-{MAX_FREQ})")
        return value
    
    def validate_points(value, target):
        if value not in VALID_POINTS:
            raise ValueError(f"Количество точек {value} недопустимо. Разрешено: {VALID_POINTS}")
        return value
    
# дескрипторы
    start_frequency = Instrument.control(
        f"hex:{CMD_READ8} {ADDR_SWEEP_START}", 
        f"hex:{CMD_WRITE8} {ADDR_SWEEP_START} %d",
        "Начальная частота свипа в Гц",
        validator=validate_freq
    )

    step_frequency = Instrument.control(
        f"hex:{CMD_READ8} {ADDR_SWEEP_STEP}", 
        f"hex:{CMD_WRITE8} {ADDR_SWEEP_STEP} %d",
        "Шаг частоты в Гц"
    )

    sweep_points = Instrument.control(
        f"hex:{CMD_READ2} {ADDR_SWEEP_POINTS}", 
        f"hex:{CMD_WRITE2} {ADDR_SWEEP_POINTS} %d",
        "Количество точек свипа",
        validator=validate_points
    )

    battery_mv = Instrument.measurement(
        f"hex:{CMD_READ2} {ADDR_VBAT_MILIVOLTS}",
        "Напряжение батареи в милливольтах"
    )

    def get_firmware_version(self) -> Tuple[int, int]:
        """Return firmware major and minor version"""
        major = self.values(f"hex:{CMD_READ} {ADDR_FW_MAJOR}")[0]
        minor = self.values(f"hex:{CMD_READ} {ADDR_FW_MINOR}")[0]
        return (major, minor)

    def get_hardware_revision(self) -> int:
        """Return hardware revision byte."""
        return self.values(f"hex:{CMD_READ} {ADDR_HARDWARE_REVISION}")[0]

    def get_battery_voltage(self) -> float:
        """Return battery voltage in volts."""
        return self.battery_mv / 1000.0

    def set_sweep(self, start_hz: int, step_hz: int, points: int):
        """Configure frequency sweep."""
        self.start_frequency = start_hz
        self.step_frequency = step_hz
        self.sweep_points = points

    def read_measurement(self, points: int) -> List[Tuple]:
        """Read measurement data for given number of points.

        Returns:
            List of tuples (fwd_real, fwd_imag, refl_real, refl_imag,
                            thru_real, thru_imag, freq_index)
        """

        if points not in VALID_POINTS:
            raise ValueError(f"Количество точек {points} недопустимо.")
        
        extra_param = struct.pack("<B", points)
        packet = struct.pack("<BB", CMD_READFIFO, ADDR_VALUES_FIFO) + extra_param
        self.adapter.write_bytes(packet)
        
        header = self.adapter.read_bytes(4)
        if not header: return []
        
        actual_count = struct.unpack("<I", header)[0]
        data = self.adapter.read_bytes(actual_count * 32)
        
        results = []
        for i in range(actual_count):
            chunk = data[i*32 : (i+1)*32]
            # Формат: 6 знаковых int32 + 1 uint16 (индекс) + 6 байт пропуска
            val = struct.unpack("<iiiiiiHxxxxxx", chunk)
            results.append(val)
        return results
    
if __name__ == "__main__":
    if Instrument is None:
        print("PyMeasure not installed. Install with: pip install pymeasure")
    else:
        print("PyMeasure skeleton - adapter creation not implemented")