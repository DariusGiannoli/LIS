# serial_api.py — 3-byte protocol (wave + mode), duty en 5 bits (0..31)
import serial
import serial.tools.list_ports
import time

# Modes (2 bits)
MODE_STOP     = 0b00
MODE_START    = 0b01
MODE_SOFTSTOP = 0b10
MODE_RSVD     = 0b11

class SERIAL_API:
    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'  # compat
        self.serial_connection = None
        self.connected = False
        # Par défaut: sinus (1). Mets 0 pour square.
        self.default_wave = 1

    # ---------- Packing 3 bytes ----------
    def create_command(self, addr, duty, freq, start_or_stop, wave=None):
        """
        Creates a 3-byte command (PC → ESP):
          Byte1: [W][0][G3][G2][G1][G0][M1][M0]
                  W: wave (0=square, 1=sine)
                  G: group 0..3  (addr//8)
                  M: mode (00=STOP, 01=START, 10=SOFTSTOP, 11=RSVD) — ici 00/01 selon start_or_stop
          Byte2: [0][0][A5][A4][A3][A2][A1][A0]
                  A: sub-address 0..7 (addr%8) — extensible à 0..63
          Byte3: [D4][D3][D2][D1][D0][F2][F1][F0]
                  D: duty5  (0..31)
                  F: freq3  (0..7)
        """
        addr = int(addr); duty = int(duty); freq = int(freq)
        start_or_stop = int(start_or_stop) & 0x01
        if wave is None:
            wave = int(self.default_wave) & 0x01
        else:
            wave = int(wave) & 0x01

        # bornes
        if not (0 <= addr <= 31): raise ValueError(f"addr out of range: {addr} (0..31)")
        if not (0 <= duty <= 31): raise ValueError(f"duty5 out of range: {duty} (0..31)")
        if not (0 <= freq <= 7):  raise ValueError(f"freq3 out of range: {freq} (0..7)")

        group  = (addr // 8) & 0x0F
        addr6  = (addr  %  8) & 0x3F
        mode   = MODE_START if start_or_stop == 1 else MODE_STOP

        b1 = (wave << 7) | (group << 2) | mode
        b2 = addr6
        b3 = ((duty & 0x1F) << 3) | (freq & 0x07)
        return bytearray([b1, b2, b3])

    def send_command(self, addr, duty, freq, start_or_stop, wave=None) -> bool:
        """Envoie UNE commande 3 octets. Param wave optionnel (0=square,1=sine)."""
        if self.serial_connection is None or not self.connected:
            return False
        try:
            pkt = self.create_command(addr, duty, freq, start_or_stop, wave=wave)
            self.serial_connection.write(pkt)
            return True
        except Exception as e:
            print(f"Serial failed to send command to #{addr} (duty5={duty}, freq={freq}, start={start_or_stop}, wave={wave}). Error: {e}")
            return False

    def send_command_list(self, commands) -> bool:
        """
        commands: liste de dicts avec clés:
          - addr (0..31), duty (0..31), freq (0..7), start_or_stop (0/1), wave (0/1, optionnel)
        """
        if self.serial_connection is None or not self.connected:
            return False
        try:
            buf = bytearray()
            for c in commands:
                addr = int(c.get('addr', -1))
                duty = int(c.get('duty', -1))
                freq = int(c.get('freq', -1))
                sos  = int(c.get('start_or_stop', -1))
                wave = c.get('wave', None)
                buf += self.create_command(addr, duty, freq, sos, wave=wave)
            self.serial_connection.write(buf)
            return True
        except Exception as e:
            print(f"Serial failed to send command list {commands}. Error: {e}")
            return False

    # ---------- Serial I/O ----------
    def get_serial_devices(self):
        ports = serial.tools.list_ports.comports()
        return [f"{p.device} - {p.description}" for p in ports]

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
                print(f"Serial connected to {port_name}")
                return True
            return False
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
                print('Serial disconnected')
                return True
        except Exception as e:
            print(f'Serial failed to disconnect. Error: {e}')
        return False


if __name__ == '__main__':
    api = SERIAL_API()
    devs = api.get_serial_devices()
    
    if not devs:
        print("Aucun port série trouvé.")
        exit(1)

    print("Ports disponibles :")
    for k, d in enumerate(devs):
        print(f"{k}: {d}")

    # Sélection du port (modifiez l'index '2' si nécessaire ou utilisez input comme avant)
    # idx = int(input("Index port: "))
    idx = 2 
    
    if idx < len(devs) and api.connect_serial_device(devs[idx]):
        print(f"Démarrage synchronisé des moteurs 0 à 7 (Sine, Duty 16)...")

        # 1. Création de la liste de commandes pour DEMARRER (0 à 7)
        # On utilise une boucle pour générer les commandes
        start_commands = []
        for i in range(8): # de 0 à 7 inclus
            cmd = {
                'addr': i,          # Adresse 0, 1, ... 7
                'duty': 16,         # Duty demandé : 16/31
                'freq': 3,          # Fréquence standard (3 = ~170Hz)
                'start_or_stop': 1, # 1 = START
                'wave': 1           # 1 = SINE (Sinus)
            }
            start_commands.append(cmd)

        # 2. Envoi groupé (Rafale)
        api.send_command_list(start_commands)
        
        # 3. On laisse vibrer s secondes
        time.sleep(1.0)

        # 4. Création de la liste de commandes pour STOPPER (0 à 7)
        stop_commands = []
        for i in range(8):
            cmd = {
                'addr': i,
                'duty': 0,          # Duty 0 pour l'arrêt
                'freq': 3,
                'start_or_stop': 0, # 0 = STOP
                'wave': 1
            }
            stop_commands.append(cmd)

        print("Arrêt synchronisé...")
        api.send_command_list(stop_commands)

        api.disconnect_serial_device()
    else:
        print("Erreur de connexion.")