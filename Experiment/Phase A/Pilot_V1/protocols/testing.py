from core.serial_api import SerialAPI
from shared import (DUTY, FREQ)

duration = 2000

api = SerialAPI()

# Find available ports
ports = api.get_serial_ports()
print("Available ports:", ports)

if ports:
    # Connect to first available port (change index as needed)
    if api.connect(ports[2]):
        # Generate test commands for addresses 0 to 15
        test_commands = []
        for addr in range(16):
            test_commands.extend(
                (
                    {
                        "addr": addr,
                        "duty": DUTY,
                        "freq": FREQ,
                        "start_or_stop": 1,
                        "delay_ms": addr * duration,
                    },
                    {
                        "addr": addr,
                        "duty": DUTY,
                        "freq": FREQ,
                        "start_or_stop": 0,
                        "delay_ms": (addr + 1) * duration,
                    },
                )
            )
            print("Sending test batch...")
            api.send_timed_batch(test_commands)

            # Wait for sequence to complete
            time.sleep(2)
            api.disconnect()
        print("Failed to connect")
    else:
        print("No serial ports found")
