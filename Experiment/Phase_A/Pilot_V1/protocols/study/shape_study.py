import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.shape import cross_pattern, h_line_pattern, v_line_pattern, square_pattern, circle_pattern, l_shape_pattern
from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

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

# Get shape names and create combined random order
shape_names = list(static_shapes.keys())
print(f"Available shapes: {shape_names}")

def create_combined_random_order():
    """Generate a random permutation of all shape-pattern combinations"""
    pattern_types = ['static', 'pulse', 'motion']
    all_combinations = []
    
    # Create all combinations of shape + pattern type
    for shape in shape_names:
        for pattern_type in pattern_types:
            all_combinations.append((shape, pattern_type))
    
    # Shuffle the complete list
    random.shuffle(all_combinations)
    return all_combinations

# Create single randomized order for all combinations
combined_random_order = create_combined_random_order()
print(f"Combined random order: {[f'{shape}_{pattern}' for shape, pattern in combined_random_order]}")

# Create combined pattern list with metadata
combined_patterns = []
for shape, pattern_type in combined_random_order:
    if pattern_type == 'static':
        pattern_data = static_shapes[shape]
    elif pattern_type == 'pulse':
        pattern_data = pulse_shapes[shape]
    else:  # motion
        pattern_data = motion_shapes[shape]
    
    combined_patterns.append({
        'pattern': pattern_data,
        'shape': shape,
        'type': pattern_type,
        'name': f"{shape}_{pattern_type}"
    })

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


def run_combined_patterns(api, combined_patterns):
    """Run all patterns in combined random order with interactive controls"""
    print(f"\n=== COMBINED RANDOMIZED PATTERNS ===")
    
    idx = 0
    while idx < len(combined_patterns):
        pattern_info = combined_patterns[idx]
        pattern = pattern_info['pattern']
        current_num = idx + 1
        
        print(f"\nPlaying {pattern_info['name']} ({current_num} of {len(combined_patterns)})")
        api.send_timed_batch(pattern)
        time.sleep(sleep_during)
        
        action = wait_for_input(pattern_info['name'], current_num, len(combined_patterns))
        
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
        print(f"Testing {len(shape_names)} shapes in random order: {', '.join(shape_names)}")
        
        # Run all patterns in combined random order
        result = run_combined_patterns(api, combined_patterns)

        print("\n=== SHAPE STUDY COMPLETED OR TERMINATED ===")
        print("Summary:")
        print(f"- Total shapes tested: {len(shape_names)}")
        print(f"- Pattern types: Static, Pulse, Motion")
        print(f"- Total combinations: {len(combined_patterns)}")
        print(f"- Randomized order: {[p['name'] for p in combined_patterns]}")
                
    api.disconnect()