import math
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass
from shared import LAYOUT_POSITIONS, MOTION_PARAMS

try:
    from Layouts.motion_actuators import get_pattern_coordinates, MOTION_PATTERNS
    MOTION_PATTERNS_AVAILABLE = True
    print("✅ Successfully imported motion_actuators")
except ImportError as e:
    print(f"⚠️ Could not import motion_actuators: {e}")
    try:
        from motion_actuators import get_pattern_coordinates, MOTION_PATTERNS
        MOTION_PATTERNS_AVAILABLE = True
        print("✅ Successfully imported motion_actuators (fallback)")
    except ImportError:
        MOTION_PATTERNS_AVAILABLE = False
        print("❌ motion_actuators not available")

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
        self.triangles = self._compute_triangles()
    
    def _compute_triangles(self):
        """Compute valid actuator triangles"""
        triangles = []
        ids = list(self.actuators.keys())
        
        for i in range(len(ids)):
            for j in range(i + 1, len(ids)):
                for k in range(j + 1, len(ids)):
                    pos1, pos2, pos3 = self.actuators[ids[i]], self.actuators[ids[j]], self.actuators[ids[k]]
                    
                    # Calculate triangle area
                    area = abs((pos1[0]*(pos2[1]-pos3[1]) + pos2[0]*(pos3[1]-pos1[1]) + pos3[0]*(pos1[1]-pos2[1])) / 2)
                    
                    if area >= MOTION_PARAMS['MIN_TRIANGLE_AREA']:
                        triangles.append({
                            'actuators': [ids[i], ids[j], ids[k]],
                            'positions': [pos1, pos2, pos3],
                            'area': area,
                            'center': ((pos1[0]+pos2[0]+pos3[0])/3, (pos1[1]+pos2[1]+pos3[1])/3)
                        })
        
        return sorted(triangles, key=lambda t: t['area'], reverse=True)
    
    def _point_in_triangle(self, point, triangle_pos):
        """Check if point is inside triangle"""
        def sign(p1, p2, p3):
            return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
        
        d1 = sign(point, triangle_pos[0], triangle_pos[1])
        d2 = sign(point, triangle_pos[1], triangle_pos[2])
        d3 = sign(point, triangle_pos[2], triangle_pos[0])
        
        has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
        has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
        
        return not (has_neg and has_pos)
    
    def _find_best_triangle(self, position):
        """Find best triangle for phantom placement"""
        # Try containing triangles first
        for triangle in self.triangles:
            if self._point_in_triangle(position, triangle['positions']):
                return triangle
        
        # Find closest by center distance
        if self.triangles:
            return min(self.triangles, 
                    key=lambda t: math.sqrt((position[0] - t['center'][0])**2 + (position[1] - t['center'][1])**2))
        return None
    
    def _calculate_phantom_intensities(self, phantom_pos, triangle_actuators, desired_intensity):
        """Calculate 3-actuator phantom intensities using Park et al. energy model"""
        distances = []
        for act_id in triangle_actuators:
            act_pos = self.actuators[act_id]
            dist = math.sqrt((phantom_pos[0] - act_pos[0])**2 + (phantom_pos[1] - act_pos[1])**2)
            distances.append(max(dist, 0.1))
        
        # Park et al. energy model: Ai = √(1/di / Σ(1/dj)) × Av
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities = []
        for dist in distances:
            intensity_factor = math.sqrt((1/dist) / sum_inv_distances)
            intensity = intensity_factor * desired_intensity
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
        
        # Only use triangulation for positions NOT at exact actuator locations
        triangle = self._find_best_triangle(position)
        if not triangle:
            return None
        
        intensities = self._calculate_phantom_intensities(position, triangle['actuators'], intensity)
        
        return {
            'actuators': triangle['actuators'],
            'intensities': intensities
        }
    
    def generate_trajectory(self, pattern_type, **kwargs):
        """Generate trajectory coordinates for motion patterns"""
        
        # Try to get coordinates from motion_actuators.py first
        if MOTION_PATTERNS_AVAILABLE:
            try:
                trajectory = get_pattern_coordinates(pattern_type)
                if trajectory:
                    return trajectory
            except:
                pass
        
        # Built-in trajectory generators
        if pattern_type == "circle":
            return self._generate_circle_trajectory(**kwargs)
        elif pattern_type == "line":
            return self._generate_line_trajectory(**kwargs)
        elif pattern_type == "spiral":
            return self._generate_spiral_trajectory(**kwargs)
        else:
            # Default to small circle
            return self._generate_circle_trajectory(center=(50, 50), radius=30)
    
    def _generate_circle_trajectory(self, center=(50, 50), radius=30, num_points=16):
        """Generate circular trajectory"""
        trajectory = []
        for i in range(num_points):
            angle = 2 * math.pi * i / num_points
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            trajectory.append((x, y))
        return trajectory
    
    def _generate_line_trajectory(self, start=(20, 50), end=(80, 50), num_points=10):
        """Generate linear trajectory"""
        trajectory = []
        for i in range(num_points):
            t = i / (num_points - 1) if num_points > 1 else 0
            x = start[0] + t * (end[0] - start[0])
            y = start[1] + t * (end[1] - start[1])
            trajectory.append((x, y))
        return trajectory
    
    def _generate_spiral_trajectory(self, center=(50, 50), max_radius=40, num_turns=2, num_points=32):
        """Generate spiral trajectory"""
        trajectory = []
        for i in range(num_points):
            t = i / (num_points - 1)
            angle = 2 * math.pi * num_turns * t
            radius = max_radius * t
            x = center[0] + radius * math.cos(angle)
            y = center[1] + radius * math.sin(angle)
            trajectory.append((x, y))
        return trajectory
    
    def generate_motion_commands(self, trajectory, velocity=60.0, intensity=0.8, duration=0.06):
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

