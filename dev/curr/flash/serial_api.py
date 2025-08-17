import serial
import serial.tools.list_ports
import time

class SerialAPI:
    def __init__(self):
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop, wave=0, delay_ms=0):
        """Create a 5-byte command with timing delay
        
        New protocol format:
        byte1: [serial_group(4) | wave(1) | is_start(1) | addr_high(2)]
        byte2: [addr_low(4) | freq(3) | duty_high(1)]  
        byte3: [duty_low(7) | marker(1)]
        byte4: delay_low
        byte5: delay_high
        """
        
        # Calculate serial group and local address
        serial_group = addr // 16
        local_addr = addr % 16

        # Validate inputs
        if not (0 <= serial_group <= 15):
            raise ValueError(f"Serial group {serial_group} out of range (0-15)")
        if not (0 <= local_addr <= 15):
            raise ValueError(f"Local addr {local_addr} out of range (0-15)")
        if not (0 <= duty <= 99):
            raise ValueError(f"Duty {duty} out of range (0-99)")
        if not (0 <= freq <= 7):
            raise ValueError(f"Freq {freq} out of range (0-7)")
        if start_or_stop not in [0, 1]:
            raise ValueError(f"start_or_stop must be 0 or 1")
        if wave not in [0, 1]:
            raise ValueError(f"wave must be 0 or 1")
        if not (0 <= delay_ms <= 65535):
            raise ValueError(f"delay_ms {delay_ms} out of range (0-65535)")
        
        # Split addr into high and low parts (6 bits total)
        addr_high = (local_addr >> 2) & 0x03  # Upper 2 bits
        addr_low = local_addr & 0x0F          # Lower 4 bits
        
        # Split duty into high and low parts (8 bits total, but limited to 0-99)
        duty_high = (duty >> 7) & 0x01        # Upper 1 bit  
        duty_low = duty & 0x7F                # Lower 7 bits
        
        # Pack bytes according to new protocol
        byte1 = (serial_group << 4) | (wave << 3) | (start_or_stop << 2) | addr_high
        byte2 = (addr_low << 4) | (freq << 1) | duty_high
        byte3 = (duty_low << 1) | 0x01  # Set marker bit
        
        # 16-bit delay in milliseconds (little-endian)
        delay_low = delay_ms & 0xFF
        delay_high = (delay_ms >> 8) & 0xFF
        
        return bytearray([byte1, byte2, byte3, delay_low, delay_high])

    def send_timed_batch(self, commands) -> bool:
        """Send batch of commands with individual timing delays"""
        if not self.connected or self.serial_connection is None:
            print("Error: Not connected to serial device")
            return False
            
        # Validate and build command batch
        command_bytes = bytearray()
        for i, cmd in enumerate(commands):
            addr = cmd.get('addr', -1)
            duty = cmd.get('duty', -1)
            freq = cmd.get('freq', -1)
            start_or_stop = cmd.get('start_or_stop', -1)
            wave = cmd.get('wave', 0)  # Default wave = 0
            delay_ms = cmd.get('delay_ms', 0)
            
            # Validate parameters (updated for 100 duty levels)
            try:
                if not (0 <= addr <= 127):
                    raise ValueError(f"addr {addr} out of range (0-127)")
                if not (0 <= duty <= 99):
                    raise ValueError(f"duty {duty} out of range (0-99)")
                if not (0 <= freq <= 7):
                    raise ValueError(f"freq {freq} out of range (0-7)")
                if start_or_stop not in [0, 1]:
                    raise ValueError(f"start_or_stop must be 0 or 1")
                if wave not in [0, 1]:
                    raise ValueError(f"wave must be 0 or 1")
                if not (0 <= delay_ms <= 65535):
                    raise ValueError(f"delay_ms {delay_ms} out of range (0-65535)")
                    
                command_bytes += self.create_command(addr, duty, freq, start_or_stop, wave, delay_ms)
                
            except ValueError as e:
                print(f"Error: Invalid parameters in command {i+1}: {e}")
                return False
        
        try:
            self.serial_connection.write(command_bytes)
            print(f"Sent batch with {len(commands)} commands ({len(command_bytes)} bytes)")
            return True
        except Exception as e:
            print(f"Failed to send batch: {e}")
            return False

    def get_serial_ports(self):
        """Get list of available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect(self, port_info, baudrate=115200) -> bool:
        """Connect to serial device"""
        try:
            port_name = port_info.split(' - ')[0]
            
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=baudrate,
                timeout=1,
                write_timeout=1
            )
            
            # time.sleep(0.5)  # Allow connection to establish
            
            if self.serial_connection.is_open:
                self.connected = True
                print(f"Connected to {port_name}")
                return True
            return False
                
        except Exception as e:
            print(f"Connection failed: {e}")
            self.serial_connection = None
            self.connected = False
            return False

    def disconnect(self) -> bool:
        """Disconnect from serial device"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.connected = False
                self.serial_connection = None
                print("Disconnected")
                return True
        except Exception as e:
            print(f"Disconnect failed: {e}")
        return False

    def is_connected(self) -> bool:
        """Check connection status"""
        return self.connected and self.serial_connection and self.serial_connection.is_open


if __name__ == '__main__':
    api = SerialAPI()
    
    # Find available ports
    ports = api.get_serial_ports()
    print("Available ports:", ports)
    
    if ports:
        # Connect to first available port (change index as needed)
        if api.connect(ports[2]):
            # Test with 100-level duty values
            test_commands = [
                {"addr": 0, "duty": 50, "freq": 3, "start_or_stop": 1, "delay_ms": 0},
                {"addr":0, "duty":99, "freq": 3, "start_or_stop": 0, "delay_ms": 2000},
                {"addr": 1, "duty":50, "freq": 3, "start_or_stop": 1, "delay_ms": 0},
                {"addr":1, "duty":99, "freq": 3, "start_or_stop": 0, "delay_ms": 2000}# Stop device 0 after 2s
            ]
            
            print("Sending test batch with 100-level duty values...")
            api.send_timed_batch(test_commands)
            
            # Wait for sequence to complete
            time.sleep(2)
            api.disconnect()
        else:
            print("Failed to connect")
    else:
        print("No serial ports found")