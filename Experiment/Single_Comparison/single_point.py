import time
import random
import os
import sys

# Add the root directory to the path for imports
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, root_dir)

from core.hardware.serial_api import SERIAL_API
from core.study_params import DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES

class SinglePointTester:
    def __init__(self):
        self.api = SERIAL_API()
        self.actuator_addresses = list(range(16))  # Actuators 0-15
        self.pattern_list = []
        self.current_index = 0
        
    def create_all_patterns(self):
        """Create all buzz and pulse patterns for all actuators and randomize them"""
        print("Creating all patterns...")
        patterns = []
        
        # Create buzz patterns for all actuators
        for addr in self.actuator_addresses:
            pattern = {
                'addr': addr,
                'type': 'buzz',
                'pattern': self.create_buzz_pattern(addr)
            }
            patterns.append(pattern)
            
        # Create pulse patterns for all actuators
        for addr in self.actuator_addresses:
            pattern = {
                'addr': addr,
                'type': 'pulse', 
                'pattern': self.create_pulse_pattern(addr)
            }
            patterns.append(pattern)
            
        # Randomize the order
        random.shuffle(patterns)
        print(f"Created and randomized {len(patterns)} patterns ({len(self.actuator_addresses)} buzz + {len(self.actuator_addresses)} pulse)")
        
        return patterns
    
    def create_buzz_pattern(self, addr, duration_ms=DURATION):
        """Create a continuous buzz pattern for specified duration"""
        return {
            'addr': addr,
            'duty': DUTY,
            'freq': FREQ,
            'duration_ms': duration_ms
        }
    
    def create_pulse_pattern(self, addr, num_pulses=NUM_PULSES, pulse_duration=PULSE_DURATION, pause_duration=PAUSE_DURATION):
        """Create a pulsed pattern with specified parameters"""
        return {
            'addr': addr,
            'duty': DUTY,
            'freq': FREQ,
            'num_pulses': num_pulses,
            'pulse_duration': pulse_duration,
            'pause_duration': pause_duration
        }
    
    def send_buzz_pattern(self, pattern):
        """Send a buzz pattern using the existing API"""
        if not self.api.connected:
            print("Device not connected!")
            return False
            
        # Start vibration
        success = self.api.send_command(pattern['addr'], pattern['duty'], pattern['freq'], 1)
        if not success:
            return False
            
        # Wait for duration
        time.sleep(pattern['duration_ms'] / 1000.0)
        
        # Stop vibration
        success = self.api.send_command(pattern['addr'], 0, 0, 0)
        if not success:
            return False
        
        # Verification stop after 500ms
        time.sleep(0.5)
        return self.api.send_command(pattern['addr'], 0, 0, 0)
    
    def send_pulse_pattern(self, pattern):
        """Send a pulse pattern using the existing API"""
        if not self.api.connected:
            print("Device not connected!")
            return False
            
        for i in range(pattern['num_pulses']):
            # Start pulse
            success = self.api.send_command(pattern['addr'], pattern['duty'], pattern['freq'], 1)
            if not success:
                return False
                
            # Wait for pulse duration
            time.sleep(pattern['pulse_duration'] / 1000.0)
            
            # Stop pulse
            success = self.api.send_command(pattern['addr'], 0, 0, 0)
            if not success:
                return False
                
            # Wait for pause between pulses (except for the last pulse)
            if i < pattern['num_pulses'] - 1:
                time.sleep(pattern['pause_duration'] / 1000.0)
        
        # Final verification stop after 500ms
        time.sleep(0.5)
        return self.api.send_command(pattern['addr'], 0, 0, 0)
    
    def play_current_pattern(self):
        """Play the current pattern in the list"""
        if not self.pattern_list:
            print("No patterns loaded!")
            return False
            
        if self.current_index >= len(self.pattern_list):
            print("Reached end of pattern list!")
            return False
            
        current = self.pattern_list[self.current_index]
        print(f"Playing pattern {self.current_index + 1}/{len(self.pattern_list)}: "
              f"Actuator {current['addr']} ({current['type']})")
        
        # Use appropriate sending method based on pattern type
        if current['type'] == 'buzz':
            return self.send_buzz_pattern(current['pattern'])
        elif current['type'] == 'pulse':
            return self.send_pulse_pattern(current['pattern'])
        else:
            print(f"Unknown pattern type: {current['type']}")
            return False
    
    def next_pattern(self):
        """Move to next pattern"""
        if self.current_index < len(self.pattern_list) - 1:
            self.current_index += 1
            return True
        else:
            print("Reached the end! Starting over from first pattern.")
            self.current_index = 0
            return True
    
    def show_current_info(self):
        """Show information about current pattern"""
        if not self.pattern_list:
            print("No patterns loaded!")
            return
            
        current = self.pattern_list[self.current_index]
        print(f"Current: Pattern {self.current_index + 1}/{len(self.pattern_list)} - "
              f"Actuator {current['addr']} ({current['type']})")
    
    def connect_to_device(self):
        """Connect to device using existing API methods"""
        print("Searching for serial devices...")
        devices = self.api.get_serial_devices()
        
        if not devices:
            print("No serial devices found!")
            return False
            
        print("Available devices:")
        for i, device in enumerate(devices):
            print(f"{i}: {device}")
            
        # Auto-connect to first device or let user choose
        device_index = 0
        if len(devices) > 1:
            try:
                choice = input(f"Select device (0-{len(devices)-1}) or press Enter for device 0: ")
                if choice.strip():
                    device_index = int(choice)
            except (ValueError, IndexError):
                print("Invalid choice, using device 0")
                device_index = 0
                
        return self.api.connect_serial_device(devices[device_index])
    
    def interactive_mode(self):
        """Run simplified interactive testing mode"""
        print("\n" + "="*50)
        print("SINGLE POINT HAPTIC TESTER")
        print("="*50)
        
        # Connect to device
        if not self.connect_to_device():
            print("Failed to connect to device")
            return
        
        # Create all patterns (buzz and pulse for all actuators) and randomize
        self.pattern_list = self.create_all_patterns()
        self.current_index = 0
        
        print("\nPattern Playback Controls:")
        print("p/play  - Play next pattern")
        print("r/repeat - Repeat current pattern")
        print("q/quit  - Exit")
        
        try:
            while True:
                self.show_current_info()
                command = input("\nEnter command: ").strip().lower()
                
                if command in ['p', 'play']:
                    # Move to next pattern first, then play it
                    self.next_pattern()
                    if self.play_current_pattern():
                        print("✓ Pattern played successfully!")
                    else:
                        print("✗ Failed to play pattern!")
                        
                elif command in ['r', 'repeat']:
                    if self.play_current_pattern():
                        print("✓ Pattern repeated successfully!")
                    else:
                        print("✗ Failed to repeat pattern!")
                        
                elif command in ['q', 'quit']:
                    break
                    
                else:
                    print("Invalid command! Use p/play, r/repeat, or q/quit")
                    
        finally:
            self.api.disconnect_serial_device()
            print("Disconnected from device")

def main():
    """Main function to run the single point tester"""
    tester = SinglePointTester()
    tester.interactive_mode()

if __name__ == '__main__':
    main()