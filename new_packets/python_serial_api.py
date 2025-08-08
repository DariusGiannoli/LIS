# The code provided is a Python class named `python_serial_api` that is used for serial communication.
# It includes an initialization method `__init__` where it sets the `MOTOR_UUID` attribute and
# initializes `serial_connection` and `connected` attributes.


import time

class python_serial_api:
    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'  # Keep for compatibility
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop, delay_ms=0):
        """Create a 5-byte command with timing"""
        serial_group = addr // 16
        serial_addr = addr % 16
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = 0x40 | (serial_addr & 0x3F)  # 0x40 represents the leading '01'
        byte3 = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07)  # 0x80 represents the leading '1'
        
        # Add 16-bit delay in milliseconds (little-endian)
        delay_low = delay_ms & 0xFF
        delay_high = (delay_ms >> 8) & 0xFF
        
        return bytearray([byte1, byte2, byte3, delay_low, delay_high])

    def create_old_command(self, addr, duty, freq, start_or_stop):
        """Create old 3-byte command for backward compatibility"""
        serial_group = addr // 16
        serial_addr = addr % 16
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = 0x40 | (serial_addr & 0x3F)
        byte3 = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07)
        return bytearray([byte1, byte2, byte3])

    def send_command(self, addr, duty, freq, start_or_stop) -> bool:
        """Send single command immediately (backward compatibility)"""
        if self.serial_connection is None or not self.connected:
            return False
        if addr < 0 or addr > 127 or duty < 0 or duty > 15 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
            return False
        
        # Use old format for immediate execution (delay=0)
        command = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop), 0)
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF]) * 19  # Padding to 100 bytes
        
        try:
            self.serial_connection.write(command)
            print(f'Serial sent command to #{addr} with duty {duty} and freq {freq}, start_or_stop {start_or_stop}')
            return True
        except Exception as e:
            print(f'Serial failed to send command to #{addr} with duty {duty} and freq {freq}. Error: {e}')
            return False

    def send_timed_command(self, addr, duty, freq, start_or_stop, delay_ms) -> bool:
        """Send single command with timing delay"""
        if self.serial_connection is None or not self.connected:
            return False
        if addr < 0 or addr > 127 or duty < 0 or duty > 15 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
            return False
        if delay_ms < 0 or delay_ms > 65535:
            return False
            
        command = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop), int(delay_ms))
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF]) * 19  # Padding to 100 bytes
        
        try:
            self.serial_connection.write(command)
            print(f'Serial sent timed command to #{addr} with duty {duty}, freq {freq}, start_or_stop {start_or_stop}, delay {delay_ms}ms')
            return True
        except Exception as e:
            print(f'Serial failed to send timed command to #{addr}. Error: {e}')
            return False

    def send_command_list(self, commands) -> bool:
        """Send list of commands (backward compatibility - no timing)"""
        if self.serial_connection is None or not self.connected:
            return False
        command = bytearray()
        for c in commands:
            addr = c.get('addr', -1)
            duty = c.get('duty', -1)
            freq = c.get('freq', -1)
            start_or_stop = c.get('start_or_stop', -1)
            if addr < 0 or addr > 127 or duty < 0 or duty > 15 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
                return False
            command = command + self.create_command(int(addr), int(duty), int(freq), int(start_or_stop), 0)
        
        # padding to 100 bytes
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF]) * (20 - len(commands))
        try:
            self.serial_connection.write(command)
            print(f'Serial sent command list {commands}')
            return True
        except Exception as e:
            print(f'Serial failed to send command list {commands}. Error: {e}')
            return False

    def send_timed_batch(self, commands) -> bool:
        """Send batch of commands with individual timing delays"""
        if self.serial_connection is None or not self.connected:
            return False
        if len(commands) > 20:
            print("Error: Maximum 20 commands per batch")
            return False
            
        command = bytearray()
        for c in commands:
            addr = c.get('addr', -1)
            duty = c.get('duty', -1)
            freq = c.get('freq', -1)
            start_or_stop = c.get('start_or_stop', -1)
            delay_ms = c.get('delay_ms', 0)
            
            if addr < 0 or addr > 127 or duty < 0 or duty > 15 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
                return False
            if delay_ms < 0 or delay_ms > 65535:
                return False
                
            command = command + self.create_command(int(addr), int(duty), int(freq), int(start_or_stop), int(delay_ms))
        
        # padding to 100 bytes
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF, 0xFF]) * (20 - len(commands))
        
        try:
            self.serial_connection.write(command)
            print(f'Serial sent timed batch with {len(commands)} commands')
            for i, c in enumerate(commands):
                print(f'  Command {i+1}: addr={c["addr"]}, duty={c["duty"]}, freq={c["freq"]}, start={c["start_or_stop"]}, delay={c.get("delay_ms", 0)}ms')
            return True
        except Exception as e:
            print(f'Serial failed to send timed batch. Error: {e}')
            return False

    def send_tactile_brush_stroke(self, start_addr, end_addr, intensity, duration_ms, total_time_ms) -> bool:
        """Helper method for tactile brush algorithm"""
        if abs(end_addr - start_addr) < 1:
            print("Error: Need at least 2 different addresses for stroke")
            return False
            
        commands = []
        num_steps = abs(end_addr - start_addr) + 1
        step_delay = total_time_ms // num_steps
        
        # Calculate SOA based on tactile brush formula: SOA = 0.32 * duration + 0.0473
        duration_sec = duration_ms / 1000.0
        soa_sec = 0.32 * duration_sec + 0.0473
        soa_ms = int(soa_sec * 1000)
        
        print(f"Tactile brush stroke: {num_steps} steps, SOA={soa_ms}ms, step_delay={step_delay}ms")
        
        # Create stroke commands
        for i in range(num_steps):
            addr = start_addr + i if end_addr > start_addr else start_addr - i
            delay = i * soa_ms
            
            # Start command
            commands.append({
                "addr": addr,
                "duty": intensity,
                "freq": 10,  # Default frequency
                "start_or_stop": 1,
                "delay_ms": delay
            })
            
            # Stop command (duration_ms later)
            commands.append({
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                "delay_ms": delay + duration_ms
            })
        
        return self.send_timed_batch(commands)

    def get_serial_devices(self):
        """Get a list of available serial ports"""
        ports = serial_api.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect_serial_device(self, port_info) -> bool:
        """Connect to a serial device using port information"""
        try:
            # Extract port name from the port_info string
            port_name = port_info.split(' - ')[0]
            
            # Try to open the serial connection
            self.serial_connection = serial_api.Serial(
                port=port_name,
                baudrate=115200,  # Match Arduino baud rate
                timeout=1,
                write_timeout=1
            )
            
            # Wait a moment for the connection to establish
            time.sleep(0.5)
            
            if self.serial_connection.is_open:
                self.connected = True
                print(f'Serial connected to {port_name}')
                return True
            else:
                return False
                
        except Exception as e:
            print(f'Serial failed to connect to {port_info}. Error: {e}')
            self.serial_connection = None
            self.connected = False
            return False

    def disconnect_serial_device(self) -> bool:
        """Disconnect from the serial device"""
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.connected = False
                self.serial_connection = None
                print('Serial disconnected')
                return True
        except Exception as e:
            print(f'Serial failed to disconnect. Error: {e}')
        return False

    # Legacy method names for compatibility with existing code
    def get_ble_devices(self):
        """Legacy method - returns serial devices instead"""
        return self.get_serial_devices()

    def connect_ble_device(self, device_name):
        """Legacy method - connects to serial device instead"""
        return self.connect_serial_device(device_name)

    def disconnect_ble_device(self):
        """Legacy method - disconnects serial device instead"""
        return self.disconnect_serial_device()


