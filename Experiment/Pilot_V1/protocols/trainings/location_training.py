
import time
import sys  
import os  

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands
from core.serial_api import SerialAPI
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)


sleep = 5


commands = create_all_commands(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
# Location : extract 4 lists 
static_horizontal = commands['static_horizontal']  # 12 commands
static_vertical = commands['static_vertical']      # 12 commands  
pulse_horizontal = commands['pulse_horizontal']    # 12 commands
pulse_vertical = commands['pulse_vertical']        # 12 commands

if __name__ == "__main__":
    
    api = SerialAPI()
    ports = api.get_serial_ports()
    if ports and api.connect(ports[2]):
        
        # Send specific patterns by index
        api.send_timed_batch(static_horizontal[0])    # First horizontal static (devices 0-1)
        time.sleep(sleep)
        
        api.send_timed_batch(pulse_horizontal[0])     # First horizontal pulse (devices 0-1)
        time.sleep(sleep)

        api.send_timed_batch(pulse_vertical[0])       # First vertical pulse (devices 0-4)
        time.sleep(sleep)

        api.send_timed_batch(static_vertical[0])      # First vertical static (devices 0-4)
        time.sleep(sleep)
        
    api.disconnect()
    
    
