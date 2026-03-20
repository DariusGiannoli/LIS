import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from serial_api import SERIAL_API

__all__ = ['SERIAL_API']

if __name__ == '__main__':
    api = SERIAL_API()
    devs = api.get_serial_devices()
    print("Available ports:")
    for i, d in enumerate(devs):
        print(f"  [{i}] {d}")

    if not devs:
        print("No serial devices found.")
        sys.exit(1)

    # Connect to master ESP32 (adjust index if needed)
    if not api.connect_serial_device(devs[2]):
        print("Failed to connect.")
        sys.exit(1)

    import time

    addr = 0

    # START sine, duty=20, freq=3
    api.send_command(addr, duty=30, freq=6, start_or_stop=1, wave=0)
    time.sleep(1.5)

    # STOP
    api.send_command(addr, duty=0, freq=6, start_or_stop=0, wave=0)
    time.sleep(0.1)
    
     # START sine, duty=20, freq=3
    api.send_command(1, duty=30, freq=6, start_or_stop=1, wave=0)
    time.sleep(1.5)

    # STOP
    api.send_command(1, duty=0, freq=6, start_or_stop=0, wave=0)
    time.sleep(0.1)

    api.disconnect_serial_device()
