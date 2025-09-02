import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.direction import get_all_direction_patterns, DIRECTION_CONFIGS
from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

sleep_during = 1.5
sleep_between = 2

# Get all direction patterns (static, pulse, motion for each direction)
def get_all_direction_patterns_organized():
    """Generate all direction patterns organized by type"""
    return get_all_direction_patterns()

# Generate all patterns
all_patterns = get_all_direction_patterns_organized()
static_directions = all_patterns['static']
pulse_directions = all_patterns['pulse']
motion_directions = all_patterns['motion']

# Get direction names (angles) and create random orders
direction_names = list(static_directions.keys())
print(f"Available directions: {direction_names}")

def create_random_direction_order():
    """Generate a random permutation of direction names"""
    directions = direction_names.copy()
    random.shuffle(directions)
    return directions

# Create random orders for each pattern type
static_random_order = create_random_direction_order()
pulse_random_order = create_random_direction_order()
motion_random_order = create_random_direction_order()

print(f"Static random order: {static_random_order}")
print(f"Pulse random order: {pulse_random_order}")
print(f"Motion random order: {motion_random_order}")

# Create randomized pattern lists
static_directions_mixed = [static_directions[direction] for direction in static_random_order]
pulse_directions_mixed = [pulse_directions[direction] for direction in pulse_random_order]
motion_directions_mixed = [motion_directions[direction] for direction in motion_random_order]

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


def run_pattern_section(api, patterns, section_name, direction_order):
    """Run a section of patterns with interactive controls"""
    print(f"\n=== {section_name.upper()} PATTERNS ===")

    idx = 0
    while idx < len(patterns):
        pattern = patterns[idx]
        current_num = idx + 1
        direction_name = direction_order[idx]

        # Get the description from DIRECTION_CONFIGS
        angle = int(direction_name.replace('_deg', ''))
        description = DIRECTION_CONFIGS[angle]['description']

        print(f"\nPlaying {section_name} {description} ({current_num} of {len(patterns)})")
        api.send_timed_batch(pattern)
        time.sleep(sleep_during)

        action = wait_for_input(f"{section_name} {description}", current_num, len(patterns))

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
        
        print("=== INTERACTIVE DIRECTION STUDY ===")
        print("Controls: 'r' = repeat pattern, 'n' = next pattern, 'q' = quit")
        print(f"Testing {len(direction_names)} directions: {', '.join([DIRECTION_CONFIGS[int(d.replace('_deg', ''))]['description'] for d in direction_names])}")
        
        # Define all sections with their corresponding random orders
        sections = [
            (static_directions_mixed, "Static Directions", static_random_order),
            (pulse_directions_mixed, "Pulse Directions", pulse_random_order), 
            (motion_directions_mixed, "Motion Directions", motion_random_order)
        ]
        
        # Run each section
        for i, (patterns, section_name, direction_order) in enumerate(sections):
            result = run_pattern_section(api, patterns, section_name, direction_order)
            
            if result == 'quit':
                break
                
            # Check if user wants to continue to next section (except for last section)
            if i < len(sections) - 1:
                section_result = wait_for_section_continue(section_name)
                if section_result == 'quit':
                    break
                
    api.disconnect()