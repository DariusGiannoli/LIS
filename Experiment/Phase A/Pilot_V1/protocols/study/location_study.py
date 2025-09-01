import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands_with_motion
from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, LAYOUT_POSITIONS, VELOCITY)

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

def create_random_indices(length=12):
    """Generate a random permutation of indices from 0 to length-1"""
    indices = list(range(length))
    random.shuffle(indices)
    return indices

horizontal_random_order = create_random_indices(12)
vertical_random_order = create_random_indices(12)

print(f"Horizontal random order: {horizontal_random_order}")
print(f"Vertical random order: {vertical_random_order}")

# STATIC
static_horizontal_mixed = [static_horizontal[i] for i in horizontal_random_order]
static_vertical_mixed = [static_vertical[i] for i in vertical_random_order]

# PULSE
pulse_horizontal_mixed = [pulse_horizontal[i] for i in horizontal_random_order]
pulse_vertical_mixed = [pulse_vertical[i] for i in vertical_random_order]

# MOTION
motion_horizontal_mixed = [motion_horizontal[i] for i in horizontal_random_order]
motion_vertical_mixed = [motion_vertical[i] for i in vertical_random_order]

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