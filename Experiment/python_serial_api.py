import time
import serial
import serial.tools.list_ports
from codec import encode_batch, hz_to_freq_index, FREQUENCY_TABLE


class python_serial_api:
    def __init__(self):
        self.connection = None
        self.connected = False

    def get_devices(self):
        """Get list of available serial ports."""
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect(self, port_info: str) -> bool:
        """Connect to serial device."""
        try:
            port_name = port_info.split(' - ')[0]
            
            self.connection = serial.Serial(
                port=port_name,
                baudrate=115200,
                timeout=1,
                write_timeout=1
            )
            
            time.sleep(0.5)  # Wait for connection
            
            if self.connection.is_open:
                self.connected = True
                print(f'Connected to {port_name}')
                return True
            return False
                
        except Exception as e:
            print(f'Failed to connect: {e}')
            self.connection = None
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from serial device."""
        try:
            if self.connection and self.connection.is_open:
                self.connection.close()
                self.connected = False
                self.connection = None
                print('Disconnected')
                return True
        except Exception as e:
            print(f'Failed to disconnect: {e}')
        return False

    def send_commands(self, commands: list, verbose: bool = True) -> bool:
        """Send commands using v15 codec."""
        if not self.connected or not self.connection:
            if verbose: print("Error: Not connected")
            return False

        # Normalize commands
        normalized = []
        for i, cmd in enumerate(commands):
            try:
                addr = int(cmd["addr"])
                duty = int(cmd["duty"])
                start = bool(cmd.get("start", cmd.get("start_or_stop", 0)))
                delay_ms = int(cmd["delay_ms"])
                flags = int(cmd.get("flags", 0))
                
                # Handle frequency
                if "freq_index" in cmd:
                    freq_index = int(cmd["freq_index"])
                elif "freq_hz" in cmd:
                    freq_index = hz_to_freq_index(float(cmd["freq_hz"]))
                elif "freq" in cmd:
                    freq_index = int(cmd["freq"])  # Assume it's already an index
                else:
                    raise KeyError("missing frequency parameter")
                
                # Validate ranges
                if not (0 <= addr <= 127): raise ValueError("addr out of range")
                if not (0 <= duty <= 127): raise ValueError("duty out of range")
                if not (0 <= freq_index <= 31): raise ValueError("freq_index out of range")
                if not (0 <= delay_ms <= 65535): raise ValueError("delay_ms out of range")
                if not (0 <= flags <= 15): raise ValueError("flags out of range")
                
                normalized.append({
                    "addr": addr,
                    "duty": duty,
                    "freq_index": freq_index,
                    "start": start,
                    "delay_ms": delay_ms,
                    "flags": flags
                })
                
            except Exception as e:
                if verbose: print(f"Invalid command #{i}: {e}")
                return False

        # Encode and send frames
        try:
            frames = encode_batch(normalized, max_frame_bytes=250)
            
            for frame in frames:
                self.connection.write(frame)
                self.connection.flush()
                time.sleep(0.002)  # Small delay between frames
                
            if verbose:
                print(f"Sent {len(normalized)} commands in {len(frames)} frame(s)")
            return True
            
        except Exception as e:
            if verbose: print(f"Send failed: {e}")
            return False

    def send_single_command(self, addr: int, duty: int, freq_index: int = None, 
                           freq_hz: float = None, start: bool = True, 
                           delay_ms: int = 0, flags: int = 0) -> bool:
        """Send a single command."""
        if freq_index is None and freq_hz is None:
            raise ValueError("Provide freq_index or freq_hz")
            
        cmd = {
            "addr": addr,
            "duty": duty,
            "start": start,
            "delay_ms": delay_ms,
            "flags": flags
        }
        
        if freq_index is not None:
            cmd["freq_index"] = freq_index
        else:
            cmd["freq_hz"] = freq_hz
            
        return self.send_commands([cmd])


if __name__ == '__main__':
    api = python_serial_api()
    devices = api.get_devices()
    print("Available devices:", devices)
    
    if devices and api.connect(devices[0]):
        # Test commands
        commands = [
            {"addr": 1, "duty": 64, "freq_index": 10, "start": True, "delay_ms": 0},
            {"addr": 1, "duty": 0, "freq_index": 0, "start": False, "delay_ms": 500},
        ]
        api.send_commands(commands)
        time.sleep(1)
        api.disconnect()