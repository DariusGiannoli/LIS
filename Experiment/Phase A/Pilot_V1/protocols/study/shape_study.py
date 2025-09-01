import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.shape import cross_pattern, h_line_pattern, v_line_pattern, square_pattern, circle_pattern, l_shape_pattern
from core.serial_api import SerialAPI
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

sleep_during = 1.5
sleep_between = 2

# Get all shape patterns (static, pulse, motion for each shape)
def get_all_shape_patterns():
    """Generate all shape patterns organized by type"""
    
    # Define all shape functions
    shape_functions = {
        'cross': cross_pattern,
        'h_line': h_line_pattern,
        'v_line': v_line_pattern,
        'square': square_pattern,
        'circle': circle_pattern,
        'l_shape': l_shape_pattern
    }
    
    # Generate patterns for each shape
    static_patterns = {}
    pulse_patterns = {}
    motion_patterns = {}
    
    for shape_name, shape_func in shape_functions.items():
        static, pulse, motion = shape_func()
        static_patterns[shape_name] = static
        pulse_patterns[shape_name] = pulse
        motion_patterns[shape_name] = motion
    
    return static_patterns, pulse_patterns, motion_patterns

# Generate all patterns
static_shapes, pulse_shapes, motion_shapes = get_all_shape_patterns()

# Get shape names and create random orders
shape_names = list(static_shapes.keys())
print(f"Available shapes: {shape_names}")

def create_random_shape_order():
    """Generate a random permutation of shape names"""
    shapes = shape_names.copy()
    random.shuffle(shapes)
    return shapes

# Create random orders for each pattern type
static_random_order = create_random_shape_order()
pulse_random_order = create_random_shape_order()
motion_random_order = create_random_shape_order()

print(f"Static random order: {static_random_order}")
print(f"Pulse random order: {pulse_random_order}")
print(f"Motion random order: {motion_random_order}")

# Create randomized pattern lists
static_shapes_mixed = [static_shapes[shape] for shape in static_random_order]
pulse_shapes_mixed = [pulse_shapes[shape] for shape in pulse_random_order]
motion_shapes_mixed = [motion_shapes[shape] for shape in motion_random_order]

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


def run_pattern_section(api, patterns, section_name, shape_order):
    """Run a section of patterns with interactive controls"""
    print(f"\n=== {section_name.upper()} PATTERNS ===")
    
    idx = 0
    while idx < len(patterns):
        pattern = patterns[idx]
        current_num = idx + 1
        shape_name = shape_order[idx]
        
        print(f"\nPlaying {section_name} {shape_name} ({current_num} of {len(patterns)})")
        api.send_timed_batch(pattern)
        time.sleep(sleep_during)
        
        action = wait_for_input(f"{section_name} {shape_name}", current_num, len(patterns))
        
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
        
        print("=== INTERACTIVE SHAPE STUDY ===")
        print("Controls: 'r' = repeat pattern, 'n' = next pattern, 'q' = quit")
        print(f"Testing {len(shape_names)} shapes: {', '.join(shape_names)}")
        
        # Define all sections with their corresponding random orders
        sections = [
            (static_shapes_mixed, "Static Shapes", static_random_order),
            (pulse_shapes_mixed, "Pulse Shapes", pulse_random_order), 
            (motion_shapes_mixed, "Motion Shapes", motion_random_order)
        ]
        
        # Run each section
        for i, (patterns, section_name, shape_order) in enumerate(sections):
            result = run_pattern_section(api, patterns, section_name, shape_order)
            
            if result == 'quit':
                break
                
            # Check if user wants to continue to next section (except for last section)
            if i < len(sections) - 1:
                section_result = wait_for_section_continue(section_name)
                if section_result == 'quit':
                    break

        print("\n=== SHAPE STUDY COMPLETED OR TERMINATED ===")
        print("Summary:")
        print(f"- Total shapes tested: {len(shape_names)}")
        print(f"- Pattern types: Static, Pulse, Motion")
        print(f"- Total possible combinations: {len(shape_names) * 3}")
                
    api.disconnect()