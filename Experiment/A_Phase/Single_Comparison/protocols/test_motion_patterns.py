import os
import sys
import time
import math

# Add root directory to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)

from core.hardware.serial_api import SERIAL_API
from core.patterns.generators import generate_coordinate_pattern, get_motion_engine
from core.hardware.actuator_layout import LAYOUT_POSITIONS
from core.study_params import DUTY, FREQ

class Actuators0123MotionTester:
    """Test motion patterns specifically for actuators 0, 1, 2, 3 (top row)"""
    
    def __init__(self, api):
        self.api = api
        self.engine = get_motion_engine()
        
        # Actuators 0,1,2,3 positions from layout
        self.test_actuators = {
            0: (0, 0),      # Top left
            1: (60, 0),     # Top second from left
            2: (120, 0),    # Top second from right  
            3: (180, 0)     # Top right
        }
        
        print("Testing actuators 0, 1, 2, 3:")
        for addr, pos in self.test_actuators.items():
            print(f"  Actuator {addr}: position {pos}")
    
    def create_trajectory_patterns(self):
        """Create different trajectory patterns using actuators 0,1,2,3"""
        patterns = {
            # Direct actuator sequences
            'left_to_right': [0, 1, 2, 3],
            'right_to_left': [3, 2, 1, 0],
            'bounce': [0, 1, 2, 3, 2, 1, 0],
            'center_out': [1, 0, 2, 3],
            'center_in': [0, 3, 1, 2],
            
            # Coordinate-based smooth motion  
            'smooth_left_right': [(0, 0), (60, 0), (120, 0), (180, 0)],
            'smooth_right_left': [(180, 0), (120, 0), (60, 0), (0, 0)],
            'smooth_curve_up': [(0, 0), (60, -20), (120, -20), (180, 0)],
            'smooth_curve_down': [(0, 0), (60, 20), (120, 20), (180, 0)],
            'smooth_wave': [(0, 0), (30, -15), (60, 0), (90, 15), (120, 0), (150, -15), (180, 0)],
            
            # Phantom-only patterns (between actuators)
            'phantom_glide': [(30, 0), (90, 0), (150, 0)],  # Between actuators
            'phantom_zigzag': [(30, 0), (90, 10), (150, -10)],
            'phantom_arc': [(30, 0), (60, -30), (90, -40), (120, -30), (150, 0)],
        }
        return patterns
    
    def test_single_actuator(self, actuator_id):
        """Test a single actuator from our test set"""
        if actuator_id not in self.test_actuators:
            print(f"Actuator {actuator_id} not in test set {list(self.test_actuators.keys())}")
            return
        
        print(f"\nTesting single actuator {actuator_id} at position {self.test_actuators[actuator_id]}")
        
        # Create simple activation pattern
        test_pattern = {
            'steps': [
                {
                    'commands': [{
                        'addr': actuator_id,
                        'duty': DUTY,
                        'freq': FREQ,
                        'start_or_stop': 1
                    }],
                    'delay_after_ms': 1000
                },
                {
                    'commands': [{
                        'addr': actuator_id,
                        'duty': 0,
                        'freq': 0,
                        'start_or_stop': 0
                    }],
                    'delay_after_ms': 0
                }
            ]
        }
        
        success = self._execute_pattern(test_pattern)
        if success:
            print(f"  ✓ Actuator {actuator_id} test completed")
        else:
            print(f"  ✗ Actuator {actuator_id} test failed")
    
    def test_all_actuators_sequence(self):
        """Test all 4 actuators in sequence"""
        print(f"\nTesting all actuators 0,1,2,3 in sequence...")
        
        pattern = generate_coordinate_pattern(
            coordinates=[0, 1, 2, 3],
            intensity=DUTY,
            freq=FREQ,
            movement_speed=1000  # Medium speed
        )
        
        if pattern and pattern.get('steps'):
            print(f"Generated {len(pattern['steps'])} steps")
            success = self._execute_pattern(pattern)
            if success:
                print("  ✓ Sequential test completed")
            else:
                print("  ✗ Sequential test failed")
        else:
            print("  ✗ Failed to generate sequential pattern")
    
    def test_motion_pattern(self, pattern_name, trajectory, movement_speed=2000):
        """Test a specific motion pattern"""
        print(f"\n--- Testing {pattern_name.upper()} motion ---")
        print(f"Trajectory: {trajectory}")
        print(f"Movement speed: {movement_speed} pixels/second")
        
        # Generate the motion pattern
        motion_pattern = generate_coordinate_pattern(
            coordinates=trajectory,
            intensity=DUTY,
            freq=FREQ,
            movement_speed=movement_speed
        )
        
        if not motion_pattern or not motion_pattern.get('steps'):
            print("  ✗ Failed to generate motion pattern")
            return False
        
        # Analyze the pattern
        total_commands = sum(len(step['commands']) for step in motion_pattern['steps'])
        total_duration = sum(step.get('delay_after_ms', 0) for step in motion_pattern['steps'])
        
        print(f"  Generated {len(motion_pattern['steps'])} execution steps")
        print(f"  Total commands: {total_commands}")
        print(f"  Estimated duration: {total_duration/1000:.2f}s")
        
        # Show which actuators will be used
        used_actuators = set()
        for step in motion_pattern['steps']:
            for cmd in step['commands']:
                used_actuators.add(cmd['addr'])
        print(f"  Actuators used: {sorted(used_actuators)}")
        
        # Ask user if they want to execute this pattern
        try:
            choice = input(f"  Execute {pattern_name} pattern? (y/n/q): ").lower().strip()
            if choice == 'q':
                return 'quit'
            elif choice == 'y':
                print(f"  Playing {pattern_name} pattern...")
                success = self._execute_pattern(motion_pattern)
                if success:
                    print(f"  ✓ {pattern_name} pattern completed")
                else:
                    print(f"  ✗ Failed to execute {pattern_name} pattern")
            else:
                print(f"  Skipped {pattern_name} pattern")
        except KeyboardInterrupt:
            return 'quit'
        
        return True
    
    def _execute_pattern(self, pattern):
        """Execute a pattern step by step"""
        try:
            for step_num, step in enumerate(pattern['steps']):
                # Send commands for this step
                if step.get('commands'):
                    success = self.api.send_command_list(step['commands'])
                    if not success:
                        print(f"    Warning: Step {step_num + 1} commands may have failed")
                
                # Wait for the delay
                delay_ms = step.get('delay_after_ms', 0)
                if delay_ms > 0:
                    time.sleep(delay_ms / 1000.0)
            
            return True
        except Exception as e:
            print(f"    Error executing pattern: {e}")
            return False
    
    def analyze_phantom_coverage(self):
        """Analyze phantom sensation coverage for our actuator positions"""
        print(f"\n=== PHANTOM COVERAGE ANALYSIS ===")
        
        # Test phantom creation at various points
        test_points = [
            (30, 0),   # Between 0 and 1
            (90, 0),   # Between 1 and 2
            (150, 0),  # Between 2 and 3
            (60, -20), # Above actuator 1
            (120, 20), # Below actuator 2
            (90, -30), # Above center
        ]
        
        for point in test_points:
            phantom = self.engine.create_phantom(point, 0.8)
            if phantom:
                print(f"Point {point}:")
                print(f"  Triangle actuators: {phantom['actuators']}")
                print(f"  Intensities: {[f'{i:.3f}' for i in phantom['intensities']]}")
                
                # Check if only our test actuators are used
                our_actuators = set(phantom['actuators']) & set(self.test_actuators.keys())
                if our_actuators:
                    print(f"  Uses our actuators: {sorted(our_actuators)}")
                else:
                    print(f"  ⚠ Uses other actuators: {phantom['actuators']}")
            else:
                print(f"Point {point}: No phantom created")
    
    def interactive_menu(self):
        """Interactive menu for testing different patterns"""
        patterns = self.create_trajectory_patterns()
        
        while True:
            print(f"\n" + "="*60)
            print("ACTUATORS 0,1,2,3 MOTION PATTERN TESTER")
            print("="*60)
            print("1. Test individual actuators")
            print("2. Test all actuators in sequence")
            print("3. Test motion patterns")
            print("4. Analyze phantom coverage")
            print("5. Custom trajectory input")
            print("6. Speed comparison test")
            print("7. Exit")
            print("-"*60)
            
            try:
                choice = input("Select option (1-7): ").strip()
                
                if choice == "1":
                    # Test individual actuators
                    print(f"\nTesting individual actuators...")
                    for actuator_id in [0, 1, 2, 3]:
                        self.test_single_actuator(actuator_id)
                        time.sleep(0.5)
                
                elif choice == "2":
                    # Test sequential pattern
                    self.test_all_actuators_sequence()
                
                elif choice == "3":
                    # Test motion patterns
                    print(f"\nAvailable motion patterns:")
                    pattern_names = list(patterns.keys())
                    for i, name in enumerate(pattern_names, 1):
                        print(f"{i:2d}. {name}")
                    
                    try:
                        pattern_choice = input("Select pattern number (or 'a' for all): ").strip()
                        if pattern_choice.lower() == 'a':
                            # Test all patterns
                            for pattern_name in pattern_names:
                                trajectory = patterns[pattern_name]
                                result = self.test_motion_pattern(pattern_name, trajectory)
                                if result == 'quit':
                                    break
                        else:
                            pattern_idx = int(pattern_choice) - 1
                            if 0 <= pattern_idx < len(pattern_names):
                                pattern_name = pattern_names[pattern_idx]
                                trajectory = patterns[pattern_name]
                                self.test_motion_pattern(pattern_name, trajectory)
                            else:
                                print("Invalid pattern number")
                    except ValueError:
                        print("Invalid input")
                
                elif choice == "4":
                    # Analyze phantom coverage
                    self.analyze_phantom_coverage()
                
                elif choice == "5":
                    # Custom trajectory input
                    print(f"\nCustom trajectory input:")
                    print("Enter coordinates as: x1,y1 x2,y2 x3,y3 ...")
                    print("Or actuator IDs as: 0 1 2 3")
                    print("Example coordinates: 0,0 60,0 120,0 180,0")
                    print("Example actuators: 0 1 2 3")
                    
                    try:
                        user_input = input("Enter trajectory: ").strip()
                        if user_input:
                            # Try to parse as coordinates or actuator IDs
                            parts = user_input.split()
                            
                            if ',' in user_input:
                                # Parse as coordinates
                                trajectory = []
                                for part in parts:
                                    x, y = map(float, part.split(','))
                                    trajectory.append((x, y))
                            else:
                                # Parse as actuator IDs
                                trajectory = [int(part) for part in parts]
                            
                            speed = input("Movement speed (default 2000): ").strip()
                            movement_speed = int(speed) if speed else 2000
                            
                            self.test_motion_pattern("custom", trajectory, movement_speed)
                    except Exception as e:
                        print(f"Error parsing input: {e}")
                
                elif choice == "6":
                    # Speed comparison test
                    print(f"\nSpeed comparison test using left-to-right motion...")
                    trajectory = [(0, 0), (60, 0), (120, 0), (180, 0)]
                    speeds = [500, 1000, 2000, 5000]
                    
                    for speed in speeds:
                        print(f"\n--- Testing speed {speed} pixels/second ---")
                        self.test_motion_pattern(f"speed_{speed}", trajectory, speed)
                
                elif choice == "7":
                    print("Exiting...")
                    break
                
                else:
                    print("Invalid choice. Please select 1-7.")
                    
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

def main():
    """Main execution function"""
    api = SERIAL_API()
    
    # Find and connect to device
    ports = api.get_serial_devices()
    if not ports:
        print("No serial devices found!")
        return
    
    if len(ports) < 3:
        print(f"Need at least 3 ports, found {len(ports)}")
        return
    
    print(f"Connecting to device: {ports[2]}")
    if not api.connect_serial_device(ports[2]):
        print("Failed to connect to device!")
        return
    
    print("Connected successfully!")
    
    # Create tester and run interactive menu
    tester = Actuators0123MotionTester(api)
    
    try:
        print(f"\nActuator positions:")
        for addr, pos in tester.test_actuators.items():
            print(f"  Actuator {addr}: {pos}")
        print(f"These form a horizontal line across the top row")
        
        tester.interactive_menu()
        
    except KeyboardInterrupt:
        print("\nTest interrupted by user")
    except Exception as e:
        print(f"\nTest error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean disconnect
        print("\nDisconnecting...")
        api.disconnect_serial_device()
        print("Disconnected successfully")

if __name__ == "__main__":
    main()