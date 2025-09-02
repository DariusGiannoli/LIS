import os
import sys
import time
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ)

duration = 2000

if __name__ == '__main__':
    api = SerialAPI()

    # Find available ports
    ports = api.get_serial_ports()
    print("Available ports:", ports)

    if ports:
        # Connect to first available port (change index as needed)
        if api.connect(ports[2]):
            print("Connected successfully! Testing all 16 actuators...")
            
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
                    },
                    {
                        "addr": addr,
                        "duty": 0,
                        "freq": 0,
                        "start_or_stop": 0,
                        "delay_ms": (addr + 1) * duration,
                    },
                ])
            
            print(f"Sending test batch with {len(test_commands)} commands...")
            print(f"Each actuator will vibrate for {duration}ms in sequence.")
            print(f"Total test duration: {16 * duration / 1000} seconds")
            api.send_timed_batch(test_commands)

            # Wait for sequence to complete
            total_duration = 16 * duration / 1000 + 2  # Add 2 seconds buffer
            print(f"Waiting {total_duration} seconds for sequence to complete...")
            time.sleep(total_duration)
            
            print("Test sequence completed.")
            api.disconnect()
        else:
            print("Failed to connect")
    else:
        print("No serial ports found")
