import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    """
    PC -> ESP32 packet (4 bytes per command; ESP32 repacks for the PIC):
      Byte 1: [ .... GGGG .. S ]   GGGG = addr//8 (0..3), S = start_or_stop (0/1)
      Byte 2: [ 00AAAAAA ]         AAAAAA = addr%8 (0..7)  (kept 6-bit for future)
      Byte 3: [ 000DDDDD ]         DDDDD = duty5 (0..31)   
      Byte 4: [ 000000FF ]         FF = freq2 (0..3)       

    The ESP32 then sends to the PIC:
      START: addr byte + single data byte [1 | duty(5) | freq(2)]
      STOP : addr byte only
    """
    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'  # kept for compatibility
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty5, freq2, start_or_stop):
        # Compute group and sub-address from 0..31 logical address
        serial_group = addr // 8            # 0..3
        serial_addr  = addr %  8            # 0..7

        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = serial_addr & 0x3F          # 6-bit address on sub-chain
        byte3 = duty5 & 0x1F                # 5-bit duty (0..31)
        byte4 = freq2 & 0x03                # 2-bit freq (0..3)
        return bytearray([byte1, byte2, byte3, byte4])

    def send_command(self, addr, duty5, freq2, start_or_stop) -> bool:
        if self.serial_connection is None or not self.connected:
            print("Not connected to any serial device.")
            return False

        # Updated range checks for new protocol
        if not (0 <= addr <= 31 and 0 <= duty5 <= 31 and 0 <= freq2 <= 3 and start_or_stop in (0, 1)):
            print(f'Invalid params: addr={addr} (0-31), duty5={duty5} (0-31), freq2={freq2} (0-3), start_or_stop={start_or_stop}')
            return False

        command = self.create_command(int(addr), int(duty5), int(freq2), int(start_or_stop))

        # Pad to 80 bytes total (20 * 4B), like before
        command = command + bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * 19
        try:
            self.serial_connection.write(command)
            print(f'Serial sent to #{addr}: duty5={duty5}, freq2={freq2}, start_or_stop={start_or_stop}')
            return True
        except Exception as e:
            print(f'Serial failed to send to #{addr}. Error: {e}')
            return False

    def send_percent(self, addr, percent, freq2, start_or_stop) -> bool:
        """
        Convenience: percent (0..100) -> duty5 (0..31), rounded.
        Matches the PIC’s LUT (0..99) well enough for testing.
        """
        p = max(0, min(100, float(percent)))
        duty5 = int(round(p * 31.0 / 100.0))
        return self.send_command(addr, duty5, freq2, start_or_stop)

    def send_command_list(self, commands) -> bool:
        if self.serial_connection is None or not self.connected:
            print("Not connected to any serial device.")
            return False

        blob = bytearray()
        for c in commands:
            addr = int(c.get('addr', -1))
            duty5 = int(c.get('duty', -1))   # interpret as duty5 now
            freq2 = int(c.get('freq', -1))   
            start = int(c.get('start_or_stop', -1))
            if not (0 <= addr <= 31 and 0 <= duty5 <= 31 and 0 <= freq2 <= 3 and start in (0, 1)):
                print(f'Invalid command in list: {c}')
                return False
            blob += self.create_command(addr, duty5, freq2, start)

        # Pad to 80 bytes (max 20 commands * 4 bytes)
        padding_count = 20 - (len(blob) // 4)
        if padding_count > 0:
            blob += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * padding_count

        try:
            self.serial_connection.write(blob)
            print(f'Serial sent command list: {commands}')
            return True
        except Exception as e:
            print(f'Serial failed to send command list. Error: {e}')
            return False

    def get_serial_devices(self):
        """Get a list of available serial ports"""
        return [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]

    def connect_serial_device(self, port_info) -> bool:
        """Connect to a serial device using '<port> - <desc>' string"""
        try:
            port_name = port_info.split(' - ')[0]
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=115200,  # matches ESP32 USB CDC
                timeout=1,
                write_timeout=1
            )
            time.sleep(2)  # settle
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
        # Pick the correct index for your ESP32 USB port
        idx = 2  # <-- change if needed
        if idx < len(device_names) and serial_api.connect_serial_device(device_names[idx]):
            # Example: start motor #0 at ~50% (duty5=16) on freq2=1
            serial_api.send_command(addr=0, duty5=16, freq2=1, start_or_stop=1)
            time.sleep(2)
            print("stop")
            serial_api.send_command(addr=0, duty5=0, freq2=1, start_or_stop=0)

            # Or use percent helper:
            # serial_api.send_percent(addr=0, percent=50, freq2=1, start_or_stop=1)

            serial_api.disconnect_serial_device()