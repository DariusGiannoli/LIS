import math
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass
from core.study_params import MOTION_PARAMS, FREQ, DURATION, DUTY, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, MOTION_DURATION
from core.hardware.actuator_layout import LAYOUT_POSITIONS
@dataclass
class MotionCommand:
    actuator_id: int
    intensity: float
    onset_time: float
    duration: float

class MotionEngine:
    """Core motion pattern engine using Park et al. algorithms"""
    
    def __init__(self):
        self.actuators = LAYOUT_POSITIONS
    
    def _find_best_triangle(self, position):
        """Find the 3 closest actuators to the target position"""
        # Calculate distances from target position to all actuators
        distances = []
        for actuator_id, actuator_pos in self.actuators.items():
            dist = math.sqrt((position[0] - actuator_pos[0])**2 + (position[1] - actuator_pos[1])**2)
            distances.append((dist, actuator_id, actuator_pos))
        
        # Sort by distance and take the 3 closest
        distances.sort(key=lambda x: x[0])
        closest_three = distances[:3]
        
        # Return triangle info for the 3 closest actuators
        return {
            'actuators': [item[1] for item in closest_three],  # actuator IDs
            'positions': [item[2] for item in closest_three], # actuator positions
            'distances': [item[0] for item in closest_three]  # distances for debugging
        }
    
    def _calculate_phantom_intensities(self, phantom_pos, triangle_actuators, desired_intensity, distances=None):
        """Calculate 3-actuator phantom intensities using Park et al. energy model"""
        if distances is None:
            # Calculate distances if not provided
            distances = []
            for act_id in triangle_actuators:
                act_pos = self.actuators[act_id]
                dist = math.sqrt((phantom_pos[0] - act_pos[0])**2 + (phantom_pos[1] - act_pos[1])**2)
                distances.append(max(dist, 0.1))
        else:
            # Use provided distances but ensure minimum distance
            distances = [max(d, 0.1) for d in distances]
        
        # Park et al. energy model reversed: Ai = Av / √(1/di / Σ(1/dj))
        # This ensures phantom feels like desired_intensity, not weaker
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities = []
        for dist in distances:
            intensity_factor = math.sqrt((1/dist) / sum_inv_distances)
            intensity = desired_intensity / intensity_factor  # Reverse calculation
            intensities.append(min(1.0, max(0.0, intensity)))
        
        return intensities
    
    def create_phantom(self, position, intensity):
        """Create phantom sensation at position"""
        
        # First check if position is exactly at an actuator location
        for actuator_id, actuator_pos in self.actuators.items():
            if position == actuator_pos:
                # Direct actuator activation - no phantom needed
                return {
                    'actuators': [actuator_id],
                    'intensities': [intensity]
                }
        
        # Find the 3 closest actuators for phantom sensation
        triangle = self._find_best_triangle(position)
        if not triangle:
            return None
        
        # Calculate phantom intensities using the pre-calculated distances
        intensities = self._calculate_phantom_intensities(
            position, 
            triangle['actuators'], 
            intensity,
            distances=triangle['distances']
        )
        
        return {
            'actuators': triangle['actuators'],
            'intensities': intensities
        }
    
    def generate_motion_commands(self, trajectory, intensity=0.8, duration=0.06):
        if len(trajectory) < 2:
            return []
        
        # Calculate timing for trajectory points
        commands = []
        current_time = 0.0
        
        # Sample points along trajectory
        for i, point in enumerate(trajectory):
            phantom = self.create_phantom(point, intensity)
            if phantom:
                for act_id, act_intensity in zip(phantom['actuators'], phantom['intensities']):
                    commands.append(MotionCommand(
                        actuator_id=act_id,
                        intensity=act_intensity,
                        onset_time=current_time,
                        duration=duration
                    ))
            
            # Calculate next timing using SOA
            if i < len(trajectory) - 1:
                soa = MOTION_PARAMS['SOA_SLOPE'] * duration + MOTION_PARAMS['SOA_BASE']
                current_time += soa
        
        return commands

