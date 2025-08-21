import time
import sys  
import os  

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands_with_motion
from core.serial_api import SerialAPI
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, LAYOUT_POSITIONS, VELOCITY)

sleep_during = 2
sleep_between = 3

# Get ALL commands (static, pulse, motion)
all_commands = create_all_commands_with_motion(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

static_horizontal = all_commands['static_horizontal']    # 12 commands
static_vertical = all_commands['static_vertical']        # 12 commands  
pulse_horizontal = all_commands['pulse_horizontal']      # 12 commands
pulse_vertical = all_commands['pulse_vertical']          # 12 commands
motion_horizontal = all_commands['motion_horizontal']    # 12 commands
motion_vertical = all_commands['motion_vertical']        # 12 commands

# Horizontal mixed order: [2,7,0,9,4,11,1,6,3,8,5,10]
# Vertical mixed order: [5,1,8,3,10,0,7,2,11,4,6,9]

#STATIC
static_horizontal_mixed = [static_horizontal[2], static_horizontal[7], static_horizontal[0], static_horizontal[9], static_horizontal[4], static_horizontal[11], static_horizontal[1], static_horizontal[6], static_horizontal[3], static_horizontal[8], static_horizontal[5], static_horizontal[10]]
static_vertical_mixed = [static_vertical[5], static_vertical[1], static_vertical[8], static_vertical[3], static_vertical[10], static_vertical[0], static_vertical[7], static_vertical[2], static_vertical[11], static_vertical[4], static_vertical[6], static_vertical[9]]

# PULSE
pulse_horizontal_mixed = [pulse_horizontal[2], pulse_horizontal[7], pulse_horizontal[0], pulse_horizontal[9], pulse_horizontal[4], pulse_horizontal[11], pulse_horizontal[1], pulse_horizontal[6], pulse_horizontal[3], pulse_horizontal[8], pulse_horizontal[5], pulse_horizontal[10]]
pulse_vertical_mixed = [pulse_vertical[5], pulse_vertical[1], pulse_vertical[8], pulse_vertical[3], pulse_vertical[10], pulse_vertical[0], pulse_vertical[7], pulse_vertical[2], pulse_vertical[11], pulse_vertical[4], pulse_vertical[6], pulse_vertical[9]]

# MOTION
#motion_horizontal_mixed = [motion_horizontal[2], motion_horizontal[7], motion_horizontal[0], motion_horizontal[9], motion_horizontal[4], motion_horizontal[11], motion_horizontal[1], motion_horizontal[6], motion_horizontal[3], motion_horizontal[8], motion_horizontal[5], motion_horizontal[10]]
#motion_vertical_mixed = [motion_vertical[5], motion_vertical[1], motion_vertical[8], motion_vertical[3], motion_vertical[10], motion_vertical[0], motion_vertical[7], motion_vertical[2], motion_vertical[11], motion_vertical[4], motion_vertical[6], motion_vertical[9]]

motion_horizontal_mixed = [motion_horizontal[0], motion_horizontal[1], motion_horizontal[2]]
motion_vertical_mixed = [motion_vertical[0], motion_vertical[1], motion_vertical[2]]

if __name__ == "__main__":
    
    api = SerialAPI()
    ports = api.get_serial_ports()
    
    if ports and api.connect(ports[2]):
        time.sleep(1)

        print("=== STATIC HORIZONTAL PATTERNS ===")
        for idx, hor in enumerate(static_horizontal_mixed, 1):
            print(f"Static Horizontal {idx} of {len(static_horizontal_mixed)}")
            api.send_timed_batch(hor)
            time.sleep(sleep_during)

        time.sleep(sleep_between)

        print("=== PULSE HORIZONTAL PATTERNS ===")
        for idx, hor in enumerate(pulse_horizontal_mixed, 1):
            print(f"Pulse Horizontal {idx} of {len(pulse_horizontal_mixed)}")
            api.send_timed_batch(hor)
            time.sleep(sleep_during)

        time.sleep(sleep_between)

        print("=== MOTION HORIZONTAL PATTERNS ===")
        for idx, hor in enumerate(motion_horizontal_mixed, 1):
            print(f"Motion Horizontal {idx} of {len(motion_horizontal_mixed)}")
            api.send_timed_batch(hor)
            time.sleep(sleep_during)

        time.sleep(sleep_between)

        print("=== STATIC VERTICAL PATTERNS ===")
        for idx, ver in enumerate(static_vertical_mixed, 1):
            print(f"Static Vertical {idx} of {len(static_vertical_mixed)}")
            api.send_timed_batch(ver)
            time.sleep(sleep_during)

        time.sleep(sleep_between)

        print("=== PULSE VERTICAL PATTERNS ===")
        for idx, ver in enumerate(pulse_vertical_mixed, 1):
            print(f"Pulse Vertical {idx} of {len(pulse_vertical_mixed)}")
            api.send_timed_batch(ver)
            time.sleep(sleep_during)

        time.sleep(sleep_between)

        print("=== MOTION VERTICAL PATTERNS ===")
        for idx, ver in enumerate(motion_vertical_mixed, 1):
            print(f"Motion Vertical {idx} of {len(motion_vertical_mixed)}")
            api.send_timed_batch(ver)
            time.sleep(sleep_during)

        print("=== ALL PATTERNS COMPLETED ===")
                
    api.disconnect()