if __name__ == '__main__':
    serial_api = python_serial_api()
    print("Searching for Serial devices...")
    device_names = serial_api.get_serial_devices()
    print(device_names)
    
    # Example usage with GUI interaction:
    if device_names:
        if serial_api.connect_serial_device(device_names[2]):
            print("\n=== Testing Timed Batch Commands ===")
            
            for i in range(2):
            # Test 1: Simple timed batch
                timed_commands = [
                    {"addr": 3, "duty": 7, "freq": 2, "start_or_stop": 1, "delay_ms": 0},     # Start immediately
                    {"addr": 1, "duty": 7, "freq": 2, "start_or_stop": 1, "delay_ms": 100},   # Start after 100ms
                    {"addr": 2, "duty": 7, "freq": 2, "start_or_stop": 1, "delay_ms": 200},   # Start after 200ms
                    {"addr": 0, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 500},   # Stop after 500ms
                    {"addr": 1, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 600},   # Stop after 600ms
                    {"addr": 2, "duty": 0, "freq": 0, "start_or_stop": 0, "delay_ms": 700},   # Stop after 700ms
                ]
                serial_api.send_timed_batch(timed_commands)
                time.sleep(0.8)
                print("new")
                

            # print("\n=== Testing Tactile Brush Stroke ===")
            # # Test 2: Tactile brush stroke from addr 0 to 3
            # serial_api.send_tactile_brush_stroke(
            #     start_addr=0, 
            #     end_addr=3, 
            #     intensity=8, 
            #     duration_ms=50,  # 50ms pulse duration
            #     total_time_ms=500  # Total stroke time
            # )
            # time.sleep(3)
            
            serial_api.disconnect_serial_device()