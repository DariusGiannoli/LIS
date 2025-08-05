#!/usr/bin/env python3
"""
Minimal test script for single slave ESP-NOW haptic system
Your slave MAC: CC:BA:97:1D:01:74
"""

import time
from python_serial_api import python_serial_api

def main():
    print("🎯 Single Slave Haptic Test")
    print("Slave MAC: CC:BA:97:1D:01:74")
    print()
    
    # Connect to serial (auto-detect first port)
    api = python_serial_api()
    ports = api.list_serial_ports()
    
    if not ports:
        print("❌ No serial ports found!")
        return
    
    print(f"🔌 Connecting to {ports[0]}...")
    if not api.connect_serial(ports[0]):
        print("❌ Connection failed!")
        return
    
    print("✅ Connected!")
    
    try:
        # Test 1: LED Flash
        print("\n1️⃣ LED Test...")
        api.test_led()
        print("👀 Check if slave LED is blinking!")
        time.sleep(3)
        
        # Test 2: Quick vibration
        print("2️⃣ Vibration Test...")
        print("🔄 Starting vibration (motor 1)...")
        api.send_command(addr=1, duty=10, freq=3, start_or_stop=1)
        time.sleep(2)
        
        print("🛑 Stopping vibration...")
        api.send_command(addr=1, duty=0, freq=0, start_or_stop=0)
        
        print("\n✅ Test complete!")
        
    except KeyboardInterrupt:
        print("\n🛑 Stopping...")
        api.send_command(addr=1, duty=0, freq=0, start_or_stop=0)
    
    finally:
        api.disconnect_serial()
        print("👋 Disconnected")

if __name__ == "__main__":
    main()