import serial
import serial.tools.list_ports
import threading
import time

class SERIAL_API:
    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'  # Keep for compatibility
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop):
        """
        Creates a 4-byte command:
        Byte 1: [00][Serial Group(4-bit)][0][Start(1-bit)]
        Byte 2: [0][Address(6-bit)]
        Byte 3: [0][Duty(7-bit)] (0-99)
        Byte 4: [00000][Freq(3-bit)] (0-7)
        """
        serial_group = addr // 8
        serial_addr = addr % 8
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = serial_addr & 0x3F  # Address on the sub-chain
        byte3 = duty & 0x7F         # 7-bit duty (will be capped 0-99)
        byte4 = freq & 0x07         # 3-bit freq
        return bytearray([byte1, byte2, byte3, byte4])

    def send_command(self, addr, duty, freq, start_or_stop) -> bool:
        if self.serial_connection is None or not self.connected:
            return False
        # Updated range checks
        if addr < 0 or addr > 127 or duty < 0 or duty > 99 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
            print(f'Invalid command parameters: addr={addr}, duty={duty}, freq={freq}')
            return False
            
        command = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        
        # Pad to 80 bytes (1 command * 4 bytes + 19 * 4-byte fillers)
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * 19  
        try:
            self.serial_connection.write(command)
            print(f'Serial sent command to #{addr} with duty {duty} and freq {freq}, start_or_stop {start_or_stop}')
            return True
        except Exception as e:
            print(f'Serial failed to send command to #{addr} with duty {duty} and freq {freq}. Error: {e}')
            return False

    def send_command_list(self, commands) -> bool:
        if self.serial_connection is None or not self.connected:
            return False
            
        command = bytearray()
        for c in commands:
            addr = c.get('addr', -1)
            duty = c.get('duty', -1)
            freq = c.get('freq', -1)
            start_or_stop = c.get('start_or_stop', -1)
            # Updated range checks
            if addr < 0 or addr > 127 or duty < 0 or duty > 99 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
                print(f'Invalid command in list: {c}')
                return False
            command = command + self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
            
        # Pad to 80 bytes (max 20 commands * 4 bytes)
        padding_count = 20 - len(commands)
        if padding_count > 0:
            command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * padding_count
            
        try:
            self.serial_connection.write(command)
            print(f'Serial sent command list {commands}')
            return True
        except Exception as e:
            print(f'Serial failed to send command list {commands}. Error: {e}')
            return False

    def get_serial_devices(self):
        """Get a list of available serial ports"""
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect_serial_device(self, port_info) -> bool:
        """Connect to a serial device using port information"""
        try:
            # Extract port name from the port_info string
            port_name = port_info.split(' - ')[0]
            
            # Try to open the serial connection
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=115200,  # Match Arduino baud rate
                timeout=1,
                write_timeout=1
            )
            
            # Wait a moment for the connection to establish
            time.sleep(2)
            
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

if __name__ == '__main__':
    serial_api = SERIAL_API()
    print("Searching for Serial devices...")
    device_names = serial_api.get_serial_devices()
    print(device_names)
    
    # Example usage with GUI interaction:
    if device_names:
        # !! CHOOSE THE CORRECT DEVICE INDEX !!
        # if serial_api.connect_serial_device(device_names[2]): 
        if serial_api.connect_serial_device(device_names[2]): # Example: connecting to first device
            # Start motor 0 at 50% duty (50) and freq index 3
            serial_api.send_command(0, 50, 3, 1) 
            time.sleep(2)
            serial_api.send_command(0, 80, 3, 0)

            
            serial_api.disconnect_serial_device()
            time.sleep(3)