#!/usr/bin/env python3
"""
Simple test using your existing python_serial_api.py
"""

import time
from python_serial_api import python_serial_api

def main():
    print("=== ESP-NOW Actuator Test ===")
    
    # Use your existing API
    api = python_serial_api()
    
    print("Searching for devices...")
    devices = api.get_serial_devices()
    print(f"Found: {devices}")
    
    if not devices:
        print("No devices found!")
        return
    
    # Connect to first device
    if not api.connect_serial_device(devices[0]):
        print("Connection failed!")
        return
    
    print("Connected! Testing vibrations...")
    time.sleep(2)
    
    # Test 1: Single actuator
    print("Test 1: Start actuator 0")
    api.send_command(0, 10, 2, 1)  # addr=0, duty=10, freq=2, start=1
    time.sleep(3)
    
    print("Stop actuator 0")
    api.send_command(0, 0, 0, 0)   # stop
    time.sleep(1)
    
    # Test 2: Different actuator
    print("Test 2: Start actuator 1") 
    api.send_command(1, 8, 1, 1)   # addr=1, duty=8, freq=1, start=1
    time.sleep(2)
    
    print("Stop actuator 1")
    api.send_command(1, 0, 0, 0)   # stop
    time.sleep(1)
    
    # Test 3: Multiple actuators
    print("Test 3: Multiple actuators")
    commands = [
        {"addr": 0, "duty": 15, "freq": 0, "start_or_stop": 1},
        {"addr": 1, "duty": 12, "freq": 1, "start_or_stop": 1},
        {"addr": 2, "duty": 8, "freq": 2, "start_or_stop": 1}
    ]
    
    api.send_command_list(commands)
    time.sleep(3)
    
    # Stop all
    print("Stopping all...")
    for cmd in commands:
        cmd['start_or_stop'] = 0
    api.send_command_list(commands)
    
    print("Test complete!")
    api.disconnect_serial_device()

def interactive():
    """Interactive mode using your API"""
    api = python_serial_api()
    
    devices = api.get_serial_devices()
    if not devices or not api.connect_serial_device(devices[0]):
        print("Failed to connect!")
        return
    
    print("Connected! Commands:")
    print("  start <addr> <duty> <freq>")
    print("  stop <addr>") 
    print("  quit")
    
    while True:
        try:
            cmd = input("> ").strip().split()
            
            if not cmd:
                continue
            
            if cmd[0] == "quit":
                break
            elif cmd[0] == "start" and len(cmd) == 4:
                addr, duty, freq = int(cmd[1]), int(cmd[2]), int(cmd[3])
                api.send_command(addr, duty, freq, 1)
            elif cmd[0] == "stop" and len(cmd) == 2:
                addr = int(cmd[1])
                api.send_command(addr, 0, 0, 0)
            else:
                print("Invalid command")
                
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"Error: {e}")
    
    api.disconnect_serial_device()

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "i":
        interactive()
    else:
        main()