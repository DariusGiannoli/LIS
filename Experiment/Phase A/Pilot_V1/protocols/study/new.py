import time
import sys  
import os  

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands_with_motion
from core.serial_api import SerialAPI
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, LAYOUT_POSITIONS, VELOCITY)

sleep_during = 1.5
sleep_between = 2

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
motion_horizontal_mixed = [motion_horizontal[2], motion_horizontal[7], motion_horizontal[0], motion_horizontal[9], motion_horizontal[4], motion_horizontal[11], motion_horizontal[1], motion_horizontal[6], motion_horizontal[3], motion_horizontal[8], motion_horizontal[5], motion_horizontal[10]]
motion_vertical_mixed = [motion_vertical[5], motion_vertical[1], motion_vertical[8], motion_vertical[3], motion_vertical[10], motion_vertical[0], motion_vertical[7], motion_vertical[2], motion_vertical[11], motion_vertical[4], motion_vertical[6], motion_vertical[9]]


def wait_for_input(pattern_name, pattern_num, total_patterns):
    """Wait for user input to repeat or continue"""
    while True:
        print(f"\n{pattern_name} {pattern_num}/{total_patterns} completed.")
        print("Press 'r' to repeat, 'n' for next pattern, or 'q' to quit: ", end='', flush=True)
        
        try:
            choice = input().lower().strip()
            if choice == 'r':
                return 'repeat'
            elif choice == 'n':
                return 'next'
            elif choice == 'q':
                return 'quit'
            else:
                print("Invalid input. Please press 'r', 'n', or 'q'.")
        except KeyboardInterrupt:
            print("\nExiting...")
            return 'quit'


def wait_for_section_continue(section_name):
    """Wait for user input between sections"""
    print(f"\n=== {section_name} SECTION COMPLETED ===")
    print("Press any key to continue to next section, or 'q' to quit: ", end='', flush=True)
    
    try:
        choice = input().lower().strip()
        if choice == 'q':
            return 'quit'
        return 'continue'
    except KeyboardInterrupt:
        print("\nExiting...")
        return 'quit'


def run_pattern_section(api, patterns, section_name):
    """Run a section of patterns with interactive controls"""
    print(f"\n=== {section_name.upper()} PATTERNS ===")
    
    idx = 0
    while idx < len(patterns):
        pattern = patterns[idx]
        current_num = idx + 1
        
        print(f"\nPlaying {section_name} {current_num} of {len(patterns)}")
        api.send_timed_batch(pattern)
        time.sleep(sleep_during)
        
        action = wait_for_input(section_name, current_num, len(patterns))
        
        if action == 'repeat':
            # Stay at same index to repeat
            continue
        elif action == 'next':
            # Move to next pattern
            idx += 1
        elif action == 'quit':
            return 'quit'
    
    return 'completed'


if __name__ == "__main__":
    
    api = SerialAPI()
    ports = api.get_serial_ports()
    
    if ports and api.connect(ports[2]):
        time.sleep(1)
        
        print("=== INTERACTIVE LOCATION STUDY ===")
        print("Controls: 'r' = repeat pattern, 'n' = next pattern, 'q' = quit")
        
        # Define all sections
        sections = [
            (static_horizontal_mixed, "Static Horizontal"),
            (pulse_horizontal_mixed, "Pulse Horizontal"), 
            (motion_horizontal_mixed, "Motion Horizontal"),
            (static_vertical_mixed, "Static Vertical"),
            (pulse_vertical_mixed, "Pulse Vertical"),
            (motion_vertical_mixed, "Motion Vertical")
        ]
        
        # Run each section
        for i, (patterns, section_name) in enumerate(sections):
            result = run_pattern_section(api, patterns, section_name)
            
            if result == 'quit':
                break
                
            # Check if user wants to continue to next section (except for last section)
            if i < len(sections) - 1:
                section_result = wait_for_section_continue(section_name)
                if section_result == 'quit':
                    break

        print("\n=== STUDY COMPLETED OR TERMINATED ===")
                
    api.disconnect()