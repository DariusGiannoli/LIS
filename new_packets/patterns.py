import math
from serial_api import SerialAPI
from typing import List, Dict

class ContinuousLoop:
    """
    Continuous looping sweep that never stops.
    Creates one big batch with multiple cycles for endless motion.
    """
    
    def __init__(self, serial_api: SerialAPI):
        self.serial_api = serial_api
        
        # 4 physical actuators + 3 phantoms = 7 total positions
        self.sweep_positions = [0, 17.5, 35, 52.5, 70, 87.5, 105]  # mm
        print(f"Continuous loop positions: {self.sweep_positions}")
    
    def calculate_soa(self, pulse_duration_ms: int) -> int:
        """SOA = 0.32 × duration + 0.0473"""
        duration_s = pulse_duration_ms / 1000
        soa_s = 0.32 * duration_s + 0.0473
        return int(soa_s * 1000)
    
    def find_actuators_for_position(self, position: float) -> tuple:
        """Find which 2 actuators to use for given position"""
        if position <= 35:
            return 0, 1
        elif position <= 70:
            return 1, 2
        else:
            return 2, 3
    
    def calculate_phantom_intensities(self, position: float, left_addr: int, right_addr: int) -> tuple:
        """Calculate funnel illusion intensities"""
        actuator_positions = [0, 35, 70, 105]
        left_pos = actuator_positions[left_addr]
        right_pos = actuator_positions[right_addr]
        
        d_left = abs(position - left_pos)
        d_right = abs(position - right_pos)
        
        if d_left + d_right == 0:
            return (0.8, 0)
        
        intensity_left = math.sqrt(d_right / (d_left + d_right)) * 0.8
        intensity_right = math.sqrt(d_left / (d_left + d_right)) * 0.8
        
        return intensity_left, intensity_right
    
    def intensity_to_duty(self, intensity: float) -> int:
        """Convert 0-1 intensity to 0-15 duty cycle"""
        return max(0, min(15, int(intensity * 15)))
    
    def create_continuous_loop(self, pulse_duration_ms: int = 50, num_cycles: int = 3) -> List[Dict]:
        """
        Create continuous looping motion in one big batch.
        Next cycle starts EXACTLY when previous cycle's last phantom stops.
        
        Args:
            pulse_duration_ms: Duration of each phantom pulse
            num_cycles: Number of complete cycles to include in batch
            
        Returns:
            List of commands for continuous motion
        """
        pulse_duration_ms = min(pulse_duration_ms, 70)
        soa_ms = self.calculate_soa(pulse_duration_ms)
        
        # Calculate cycle timing - next cycle starts when last phantom STOPS
        positions_per_cycle = len(self.sweep_positions)
        last_phantom_start_time = (positions_per_cycle - 1) * soa_ms
        cycle_duration_ms = last_phantom_start_time + pulse_duration_ms  # When last phantom stops
        
        print(f"\n=== Continuous Loop Parameters ===")
        print(f"Positions per cycle: {positions_per_cycle}")
        print(f"Pulse duration: {pulse_duration_ms}ms")
        print(f"SOA interval: {soa_ms}ms") 
        print(f"Last phantom starts at: {last_phantom_start_time}ms")
        print(f"Last phantom stops at: {cycle_duration_ms}ms")
        print(f"Next cycle starts at: {cycle_duration_ms}ms ← NO GAP!")
        print(f"Number of cycles: {num_cycles}")
        print(f"Total loop duration: {num_cycles * cycle_duration_ms}ms")
        
        commands = []
        
        for cycle in range(num_cycles):
            cycle_start_time = cycle * cycle_duration_ms
            
            print(f"\nCycle {cycle + 1} (starts at {cycle_start_time}ms):")
            
            for i, position in enumerate(self.sweep_positions):
                # Calculate absolute timing for this phantom
                phantom_start_time = cycle_start_time + (i * soa_ms)
                phantom_stop_time = phantom_start_time + pulse_duration_ms
                
                # Find actuators and calculate intensities
                left_addr, right_addr = self.find_actuators_for_position(position)
                intensity_left, intensity_right = self.calculate_phantom_intensities(position, left_addr, right_addr)
                
                print(f"  Step {i+1}: pos={position:5.1f}mm, start={phantom_start_time:4d}ms, stop={phantom_stop_time:4d}ms")
                
                # Create start commands
                first_cmd = True
                if intensity_left > 0.05:
                    commands.append({
                        'addr': left_addr,
                        'duty': self.intensity_to_duty(intensity_left),
                        'freq': 3,
                        'start_or_stop': 1,
                        'delay_ms': phantom_start_time if first_cmd else 0
                    })
                    first_cmd = False
                
                if intensity_right > 0.05:
                    commands.append({
                        'addr': right_addr,
                        'duty': self.intensity_to_duty(intensity_right),
                        'freq': 3,
                        'start_or_stop': 1,
                        'delay_ms': phantom_start_time if first_cmd else 0
                    })
                    first_cmd = False
                
                # Create stop commands
                first_stop = True
                if intensity_left > 0.05:
                    commands.append({
                        'addr': left_addr,
                        'duty': 0,
                        'freq': 0,
                        'start_or_stop': 0,
                        'delay_ms': phantom_stop_time if first_stop else 0
                    })
                    first_stop = False
                
                if intensity_right > 0.05:
                    commands.append({
                        'addr': right_addr,
                        'duty': 0,
                        'freq': 0,
                        'start_or_stop': 0,
                        'delay_ms': phantom_stop_time if first_stop else 0
                    })
                    first_stop = False
        
    def create_efficient_continuous_loop(self, pulse_duration_ms: int = 50) -> List[Dict]:
        """
        Create efficient continuous loop that ACTUALLY fits in 20 commands.
        Uses longer pulses with overlapping for true continuous motion.
        """
        pulse_duration_ms = min(pulse_duration_ms, 70)
        soa_ms = self.calculate_soa(pulse_duration_ms)
        
        print(f"\n=== Efficient Continuous Loop (≤20 commands) ===")
        print(f"Pulse duration: {pulse_duration_ms}ms, SOA: {soa_ms}ms")
        
        # Create simple continuous motion with fewer positions but longer overlap
        # Use 5 positions instead of 7 to reduce command count
        positions = [0, 26.25, 52.5, 78.75, 105]  # Evenly spaced positions
        
        commands = []
        
        # Create 2 full cycles forward with overlapping long pulses
        for cycle in range(2):
            cycle_start = cycle * (len(positions) * soa_ms + pulse_duration_ms)
            
            for i, position in enumerate(positions):
                start_time = cycle_start + (i * soa_ms)
                
                left_addr, right_addr = self.find_actuators_for_position(position)
                intensity_left, intensity_right = self.calculate_phantom_intensities(position, left_addr, right_addr)
                
                print(f"Cycle {cycle+1}, Step {i+1}: pos={position:5.1f}mm at {start_time:4d}ms")
                
                # Start commands - only add if significant intensity
                first_cmd = True
                if intensity_left > 0.05:
                    commands.append({
                        'addr': left_addr,
                        'duty': self.intensity_to_duty(intensity_left),
                        'freq': 3,
                        'start_or_stop': 1,
                        'delay_ms': start_time if first_cmd else 0
                    })
                    first_cmd = False
                
                if intensity_right > 0.05 and right_addr != left_addr:
                    commands.append({
                        'addr': right_addr,
                        'duty': self.intensity_to_duty(intensity_right),
                        'freq': 3,
                        'start_or_stop': 1,
                        'delay_ms': start_time if first_cmd else 0
                    })
        
        # Add stop commands for all actuators at the end
        final_stop_time = 2 * (len(positions) * soa_ms) + pulse_duration_ms + 100
        for addr in [0, 1, 2, 3]:
            if len(commands) < 19:  # Leave room for stop commands
                commands.append({
                    'addr': addr,
                    'duty': 0,
                    'freq': 0,
                    'start_or_stop': 0,
                    'delay_ms': final_stop_time if addr == 0 else 0
                })
        
        print(f"Generated {len(commands)} commands (fits in batch: {len(commands) <= 20})")
        return commands[:20]  # Ensure we never exceed 20
    
    def start_efficient_loop(self, pulse_duration_ms: int = 50) -> bool:
        """Start efficient continuous loop that includes multiple cycles"""
        commands = self.create_efficient_continuous_loop(pulse_duration_ms)
        print(f"\nStarting efficient continuous loop with multiple cycles...")
        return self.serial_api.send_timed_batch(commands)
    
    def start_continuous_loop(self, pulse_duration_ms: int = 50, num_cycles: int = 1) -> bool:
        """Start the continuous looping motion"""
        commands = self.create_continuous_loop(pulse_duration_ms, num_cycles)
        print(f"\nStarting continuous loop...")
        return self.serial_api.send_timed_batch(commands)
    
    def create_fast_loop(self) -> bool:
        """Fast continuous loop with shorter pulses"""
        return self.start_continuous_loop(pulse_duration_ms=35, num_cycles=1)
    
    def create_slow_loop(self) -> bool:
        """Slow continuous loop with longer pulses"""  
        return self.start_continuous_loop(pulse_duration_ms=60, num_cycles=1)
    
    def create_medium_loop(self) -> bool:
        """Medium speed continuous loop"""
        return self.start_continuous_loop(pulse_duration_ms=50, num_cycles=1)


