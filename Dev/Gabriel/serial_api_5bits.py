# serial_api.py  — duty transmis en 5 bits (0..31) tel quel
import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'  # compat
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty, freq, start_or_stop):
        """
        Creates a 4-byte command (PC → ESP):
          Byte 1: [GGGG][0][S]               (4-bit serial group, S=start bit)
          Byte 2: [00][ADDR(6-bit)]          (0..7 dans la sous-chaîne)
          Byte 3: [-----DUTY5]               (5-bit duty brut: 0..31)
          Byte 4: [-----FREQ3]               (3-bit freq: 0..7)
        """
        addr = int(addr); duty = int(duty); freq = int(freq); start_or_stop = int(start_or_stop) & 0x01
        serial_group = addr // 8           # 0..3
        serial_addr  = addr % 8            # 0..7

        byte1 = ((serial_group & 0x0F) << 2) | start_or_stop
        byte2 = serial_addr & 0x3F
        byte3 = duty & 0x1F                # ✅ 5 bits stricts (0..31)
        byte4 = freq & 0x07
        return bytearray([byte1, byte2, byte3, byte4])

    def send_command(self, addr, duty, freq, start_or_stop) -> bool:
        if self.serial_connection is None or not self.connected:
            return False

        # bornes alignées sur le protocole (5b duty)
        if not (0 <= int(addr) <= 31 and 0 <= int(duty) <= 31 and 0 <= int(freq) <= 7 and int(start_or_stop) in (0,1)):
            print(f'Invalid command parameters: addr={addr} (0..31), duty5={duty} (0..31), freq={freq} (0..7), start/stop={start_or_stop}')
            return False

        command = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))

        # Padding legacy (80 octets = 20 trames) — garde-le si ton ESP l’attend
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * 19
        try:
            self.serial_connection.write(command)
            print(f'Serial sent command to #{addr} with duty5 {duty} and freq {freq}, start_or_stop {start_or_stop}')
            return True
        except Exception as e:
            print(f'Serial failed to send command to #{addr} with duty5 {duty} and freq {freq}. Error: {e}')
            return False

    def send_command_list(self, commands) -> bool:
        if self.serial_connection is None or not self.connected:
            return False

        command = bytearray()
        for c in commands:
            addr = int(c.get('addr', -1))
            duty = int(c.get('duty', -1))
            freq = int(c.get('freq', -1))
            sos  = int(c.get('start_or_stop', -1))
            if not (0 <= addr <= 31 and 0 <= duty <= 31 and 0 <= freq <= 7 and sos in (0,1)):
                print(f'Invalid command in list: {c}')
                return False
            command += self.create_command(addr, duty, freq, sos)

        padding_count = 20 - len(commands)
        if padding_count > 0:
            command += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * padding_count

        try:
            self.serial_connection.write(command)
            print(f'Serial sent command list {commands}')
            return True
        except Exception as e:
            print(f'Serial failed to send command list {commands}. Error: {e}')
            return False

    def get_serial_devices(self):
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect_serial_device(self, port_info) -> bool:
        try:
            port_name = port_info.split(' - ')[0]
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=115200,
                timeout=1,
                write_timeout=1
            )
            time.sleep(2)
            if self.serial_connection.is_open:
                self.connected = True
                print(f'Serial connected to {port_name}')
                return True
            return False
        except Exception as e:
            print(f'Serial failed to connect to {port_info}. Error: {e}')
            self.serial_connection = None
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
            print(f'Serial failed to disconnect. Error: {e}')
        return False


if __name__ == '__main__':
    serial_api = SERIAL_API()
    print("Searching for Serial devices...")
    device_names = serial_api.get_serial_devices()
    print(device_names)

    if device_names:
        # ⚠️ choisis l’index correct
        if serial_api.connect_serial_device(device_names[2]):
            addr = 0
            # START à duty5 = 15 (~50%) et freq index 3
            serial_api.send_command(addr, 15, 3, 1)
            time.sleep(2)
            print("STOP")
            serial_api.send_command(addr, 15, 3, 0)

            # Autre essai: duty5 = 25 (~80%)
            serial_api.send_command(addr, 25, 3, 1)
            time.sleep(1.5)
            serial_api.send_command(addr, 25, 3, 0)

            serial_api.disconnect_serial_device()
            time.sleep(1)