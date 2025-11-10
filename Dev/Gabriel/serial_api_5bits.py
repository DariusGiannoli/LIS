# serial_api.py
import serial
import serial.tools.list_ports
import time

class SERIAL_API:
    """
    PC → ESP : 4 octets par commande
      Byte1: [GGGG][0][S]        (4-bit group, bit1=0, S=start bit)
      Byte2: [00][ADDR6]         (6-bit adresse dans la sous-chaîne, 0..7)
      Byte3: [-----DUTY5]        (5-bit duty, 0..31 ; PC mappe 0..99 → 0..31)
      Byte4: [-----FREQ3]        (3-bit freq, 0..7)

    ESP → PIC : inchangé (MSB=0 pour addr, MSB=1 pour data), géré côté firmware.
    """

    # ===== Options protocole / perfs =====
    USE_PADDING = False         # True pour bourrer à 80 octets (legacy), False recommandé
    PAD_COMMANDS_TO = 20        # 20 trames * 4 = 80 octets si USE_PADDING=True

    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'  # compat
        self.serial_connection = None
        self.connected = False

    # ---------- Packing ----------
    @staticmethod
    def _clamp(val, lo, hi):
        return lo if val < lo else hi if val > hi else val

    @staticmethod
    def _duty99_to_duty5(duty_0_99: int) -> int:
        """Mappe 0..99 → 0..31 (arrondi)."""
        duty_0_99 = 0 if duty_0_99 < 0 else 99 if duty_0_99 > 99 else duty_0_99
        return (duty_0_99 * 31 + 50) // 100

    def create_command(self, addr, duty, freq, start_or_stop):
        """
        Retourne un bytearray(4) prêt à l'envoi (PC→ESP).
        - addr : 0..31 (4 groupes * 8 adresses)
        - duty : 0..99 (sera mappé en 0..31)
        - freq : 0..7
        - start_or_stop : 1=START, 0=STOP
        """
        addr = int(addr)
        duty = int(duty)
        freq = int(freq)
        start_or_stop = int(start_or_stop) & 0x01

        # group/addr sur 4*8
        serial_group = addr // 8       # 0..3
        serial_addr  = addr % 8        # 0..7

        duty5 = self._duty99_to_duty5(duty)

        byte1 = ((serial_group & 0x0F) << 2) | start_or_stop
        byte2 = serial_addr & 0x3F
        byte3 = duty5 & 0x1F           # ✅ 5 bits alignés avec le PIC
        byte4 = freq & 0x07
        return bytearray([byte1, byte2, byte3, byte4])

    # ---------- I/O ----------
    def get_serial_devices(self):
        """Liste des ports série disponibles (strings 'device - description')."""
        ports = serial.tools.list_ports.comports()
        return [f"{port.device} - {port.description}" for port in ports]

    def connect_serial_device(self, port_info) -> bool:
        """Connexion au port (passer une string retournée par get_serial_devices())."""
        try:
            port_name = port_info.split(' - ')[0]
            self.serial_connection = serial.Serial(
                port=port_name,
                baudrate=115200,
                timeout=1,
                write_timeout=1
            )
            time.sleep(2)  # laisse le temps d'ouverture
            self.connected = bool(self.serial_connection and self.serial_connection.is_open)
            if self.connected:
                print(f'Serial connected to {port_name}')
            return self.connected
        except Exception as e:
            print(f'Serial failed to connect to {port_info}. Error: {e}')
            self.serial_connection = None
            self.connected = False
            return False

    def disconnect_serial_device(self) -> bool:
        """Déconnexion du port série."""
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

    # ---------- Envoi commandes ----------
    def send_command(self, addr, duty, freq, start_or_stop) -> bool:
        """Envoie UNE commande (4 octets). Optionnellement pad jusqu’à 80 octets."""
        if self.serial_connection is None or not self.connected:
            return False

        # bornes
        if not (0 <= int(addr) <= 31 and 0 <= int(duty) <= 99 and 0 <= int(freq) <= 7 and int(start_or_stop) in (0,1)):
            print(f'Invalid command parameters: addr={addr} (0..31), duty={duty} (0..99), freq={freq} (0..7), start_or_stop={start_or_stop}')
            return False

        pkt = self.create_command(addr, duty, freq, start_or_stop)

        if self.USE_PADDING:
            # On bourre à 80 octets (1 trame + 19 trames 0xFF)
            filler_frames = self.PAD_COMMANDS_TO - 1
            if filler_frames > 0:
                pkt += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * filler_frames

        try:
            self.serial_connection.write(pkt)
            return True
        except Exception as e:
            print(f'Serial failed to send command to #{addr} with duty {duty} and freq {freq}. Error: {e}')
            return False

    def send_command_list(self, commands) -> bool:
        """Envoie N commandes consécutives (4*N octets). Optionnellement pad à 80 octets."""
        if self.serial_connection is None or not self.connected:
            return False

        pkt = bytearray()
        for c in commands:
            addr = int(c.get('addr', -1))
            duty = int(c.get('duty', -1))
            freq = int(c.get('freq', -1))
            sos  = int(c.get('start_or_stop', -1))
            if not (0 <= addr <= 31 and 0 <= duty <= 99 and 0 <= freq <= 7 and sos in (0,1)):
                print(f'Invalid command in list: {c}')
                return False
            pkt += self.create_command(addr, duty, freq, sos)

        if self.USE_PADDING:
            frames = len(pkt) // 4
            if frames < self.PAD_COMMANDS_TO:
                pad_frames = self.PAD_COMMANDS_TO - frames
                pkt += bytearray([0xFF, 0xFF, 0xFF, 0xFF]) * pad_frames

        try:
            self.serial_connection.write(pkt)
            return True
        except Exception as e:
            print(f'Serial failed to send command list {commands}. Error: {e}')
            return False


# ========== Usage en ligne de commande (démo) ==========
if __name__ == '__main__':
    api = SERIAL_API()
    print("Searching for Serial devices...")
    devices = api.get_serial_devices()
    print(devices)
    if not devices:
        raise SystemExit("No serial devices found.")

    # ⚠️ Choisis le bon index !
    port_idx = 2
    if api.connect_serial_device(devices[port_idx]):
        addr = 0
        # START à 50% (sera mappé en duty5 0..31)
        api.send_command(addr, 50, 3, 1)
        time.sleep(1.5)
        print("STOP")
        api.send_command(addr, 50, 3, 0)
        api.disconnect_serial_device()