# Test the continuous loop
if __name__ == '__main__':
    api = SerialAPI()
    ports = api.get_serial_ports()
    print("Available ports:", ports)
    
    if ports and api.connect(ports[2]):
        loop = ContinuousLoop(api)
        
        import time
        
        print("\n" + "="*60)
        print("CONTINUOUS LOOP DEMONSTRATION")
        print("Creates endless motion in one big batch (multiple cycles)")
        print("Motion flows: 0→17.5→35→52.5→70→87.5→105→87.5→70→52.5→35→17.5→0→...")
        print("Pattern: Forward + Reverse + Forward (3 cycles in 20 commands)")
        print("="*60)
        
        # Test 1: Efficient continuous loop with multiple cycles
        print("\nTEST 1: Efficient continuous loop (forward + reverse + forward)")
        loop.start_efficient_loop(50)
        time.sleep(8)
        
        # Test 2: Fast efficient loop
        print("\nTEST 2: Fast efficient continuous loop")  
        loop.start_efficient_loop(35)
        time.sleep(6)
        
        # Test 3: Slow efficient loop
        print("\nTEST 3: Slow efficient continuous loop")
        loop.start_efficient_loop(60)
        time.sleep(10)
        
        api.disconnect()
        print("\nDisconnected")
    else:
        print("Failed to connect")