def generate_coordinate_pattern(coordinates, intensity=DUTY, freq=FREQ, duration=MOTION_DURATION):

    # Check if coordinates is None or empty
    if not coordinates:
        print("Warning: No coordinates provided, returning empty pattern")
        return {'steps': []}  # ← FIX: Consistent return format
    
    # Check if this is all device addresses (simple sequential motion)
    if all(isinstance(item, int) for item in coordinates):
        # This is a simple sequence of device addresses like [0, 1, 2, 3]
        # Use sequential pattern for clean start/stop pairs
        duration_ms = int(duration * 1000)
        pause_ms = max(50, int(duration_ms * 0.2))  # 20% pause between activations
        return generate_sequential_pattern(
            devices=coordinates,  # Use original device addresses
            duty=intensity,
            freq=freq,
            duration_per_device=duration_ms,
            pause_between=pause_ms
        )
    
    # Mixed coordinates or pure coordinates - use complex motion system
    return generate_motion_pattern(
        devices=coordinates,
        intensity=intensity,
        freq=freq,
        duration=duration
    )

# Global motion engine
_motion_engine = None

def get_motion_engine():
    global _motion_engine
    if _motion_engine is None:
        _motion_engine = MotionEngine()
    return _motion_engine

# ================================
# COORDINATE/ADDRESS CONVERSION
# ================================

def _convert_to_coordinates(mixed_list: List[Union[int, Tuple[float, float]]]) -> List[Tuple[float, float]]:
    """Convert mixed list of device addresses and coordinates to pure coordinate list"""
    coordinates = []
    
    for item in mixed_list:
        if isinstance(item, tuple) and len(item) == 2:
            # It's already a coordinate
            coordinates.append(item)
        elif isinstance(item, int):
            # It's a device address, convert to coordinate
            if item in LAYOUT_POSITIONS:
                coordinates.append(LAYOUT_POSITIONS[item])
            else:
                print(f"Warning: Device address {item} not found in LAYOUT_POSITIONS")
                # Skip invalid addresses
                continue
        else:
            print(f"Warning: Invalid item {item} in trajectory. Expected int or tuple.")
            continue
    
    return coordinates

# ================================
# MAIN PATTERN FUNCTIONS
# ================================

def generate_static_pattern(devices, duty=DUTY, freq=FREQ, duration=DURATION):
    """Generate static vibration pattern for all devices, supporting per-actuator duty if duty is a list"""
    # Support per-actuator duty cycle
    duties = duty if isinstance(duty, list) else [duty] * len(devices)
    
    # Start commands (immediate execution)
    start_commands = [
        {
            "addr": addr,
            "duty": d,
            "freq": freq,
            "start_or_stop": 1,
            # No delay_ms field!
        }
        for addr, d in zip(devices, duties)
    ]
    
    # Stop commands (immediate execution)
    stop_commands = [
        {
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
            # No delay_ms field!
        }
        for addr in devices
    ]
    
    # Return execution steps with timing info
    return {
        'steps': [
            {
                'commands': start_commands, 
                'delay_after_ms': duration  # Software timing
            },
            {
                'commands': stop_commands, 
                'delay_after_ms': 0  # No delay after stop
            }
        ]
    }

def generate_pulse_pattern(devices, duty=DUTY, freq=FREQ, pulse_duration=PULSE_DURATION, pause_duration=PAUSE_DURATION, num_pulses=NUM_PULSES):
    """Generate pulsed vibration pattern, supporting per-actuator duty if duty is a list"""
    duties = duty if isinstance(duty, list) else [duty] * len(devices)
    
    steps = []
    
    for pulse_num in range(num_pulses):
        # Start commands for this pulse (immediate execution)
        start_commands = [
            {
                "addr": addr,
                "duty": d,
                "freq": freq,
                "start_or_stop": 1,
                # No delay_ms field!
            }
            for addr, d in zip(devices, duties)
        ]
        
        # Stop commands for this pulse (immediate execution)
        stop_commands = [
            {
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                # No delay_ms field!
            }
            for addr in devices
        ]
        
        # Add start step
        steps.append({
            'commands': start_commands,
            'delay_after_ms': pulse_duration  # Wait for pulse to complete
        })
        
        # Add stop step
        delay_after_stop = pause_duration if pulse_num < num_pulses - 1 else 0  # No pause after last pulse
        steps.append({
            'commands': stop_commands,
            'delay_after_ms': delay_after_stop  # Wait between pulses
        })
    
    return {
        'steps': steps
    }

