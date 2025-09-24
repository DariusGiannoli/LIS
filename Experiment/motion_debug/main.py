"""
Motion Pattern Demo for Actuators 0, 1, 2, 3
Demonstrates different types of haptic motion patterns using the top row actuators.
"""

import time
from generators import (
    generate_static_pattern, 
    generate_sequential_pattern, 
    generate_motion_pattern, 
    generate_pulse_pattern,
    generate_coordinate_pattern
)
from serial_api import SERIAL_API
from actuator_layout import LAYOUT_POSITIONS
from study_params import DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, MOVEMENT_SPEED

class MotionDemo:
    def __init__(self):
        self.serial_api = SERIAL_API()
        self.target_actuators = [0, 1, 2, 3]  # Top row actuators
        self.connected = False
        
    def connect_to_device(self):
        """Connect to the first available serial device"""
        devices = self.serial_api.get_serial_devices()
        if not devices:
            print("No serial devices found!")
            return False
            
        print(f"Available devices: {devices}")
        # Try to connect to the first device
        if self.serial_api.connect_serial_device(devices[2]):
            self.connected = True
            print(f"Connected to {devices[2]}")
            return True
        else:
            print("Failed to connect to device")
            return False
    
    def execute_pattern(self, pattern, pattern_name="Pattern"):
        """Execute a pattern and handle timing"""
        if not self.connected:
            print("Not connected to device!")
            return
            
        print(f"\nExecuting {pattern_name}...")
        print(f"Pattern has {len(pattern['steps'])} steps")
        
        for i, step in enumerate(pattern['steps']):
            print(f"Step {i+1}: {len(step['commands'])} commands, delay: {step['delay_after_ms']}ms")
            
            # Send commands
            if step['commands']:
                self.serial_api.send_command_list(step['commands'])
            
            # Wait for delay
            if step['delay_after_ms'] > 0:
                time.sleep(step['delay_after_ms'] / 1000.0)
        
        print(f"{pattern_name} completed!")
    
    def demo_static_pattern(self):
        """Demonstrate static vibration on all target actuators"""
        pattern = generate_static_pattern(
            devices=self.target_actuators,
            duty=DUTY,
            freq=FREQ,
            duration=2000  # 2 seconds
        )
        self.execute_pattern(pattern, "Static Pattern (All Actuators)")
    
    def demo_sequential_pattern(self):
        """Demonstrate sequential activation of actuators 0->1->2->3"""
        pattern = generate_sequential_pattern(
            devices=self.target_actuators,
            duty=DUTY,
            freq=FREQ,
            duration_per_device=500,  # 0.5 seconds per actuator
            pause_between=200  # 0.2 seconds pause
        )
        self.execute_pattern(pattern, "Sequential Pattern (0->1->2->3)")
    
    def demo_pulse_pattern(self):
        """Demonstrate pulsed vibration on all target actuators"""
        pattern = generate_pulse_pattern(
            devices=self.target_actuators,
            duty=DUTY,
            freq=FREQ,
            pulse_duration=150,  # 150ms pulses
            pause_duration=150,  # 150ms pauses
            num_pulses=3
        )
        self.execute_pattern(pattern, "Pulse Pattern (3 pulses)")
    
    def demo_smooth_motion(self):
        """Demonstrate smooth motion from actuator 0 to 3 using Park et al. algorithm"""
        # Get actual coordinates for the actuators
        start_pos = LAYOUT_POSITIONS[0]  # (0, 0)
        end_pos = LAYOUT_POSITIONS[0]    # (180, 0)
        
        # Create a trajectory with intermediate points for smooth motion
        trajectory = [
            start_pos,           # (0, 0)
            (0,0), (30,0), (60,0), (90,0), (120,0), (150,0), (180,0), (210,0), (240,0), (270,0), 
                (270,30), (270,60), (270,90), (270,120), (270,150), (270,180), (270,210), (270,240), (270,270),
                (240,270), (210,270), (180,270), (150,270), (120,270), (90,270), (60,270), (30,270), (0,270),
                (0,240), (0,210), (0,180), (0,150), (0,120), (0,90), (0,60), (0,30), (0,0),          # Between 2 and 3
            end_pos             # (180, 0)
        ]
        
        pattern = generate_motion_pattern(
            devices=trajectory,
            intensity=DUTY,
            freq=FREQ,
            duration=0.06,      # 60ms per phantom
            movement_speed=MOVEMENT_SPEED  # Moderate speed for smooth motion
        )
        self.execute_pattern(pattern, "Smooth Motion (0->3)")
    
    def demo_back_and_forth(self):
        """Demonstrate back and forth motion along the top row"""
        # Forward motion: 0 -> 3
        forward_trajectory = [
            LAYOUT_POSITIONS[0],  # (0, 0)
            (60, 0),             # Actuator 1 position
            (120, 0),            # Actuator 2 position
            LAYOUT_POSITIONS[3]   # (180, 0)
        ]
        
        # Backward motion: 3 -> 0
        backward_trajectory = [
            LAYOUT_POSITIONS[3],  # (180, 0)
            (120, 0),            # Actuator 2 position
            (60, 0),             # Actuator 1 position
            LAYOUT_POSITIONS[0]   # (0, 0)
        ]
        
        # Execute forward motion
        forward_pattern = generate_motion_pattern(
            devices=forward_trajectory,
            intensity=DUTY,
            freq=FREQ,
            duration=0.05,
            movement_speed=MOVEMENT_SPEED
        )
        self.execute_pattern(forward_pattern, "Forward Motion (0->3)")
        
        time.sleep(0.5)  # Brief pause
        
        # Execute backward motion
        backward_pattern = generate_motion_pattern(
            devices=backward_trajectory,
            intensity=DUTY,
            freq=FREQ,
            duration=0.05,
            movement_speed=MOVEMENT_SPEED
        )
        self.execute_pattern(backward_pattern, "Backward Motion (3->0)")
    
    def demo_coordinate_based_motion(self):
        """Demonstrate coordinate-based motion using generate_coordinate_pattern"""
        # Mix of actuator IDs and custom coordinates
        mixed_trajectory = [
            0,              # Actuator 0
            (30, 0),        # Custom point between 0 and 1
            1,              # Actuator 1
            (90, 0),        # Custom point between 1 and 2
            2,              # Actuator 2
            (150, 0),       # Custom point between 2 and 3
            3               # Actuator 3
        ]
        
        pattern = generate_coordinate_pattern(
            coordinates=mixed_trajectory,
            intensity=DUTY,
            freq=FREQ,
            duration=0.04,
            movement_speed=MOVEMENT_SPEED
        )
        self.execute_pattern(pattern, "Coordinate-Based Motion")
    
    def run_all_demos(self):
        """Run all demonstration patterns"""
        if not self.connect_to_device():
            return
        
        demos = [
            #("Static Pattern", self.demo_static_pattern),
            #("Sequential Pattern", self.demo_sequential_pattern),
            ("Pulse Pattern", self.demo_pulse_pattern),
            ("Smooth Motion", self.demo_smooth_motion),
            #("Back and Forth Motion", self.demo_back_and_forth),
            #("Coordinate-Based Motion", self.demo_coordinate_based_motion)
        ]
        
        print("=== Actuator Motion Demo ===")
        print(f"Target actuators: {self.target_actuators}")
        print(f"Actuator positions: {[LAYOUT_POSITIONS[i] for i in self.target_actuators]}")
        print("=" * 40)
        
        for demo_name, demo_func in demos:
            print(f"\n--- {demo_name} ---")
            demo_func()
            time.sleep(1.5)  # Pause between demos
        
        print("\n=== Demo Complete ===")
        self.serial_api.disconnect_serial_device()
    
    def disconnect(self):
        """Clean disconnect from device"""
        if self.connected:
            self.serial_api.disconnect_serial_device()
            self.connected = False

def main():
    """Main function to run the motion demo"""
    demo = MotionDemo()
    
    try:
        demo.run_all_demos()
    except KeyboardInterrupt:
        print("\nDemo interrupted by user")
    except Exception as e:
        print(f"Error during demo: {e}")
    finally:
        demo.disconnect()

if __name__ == "__main__":
    main()