import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.direction import get_all_direction_patterns, DIRECTION_CONFIGS
from core.hardware.serial.serial_api import SERIAL_API
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

# Optimized delays for smoother experience
sleep_during = 0.5  # Reduced from 1.5
sleep_between = 1.0  # Reduced from 2

# Get all direction patterns (static, pulse, motion for each direction)
all_patterns = get_all_direction_patterns()
static_directions = all_patterns['static']
pulse_directions = all_patterns['pulse'] 
motion_directions = all_patterns['motion']

# Only test motion patterns for now
motion_directions_only = all_patterns['motion']

print(f"Available directions: {list(motion_directions_only.keys())}")

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

def execute_pattern_optimized(api, pattern, pattern_type):
    """Execute pattern with optimized timing based on pattern type"""
    activated_actuators = set()
    
    try:
        for step_num, step in enumerate(pattern['steps']):
            # Send commands for this step
            success = api.send_command_list(step['commands'])
            if not success:
                print(f"Warning: Step {step_num + 1} may have failed")
            
            # Track actuators that were started
            for cmd in step['commands']:
                if cmd.get('start_or_stop') == 1:
                    activated_actuators.add(cmd['addr'])
            
            # Wait if there's a delay after this step
            if step['delay_after_ms'] > 0:
                time.sleep(step['delay_after_ms'] / 1000.0)
        
        # Single optimized final stop for activated actuators only
        if activated_actuators:
            final_stop_commands = [
                {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
                for addr in activated_actuators
            ]
            api.send_command_list(final_stop_commands)
            
            # Brief pause for motion patterns to ensure clean stop
            if pattern_type == 'motion':
                time.sleep(0.05)
            
    except Exception as e:
        print(f"Error during pattern execution: {e}")
        emergency_stop_all(api)
        raise

def safe_pattern_execution(api, pattern, pattern_type):
    """Execute pattern with optimized safety measures for all pattern types"""
    try:
        # Pre-execution clean stop (minimal)
        emergency_stop_all(api)
        
        # Different pre-delays based on pattern type
        if pattern_type == 'motion':
            time.sleep(0.1)  # Minimal delay for motion
        else:
            time.sleep(0.05)  # Even shorter for static/pulse
        
        # Execute the pattern with optimized timing
        execute_pattern_optimized(api, pattern, pattern_type)
        
        # Brief post-execution pause
        time.sleep(0.05)
        
    except Exception as e:
        print(f"Critical error during pattern execution: {e}")
        emergency_stop_all(api)
        raise

def create_random_direction_order():
    """Generate a random permutation of direction names"""
    directions = list(motion_directions_only.keys())
    random.shuffle(directions)
    return directions

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

def run_direction_patterns(api, patterns, direction_order):
    """Run direction patterns with optimized execution"""
    print(f"\n=== DIRECTION MOTION PATTERNS ===")
    print(f"Total directions: {len(patterns)}")
    print("Patterns start from center and radiate outward")

    idx = 0
    while idx < len(direction_order):
        direction_name = direction_order[idx]
        pattern = patterns[direction_name]
        current_num = idx + 1
        
        # Get the description from DIRECTION_CONFIGS
        description = DIRECTION_CONFIGS[direction_name]['description']

        print(f"\nPlaying {description} ({current_num} of {len(direction_order)})")
        print(f"Steps: {len(pattern['steps'])}")
        
        try:
            # Execute pattern with optimized safety measures
            safe_pattern_execution(api, pattern, 'motion')
            time.sleep(sleep_during)

            action = wait_for_input(description, current_num, len(direction_order))

            if action == 'next':
                idx += 1
            elif action == 'quit':
                emergency_stop_all(api)
                return 'quit'
            elif action == 'emergency_stop':
                print("Emergency stop activated!")
                emergency_stop_all(api)
                time.sleep(0.5)
                continue  # Stay on current pattern
            elif action == 'repeat':
                continue
                
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
    api = None
    try:
        # Create random order for directions
        direction_order = create_random_direction_order()
        print(f"Random direction order: {[DIRECTION_CONFIGS[d]['description'] for d in direction_order]}")
        
        api = SERIAL_API()
        ports = api.get_serial_devices()
        
        if not ports:
            print("No serial devices found!")
            exit(1)
            
        if len(ports) <= 2:
            print(f"Need at least 3 ports, only found {len(ports)}")
            exit(1)
        
        if api.connect_serial_device(ports[2]):
            time.sleep(0.5)  # Reduced connection delay
            
            # Initial clean stop
            emergency_stop_all(api)
            
            print("=== INTERACTIVE DIRECTION STUDY - OPTIMIZED ===")
            print("Controls: 'r' = repeat, 'n' = next, 'q' = quit, 's' = emergency stop")
            print("Testing 8 directions: North, Northeast, East, Southeast, South, Southwest, West, Northwest")
            print("All patterns start from center and radiate outward")
            print("Pattern type: Motion only (smooth directional movement)")
            print("Optimized for smooth and responsive haptic feedback")
            
            # Run direction patterns
            result = run_direction_patterns(api, motion_directions_only, direction_order)
            
            if result == 'completed':
                print("\n=== DIRECTION STUDY COMPLETED ===")
                print("Study Summary:")
                print(f"All {len(direction_order)} directions completed")
                print("Randomized order eliminates order effects")
                print("Tests directional discrimination with center-radiating patterns")
            else:
                print("\n=== DIRECTION STUDY TERMINATED ===")
                
        else:
            print("Failed to connect to serial device!")
            
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    except Exception as e:
        print(f"Unexpected error: {e}")
    finally:
        # Ensure we always try to stop everything and disconnect
        if api:
            try:
                emergency_stop_all(api)
                time.sleep(0.2)
                api.disconnect_serial_device()
                print("Safely disconnected")
            except:
                print("Error during cleanup - device may still be connected")
        
    print("\nDirection study session ended.")