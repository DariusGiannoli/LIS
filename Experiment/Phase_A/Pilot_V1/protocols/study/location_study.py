import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands_with_motion
from core.hardware.serial_api import SerialAPI
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

sleep_during = 1.5
sleep_between = 2

# Get ALL commands (static, pulse, motion)
all_commands = create_all_commands_with_motion(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

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

def create_combined_random_patterns(pattern_dict, pattern_type_name, random_order):
    """Create a combined list mixing all pattern types for a given orientation"""
    pattern_types = ['static', 'pulse', 'motion']
    all_combinations = []
    
    # Create all combinations of pattern index + pattern type
    for i, pattern_index in enumerate(random_order):
        for pattern_type in pattern_types:
            pattern_key = f"{pattern_type}_{pattern_type_name}"
            pattern_data = pattern_dict[pattern_key][pattern_index]
            all_combinations.append({
                'pattern': pattern_data,
                'type': pattern_type,
                'original_index': pattern_index,
                'randomized_position': i,
                'name': f"{pattern_type}_{pattern_type_name}_{pattern_index+1}"
            })
    
    # Shuffle the complete list to mix pattern types
    random.shuffle(all_combinations)
    return all_combinations

horizontal_random_order = create_random_indices(12)
vertical_random_order = create_random_indices(12)

print(f"Horizontal random order: {horizontal_random_order}")
print(f"Vertical random order: {vertical_random_order}")

# Create combined randomized patterns
horizontal_combined = create_combined_random_patterns(all_commands, 'horizontal', horizontal_random_order)
vertical_combined = create_combined_random_patterns(all_commands, 'vertical', vertical_random_order)

print(f"Horizontal combined order: {[p['name'] for p in horizontal_combined[:6]]}...") # Show first 6
print(f"Vertical combined order: {[p['name'] for p in vertical_combined[:6]]}...")  # Show first 6

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
        return 'quit' if choice == 'q' else 'continue'
    except KeyboardInterrupt:
        print("\nExiting...")
        return 'quit'


def run_combined_patterns(api, combined_patterns, section_name):
    """Run combined patterns with interactive controls"""
    print(f"\n=== {section_name.upper()} PATTERNS ===")

    idx = 0
    while idx < len(combined_patterns):
        pattern_info = combined_patterns[idx]
        pattern = pattern_info['pattern']
        current_num = idx + 1

        print(f"\nPlaying {pattern_info['name']} ({current_num} of {len(combined_patterns)})")
        api.send_timed_batch(pattern)
        time.sleep(sleep_during)

        action = wait_for_input(pattern_info['name'], current_num, len(combined_patterns))

        if action == 'next':
            # Move to next pattern
            idx += 1
        elif action == 'quit':
            return 'quit'
        elif action == 'repeat':
            # Stay at same index to repeat
            continue
    return 'completed'


if __name__ == "__main__":
    
    api = SerialAPI()
    ports = api.get_serial_ports()
    
    if ports and api.connect(ports[2]):
        time.sleep(1)
        
        print("=== INTERACTIVE LOCATION STUDY ===")
        print("Controls: 'r' = repeat pattern, 'n' = next pattern, 'q' = quit")
        print(f"Total patterns: {len(horizontal_combined)} horizontal + {len(vertical_combined)} vertical")
        
        # Define sections with combined randomized patterns
        sections = [
            (horizontal_combined, "Combined Horizontal (Static/Pulse/Motion)"),
            (vertical_combined, "Combined Vertical (Static/Pulse/Motion)")
        ]
        
        # Run each section
        for i, (patterns, section_name) in enumerate(sections):
            result = run_combined_patterns(api, patterns, section_name)
            
            if result == 'quit':
                break
                
            # Check if user wants to continue to next section (except for last section)
            if i < len(sections) - 1:
                section_result = wait_for_section_continue(section_name)
                if section_result == 'quit':
                    break

        print("\n=== STUDY COMPLETED OR TERMINATED ===")
                
    api.disconnect()