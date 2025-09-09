import asyncio
from bleak import BleakScanner, BleakClient
import threading
import time

class python_ble_api:
    def __init__(self):
        self.MOTOR_UUID = 'f22535de-5375-44bd-8ca9-d0ea9ff9e410'
        self.client = None
        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.run_loop, daemon=True)
        self.thread.start()

    def run_loop(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def create_command(self, addr, duty, freq, start_or_stop):
        serial_group = addr // 16
        serial_addr = addr % 16
        byte1 = (serial_group << 2) | (start_or_stop & 0x01)
        byte2 = 0x40 | (serial_addr & 0x3F)  # 0x40 represents the leading '01'
        byte3 = 0x80 | ((duty & 0x0F) << 3) | (freq & 0x07)  # 0x80 represents the leading '1'
        return bytearray([byte1, byte2, byte3])

    async def send_command_async(self, addr, duty, freq, start_or_stop) -> bool:
        if self.client is None or not self.client.is_connected:
            return False
        if addr < 0 or addr > 127 or duty < 0 or duty > 15 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
            return False
        command = self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        command = command + bytearray([0xFF, 0xFF, 0xFF]) * 19 # Padding
        try:
            await self.client.write_gatt_char(self.MOTOR_UUID, command)
            print(f'BLE sent command to #{addr} with duty {duty} and freq {freq}, start_or_stop {start_or_stop}')
            return True
        except Exception as e:
            print(f'BLE failed to send command to #{addr} with duty {duty} and freq {freq}. Error: {e}')
            return False

    '''
    send a list of commands to the BLE device at once.
    10 commands at most.
    commands is in the format of a list of json objects:
    [
        {
            "addr": 1,
            "duty": 7,
            "freq": 2,
            "start_or_stop": 1
        },
        {
            "addr": 2,
            "duty": 8,
            "freq": 3,
            "start_or_stop": 0
        }
    ]
    '''
    async def send_command_list_async(self, commands) -> bool:
        if self.client is None or not self.client.is_connected:
            return False
        command = bytearray()
        for c in commands:
            addr = c.get('addr', -1)
            duty = c.get('duty', -1)
            freq = c.get('freq', -1)
            start_or_stop = c.get('start_or_stop', -1)
            if addr < 0 or addr > 127 or duty < 0 or duty > 15 or freq < 0 or freq > 7 or start_or_stop not in [0, 1]:
                return False
            command = command + self.create_command(int(addr), int(duty), int(freq), int(start_or_stop))
        # padding to 60 bytes
        command = command + bytearray([0xFF, 0xFF, 0xFF]) * (20 - len(commands))
        try:
            await self.client.write_gatt_char(self.MOTOR_UUID, command)
            print(f'BLE sent command list {commands}')
            return True
        except Exception as e:
            print(f'BLE failed to send command list {commands}. Error: {e}')
            return False

    async def get_ble_devices_async(self):
        devices = await BleakScanner.discover()
        return [d.name for d in devices if d.name != '']

    async def connect_ble_device_async(self, device_name) -> bool:
        devices = await BleakScanner.discover()
        for d in devices:
            if d.name == device_name:
                self.client = BleakClient(d.address)
                try:
                    await self.client.connect()
                    if self.client.is_connected:
                        print(f'BLE connected to {d.address}')
                        return True
                except Exception as e:
                    print(f'BLE failed to connect to {d.address}. Error: {e}')
                    return False
        print(f'BLE failed to find device with name: {device_name}')
        return False

    async def disconnect_ble_device_async(self) -> bool:
        try:
            await self.client.disconnect()
            if not self.client.is_connected:
                self.client = None
                print(f'BLE disconnected')
                return True
        except Exception as e:
            print(f'BLE failed to disconnect. Error: {e}')
        return False

    def run_async(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)
    
    def get_ble_devices(self):
        return self.run_async(self.get_ble_devices_async()).result()

    def connect_ble_device(self, device_name):
        return self.run_async(self.connect_ble_device_async(device_name)).result()

    def disconnect_ble_device(self):
        return self.run_async(self.disconnect_ble_device_async()).result()

    def send_command(self, addr, duty, freq, start_or_stop):
        return self.run_async(self.send_command_async(addr, duty, freq, start_or_stop)).result()
    
    def send_command_list(self, commands):
        return self.run_async(self.send_command_list_async(commands)).result()
        

if __name__ == '__main__':
    ble_api = python_ble_api()
    print("Searching for BLE devices...")
    device_names = ble_api.get_ble_devices()
    print(device_names)
    
    # Example usage with GUI interaction:
    if 'QT Py ESP32-S3' in device_names:
        if ble_api.connect_ble_device('QT Py ESP32-S3'):
            ble_api.send_command(1, 7, 2, 1)
            time.sleep(3)

            ble_api.send_command(1, 7, 2, 0)
            time.sleep(3)

            # Example usage with a list of commands:
            commands = [
                {
                    "addr": 1,
                    "duty": 7,
                    "freq": 2,
                    "start_or_stop": 1
                },
                {
                    "addr": 2,
                    "duty": 7,
                    "freq": 2,
                    "start_or_stop": 1
                },
                {
                    "addr": 3,
                    "duty": 7,
                    "freq": 2,
                    "start_or_stop": 1
                }
            ]
            ble_api.send_command_list(commands)
            time.sleep(3)

            for c in commands:
                c['start_or_stop'] = 0
            ble_api.send_command_list(commands)
            time.sleep(3)
            
            ble_api.disconnect_ble_device()
            time.sleep(3)

