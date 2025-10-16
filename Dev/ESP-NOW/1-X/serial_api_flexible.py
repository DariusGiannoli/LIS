import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    def __init__(self):
        self.serial_connection = None
        self.connected = False
        self.BROADCAST_ID = 255 # Use this ID to send to all slaves

    def create_command(self, addr, duty, freq, start_or_stop):
        serial_group = addr // 8
        serial_addr = addr % 8
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = 0x40 | (serial_addr & 0x3F)
        byte3 = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07)
        return bytearray([byte1, byte2, byte3])

    def send_command(self, slave_id, addr, duty, freq, start_or_stop) -> bool:
        if not self.connected: return False
        if not (0 <= addr <= 127 and 0 <= duty <= 15 and 0 <= freq <= 7 and start_or_stop in [0, 1]): return False
        
        payload = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        payload += bytearray([0xFF, 0xFF, 0xFF]) * 19 # Padding
        
        # Prepend the slave ID (or broadcast ID) to the packet
        full_packet = bytearray([slave_id]) + payload
        
        try:
            self.serial_connection.write(full_packet)
            target = f"Slave #{slave_id}" if slave_id != self.BROADCAST_ID else "ALL Slaves (Broadcast)"
            print(f'Sent command to {target} (motor #{addr})')
            return True
        except Exception as e:
            print(f'Failed to send command. Error: {e}')
            return False

    def send_command_list(self, slave_id, commands) -> bool:
        if not self.connected: return False
        
        payload = bytearray()
        for c in commands:
            addr = c.get('addr', -1)
            duty = c.get('duty', -1)
            freq = c.get('freq', -1)
            start_or_stop = c.get('start_or_stop', -1)
            if not (0 <= addr <= 127 and 0 <= duty <= 15 and 0 <= freq <= 7 and start_or_stop in [0, 1]): return False
            payload += self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        
        padding_needed = 20 - len(commands)
        if padding_needed > 0: payload += bytearray([0xFF, 0xFF, 0xFF]) * padding_needed

        # Prepend the slave ID (or broadcast ID)
        full_packet = bytearray([slave_id]) + payload

        try:
            self.serial_connection.write(full_packet)
            target = f"Slave #{slave_id}" if slave_id != self.BROADCAST_ID else "ALL Slaves (Broadcast)"
            print(f'Sent command list to {target}')
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
            self.serial_connection = serial.Serial(port=port_name, baudrate=115200, timeout=1, write_timeout=1)
            time.sleep(2)
            self.connected = self.serial_connection.is_open
            if self.connected: print(f'Successfully connected to {port_name}')
            return self.connected
        except Exception as e:
            print(f'Failed to connect. Error: {e}')
            self.connected = False
            return False

    def disconnect_serial_device(self) -> bool:
        if self.serial_connection and self.serial_connection.is_open:
            self.serial_connection.close()
        self.connected = False
        print('Serial disconnected')
        return True