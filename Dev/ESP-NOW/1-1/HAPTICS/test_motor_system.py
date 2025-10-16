from serial_api_espnow import SERIAL_API
import time

# --- IMPORTANT ---
# You must find the correct serial port for your MASTER ESP32 and change it below.
#
# How to find your serial port:
#   - Windows: Open Device Manager -> Ports (COM & LPT).
#   - macOS: Open Terminal -> run: ls /dev/tty.*
#   - Linux: Open Terminal -> run: ls /dev/ttyUSB*
#
# Pick the correct device from the list printed by the script.
# For example: '/dev/tty.usbserial-110' or 'COM3'

def main():
    api = SERIAL_API()
    
    print("Searching for available serial devices...")
    devices = api.get_serial_devices()
    
    if not devices:
        print("No serial devices found. Please connect your Master ESP32.")
        return

    print("Found devices:")
    for i, device in enumerate(devices):
        print(f"  [{i}] {device}")
    
    try:
        selection = int(input("Select the device for the Master ESP32 (enter the number): "))
        port_to_use = devices[selection]
    except (ValueError, IndexError):
        print("Invalid selection. Exiting.")
        return

    if not api.connect_serial_device(port_to_use):
        print("Could not connect. Aborting test.")
        return

    print("\n--- Starting Motor Test ---")

    # Test 1: Send a single command to start motor #1
    print("\n[Test 1] Starting motor #1...")
    api.send_command(addr=1, duty=7, freq=2, start_or_stop=1)
    time.sleep(3)

    # Test 2: Send a single command to stop motor #1
    print("\n[Test 2] Stopping motor #1...")
    api.send_command(addr=1, duty=7, freq=2, start_or_stop=0)
    time.sleep(3)

    # Test 3: Send a list of commands to start 4 motors at once
    print("\n[Test 3] Starting motors #0, #1, #2, #3...")
    commands_start = [
        {"addr": 0, "duty": 7, "freq": 2, "start_or_stop": 1},
        {"addr": 1, "duty": 7, "freq": 2, "start_or_stop": 1},
        {"addr": 2, "duty": 7, "freq": 2, "start_or_stop": 1},
        {"addr": 3, "duty": 7, "freq": 2, "start_or_stop": 1},
    ]
    api.send_command_list(commands_start)
    time.sleep(3)
    
    # Test 4: Send a list of commands to stop those 4 motors
    print("\n[Test 4] Stopping motors #0, #1, #2, #3...")
    commands_stop = [
        {"addr": 0, "start_or_stop": 0, "duty": 0, "freq": 0},
        {"addr": 1, "start_or_stop": 0, "duty": 0, "freq": 0},
        {"addr": 2, "start_or_stop": 0, "duty": 0, "freq": 0},
        {"addr": 3, "start_or_stop": 0, "duty": 0, "freq": 0},
    ]
    api.send_command_list(commands_stop)
    time.sleep(1)

    print("\n--- Test Complete ---")
    api.disconnect_serial_device()

if __name__ == "__main__":
    main()