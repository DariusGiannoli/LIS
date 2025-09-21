import os
import sys
import time
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from core.hardware.serial_api import SerialAPI
from core.study_params import (DUTY, FREQ)

duration = 500

def test_single_actuator(api, addr):
    """Test a single actuator by address"""
    print(f"Testing actuator {addr}...")
    
    # Create test commands for this specific actuator
    test_commands = [
        {
            "addr": addr,
            "duty": DUTY,
            "freq": FREQ,
            "start_or_stop": 1,
            "delay_ms": 0,  # Start immediately
        },
        {
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
            "delay_ms": duration,  # Stop after duration
        }
    ]
    
    print(f"Sending commands to actuator {addr}...")
    print(f"Actuator will vibrate for {duration}ms")
    
    success = api.send_timed_batch(test_commands)
    if success:
        print(f"Commands sent to actuator {addr}")
        # Wait for vibration to complete - FIXED: reasonable wait time
        time.sleep((duration + 500) / 1000)  # duration + buffer in seconds
        print(f"Test of actuator {addr} completed")
        return True
    else:
        print(f"Failed to send commands to actuator {addr}")
        return False

def test_all_actuators(api):
    """Test all 8 actuators in sequence"""
    print("Testing all 8 actuators...")
    
    # Add gap between actuators to prevent timing collisions
    gap_ms = 100  # 100ms gap between stop and next start
    
    test_commands = []
    for addr in range(8):
        start_time = addr * (duration + gap_ms)
        stop_time = start_time + duration
        
        test_commands.extend([
            {
                "addr": addr,
                "duty": DUTY,
                "freq": FREQ,
                "start_or_stop": 1,
                "delay_ms": start_time
            },
            {
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                "delay_ms": stop_time
            },
        ])
    
    print(f"Sending test batch with {len(test_commands)} commands...")
    print(f"Each actuator will vibrate for {duration}ms with {gap_ms}ms gaps.")
    total_sequence_time = (8 * (duration + gap_ms)) / 1000
    print(f"Total sequence duration: {total_sequence_time} seconds")
    
    success = api.send_timed_batch(test_commands)
    if not success:
        print("Failed to send test commands")
        return False

    # Wait for the complete sequence to finish
    total_duration = (8 * (duration + gap_ms)) / 1000 + 1  # Add 1s buffer
    print(f"Waiting {total_duration} seconds for sequence to complete...")
    time.sleep(total_duration)  # Actually wait for completion
    
    print("Test sequence completed.")
    return True

if __name__ == '__main__':
    api = SerialAPI()

    # Find available ports
    ports = api.get_serial_ports()
    print("Available ports:", ports)

    if not ports:
        print("No serial ports found")
        exit(1)

    if len(ports) < 3:
        print(f"Need at least 3 ports, only found {len(ports)}")
        exit(1)

    # Connect to port 2 (third port)
    print(f"Connecting to port 2: {ports[2]}")
    if api.connect(ports[2]):
        print(f"Connected successfully to {ports[2]}!")
    else:
        print(f"Failed to connect to {ports[2]}")
        exit(1)

    # Interactive menu
    while True:
        print("\n" + "="*50)
        print("ACTUATOR TESTING MENU")
        print("="*50)
        print("1. Test single actuator (enter address)")
        print("2. Test all actuators (0-7)")
        print("3. Test all actuators twice")
        print("4. Exit")
        print("-"*50)

        choice = input("Enter your choice (1-4): ").strip()

        if choice == "1":
            try:
                addr = int(input("Enter actuator address (0-7): ").strip())
                if 0 <= addr <= 7:
                    test_single_actuator(api, addr)
                else:
                    print("Invalid address. Must be between 0 and 7.")
            except ValueError:
                print("Invalid input. Please enter a number.")

        elif choice == "2":
            test_all_actuators(api)

        elif choice == "3":
            print("Running sequence twice...")
            test_all_actuators(api)
            print("First sequence completed. Starting second...")
            test_all_actuators(api)
            print("Both sequences completed!")

        elif choice == "4":
            print("Exiting...")
            break

        else:
            print("Invalid choice. Please enter 1-4.")

    api.disconnect()
    print("Disconnected from device.")