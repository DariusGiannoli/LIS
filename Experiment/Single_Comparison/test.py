import time 
from core.hardware.serial_api import Serial_API

if __name__ == '__main__':
    api = Serial_API()
    
    # Find available ports
    ports = api.get_serial_ports()
    print("Available ports:", ports)
    
    if ports:
        # Connect to first available port (change index as needed)
        if api.connect(ports[2]):
            # Test with 100-level duty values
            test_commands = [
                {"addr": 0, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":0, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 1, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":1, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 2, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":2, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 3, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":3, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 4, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":4, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 5, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":5, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 6, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":6, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
                {"addr": 7, "duty": 13, "freq": 4, "start_or_stop": 1, "delay_ms": 0},
                {"addr":7, "duty":8, "freq": 4, "start_or_stop": 0, "delay_ms": 1000},
            ]
            print("Sending test batch with 100-level duty values...")
            api.send_timed_batch(test_commands)
            
            # Wait for sequence to complete
            time.sleep(2)
            api.disconnect()
        else:
            print("Failed to connect")
    else:
        print("No serial ports found")