# Command structure (40 bits total):
# B0: [addr:7][start:1]
# B1: [duty:7][freq_hi:1] 
# B2: [freq_lo:4][delay_hi:4]
# B3: [delay_mid:8]
# B4: [delay_lo:4][flags:4]
#
# Ranges: addr(0-127), duty(0-127), freq_index(0-31), delay_ms(0-65535), flags(0-15)

import math
import bisect
from typing import List, Dict, Union


def create_command(addr: int, duty: int, freq_index: int, start: bool, 
                  delay_ms: int, flags: int = 0) -> bytes:
    """Encode a single command into 5 bytes."""
    # Validate ranges
    if not (0 <= addr <= 127): raise ValueError(f"addr={addr} must be 0-127")
    if not (0 <= duty <= 127): raise ValueError(f"duty={duty} must be 0-127") 
    if not (0 <= freq_index <= 31): raise ValueError(f"freq_index={freq_index} must be 0-31")
    if not (0 <= delay_ms <= 65535): raise ValueError(f"delay_ms={delay_ms} must be 0-65535")
    if not (0 <= flags <= 15): raise ValueError(f"flags={flags} must be 0-15")

    start_bit = 1 if start else 0

    # Pack bits according to layout
    b0 = ((addr & 0x7F) << 1) | (start_bit & 0x01)
    b1 = ((duty & 0x7F) << 1) | ((freq_index >> 4) & 0x01)
    b2 = ((freq_index & 0x0F) << 4) | ((delay_ms >> 12) & 0x0F)
    b3 = (delay_ms >> 4) & 0xFF
    b4 = ((delay_ms & 0x0F) << 4) | (flags & 0x0F)
    
    return bytes([b0, b1, b2, b3, b4])


def decode_command(packet: bytes) -> Dict[str, int]:
    """Decode 5-byte packet into command dictionary."""
    if len(packet) != 5:
        raise ValueError(f"packet must be 5 bytes, got {len(packet)}")
    
    b0, b1, b2, b3, b4 = packet
    
    addr = (b0 >> 1) & 0x7F
    start = b0 & 0x01
    duty = (b1 >> 1) & 0x7F
    freq_index = ((b1 & 0x01) << 4) | ((b2 >> 4) & 0x0F)
    delay_ms = ((b2 & 0x0F) << 12) | ((b3 & 0xFF) << 4) | ((b4 >> 4) & 0x0F)
    flags = b4 & 0x0F
    
    return {
        "addr": addr,
        "duty": duty,
        "freq_index": freq_index,
        "start": start,
        "delay_ms": delay_ms,
        "flags": flags,
    }


def encode_batch(commands: List[Dict], max_frame_bytes: int = 250) -> List[bytes]:
    """Encode command list into frames, splitting if needed."""
    if not commands:
        raise ValueError("commands cannot be empty")
    
    max_commands_per_frame = max_frame_bytes // 5
    frames = []
    
    for i in range(0, len(commands), max_commands_per_frame):
        chunk = commands[i:i + max_commands_per_frame]
        frame = bytearray()
        
        for j, cmd in enumerate(chunk):
            try:
                # Handle flexible key names
                addr = cmd["addr"]
                duty = cmd["duty"]
                freq_index = cmd.get("freq_index", cmd.get("freq"))
                if freq_index is None:
                    raise KeyError("missing 'freq_index' or 'freq'")
                start = cmd.get("start", cmd.get("start_or_stop", 0))
                delay_ms = cmd["delay_ms"]
                flags = cmd.get("flags", 0)
                
                frame += create_command(addr, duty, freq_index, bool(start), delay_ms, flags)
                
            except (KeyError, ValueError) as e:
                raise ValueError(f"Error in command {j}: {e}")

        frames.append(bytes(frame))
    
    return frames


def decode_batch(frame: bytes) -> List[Dict[str, int]]:
    """Decode frame into list of commands."""
    if len(frame) % 5 != 0:
        raise ValueError(f"frame length {len(frame)} must be multiple of 5")
    
    commands = []
    for i in range(0, len(frame), 5):
        block = frame[i:i + 5]
        commands.append(decode_command(block))
    
    return commands


# Frequency mapping for tactile range
def build_frequency_table(min_hz: float = 40.0, max_hz: float = 250.0, steps: int = 32) -> List[int]:
    """Build logarithmic frequency table for tactile perception."""
    if steps < 2 or min_hz <= 0 or max_hz <= min_hz:
        raise ValueError("Invalid parameters")
    
    table = []
    ratio = max_hz / min_hz
    
    for i in range(steps):
        freq = min_hz * math.pow(ratio, i / (steps - 1))
        table.append(int(round(freq)))
    
    table[0] = int(round(min_hz))
    table[-1] = int(round(max_hz))
    
    return table


# Default frequency table (40-250Hz, 32 steps)
FREQUENCY_TABLE = build_frequency_table()


def hz_to_freq_index(freq_hz: float, table: List[int] = FREQUENCY_TABLE) -> int:
    """Convert Hz to closest frequency index."""
    if freq_hz <= table[0]: return 0
    if freq_hz >= table[-1]: return len(table) - 1
    
    idx = bisect.bisect_left(table, freq_hz)
    if idx > 0 and abs(table[idx-1] - freq_hz) < abs(table[idx] - freq_hz):
        return idx - 1
    return idx


def freq_index_to_hz(index: int, table: List[int] = FREQUENCY_TABLE) -> int:
    """Convert frequency index to Hz."""
    index = max(0, min(index, len(table) - 1))
    return table[index]


def intensity_to_duty(intensity: float, gamma: float = 0.7) -> int:
    """Convert normalized intensity [0-1] to duty cycle [0-127] with gamma correction."""
    if intensity <= 0: return 0
    if intensity >= 1: return 127
    
    corrected = math.pow(intensity, gamma)
    return int(round(corrected * 127))


def duty_to_intensity(duty: int, gamma: float = 0.7) -> float:
    """Convert duty cycle [0-127] to normalized intensity [0-1]."""
    if duty <= 0: return 0.0
    if duty >= 127: return 1.0
    
    normalized = duty / 127.0
    return math.pow(normalized, 1.0 / gamma)