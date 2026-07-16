# ble_api.py — 3-byte protocol (wave + mode), duty 5 bits (0..31)
import asyncio
from bleak import BleakClient, BleakScanner
import time

# Modes (2 bits)
MODE_STOP     = 0b00
MODE_START    = 0b01

# Wave modes
WAVE_SQUARE = 0
WAVE_SINE   = 1

class BLE_API:
    def __init__(self):
        self.SERVICE_UUID        = "f10016f6-542b-460a-ac8b-bbb0b2010599"
        self.CHARACTERISTIC_UUID = "f22535de-5375-44bd-8ca9-d0ea9ff9e410"
        self.DEVICE_NAME         = "VibraForge-BLE"
        self.client = None
        self.connected = False
        self.default_wave = WAVE_SINE

    # ---------- Packing 3 bytes ----------
    def create_command(self, addr, duty, freq, start_or_stop, wave=None):
        addr = int(addr); duty = int(duty); freq = int(freq)
        start_or_stop = int(start_or_stop) & 0x01
        wave = int(self.default_wave if wave is None else wave) & 0x01

        if not (0 <= addr <= 31): raise ValueError(f"addr out of range: {addr}")
        if not (0 <= duty <= 31): raise ValueError(f"duty out of range: {duty}")
        if not (0 <= freq <= 7):  raise ValueError(f"freq out of range: {freq}")

        group = (addr // 16) & 0x0F
        addr6 = (addr % 16) & 0x3F
        mode  = MODE_START if start_or_stop else MODE_STOP

        b1 = (wave << 7) | (group << 2) | mode
        b2 = addr6
        b3 = ((duty & 0x1F) << 3) | (freq & 0x07)
        return bytearray([b1, b2, b3])

    def send_command(self, addr, duty, freq, start_or_stop, wave=None) -> bool:
        if not self.connected or self.client is None:
            return False
        try:
            pkt = self.create_command(addr, duty, freq, start_or_stop, wave)
            asyncio.get_event_loop().run_until_complete(
                self.client.write_gatt_char(self.CHARACTERISTIC_UUID, pkt, response=False))
            return True
        except Exception as e:
            print(f"BLE send failed: {e}")
            return False

    def send_command_list(self, commands) -> bool:
        if not self.connected or self.client is None:
            return False
        try:
            buf = bytearray()
            for c in commands:
                buf += self.create_command(
                    c.get('addr', 0), c.get('duty', 0), c.get('freq', 3),
                    c.get('start_or_stop', 0), c.get('wave', None))
            asyncio.get_event_loop().run_until_complete(
                self.client.write_gatt_char(self.CHARACTERISTIC_UUID, buf, response=False))
            return True
        except Exception as e:
            print(f"BLE send_command_list failed: {e}")
            return False

    # ---------- BLE I/O ----------
    def get_ble_devices(self, timeout=5.0):
        devices = asyncio.get_event_loop().run_until_complete(BleakScanner.discover(timeout=timeout))
        return [f"{d.address} - {d.name or 'Unknown'}" for d in devices]

    def connect_ble_device(self, device_info=None) -> bool:
        async def _connect():
            if device_info:
                address = device_info.split(' - ')[0]
            else:
                print(f"Scanning for '{self.DEVICE_NAME}'...")
                devices = await BleakScanner.discover(timeout=10.0)
                address = None
                for d in devices:
                    if d.name and self.DEVICE_NAME in d.name:
                        print(f"Found: {d.name} [{d.address}]")
                        address = d.address
                        break
                if not address:
                    print("Device not found")
                    return False
            
            print(f"Connecting to {address}...")
            self.client = BleakClient(address)
            await self.client.connect()
            if self.client.is_connected:
                self.connected = True
                print(f"BLE connected to {address}")
                return True
            return False
        
        try:
            return asyncio.get_event_loop().run_until_complete(_connect())
        except Exception as e:
            print(f"BLE connection failed: {e}")
            self.connected = False
            return False

    def disconnect_ble_device(self) -> bool:
        try:
            if self.client and self.client.is_connected:
                asyncio.get_event_loop().run_until_complete(self.client.disconnect())
                self.connected = False
                self.client = None
                print("BLE disconnected")
                return True
        except Exception as e:
            print(f"BLE disconnect failed: {e}")
        return False


if __name__ == '__main__':
    api = BLE_API()
    
    if not api.connect_ble_device():
        print("Erreur de connexion.")
        exit(1)

    print("Démarrage moteurs 0-7 (Sine, Duty 16)...")
    start_cmds = [{'addr': i, 'duty': 16, 'freq': 3, 'start_or_stop': 1, 'wave': 1} for i in range(8)]
    api.send_command_list(start_cmds)
    
    time.sleep(1.0)

    print("Arrêt...")
    stop_cmds = [{'addr': i, 'duty': 0, 'freq': 3, 'start_or_stop': 0, 'wave': 1} for i in range(8)]
    api.send_command_list(stop_cmds)
    
    time.sleep(0.3)
    api.disconnect_ble_device()