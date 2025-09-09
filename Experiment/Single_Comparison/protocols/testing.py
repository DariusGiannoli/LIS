import os
import sys
import time
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from core.hardware.serial_api import SerialAPI
from core.study_params import (DUTY, FREQ)

duration = 2000

def test_single_actuator(api, addr):
    """Test a single actuator by address"""
    print(f"🎯 Testing actuator {addr}...")
    
    # Create test commands for this specific actuator
    test_commands = [
        {
            "addr": addr,
            "duty": DUTY,
            "freq": FREQ,
            "start_or_stop": 1,
            "delay_ms": 0,  # Start immediately
            "wave": 0
        },
        {
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
            "delay_ms": duration,  # Stop after duration
            "wave": 0
        }
    ]
    
    print(f"📤 Sending commands to actuator {addr}...")
    print(f"⏱️ Actuator will vibrate for {duration}ms")
    
    success = api.send_timed_batch(test_commands)
    if success:
        print(f"✅ Commands sent to actuator {addr}")
        # Wait for vibration to complete
        time.sleep((duration + 500) / 1000)  # Add 500ms buffer
        print(f"🏁 Test of actuator {addr} completed")
        return True
    else:
        print(f"❌ Failed to send commands to actuator {addr}")
        return False

def test_all_actuators(api):
    """Test all 16 actuators in sequence"""
    print("🧪 Testing all 16 actuators...")
    
    # Generate test commands for addresses 0 to 15
    test_commands = []
    for addr in range(16):
        test_commands.extend([
            {
                "addr": addr,
                "duty": DUTY,
                "freq": FREQ,
                "start_or_stop": 1,
                "delay_ms": addr * duration,
                "wave": 0
            },
            {
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                "delay_ms": (addr + 1) * duration,
                "wave": 0
            },
        ])
    
    print(f"📤 Sending test batch with {len(test_commands)} commands...")
    print(f"⏱️ Each actuator will vibrate for {duration}ms in sequence.")
    print(f"🕒 Total test duration: {16 * duration / 1000} seconds")
    
    success = api.send_timed_batch(test_commands)
    if not success:
        print("❌ Failed to send test commands")
        return False

    # Wait for sequence to complete
    total_duration = 16 * duration / 1000 + 2  # Add 2 seconds buffer
    print(f"⏳ Waiting {total_duration} seconds for sequence to complete...")
    time.sleep(total_duration)
    
    print("✅ Test sequence completed.")
    return True

if __name__ == '__main__':
    api = SerialAPI()

    # Find available ports
    ports = api.get_serial_ports()
    print("Available ports:", ports)

    if not ports:
        print("❌ No serial ports found")
        exit(1)

    if len(ports) < 3:
        print(f"❌ Need at least 3 ports, only found {len(ports)}")
        exit(1)

    # Connect to port 2 (third port)
    print(f"🔄 Connecting to port 2: {ports[2]}")
    if api.connect(ports[2]):
        print(f"✅ Connected successfully to {ports[2]}!")
    else:
        print(f"❌ Failed to connect to {ports[2]}")
        exit(1)
    
    # Interactive menu
    while True:
        print("\n" + "="*50)
        print("🎛️  ACTUATOR TESTING MENU")
        print("="*50)
        print("1. Test single actuator (enter address)")
        print("2. Test all actuators (0-15)")
        print("3. Exit")
        print("-"*50)
        
        choice = input("Enter your choice (1-3): ").strip()
        
        if choice == "1":
            try:
                addr = int(input("Enter actuator address (0-15): ").strip())
                if 0 <= addr <= 15:
                    test_single_actuator(api, addr)
                else:
                    print("❌ Invalid address. Must be between 0 and 15.")
            except ValueError:
                print("❌ Invalid input. Please enter a number.")
                
        elif choice == "2":
            test_all_actuators(api)
            
        elif choice == "3":
            print("👋 Exiting...")
            break
            
        else:
            print("❌ Invalid choice. Please enter 1, 2, or 3.")
    
    api.disconnect()
    print("✅ Disconnected from device.")
