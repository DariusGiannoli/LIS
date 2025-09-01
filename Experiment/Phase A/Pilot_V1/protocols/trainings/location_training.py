import time
import sys  
import os  

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import  create_all_commands_with_motion
from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

sleep_during = 2.5
sleep_between = 5

# Get ALL commands including motion patterns
all_commands = create_all_commands_with_motion(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

static_horizontal = all_commands['static_horizontal']    # 12 commands
static_vertical = all_commands['static_vertical']        # 12 commands  
pulse_horizontal = all_commands['pulse_horizontal']      # 12 commands
pulse_vertical = all_commands['pulse_vertical']          # 12 commands
motion_horizontal = all_commands['motion_horizontal']    # 12 commands
motion_vertical = all_commands['motion_vertical']        # 12 commands 

#Horizontal 
static_horizontal = [static_horizontal[2], static_horizontal[7]]
pulse_horizontal = [pulse_horizontal[2], pulse_horizontal[7]]
motion_horizontal = [motion_horizontal[2], motion_horizontal[7]]

#Vertical
static_vertical = [static_vertical[5], static_vertical[1]]
pulse_vertical = [pulse_vertical[5], pulse_vertical[1]]
motion_vertical = [motion_vertical[5], motion_vertical[1]]

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
            (static_horizontal, "Static Horizontal"),
            (pulse_horizontal, "Pulse Horizontal"), 
            (motion_horizontal, "Motion Horizontal"),
            (static_vertical, "Static Vertical"),
            (pulse_vertical, "Pulse Vertical"),
            (motion_vertical, "Motion Vertical")
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