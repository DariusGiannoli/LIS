
import math
from typing import List, Tuple, Dict, Optional
from dataclasses import dataclass
from shared import LAYOUT_POSITIONS, MOTION_PARAMS

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
        triangle = self._find_best_triangle(position)
        if not triangle:
            return None
        
        intensities = self._calculate_phantom_intensities(position, triangle['actuators'], intensity)
        
        return {
            'actuators': triangle['actuators'],
            'intensities': intensities
        }
    
    def generate_trajectory(self, pattern_type, **kwargs):
    
    # Try to get coordinates from shared.py first
        try:
            trajectory = get_pattern_coordinates(pattern_type)
            if trajectory:
                return trajectory
        except:
            pass
    
    
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

# Global motion engine
_motion_engine = None

def get_motion_engine():
    global _motion_engine
    if _motion_engine is None:
        _motion_engine = MotionEngine()
    return _motion_engine

# ================================
# THREE MAIN PATTERN FUNCTIONS
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

def generate_motion_pattern(devices, motion_type="circle", velocity=60, intensity=8, freq=3, **kwargs):

    engine = get_motion_engine()
    
    # Generate trajectory
    trajectory = engine.generate_trajectory(motion_type, **kwargs)
    
    # Generate motion commands
    motion_commands = engine.generate_motion_commands(
        trajectory,
        velocity=velocity,
        intensity=intensity / 15.0,  # Convert to 0-1 scale
        duration=0.06
    )
    
    # Convert to command format
    commands = []
    available_devices = set(devices) if devices else set(LAYOUT_POSITIONS.keys())
    
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