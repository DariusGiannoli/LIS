import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    def __init__(self):
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop):
        serial_group = addr // 8
        serial_addr = addr % 8
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = 0x40 | (serial_addr & 0x3F)
        byte3 = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07)
        return bytearray([byte1, byte2, byte3])

    def send_command(self, addr, duty, freq, start_or_stop) -> bool:
        if not self.connected:
            return False
        if not (0 <= addr <= 127 and 0 <= duty <= 15 and 0 <= freq <= 7 and start_or_stop in [0, 1]):
            return False
        
        command = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        # Pad to 60 bytes to match buffer on master ESP32
        command += bytearray([0xFF, 0xFF, 0xFF]) * 19
        try:
            self.serial_connection.write(command)
            print(f'Sent command to #{addr} with duty {duty}, freq {freq}, start_or_stop {start_or_stop}')
            return True
        except Exception as e:
            print(f'Failed to send command to #{addr}. Error: {e}')
            return False

    def send_command_list(self, commands) -> bool:
        if not self.connected:
            return False
        
        command_bytes = bytearray()
        for c in commands:
            addr = c.get('addr', -1)
            duty = c.get('duty', -1)
            freq = c.get('freq', -1)
            start_or_stop = c.get('start_or_stop', -1)
            if not (0 <= addr <= 127 and 0 <= duty <= 15 and 0 <= freq <= 7 and start_or_stop in [0, 1]):
                return False
            command_bytes += self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        
        # Pad to 60 bytes
        padding_needed = 20 - len(commands)
        if padding_needed > 0:
            command_bytes += bytearray([0xFF, 0xFF, 0xFF]) * padding_needed

        try:
            self.serial_connection.write(command_bytes)
            print(f'Sent command list with {len(commands)} commands.')
            return True
        except Exception as e:
            print(f'Failed to send command list. Error: {e}')
            return False

    def get_serial_devices(self):
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect_serial_device(self, port_info) -> bool:
        try:
            port_name = port_info.split(' - ')[0]
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=115200, # Must match Master ESP32 baud rate
                timeout=1,
                write_timeout=1
            )
            time.sleep(2) # Wait for connection
            if self.serial_connection.is_open:
                self.connected = True
                print(f'Successfully connected to {port_name}')
                return True
            return False
        except Exception as e:
            print(f'Failed to connect to {port_info}. Error: {e}')
            self.connected = False
            return False

    def disconnect_serial_device(self) -> bool:
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            self.connected = False
            self.serial_connection = None
            print('Serial disconnected')
            return True
        except Exception as e:
            print(f'Failed to disconnect. Error: {e}')
        return False