import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.size import get_all_size_patterns
from core.hardware.serial_api import SERIAL_API
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

sleep_during = 1.5
sleep_between = 2

def nuclear_stop_all(api):
    """Send stop commands to ALL 16 actuators multiple times"""
    all_stop_commands = [
        {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
        for addr in range(16)
    ]
    
    print("NUCLEAR STOP - Stopping all 16 actuators...")
    for i in range(4):  # 4 rounds of stops
        try:
            success = api.send_command_list(all_stop_commands)
            if not success:
                print(f"Warning: Nuclear stop round {i+1} may have failed")
            time.sleep(0.15)  # Delay between rounds
            print(f"Nuclear stop round {i+1}/4")
        except Exception as e:
            print(f"Error during nuclear stop round {i+1}: {e}")

def execute_pattern_steps(api, pattern):
    """Execute pattern steps with aggressive safety stops"""
    activated_actuators = set()  # Track which actuators were started
    
    try:
        for step_num, step in enumerate(pattern['steps']):
            print(f"Executing step {step_num + 1}/{len(pattern['steps'])}")
            
            # Send commands for this step
            success = api.send_command_list(step['commands'])
            if not success:
                print(f"Warning: Step {step_num + 1} commands may have failed")
            
            # Track actuators that were started
            for cmd in step['commands']:
                if cmd.get('start_or_stop') == 1:
                    activated_actuators.add(cmd['addr'])
            
            # Check if this step contains stop commands
            stop_commands = [cmd for cmd in step['commands'] if cmd.get('start_or_stop') == 0]
            
            # Wait if there's a delay after this step
            if step['delay_after_ms'] > 0:
                time.sleep(step['delay_after_ms'] / 1000.0)
                
            # Send multiple aggressive stops if we just sent stops
            if stop_commands:
                print(f"Sending safety stops for {len(stop_commands)} actuators...")
                for i in range(4):  # Send stop command 4 times
                    try:
                        api.send_command_list(stop_commands)
                        time.sleep(0.1)  # 100ms delay between each
                        print(f"Safety stop #{i+1}/4")
                    except Exception as e:
                        print(f"Error during safety stop #{i+1}: {e}")
        
        # Final safety stop for all activated actuators
        if activated_actuators:
            final_stop_commands = [
                {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
                for addr in activated_actuators
            ]
            
            print(f"Final safety stops for {len(activated_actuators)} activated actuators...")
            for i in range(3):
                try:
                    api.send_command_list(final_stop_commands)
                    time.sleep(0.1)
                except Exception as e:
                    print(f"Error during final safety stop #{i+1}: {e}")
                    
    except Exception as e:
        print(f"Error during pattern execution: {e}")
        # Emergency stop all if something goes wrong
        nuclear_stop_all(api)

def safe_pattern_execution(api, pattern):
    """Execute pattern with full safety measures"""
    try:
        # Pre-execution nuclear stop
        nuclear_stop_all(api)
        time.sleep(0.2)
        
        # Execute the pattern steps
        execute_pattern_steps(api, pattern)
        time.sleep(0.2)
        
        # Post-execution nuclear stop
        nuclear_stop_all(api)
        
    except Exception as e:
        print(f"Critical error during pattern execution: {e}")
        # Emergency nuclear stop
        nuclear_stop_all(api)
        raise

def create_randomized_pattern_list():
    """Create a completely randomized list of all size-shape-pattern combinations"""
    
    all_patterns = get_all_size_patterns()
    pattern_list = []
    
    # Create all possible combinations
    for shape_name, shape_patterns in all_patterns.items():
        for pattern_type in ['static', 'pulse', 'motion']:
            for size_name, pattern_commands in shape_patterns[pattern_type].items():
                
                # Create a descriptive name for this combination
                combination_name = f"{size_name}_{shape_name}_{pattern_type}"
                
                # Store the combination
                pattern_entry = {
                    'name': combination_name,
                    'shape': shape_name,
                    'size': size_name,
                    'pattern_type': pattern_type,
                    'commands': pattern_commands
                }
                
                pattern_list.append(pattern_entry)
    
    # Completely randomize the order
    random.shuffle(pattern_list)
    
    return pattern_list

def print_randomized_order(pattern_list):
    """Print the randomized order for reference"""
    print(f"\n=== RANDOMIZED PATTERN ORDER ({len(pattern_list)} total patterns) ===")
    
    for i, pattern in enumerate(pattern_list, 1):
        print(f"{i:2d}. {pattern['name']}")
    
    print(f"\nPattern breakdown:")
    
    # Count patterns by type
    static_count = sum(1 for p in pattern_list if p['pattern_type'] == 'static')
    pulse_count = sum(1 for p in pattern_list if p['pattern_type'] == 'pulse')
    motion_count = sum(1 for p in pattern_list if p['pattern_type'] == 'motion')
    
    print(f"  Static patterns: {static_count}")
    print(f"  Pulse patterns: {pulse_count}")
    print(f"  Motion patterns: {motion_count}")
    
    # Count patterns by shape
    shape_counts = {}
    for pattern in pattern_list:
        shape = pattern['shape']
        shape_counts[shape] = shape_counts.get(shape, 0) + 1
    
    print(f"\nPatterns per shape:")
    for shape, count in sorted(shape_counts.items()):
        print(f"  {shape}: {count}")

def wait_for_input(pattern_name, pattern_num, total_patterns):
    """Wait for user input to repeat or continue"""
    while True:
        print(f"\n{pattern_name} ({pattern_num}/{total_patterns}) completed.")
        print("Press 'r' to repeat, 'n' for next pattern, 'q' to quit, 's' for summary, 'e' for emergency stop: ", end='', flush=True)
        
        try:
            choice = input().lower().strip()
            if choice == 'r':
                return 'repeat'
            elif choice == 'n':
                return 'next'
            elif choice == 'q':
                return 'quit'
            elif choice == 's':
                return 'summary'
            elif choice == 'e':
                return 'emergency_stop'
            else:
                print("Invalid input. Please press 'r', 'n', 'q', 's', or 'e'.")
        except KeyboardInterrupt:
            print("\nExiting...")
            return 'quit'

def show_progress_summary(current_idx, pattern_list):
    """Show progress summary"""
    total = len(pattern_list)
    completed = current_idx
    remaining = total - completed
    
    print(f"\n=== PROGRESS SUMMARY ===")
    print(f"Completed: {completed}/{total} patterns")
    print(f"Remaining: {remaining} patterns")
    print(f"Progress: {(completed/total)*100:.1f}%")
    
    if remaining > 0:
        print(f"\nNext few patterns:")
        for i in range(current_idx, min(current_idx + 3, total)):
            pattern = pattern_list[i]
            print(f"  {i+1}. {pattern['name']}")

def run_randomized_size_study(api, pattern_list):
    """Run the completely randomized size study"""
    
    print(f"\n=== STARTING RANDOMIZED SIZE STUDY ===")
    print(f"Total patterns to test: {len(pattern_list)}")
    print("Controls: 'r' = repeat, 'n' = next, 'q' = quit, 's' = summary, 'e' = emergency stop")
    
    idx = 0
    while idx < len(pattern_list):
        pattern = pattern_list[idx]
        current_num = idx + 1
        total_patterns = len(pattern_list)
        
        print(f"\n{'='*60}")
        print(f"Pattern {current_num}/{total_patterns}: {pattern['name']}")
        print(f"Shape: {pattern['shape']} | Size: {pattern['size']} | Type: {pattern['pattern_type']}")
        print(f"{'='*60}")
        
        print(f"Playing {pattern['name']}...")
        
        try:
            # Execute pattern with full safety measures
            safe_pattern_execution(api, pattern['commands'])
            time.sleep(sleep_during)

            action = wait_for_input(pattern['name'], current_num, total_patterns)

            if action == 'repeat':
                # Stay at same index to repeat
                continue
            elif action == 'next':
                # Move to next pattern
                idx += 1
            elif action == 'summary':
                # Show progress summary but stay at same index
                show_progress_summary(idx, pattern_list)
                continue
            elif action == 'emergency_stop':
                print("Emergency stop activated!")
                nuclear_stop_all(api)
                time.sleep(1)
                # Don't advance, stay on current pattern
                continue
            elif action == 'quit':
                # Final nuclear stop before quitting
                nuclear_stop_all(api)
                return 'quit'
                
        except Exception as e:
            print(f"Error during pattern execution: {e}")
            nuclear_stop_all(api)
            
            # Ask user what to do
            while True:
                choice = input("Error occurred. Continue (c), repeat (r), or quit (q)? ").lower().strip()
                if choice == 'c':
                    idx += 1
                    break
                elif choice == 'r':
                    break
                elif choice == 'q':
                    nuclear_stop_all(api)
                    return 'quit'
    
    return 'completed'

def save_pattern_order(pattern_list, filename="size_study_order.txt"):
    """Save the randomized pattern order to a file for reference"""
    try:
        with open(filename, 'w') as f:
            f.write("Randomized Size Study Pattern Order\n")
            f.write("="*50 + "\n\n")
            
            for i, pattern in enumerate(pattern_list, 1):
                f.write(f"{i:2d}. {pattern['name']}\n")
                f.write(f"    Shape: {pattern['shape']}, Size: {pattern['size']}, Type: {pattern['pattern_type']}\n\n")
        
        print(f"Pattern order saved to: {filename}")
        return True
    except Exception as e:
        print(f"Failed to save pattern order: {e}")
        return False

if __name__ == "__main__":
    
    # Generate the randomized pattern list
    print("Generating randomized size study patterns...")
    pattern_list = create_randomized_pattern_list()
    
    # Print the order for reference
    print_randomized_order(pattern_list)
    
    # Ask if user wants to save the order
    try:
        save_choice = input("\nSave pattern order to file? (y/n): ").lower().strip()
        if save_choice in ['y', 'yes']:
            save_pattern_order(pattern_list)
    except KeyboardInterrupt:
        pass
    
    # Connect to device and run study
    api = SERIAL_API()
    ports = api.get_serial_devices()
    
    if not ports:
        print("No serial devices found!")
        exit(1)
        
    if len(ports) <= 2:
        print(f"Need at least 3 ports, only found {len(ports)}")
        exit(1)
    
    if api.connect_serial_device(ports[2]):
        time.sleep(1)
        
        # Initial nuclear stop to ensure clean state
        nuclear_stop_all(api)
        
        try:
            # Ask for confirmation before starting
            print(f"\nReady to start randomized size study with {len(pattern_list)} patterns.")
            print("Controls: 'r' = repeat, 'n' = next, 'q' = quit, 's' = summary, 'e' = emergency stop")
            start_choice = input("Start study? (y/n): ").lower().strip()
            
            if start_choice in ['y', 'yes']:
                result = run_randomized_size_study(api, pattern_list)
                
                print(f"\n=== RANDOMIZED SIZE STUDY {result.upper()} ===")
                
                if result == 'completed':
                    print("Study Summary:")
                    print(f"✓ All {len(pattern_list)} patterns completed")
                    print("✓ Fully randomized order eliminates order effects")
                    print("✓ Tests size discrimination across all shapes and pattern types")
                elif result == 'quit':
                    print("Study ended early after testing some patterns")
            else:
                print("Study cancelled.")
                
        except KeyboardInterrupt:
            print("\nStudy interrupted by user")
            nuclear_stop_all(api)
        except Exception as e:
            print(f"Unexpected error: {e}")
            nuclear_stop_all(api)
        finally:
            # Ensure we always try to stop everything and disconnect
            try:
                nuclear_stop_all(api)
                time.sleep(0.5)
                api.disconnect_serial_device()
                print("Safely disconnected")
            except:
                print("Error during cleanup - device may still be connected")
    else:
        print("Failed to connect to serial device")
        
    print("\nStudy session ended.")