from serial_api_flexible import SERIAL_API
import time

def main():
    api = SERIAL_API()
    
    print("Searching for serial devices...")
    devices = api.get_serial_devices()
    
    if not devices:
        print("No serial devices found. Connect your Master ESP32.")
        return

    print("Found devices:")
    for i, device in enumerate(devices):
        print(f"  [{i}] {device}")
    
    try:
        selection = int(input("Select the device for the Master ESP32: "))
        port_to_use = devices[selection]
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        return

    if not api.connect_serial_device(port_to_use):
        return

    print("\n--- Starting Flexible Motor Test ---")

    # Test 1: Send a targeted command to start motor #1 on SLAVE 0
    print("\n[Test 1] Starting motor #1 on SLAVE 0...")
    api.send_command(slave_id=0, addr=0, duty=7, freq=2, start_or_stop=1)
    time.sleep(2)

    # Test 3: Stop motor #1 on SLAVE 0
    print("\n[Test 3] Stopping motor #1 on SLAVE 0...")
    api.send_command(slave_id=0, addr=0, duty=0, freq=0, start_or_stop=0)
    time.sleep(2)
    
    print("\n[Test 1] Starting motor #1 on SLAVE 0...")
    api.send_command(slave_id=1, addr=0, duty=7, freq=2, start_or_stop=1)
    time.sleep(3)

    # Test 3: Stop motor #1 on SLAVE 0
    print("\n[Test 3] Stopping motor #1 on SLAVE 0...")
    api.send_command(slave_id=1, addr=0, duty=0, freq=0, start_or_stop=0)
    time.sleep(3)
    
    print("\n--- Test Complete ---")
    api.disconnect_serial_device()

if __name__ == "__main__":
    main()