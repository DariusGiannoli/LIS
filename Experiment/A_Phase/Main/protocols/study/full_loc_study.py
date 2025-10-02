import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands_with_motion
from core.hardware.serial.serial_api import SERIAL_API
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, MOVEMENT_SPEED)

# Optimized delays for smoother experience
sleep_during = 0.5  # Reduced from 1.5
sleep_between = 1.0  # Reduced from 2

# Get ALL commands (static, pulse, motion)
all_commands = create_all_commands_with_motion(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

# All pattern types
# static_horizontal = all_commands['static_horizontal']    # 12 commands
# static_vertical = all_commands['static_vertical']        # 12 commands  
# pulse_horizontal = all_commands['pulse_horizontal']      # 12 commands
# pulse_vertical = all_commands['pulse_vertical']          # 12 commands
motion_horizontal = all_commands['motion_horizontal']    # 12 commands
# motion_vertical = all_commands['motion_vertical']        # 12 commands

def create_random_indices(length=12):
    """Generate a random permutation of indices from 0 to length-1"""
    indices = list(range(length))
    random.shuffle(indices)
    return indices

def create_combined_random_patterns(pattern_dict, pattern_type_name, random_order):
    """Create a combined list mixing all pattern types for a given orientation"""
    #pattern_types = ['static', 'pulse', 'motion']
    pattern_types = ['motion']
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
    """Run combined patterns with optimized execution for all pattern types"""
    print(f"\n=== {section_name.upper()} PATTERNS ===")
    print(f"Total patterns: {len(combined_patterns)} (Static: {len([p for p in combined_patterns if p['type'] == 'static'])}, "
          f"Pulse: {len([p for p in combined_patterns if p['type'] == 'pulse'])}, "
          f"Motion: {len([p for p in combined_patterns if p['type'] == 'motion'])})")

    idx = 0
    while idx < len(combined_patterns):
        pattern_info = combined_patterns[idx]
        pattern = pattern_info['pattern']
        pattern_type = pattern_info['type']
        current_num = idx + 1

        print(f"\nPlaying {pattern_info['name']} ({current_num} of {len(combined_patterns)})")
        print(f"Type: {pattern_type.upper()}, Steps: {len(pattern['steps'])}")
        
        try:
            # Execute pattern with optimized safety measures
            safe_pattern_execution(api, pattern, pattern_type)
            time.sleep(sleep_during)

            action = wait_for_input(pattern_info['name'], current_num, len(combined_patterns))

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
            
            print("=== INTERACTIVE LOCATION STUDY - OPTIMIZED ===")
            print("Controls: 'r' = repeat, 'n' = next, 'q' = quit, 's' = emergency stop")
            print(f"Total patterns: {len(horizontal_combined)} horizontal + {len(vertical_combined)} vertical")
            print("Pattern types: Static (simultaneous), Pulse (rhythmic), Motion (smooth movement)")
            print("Optimized for smooth and responsive haptic feedback")
            
            # Define sections with combined randomized patterns
            # sections = [
            #     (horizontal_combined, "Combined Horizontal (Static/Pulse/Motion)"),
            #     (vertical_combined, "Combined Vertical (Static/Pulse/Motion)")
            # ]
            sections = [(horizontal_combined, "Combined Horizontal (Static/Pulse/Motion)")]
            
            # Run each section
            for i, (patterns, section_name) in enumerate(sections):
                result = run_combined_patterns(api, patterns, section_name)
                
                if result == 'quit':
                    break
                    
                # Check if user wants to continue to next section
                if i < len(sections) - 1:
                    section_result = wait_for_section_continue(section_name)
                    if section_result == 'quit':
                        break

            print("\n=== LOCATION STUDY COMPLETED OR TERMINATED ===")
            print("Thank you for participating in the haptic location study!")
            
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