def generate_motion_pattern(devices, intensity=DUTY, freq=FREQ, duration=0.06, **kwargs):
    """
    Generate motion pattern using the exact devices/coordinates provided.
    """
    
    engine = get_motion_engine()

    # Convert everything to coordinates for consistent processing
    coordinates = _convert_to_coordinates(devices)

    if len(coordinates) < 1:
        print("Warning: No valid coordinates found")
        return {'steps': []}

    # Use the exact coordinates provided - no built-in pattern generation
    trajectory = coordinates
    available_devices = set(LAYOUT_POSITIONS.keys())

    # Generate motion commands
    motion_commands = engine.generate_motion_commands(
        trajectory,
        intensity=intensity / 15.0,  # Convert to 0-1 scale
        duration=duration
    )

    if not motion_commands:
        return {'steps': []}

    # Group commands by timing to create execution steps
    # Sort motion commands by onset time
    motion_commands.sort(key=lambda x: x.onset_time)
    
    steps = []
    current_time = 0.0
    command_events = []  # List of (time, 'start'/'stop', command_data)
    
    # Create start and stop events for each motion command
    for cmd in motion_commands:
        if cmd.actuator_id in available_devices:
            device_intensity = max(1, min(15, int(cmd.intensity * 15)))
            
            # Start event
            command_events.append((
                cmd.onset_time,
                'start',
                {
                    "addr": cmd.actuator_id,
                    "duty": device_intensity,
                    "freq": freq,
                    "start_or_stop": 1,
                }
            ))
            
            # Stop event
            command_events.append((
                cmd.onset_time + cmd.duration,
                'stop',
                {
                    "addr": cmd.actuator_id,
                    "duty": 0,
                    "freq": 0,
                    "start_or_stop": 0,
                }
            ))
    
    # Sort all events by time
    command_events.sort(key=lambda x: x[0])
    
    # Group events that happen at the same time
    i = 0
    while i < len(command_events):
        event_time = command_events[i][0]
        
        # Find all events at this time
        same_time_events = []
        while i < len(command_events) and command_events[i][0] == event_time:
            same_time_events.append(command_events[i])
            i += 1
        
        # Calculate delay from current time to this event time
        delay_ms = int((event_time - current_time) * 1000)
        
        # Add delay step if needed (except for first step at time 0)
        if delay_ms > 0 and steps:
            # Modify the previous step to include this delay
            steps[-1]['delay_after_ms'] = delay_ms
        
        # Create commands for this time point
        commands_at_this_time = [event[2] for event in same_time_events]
        
        # Add execution step
        steps.append({
            'commands': commands_at_this_time,
            'delay_after_ms': 0  # Will be updated if there's a next step
        })
        
        current_time = event_time

    return {
        'steps': steps
    }

def generate_sequential_pattern(devices, duty=DUTY, freq=FREQ, duration_per_device=500, pause_between=100):
    """Generate sequential activation pattern through devices in order"""
    steps = []
    
    for i, addr in enumerate(devices):
        # Start command for this device
        start_command = {
            "addr": addr,
            "duty": duty,
            "freq": freq,
            "start_or_stop": 1,
        }
        
        # Stop command for this device  
        stop_command = {
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
        }
        
        # Add start step
        steps.append({
            'commands': [start_command],
            'delay_after_ms': duration_per_device
        })
        
        # Add stop step
        # Only add pause if this isn't the last device
        delay_after_stop = pause_between if i < len(devices) - 1 else 0
        steps.append({
            'commands': [stop_command], 
            'delay_after_ms': delay_after_stop
        })
    
    return {
        'steps': steps
    }