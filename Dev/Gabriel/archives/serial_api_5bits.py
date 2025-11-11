# serial_api.py — Duty hybride: accepte 0..31 (raw5) OU 0..99 (pourcent)
import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    """
    PC → ESP : 4 octets par commande
      Byte1: [GGGG][0][S]        (4-bit group, S=start bit)
      Byte2: [00][ADDR6]         (0..7 sur la sous-chaîne)
      Byte3: [-----DUTY5]        (5-bit duty : 0..31)
      Byte4: [-----FREQ3]        (3-bit freq : 0..7)

    Entrée API (duty) :
      - 0..31  → interprété comme 5 bits bruts
      - 32..99 → pourcentage, mappé en 0..31 (arrondi)
    """

    USE_PADDING = True          # garde le bourrage 80 octets (legacy)
    PAD_COMMANDS_TO = 20        # 20 trames * 4 = 80 octets

    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'
        self.serial_connection = None
        self.connected = False

    @staticmethod
    def _clamp(v, lo, hi):
        return lo if v < lo else hi if v > hi else v

    @staticmethod
    def _percent_to_duty5(duty_percent_0_99: int) -> int:
        """0..99 % → 0..31 (arrondi)"""
        d = 0 if duty_percent_0_99 < 0 else 99 if duty_percent_0_99 > 99 else duty_percent_0_99
        return (d * 31 + 50) // 100

    @staticmethod
    def _to_duty5_hybrid(duty_input: int) -> int:
        """≤31 => raw5, sinon (32..99) => mapping % → 5 bits"""
        d = int(duty_input)
        if d <= 31:
            return 0 if d < 0 else 31 if d > 31 else d
        return SERIAL_API._percent_to_duty5(d)

    def create_command(self, addr, duty, freq, start_or_stop):
        """
        Retourne un bytearray(4) prêt à l'envoi (PC→ESP).
        - addr : 0..31  (4 groupes * 8 adresses)
        - duty : 0..31 (raw5) OU 32..99 (pourcent)
        - freq : 0..7
        - start_or_stop : 1=START, 0=STOP
        """
        addr = int(addr); duty = int(duty); freq = int(freq); start_or_stop = int(start_or_stop) & 0x01

        serial_group = addr // 8                 # 0..3
        serial_addr  = addr % 8                  # 0..7
        duty5 = self._to_duty5_hybrid(duty)      # ✅ 5 bits alignés PIC

        byte1 = ((serial_group & 0x0F) << 2) | start_or_stop
        byte2 = serial_addr & 0x3F
        byte3 = duty5 & 0x1F
        byte4 = freq & 0x07
        return bytearray([byte1, byte2, byte3, byte4])

    # ---------------- I/O ----------------
    def get_serial_devices(self):
        ports = serial.tools.list_ports.comports()
        return [f"{p.device} - {p.description}" for p in ports]

    def connect_serial_device(self, port_info) -> bool:
        try:
            port_name = port_info.split(' - ')[0]
            self.serial_connection = serial.Serial(
                port=port_name, baudrate=115200, timeout=1, write_timeout=1
            )
            time.sleep(2)
            self.connected = bool(self.serial_connection and self.serial_connection.is_open)
            if self.connected:
                print(f"Serial connected to {port_name}")
            return self.connected
        except Exception as e:
            print(f"Serial failed to connect to {port_info}. Error: {e}")
            self.serial_connection = None
            self.connected = False
            return False

    def disconnect_serial_device(self) -> bool:
        try:
            if self.serial_connection and self.serial_connection.is_open:
                self.serial_connection.close()
            self.connected = False
            self.serial_connection = None
            print("Serial disconnected")
            return True
        except Exception as e:
            print(f"Serial failed to disconnect. Error: {e}")
            return False

    # ------------- Envoi commandes -------------
    def send_command(self, addr, duty, freq, start_or_stop) -> bool:
        if self.serial_connection is None or not self.connected:
            return False
        # bornes souples: addr 0..31, freq 0..7, duty 0..99 (pourcent) OU 0..31 (raw)
        if not (0 <= int(addr) <= 31 and 0 <= int(freq) <= 7 and 0 <= int(duty) <= 99):
            print(f"Invalid params: addr={addr} (0..31), duty={duty} (0..31 or 0..99), freq={freq} (0..7), start_or_stop={start_or_stop}")
            return False

        pkt = self.create_command(addr, duty, freq, start_or_stop)
        if self.USE_PADDING:
            pad_frames = self.PAD_COMMANDS_TO - 1
            if pad_frames > 0:
                pkt += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * pad_frames
        try:
            self.serial_connection.write(pkt)
            print(f"Sent: addr={addr}, duty_in={duty} -> duty5={pkt[2]}, freq={freq}, sos={start_or_stop}")
            return True
        except Exception as e:
            print(f"Write failed: {e}")
            return False

    def send_command_list(self, commands) -> bool:
        if self.serial_connection is None or not self.connected:
            return False
        pkt = bytearray()
        for c in commands:
            addr = int(c.get('addr', -1))
            duty = int(c.get('duty', -1))
            freq = int(c.get('freq', -1))
            sos  = int(c.get('start_or_stop', -1))
            if not (0 <= addr <= 31 and 0 <= duty <= 99 and 0 <= freq <= 7 and sos in (0,1)):
                print(f"Invalid command in list: {c}")
                return False
            pkt += self.create_command(addr, duty, freq, sos)

        if self.USE_PADDING:
            frames = len(pkt) // 4
            if frames < self.PAD_COMMANDS_TO:
                pkt += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * (self.PAD_COMMANDS_TO - frames)

        try:
            self.serial_connection.write(pkt)
            print(f"Sent list of {len(commands)} cmds")
            return True
        except Exception as e:
            print(f"Write failed: {e}")
            return False


# Démo simple
if __name__ == '__main__':
    api = SERIAL_API()
    devs = api.get_serial_devices()
    print(devs)
    if devs and api.connect_serial_device(devs[2]):
        addr = 0
        # Exemple 2: 5 bits brut (25/31 ≈ 80%)
        api.send_command(addr, 25, 3, 1); time.sleep(1.0); api.send_command(addr, 25, 3, 0)
        api.disconnect_serial_device()