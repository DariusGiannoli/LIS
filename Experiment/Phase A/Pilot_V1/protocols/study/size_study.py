import time
import sys  
import os  
import random

root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
sys.path.insert(0, root_dir)
from categories.size import get_all_size_patterns
from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

sleep_during = 1.5
sleep_between = 2

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
        print("Press 'r' to repeat, 'n' for next pattern, 'q' to quit, 's' for summary: ", end='', flush=True)
        
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
            else:
                print("Invalid input. Please press 'r', 'n', 'q', or 's'.")
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
    print("Controls: 'r' = repeat, 'n' = next, 'q' = quit, 's' = summary")
    
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
        api.send_timed_batch(pattern['commands'])
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
        elif action == 'quit':
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
    api = SerialAPI()
    ports = api.get_serial_ports()
    
    if ports and api.connect(ports[2]):
        time.sleep(1)
        
        try:
            # Ask for confirmation before starting
            print(f"\nReady to start randomized size study with {len(pattern_list)} patterns.")
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
                    completed = 0  # You'd need to track this if you wanted exact count
                    print(f"Study ended early after testing some patterns")
            else:
                print("Study cancelled.")
                
        except KeyboardInterrupt:
            print("\nStudy interrupted by user")
        
        api.disconnect()
    else:
        print("Failed to connect to serial device")
        
    print("\nStudy session ended.")