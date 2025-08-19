import serial
import serial.tools.list_ports
import time

class SerialAPI:
    def __init__(self):
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop, delay_ms=0):
        """Create a 5-byte command with timing delay"""
        serial_group = addr // 16
        serial_addr = addr % 16
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = 0x40 | (serial_addr & 0x3F)
        byte3 = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07)
        
        # 16-bit delay in milliseconds (little-endian)
        delay_low = delay_ms & 0xFF
        delay_high = (delay_ms >> 8) & 0xFF
        
        return bytearray([byte1, byte2, byte3, delay_low, delay_high])

    def send_timed_batch(self, commands) -> bool:
        """Send batch of commands with individual timing delays"""
        if not self.connected or self.serial_connection is None:
            print("Error: Not connected to serial device")
            return False
        
        # Removed the 20-command limit check
            
        # Validate and build command batch
        command_bytes = bytearray()
        for i, cmd in enumerate(commands):
            addr = cmd.get('addr', -1)
            duty = cmd.get('duty', -1)
            freq = cmd.get('freq', -1)
            start_or_stop = cmd.get('start_or_stop', -1)
            delay_ms = cmd.get('delay_ms', 0)
            
            # Validate parameters
            if not (0 <= addr <= 127 and 0 <= duty <= 15 and 0 <= freq <= 7 
                    and start_or_stop in [0, 1] and 0 <= delay_ms <= 65535):
                print(f"Error: Invalid parameters in command {i+1}")
                return False
                
            command_bytes += self.create_command(addr, duty, freq, start_or_stop, delay_ms)
        
        # No padding - send exactly what we have
        
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
            # Simple test batch: activate 3 devices in sequence, then stop them
            test_commands = [
                {"addr": 0, "duty": 8, "freq": 3, "start_or_stop": 1, "delay_ms": 0},     # Start device 0 immediately
                {"addr": 1, "duty": 8, "freq": 3, "start_or_stop": 1, "delay_ms": 200},   # Start device 1 after 200ms
                {"addr": 2, "duty": 8, "freq": 3, "start_or_stop": 1, "delay_ms": 400},
                {"addr": 3, "duty": 8, "freq": 3, "start_or_stop": 1, "delay_ms": 600},# Start device 2 after 400ms
                {"addr": 0, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 1000},  # Stop device 0 after 1s
                {"addr": 1, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 1200},  # Stop device 1 after 1.2s
                {"addr": 2, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 1400},
                {"addr": 3, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 1600},# Stop device 2 after 1.4s
            ]
            
            print("Sending test batch...")
            api.send_timed_batch(test_commands)
            
            # Wait for sequence to complete
            time.sleep(2)
            api.disconnect()
        else:
            print("Failed to connect")
    else:
        print("No serial ports found")
        
