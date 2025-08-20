from core.serial_api import SerialAPI

from Categories.location import create_all_commands
from Categories.shape import cross

import shared as shared

import time
import random

def main():
    # Create all commands
    commands = create_all_commands()
    
    # Location : extract 4 lists 
    static_horizontal = commands['static_horizontal']  # 12 commands
    static_vertical = commands['static_vertical']      # 12 commands  
    pulse_horizontal = commands['pulse_horizontal']    # 12 commands
    pulse_vertical = commands['pulse_vertical']        # 12 commands
    
    
    #Cross 
    cross_static, cross_pulse = cross()
    static_commands = cross_static(duty=8, freq=3, duration=2000)
    pulse_commands = cross_pulse(duty=8, freq=3, pulse_duration=500, pause_duration=500, num_pulses=3)
    
    #H Line 
    
    
    
    #V Line
    
    
    

    
    
    
    
    # Connect to device
    api = SerialAPI()
    ports = api.get_serial_ports()
    if ports and api.connect(ports[0]):
        
        # Send specific patterns by index
        api.send_timed_batch(static_horizontal[0])    # First horizontal static (devices 0-1)
        time.sleep(2.5)
        
        api.send_timed_batch(pulse_vertical[3])       # 4th vertical pulse (devices 1-5)
        time.sleep(4)
        
        api.send_timed_batch(static_vertical[0])      # First vertical static (devices 0-4)
        time.sleep(2)
        
        # Send random patterns
        random_h_static = random.choice(static_horizontal)
        api.send_timed_batch(random_h_static)
        time.sleep(2)
        
        random_v_pulse = random.choice(pulse_vertical)
        api.send_timed_batch(random_v_pulse)
        time.sleep(4)
        
        # Send all horizontal static patterns
        for i, pattern in enumerate(static_horizontal):
            print(f"Sending horizontal static pattern {i+1}")
            api.send_timed_batch(pattern)
            time.sleep(1.5)
        
        api.disconnect()

if __name__ == '__main__':
    main()