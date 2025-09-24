import math
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass
from core.study_params import MOTION_PARAMS, FREQ, DURATION, DUTY, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, MOTION_DURATION, MOVEMENT_SPEED
from core.hardware.actuator_layout import LAYOUT_POSITIONS

@dataclass
class MotionCommand:
    """Represents a timed motion command for an actuator"""
    actuator_id: int
    intensity: float
    onset_time: float
    duration: float

class MotionEngine:
    """Core motion pattern engine using Park et al. (2016) algorithms - exact paper implementation"""
    
    def __init__(self):
        self.actuators = LAYOUT_POSITIONS
        self.MAX_DURATION = 0.07     # Maximum duration constraint from paper
        self.DEBUG = False           # Set to True for debugging
    
    def _distance(self, pos1, pos2):
        """Calculate Euclidean distance between two positions"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def _find_three_closest_actuators(self, position):
        """Find the three closest physical tactors around the point (Park et al. Eq. 10)"""
        distances = []
        for actuator_id, actuator_pos in self.actuators.items():
            dist = self._distance(position, actuator_pos)
            distances.append((dist, actuator_id, actuator_pos))
        
        # Sort by distance and take the 3 closest
        distances.sort(key=lambda x: x[0])
        closest_three = distances[:3]
        
        if self.DEBUG:
            print(f"Point {position}: closest actuators {[item[1] for item in closest_three]} "
                  f"at distances {[round(item[0], 1) for item in closest_three]}")
        
        return {
            'actuators': [item[1] for item in closest_three],
            'positions': [item[2] for item in closest_three],
            'distances': [item[0] for item in closest_three]
        }
    
    def _is_on_line_segment(self, position, tolerance=1.0):
        """Check if point is aligned on a line segment between any two actuators"""
        actuator_items = list(self.actuators.items())
        
        for i in range(len(actuator_items)):
            for j in range(i+1, len(actuator_items)):
                id1, pos1 = actuator_items[i]
                id2, pos2 = actuator_items[j]
                
                # Calculate distance from point to line segment
                # Vector from pos1 to pos2
                line_vec = (pos2[0] - pos1[0], pos2[1] - pos1[1])
                line_length_sq = line_vec[0]**2 + line_vec[1]**2
                
                if line_length_sq == 0:  # pos1 and pos2 are the same point
                    continue
                
                # Vector from pos1 to position
                point_vec = (position[0] - pos1[0], position[1] - pos1[1])
                
                # Project point onto line
                t = max(0, min(1, (point_vec[0] * line_vec[0] + point_vec[1] * line_vec[1]) / line_length_sq))
                
                # Find closest point on line segment
                closest_on_line = (pos1[0] + t * line_vec[0], pos1[1] + t * line_vec[1])
                
                # Check if position is close to this line segment
                dist_to_line = self._distance(position, closest_on_line)
                
                if dist_to_line <= tolerance:
                    if self.DEBUG:
                        print(f"Point {position} is on line segment between actuators {id1} and {id2}")
                    return True, id1, id2, (1-t, t)  # Return weights for 2-actuator phantom
        
        return False, None, None, None
    
    def _calculate_2_actuator_intensities(self, phantom_pos, actuator1_id, actuator2_id, weights, desired_intensity):
        """Calculate 2-actuator phantom intensities using Park et al. Eq. (2)"""
        pos1 = self.actuators[actuator1_id]
        pos2 = self.actuators[actuator2_id]
        
        d1 = self._distance(phantom_pos, pos1)
        d2 = self._distance(phantom_pos, pos2)
        
        # Park et al. Equation (2): A1 = sqrt(d2/(d1+d2)) * Av, A2 = sqrt(d1/(d1+d2)) * Av
        A1 = math.sqrt(d2 / (d1 + d2)) * desired_intensity
        A2 = math.sqrt(d1 / (d1 + d2)) * desired_intensity
        
        if self.DEBUG:
            print(f"2-actuator phantom: {actuator1_id}={A1:.3f}, {actuator2_id}={A2:.3f}")
        
        return {
            'actuators': [actuator1_id, actuator2_id],
            'intensities': [A1, A2]
        }
    
    def _calculate_3_actuator_intensities(self, phantom_pos, triangle_actuators, desired_intensity, distances=None):
        """Calculate 3-actuator phantom intensities using Park et al. Eq. (10)"""
        if distances is None:
            distances = []
            for act_id in triangle_actuators:
                act_pos = self.actuators[act_id]
                dist = self._distance(phantom_pos, act_pos)
                distances.append(max(dist, 0.1))  # Prevent division by zero
        else:
            distances = [max(d, 0.1) for d in distances]
        
        # Park et al. Equation (10): Ai = sqrt(1/di / Σ(1/dj)) × Av
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities = []
        for i, dist in enumerate(distances):
            intensity_factor = math.sqrt((1/dist) / sum_inv_distances)
            intensity = desired_intensity * intensity_factor
            final_intensity = min(1.0, max(0.0, intensity))
            intensities.append(final_intensity)
            
            if self.DEBUG:
                print(f"  Actuator {triangle_actuators[i]}: distance={dist:.1f}, "
                      f"factor={intensity_factor:.3f}, intensity={final_intensity:.3f}")
        
        return intensities
    
    def create_phantom(self, position, intensity):
        """Create phantom sensation using exact Park et al. (2016) algorithm"""
        
        # Check if position is exactly at an actuator location
        for actuator_id, actuator_pos in self.actuators.items():
            if self._distance(position, actuator_pos) < 1.0:  # Within 1 unit
                if self.DEBUG:
                    print(f"Direct actuator {actuator_id} at {actuator_pos}")
                return {
                    'actuators': [actuator_id],
                    'intensities': [intensity]
                }
        
        # Check if point is on a line segment (use 2-actuator phantom)
        is_on_line, id1, id2, weights = self._is_on_line_segment(position)
        if is_on_line:
            return self._calculate_2_actuator_intensities(position, id1, id2, weights, intensity)
        
        # Use 3-actuator phantom: "the three closest physical tactors around the point are selected"
        closest_three = self._find_three_closest_actuators(position)
        
        # Calculate intensities using Park et al. Equation (10)
        intensities = self._calculate_3_actuator_intensities(
            position, 
            closest_three['actuators'], 
            intensity,
            distances=closest_three['distances']
        )
        
        return {
            'actuators': closest_three['actuators'],
            'intensities': intensities
        }
    
    def _resample_trajectory(self, trajectory, max_interval_s=0.07, movement_speed = MOVEMENT_SPEED):
        """Resample trajectory to meet Park et al. timing constraints"""
        if len(trajectory) < 2:
            return trajectory
        
        resampled = [trajectory[0]]  # Always include first point
        
        for i in range(1, len(trajectory)):
            prev_point = resampled[-1]
            curr_point = trajectory[i]
            
            # Calculate distance between points
            distance = self._distance(prev_point, curr_point)
            
            # Estimate required samples based on distance and timing
            estimated_time = distance / movement_speed
            
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
    
    def generate_motion_commands(self, trajectory, intensity=0.8, base_duration=0.06, 
                               movement_speed=MOVEMENT_SPEED, max_sampling_interval=0.07):
        """Generate motion commands using exact Park et al. (2016) algorithm"""
        if len(trajectory) < 1:
            return []
        
        # Enforce duration constraint from paper: duration ≤ 0.07 s
        duration = min(base_duration, self.MAX_DURATION)
        
        # "points on the path are sampled at a rate less than or equal to 0.07 s"
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
                              movement_speed=MOVEMENT_SPEED):
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

def generate_motion_pattern(devices, intensity=DUTY, freq=FREQ, duration=0.04, 
                          movement_speed=MOVEMENT_SPEED, max_sampling_interval=0.05, **kwargs):
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