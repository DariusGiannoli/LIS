import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    """
    PC -> ESP32 : 4 octets par commande :
      Byte1 : [ .... GGGG .. S ]   GGGG = addr//8 (0..3), S = start_or_stop (0/1)
      Byte2 : [ 00AAAAAA ]         AAAAAA = addr%8 (0..7)
      Byte3 : [ 000DDDDD ]         DDDDD = duty5 (0..31)
      Byte4 : [ 000000FF ]         FF = freq2 (0..3)

    L'ESP32 re-packe et envoie au PIC :
      START : addr + data (1 seul octet data : [1|duty(5)|freq(2)])
      STOP  : addr seul
    """
    def __init__(self):
        self.serial_connection = None
        self.connected = False

    def create_command(self, addr, duty5, freq2, start_or_stop):
        serial_group = addr // 8            # 0..3
        serial_addr  = addr %  8            # 0..7

        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = serial_addr & 0x3F
        byte3 = duty5 & 0x1F
        byte4 = freq2 & 0x03
        return bytearray([byte1, byte2, byte3, byte4])

    def send_command(self, addr, duty5, freq2, start_or_stop) -> bool:
        if self.serial_connection is None or not self.connected:
            print("Not connected.")
            return False

        if not (0 <= addr <= 31 and 0 <= duty5 <= 31 and 0 <= freq2 <= 3 and start_or_stop in (0,1)):
            print(f'Invalid params: addr={addr} (0-31), duty5={duty5} (0-31), freq2={freq2} (0-3), start_or_stop={start_or_stop}')
            return False

        pkt = self.create_command(int(addr), int(duty5), int(freq2), int(start_or_stop))
        # Pad à 80 octets (20 * 4B) pour rester compatible avec le firmware ESP
        pkt += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * 19
        try:
            self.serial_connection.write(pkt)
            print(f'Sent -> addr={addr}, duty5={duty5}, freq2={freq2}, start={start_or_stop}')
            return True
        except Exception as e:
            print(f'Write error: {e}')
            return False

    def send_percent(self, addr, percent, freq2, start_or_stop) -> bool:
        p = max(0, min(100, float(percent)))
        duty5 = int(round(p * 31.0 / 100.0))
        return self.send_command(addr, duty5, freq2, start_or_stop)

    def send_command_list(self, commands) -> bool:
        if self.serial_connection is None or not self.connected:
            print("Not connected.")
            return False

        blob = bytearray()
        for c in commands:
            addr = int(c.get('addr', -1))
            duty5 = int(c.get('duty', -1))
            freq2 = int(c.get('freq', -1))
            start = int(c.get('start_or_stop', -1))
            if not (0 <= addr <= 31 and 0 <= duty5 <= 31 and 0 <= freq2 <= 3 and start in (0,1)):
                print(f'Invalid command in list: {c}')
                return False
            blob += self.create_command(addr, duty5, freq2, start)

        padding_count = 20 - (len(blob)//4)
        if padding_count > 0:
            blob += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * padding_count

        try:
            self.serial_connection.write(blob)
            print(f'Sent list ({len(blob)//4} cmds)')
            return True
        except Exception as e:
            print(f'Write error: {e}')
            return False

    def get_serial_devices(self):
        return [f"{p.device} - {p.description}" for p in serial.tools.list_ports.comports()]

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
                print(f'Connected to {port_name}')
                return True
            return False
        except Exception as e:
            print(f'Connect error: {e}')
            self.serial_connection = None
            self.connected = False
            return False

    def disconnect_serial_device(self) -> bool:
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
                self.connected = False
                self.serial_connection = None
                print('Disconnected')
                return True
        except Exception as e:
            print(f'Disconnect error: {e}')
        return False


if __name__ == '__main__':
    api = SERIAL_API()
    print("Searching ports…")
    devs = api.get_serial_devices()
    print(devs)

    if devs:
        # Choisis l’index correspondant à /dev/cu.usbmodem***
        idx = 2
        # auto-pick si possible
        for i, d in enumerate(devs):
            if 'usbmodem' in d:
                idx = i
                break

        if api.connect_serial_device(devs[idx]):


            # Exemples ciblés
            api.send_command(addr=0, duty5=16, freq2=1, start_or_stop=1)
            time.sleep(2)
            api.send_command(addr=0, duty5=0,  freq2=1, start_or_stop=0)

            api.disconnect_serial_device()