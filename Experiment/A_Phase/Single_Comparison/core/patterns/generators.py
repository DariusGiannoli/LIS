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
    """Core motion pattern engine using Park et al. (2016) algorithms"""
    
    def __init__(self):
        self.actuators = LAYOUT_POSITIONS
        self.MIN_TRIANGLE_AREA = 25  # Minimum triangle area from paper
        self.MAX_DURATION = 0.07     # Maximum duration constraint
    
    def _distance(self, pos1, pos2):
        """Calculate Euclidean distance between two positions"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _triangle_area(self, triangle_positions):
        """Calculate area of triangle formed by three positions"""
        p1, p2, p3 = triangle_positions
        return abs((p1[0]*(p2[1] - p3[1]) + p2[0]*(p3[1] - p1[1]) + p3[0]*(p1[1] - p2[1])) / 2.0)
    
    def _point_in_triangle(self, point, triangle_positions):
        """Check if a point lies inside a triangle using barycentric coordinates"""
        p1, p2, p3 = triangle_positions
        px, py = point
        
        # Calculate barycentric coordinates
        denom = (p2[1] - p3[1])*(p1[0] - p3[0]) + (p3[0] - p2[0])*(p1[1] - p3[1])
        if abs(denom) < 1e-10:  # Degenerate triangle
            return False
            
        a = ((p2[1] - p3[1])*(px - p3[0]) + (p3[0] - p2[0])*(py - p3[1])) / denom
        b = ((p3[1] - p1[1])*(px - p3[0]) + (p1[0] - p3[0])*(py - p3[1])) / denom
        c = 1 - a - b
        
        # Point is inside if all barycentric coordinates are non-negative
        return a >= -1e-10 and b >= -1e-10 and c >= -1e-10
    
    def _find_best_triangle(self, position):
        """Find optimal triangle of actuators for phantom sensation"""
        # First try to find actuators that form a triangle containing the position
        best_triangle = None
        min_area = float('inf')
        
        actuator_ids = list(self.actuators.keys())
        
        # Try all combinations of 3 actuators
        for i in range(len(actuator_ids)):
            for j in range(i+1, len(actuator_ids)):
                for k in range(j+1, len(actuator_ids)):
                    triangle_ids = [actuator_ids[i], actuator_ids[j], actuator_ids[k]]
                    triangle_positions = [self.actuators[id] for id in triangle_ids]
                    
                    # Check if phantom position is inside this triangle
                    if self._point_in_triangle(position, triangle_positions):
                        area = self._triangle_area(triangle_positions)
                        if area > self.MIN_TRIANGLE_AREA and area < min_area:
                            min_area = area
                            distances = [self._distance(position, pos) for pos in triangle_positions]
                            best_triangle = {
                                'actuators': triangle_ids,
                                'positions': triangle_positions,
                                'distances': distances
                            }
        
        # Fallback to 3 closest actuators if no containing triangle found
        if best_triangle is None:
            distances = []
            for actuator_id, actuator_pos in self.actuators.items():
                dist = self._distance(position, actuator_pos)
                distances.append((dist, actuator_id, actuator_pos))
            
            # Sort by distance and take the 3 closest
            distances.sort(key=lambda x: x[0])
            closest_three = distances[:3]
            
            # Check if these 3 form a valid triangle
            triangle_positions = [item[2] for item in closest_three]
            area = self._triangle_area(triangle_positions)
            
            if area < self.MIN_TRIANGLE_AREA:
                # Try to find a better triangle by replacing the farthest actuator
                for replacement_idx in range(3, min(len(distances), 6)):
                    for replace_pos in range(3):
                        test_triangle = closest_three.copy()
                        test_triangle[replace_pos] = distances[replacement_idx]
                        test_positions = [item[2] for item in test_triangle]
                        test_area = self._triangle_area(test_positions)
                        
                        if test_area >= self.MIN_TRIANGLE_AREA:
                            closest_three = test_triangle
                            area = test_area
                            break
                    if area >= self.MIN_TRIANGLE_AREA:
                        break
            
            best_triangle = {
                'actuators': [item[1] for item in closest_three],
                'positions': [item[2] for item in closest_three],
                'distances': [item[0] for item in closest_three]
            }
        
        return best_triangle
    
    def _calculate_phantom_intensities(self, phantom_pos, triangle_actuators, desired_intensity, distances=None):
        """Calculate 3-actuator phantom intensities using Park et al. (2016) energy model"""
        if distances is None:
            distances = []
            for act_id in triangle_actuators:
                act_pos = self.actuators[act_id]
                dist = self._distance(phantom_pos, act_pos)
                distances.append(max(dist, 0.1))  # Prevent division by zero
        else:
            distances = [max(d, 0.1) for d in distances]
        
        # Park et al. Equation (10): A_i = √(1/d_i / Σ(1/d_j)) × A_v
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities = []
        for dist in distances:
            intensity_factor = math.sqrt((1/dist) / sum_inv_distances)
            # CORRECTED: Multiply by intensity factor, not divide
            intensity = desired_intensity * intensity_factor
            intensities.append(min(1.0, max(0.0, intensity)))
        
        return intensities
    
    def _resample_trajectory(self, trajectory, max_interval_s=0.07, movement_speed=500):
        """Resample trajectory to meet Park et al. timing constraints
        
        Args:
            trajectory: List of (x, y) coordinate tuples
            max_interval_s: Maximum time interval between samples (default 0.07s from paper)
            movement_speed: Assumed movement speed in pixels/second (higher = fewer samples)
        """
        if len(trajectory) < 2:
            return trajectory
        
        resampled = [trajectory[0]]  # Always include first point
        
        for i in range(1, len(trajectory)):
            prev_point = resampled[-1]
            curr_point = trajectory[i]
            
            # Calculate distance between points
            distance = self._distance(prev_point, curr_point)
            
            # Estimate required samples based on distance and timing
            estimated_time = distance / movement_speed  # Configurable speed
            
            if estimated_time > max_interval_s:
                # Need to add intermediate points
                num_segments = int(math.ceil(estimated_time / max_interval_s))
                for j in range(1, num_segments):
                    t = j / num_segments
                    interpolated_point = (
                        prev_point[0] + t * (curr_point[0] - prev_point[0]),
                        prev_point[1] + t * (curr_point[1] - prev_point[1])
                    )
                    resampled.append(interpolated_point)
            
            resampled.append(curr_point)
        
        return resampled
    
    def create_phantom(self, position, intensity):
        """Create phantom sensation at position using Park et al. algorithm"""
        
        # Check if position is exactly at an actuator location
        for actuator_id, actuator_pos in self.actuators.items():
            if self._distance(position, actuator_pos) < 1.0:  # Within 1 unit
                return {
                    'actuators': [actuator_id],
                    'intensities': [intensity]
                }
        
        # Find the optimal triangle for phantom sensation
        triangle = self._find_best_triangle(position)
        if not triangle:
            return None
        
        # Calculate phantom intensities using corrected Park et al. formula
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
    
    def generate_motion_commands(self, trajectory, intensity=0.8, base_duration=0.06, 
                               movement_speed=500, max_sampling_interval=0.07):
        """Generate motion commands using Park et al. (2016) algorithm
        
        Args:
            trajectory: List of (x, y) coordinate tuples
            intensity: Phantom intensity (0-1)
            base_duration: Duration per phantom (max 0.07s)
            movement_speed: Movement speed in pixels/second (higher = fewer samples)
            max_sampling_interval: Max time between samples (0.07s from paper)
        """
        if len(trajectory) < 1:
            return []
        
        # Enforce duration constraint from paper
        duration = min(base_duration, self.MAX_DURATION)
        
        # Resample trajectory to meet timing constraints
        resampled_trajectory = self._resample_trajectory(
            trajectory, 
            max_interval_s=max_sampling_interval,
            movement_speed=movement_speed
        )
        
        commands = []
        current_time = 0.0
        
        # Sample points along trajectory
        for i, point in enumerate(resampled_trajectory):
            phantom = self.create_phantom(point, intensity)
            if phantom:
                for act_id, act_intensity in zip(phantom['actuators'], phantom['intensities']):
                    commands.append(MotionCommand(
                        actuator_id=act_id,
                        intensity=act_intensity,
                        onset_time=current_time,
                        duration=duration
                    ))
            
            # Calculate next timing using Park et al. SOA formula
            if i < len(resampled_trajectory) - 1:
                # Equation (5): SOA = 0.32 × duration + 0.0473
                soa = MOTION_PARAMS['SOA_SLOPE'] * duration + MOTION_PARAMS['SOA_BASE']
                
                # Ensure SOA >= duration to prevent overlap (constraint from paper)
                soa = max(soa, duration)
                
                current_time += soa
        
        return commands

def generate_coordinate_pattern(coordinates, intensity=DUTY, freq=FREQ, duration=MOTION_DURATION, 
                              movement_speed=500):
    """Generate coordinate-based motion patterns with Park et al. algorithm"""
    
    # Check if coordinates is None or empty
    if not coordinates:
        print("Warning: No coordinates provided, returning empty pattern")
        return {'steps': []}
    
    # Check if this is all device addresses (simple sequential motion)
    if all(isinstance(item, int) for item in coordinates):
        # Use sequential pattern for clean start/stop pairs
        duration_ms = int(duration * 1000)
        pause_ms = max(50, int(duration_ms * 0.2))  # 20% pause between activations
        return generate_sequential_pattern(
            devices=coordinates,
            duty=intensity,
            freq=freq,
            duration_per_device=duration_ms,
            pause_between=pause_ms
        )
    
    # Mixed coordinates or pure coordinates - use Park et al. motion system
    return generate_motion_pattern(
        devices=coordinates,
        intensity=intensity,
        freq=freq,
        duration=duration,
        movement_speed=movement_speed
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
            coordinates.append(item)
        elif isinstance(item, int):
            if item in LAYOUT_POSITIONS:
                coordinates.append(LAYOUT_POSITIONS[item])
            else:
                print(f"Warning: Device address {item} not found in LAYOUT_POSITIONS")
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
    duties = duty if isinstance(duty, list) else [duty] * len(devices)
    
    start_commands = [
        {
            "addr": addr,
            "duty": d,
            "freq": freq,
            "start_or_stop": 1,
        }
        for addr, d in zip(devices, duties)
    ]
    
    stop_commands = [
        {
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
        }
        for addr in devices
    ]
    
    return {
        'steps': [
            {
                'commands': start_commands, 
                'delay_after_ms': duration
            },
            {
                'commands': stop_commands, 
                'delay_after_ms': 0
            }
        ]
    }

def generate_pulse_pattern(devices, duty=DUTY, freq=FREQ, pulse_duration=PULSE_DURATION, pause_duration=PAUSE_DURATION, num_pulses=NUM_PULSES):
    """Generate pulsed vibration pattern, supporting per-actuator duty if duty is a list"""
    duties = duty if isinstance(duty, list) else [duty] * len(devices)
    
    steps = []
    
    for pulse_num in range(num_pulses):
        start_commands = [
            {
                "addr": addr,
                "duty": d,
                "freq": freq,
                "start_or_stop": 1,
            }
            for addr, d in zip(devices, duties)
        ]
        
        stop_commands = [
            {
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
            }
            for addr in devices
        ]
        
        steps.append({
            'commands': start_commands,
            'delay_after_ms': pulse_duration
        })
        
        delay_after_stop = pause_duration if pulse_num < num_pulses - 1 else 0
        steps.append({
            'commands': stop_commands,
            'delay_after_ms': delay_after_stop
        })
    
    return {
        'steps': steps
    }

def generate_motion_pattern(devices, intensity=DUTY, freq=FREQ, duration=0.06, 
                          movement_speed=500, max_sampling_interval=0.07, **kwargs):
    """Generate motion pattern using Park et al. (2016) algorithm
    
    Args:
        devices: List of device addresses or coordinates  
        intensity: Intensity value (0-15 scale)
        freq: Frequency parameter
        duration: Duration per phantom
        movement_speed: Movement speed in pixels/second (higher = fewer samples)
        max_sampling_interval: Max time between samples (0.07s from paper)
    """
    
    engine = get_motion_engine()

    # Convert everything to coordinates for consistent processing
    coordinates = _convert_to_coordinates(devices)

    if len(coordinates) < 1:
        print("Warning: No valid coordinates found")
        return {'steps': []}

    # Use the exact coordinates provided
    trajectory = coordinates
    available_devices = set(LAYOUT_POSITIONS.keys())

    # Generate motion commands using corrected Park et al. algorithm
    motion_commands = engine.generate_motion_commands(
        trajectory,
        intensity=intensity / 15.0,  # Convert to 0-1 scale
        base_duration=duration,
        movement_speed=movement_speed,
        max_sampling_interval=max_sampling_interval
    )

    if not motion_commands:
        return {'steps': []}

    # Group commands by timing to create execution steps
    motion_commands.sort(key=lambda x: x.onset_time)
    
    steps = []
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
    current_time = 0.0
    
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
            steps[-1]['delay_after_ms'] = delay_ms
        
        # Create commands for this time point
        commands_at_this_time = [event[2] for event in same_time_events]
        
        # Add execution step
        steps.append({
            'commands': commands_at_this_time,
            'delay_after_ms': 0
        })
        
        current_time = event_time

    return {
        'steps': steps
    }

def generate_sequential_pattern(devices, duty=DUTY, freq=FREQ, duration_per_device=500, pause_between=100):
    """Generate sequential activation pattern through devices in order"""
    steps = []
    
    for i, addr in enumerate(devices):
        start_command = {
            "addr": addr,
            "duty": duty,
            "freq": freq,
            "start_or_stop": 1,
        }
        
        stop_command = {
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
        }
        
        steps.append({
            'commands': [start_command],
            'delay_after_ms': duration_per_device
        })
        
        delay_after_stop = pause_between if i < len(devices) - 1 else 0
        steps.append({
            'commands': [stop_command], 
            'delay_after_ms': delay_after_stop
        })
    
    return {
        'steps': steps
    }