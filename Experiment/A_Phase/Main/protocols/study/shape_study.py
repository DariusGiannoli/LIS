import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.shape import cross_pattern, h_line_pattern, v_line_pattern, square_pattern, circle_pattern, l_shape_pattern
from core.hardware.serial.serial_api import SERIAL_API
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

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
shape_names = list(static_shapes.keys())  # All shapes
#shape_names = ['square']  # Only test square
print(f"Available shapes: {shape_names}")

def create_combined_random_order():
    """Generate a random permutation of all shape-pattern combinations"""
    # pattern_types = ['static', 'pulse', 'motion']  # All pattern types
    pattern_types = ['motion']  # Only motion patterns
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

def send_timed_batch(api, pattern):
    """Adapter function to execute pattern using SERIAL_API"""
    if 'steps' not in pattern:
        print("Warning: Pattern has no steps")
        return
    
    for step in pattern['steps']:
        commands = step.get('commands', [])
        delay_after_ms = step.get('delay_after_ms', 0)
        
        if commands:
            # Send all commands in this step
            api.send_command_list(commands)
        
        # Wait for the specified delay
        if delay_after_ms > 0:
            time.sleep(delay_after_ms / 1000.0)

def emergency_stop_all(api):
    """Send stop commands to ALL 16 actuators - optimized version"""
    all_stop_commands = [
        {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
        for addr in range(16)
    ]
    
    print("Emergency stop - Stopping all actuators...")
    try:
        api.send_command_list(all_stop_commands)
        time.sleep(0.1)
        print("Emergency stop completed")
    except Exception as e:
        print(f"Error during emergency stop: {e}")


def wait_for_input(pattern_name, pattern_num, total_patterns):
    """Wait for user input to repeat or continue"""
    while True:
        print(f"\n{pattern_name} {pattern_num}/{total_patterns} completed.")
        print("Press 'r' to repeat, 'n' for next pattern, 'q' to quit, 's' to emergency stop: ", end='', flush=True)
        
        try:
            choice = input().lower().strip()
            if choice == 'r':
                return 'repeat'
            elif choice == 'n':
                return 'next'
            elif choice == 'q':
                return 'quit'
            elif choice == 's':
                return 'emergency_stop'
            else:
                print("Invalid input. Please press 'r', 'n', 'q', or 's'.")
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
        
        try:
            send_timed_batch(api, pattern)
            time.sleep(sleep_during)
            
            action = wait_for_input(pattern_info['name'], current_num, len(combined_patterns))
            
            if action == 'repeat':
                # Stay at same index to repeat
                continue
            elif action == 'next':
                # Move to next pattern
                idx += 1
            elif action == 'quit':
                emergency_stop_all(api)
                return 'quit'
            elif action == 'emergency_stop':
                print("Emergency stop activated!")
                emergency_stop_all(api)
                time.sleep(0.5)
                continue  # Stay on current pattern
                
        except Exception as e:
            print(f"Error during pattern execution: {e}")
            emergency_stop_all(api)
            
            # Ask user what to do
            while True:
                choice = input("Error occurred. Continue (c), repeat (r), or quit (q)? ").lower().strip()
                if choice == 'c':
                    idx += 1
                    break
                elif choice == 'r':
                    break
                elif choice == 'q':
                    return 'quit'
    
    return 'completed'

if __name__ == "__main__":
    
    api = SERIAL_API()
    devices = api.get_serial_devices()
    
    print("Available serial devices:")
    for i, device in enumerate(devices):
        print(f"{i}: {device}")
    
    if devices and api.connect_serial_device(devices[2]):  # Use device index 2, change if needed
        time.sleep(1)
        
        print("=== INTERACTIVE SHAPE STUDY ===")
        print("Controls: 'r' = repeat pattern, 'n' = next pattern, 'q' = quit, 's' = emergency stop")
        print(f"Testing {len(shape_names)} shapes: {', '.join(shape_names)}")
        print(f"Pattern types: Motion only (static and pulse are commented)")
        
        # Run all patterns in combined random order
        result = run_combined_patterns(api, combined_patterns)

        print("\n=== SHAPE STUDY COMPLETED OR TERMINATED ===")
        print("Summary:")
        print(f"- Total shapes tested: {len(shape_names)}")
        print(f"- Pattern types: Motion only")
        print(f"- Total combinations: {len(combined_patterns)}")
        print(f"- Randomized order: {[p['name'] for p in combined_patterns]}")
                
    api.disconnect_serial_device()