def generate_coordinate_pattern(coordinates, velocity=60, intensity=8, freq=3, duration=0.06):
    """
    Generate motion pattern from coordinate list.
    This is a wrapper around generate_motion_pattern for coordinate-only trajectories.
    
    Args:
        coordinates: List of coordinate tuples [(x1,y1), (x2,y2), ...]
        velocity: Motion velocity (affects timing between points)
        intensity: Vibration intensity (1-15)
        freq: Vibration frequency
        duration: Duration of each vibration point in seconds
    
    Returns:
        List of command dictionaries for the motion pattern
    """
    
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
        velocity=velocity,
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
# FIVE MAIN PATTERN FUNCTIONS
# ================================

def generate_static_pattern(devices, duty=8, freq=3, duration=2000):
    """Generate static vibration pattern for all devices"""
    commands = []
    
    # Start all devices immediately
    for addr in devices:
        commands.append({
            "addr": addr,
            "duty": duty,
            "freq": freq,
            "start_or_stop": 1,
            "delay_ms": 0
        })
    
    # Stop all devices after duration
    for addr in devices:
        commands.append({
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
            "delay_ms": duration
        })
    
    return commands

def generate_pulse_pattern(devices, duty=8, freq=3, pulse_duration=500, pause_duration=500, num_pulses=3):
    """Generate pulsed vibration pattern"""
    commands = []
    
    for pulse_num in range(num_pulses):
        # Calculate timing for this pulse
        pulse_start_time = pulse_num * (pulse_duration + pause_duration)
        pulse_stop_time = pulse_start_time + pulse_duration
        
        # Start all devices for this pulse
        for addr in devices:
            commands.append({
                "addr": addr,
                "duty": duty,
                "freq": freq,
                "start_or_stop": 1,
                "delay_ms": pulse_start_time
            })
        
        # Stop all devices after pulse duration
        for addr in devices:
            commands.append({
                "addr": addr,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                "delay_ms": pulse_stop_time
            })
    
    return commands

def generate_motion_pattern(devices, motion_type="circle", velocity=60, intensity=8, freq=3, duration=0.06, **kwargs):
    """
    Generate motion pattern using the exact devices/coordinates provided.
    
    Args:
        devices: Either:
                - List of device addresses: [0, 1, 2, 3]
                - Mixed list of addresses and coordinates: [0, (30,0), 1, (60,0)]
                - Pure coordinates: [(30,0), (60,0), (90,0)]
        velocity: Motion velocity (affects timing between points)
        intensity: Vibration intensity (1-15)
        freq: Vibration frequency
        duration: Duration of each vibration point in seconds
    
    Returns:
        List of command dictionaries for the motion pattern
    """
    
    engine = get_motion_engine()
    
    # Convert everything to coordinates for consistent processing
    coordinates = _convert_to_coordinates(devices)
    
    if len(coordinates) < 1:
        print("Warning: No valid coordinates found")
        return []
    
    # Use the exact coordinates provided - no built-in pattern generation
    trajectory = coordinates
    available_devices = set(LAYOUT_POSITIONS.keys())  # Use all available devices for phantom sensations
    
    # Generate motion commands
    motion_commands = engine.generate_motion_commands(
        trajectory,
        velocity=velocity,
        intensity=intensity / 15.0,  # Convert to 0-1 scale
        duration=duration
    )
    
    # Convert to command format
    commands = []
    
    for cmd in motion_commands:
        if cmd.actuator_id in available_devices:
            device_intensity = max(1, min(15, int(cmd.intensity * 15)))
            
            # Start command
            commands.append({
                "addr": cmd.actuator_id,
                "duty": device_intensity,
                "freq": freq,
                "start_or_stop": 1,
                "delay_ms": int(cmd.onset_time * 1000)
            })
            
            # Stop command
            commands.append({
                "addr": cmd.actuator_id,
                "duty": 0,
                "freq": 0,
                "start_or_stop": 0,
                "delay_ms": int((cmd.onset_time + cmd.duration) * 1000)
            })
    
    # Sort by delay time
    commands.sort(key=lambda x: x['delay_ms'])
    
    return commands

def generate_sequential_pattern(devices, duty=8, freq=3, duration_per_device=500, pause_between=100):
    """Generate sequential activation pattern through devices in order"""
    commands = []
    current_time = 0
    
    for addr in devices:
        # Start this device
        commands.append({
            "addr": addr,
            "duty": duty,
            "freq": freq,
            "start_or_stop": 1,
            "delay_ms": current_time
        })
        
        # Stop this device
        commands.append({
            "addr": addr,
            "duty": 0,
            "freq": 0,
            "start_or_stop": 0,
            "delay_ms": current_time + duration_per_device
        })
        
        # Move to next device timing
        current_time += duration_per_device + pause_between
    
    return commands