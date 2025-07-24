#!/usr/bin/env python3
"""
Complete Enhanced Interactive Tactile Pattern Creator with Trajectory Support
Park et al. (2016) Implementation with Smooth Trajectory Drawing

Features:
- 3-actuator phantom sensations for arbitrary 2D positioning
- Trajectory drawing with automatic phantom creation
- Non-overlapping SOA constraints (duration ≤ 70ms)
- Smooth motion along curved paths
- Real-time visualization and interaction
"""
import sys
import time
import math
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QApplication, QMainWindow, QComboBox, QTextEdit, QSlider,
    QCheckBox, QTabWidget, QFileDialog, QListWidget, QMessageBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QMouseEvent

# Import your API (optional)
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found. Running in simulation mode.")
    python_serial_api = None

# 4x4 Grid Configuration
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
GRID_ROWS = 4
GRID_COLS = 4

USER_LAYOUT = [
    [0, 1, 2, 3],      # Row 0
    [7, 6, 5, 4],      # Row 1
    [8, 9, 10, 11],    # Row 2
    [15, 14, 13, 12]   # Row 3
]

# Park et al. (2016) parameters
PAPER_PARAMS = {
    'SOA_SLOPE': 0.32,
    'SOA_BASE': 47.3,  # in ms (converted from 0.0473s)
    'MIN_DURATION': 40,
    'MAX_DURATION': 70,  # Maximum 70ms to prevent overlapping
    'OPTIMAL_FREQ': 250,  # 250Hz optimal frequency
    'SAMPLING_RATE': 70,  # Maximum sampling rate 70ms
}

def get_grid_position(actuator_id: int, spacing_mm: float) -> Tuple[float, float]:
    """Convert actuator ID to (x, y) position in mm for user's 4x4 layout"""
    if actuator_id < 0 or actuator_id >= 16:
        raise ValueError(f"Invalid actuator ID {actuator_id} for 4x4 grid")
    
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            if USER_LAYOUT[row][col] == actuator_id:
                x_positions = [0, 50, 110, 160]
                y_positions = [0, 60, 120, 180]
                x = x_positions[col]
                y = y_positions[row]
                return (x, y)
    
    raise ValueError(f"Actuator ID {actuator_id} not found in layout")

def get_actuator_id(row: int, col: int) -> int:
    """Convert grid (row, col) to actuator ID using user's layout"""
    if row < 0 or row >= GRID_ROWS or col < 0 or col >= GRID_COLS:
        return -1
    return USER_LAYOUT[row][col]

def point_in_triangle(p: Tuple[float, float], a: Tuple[float, float], 
                     b: Tuple[float, float], c: Tuple[float, float]) -> bool:
    """Check if point p is inside triangle abc using barycentric coordinates"""
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    
    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)
    
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    
    return not (has_neg and has_pos)

@dataclass
class SOAStep:
    actuator_id: int
    onset_time: float
    duration: float
    intensity: int

@dataclass
class PatternStep:
    actuator_id: int
    timestamp: float
    duration: float
    intensity: int

@dataclass
class TactilePattern:
    name: str
    steps: List[PatternStep]
    total_duration: float
    created_timestamp: float

    def to_dict(self):
        return {
            'name': self.name,
            'steps': [asdict(step) for step in self.steps],
            'total_duration': self.total_duration,
            'created_timestamp': self.created_timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        steps = [PatternStep(**step_data) for step_data in data['steps']]
        return cls(
            name=data['name'],
            steps=steps,
            total_duration=data['total_duration'],
            created_timestamp=data['created_timestamp']
        )

@dataclass
class Enhanced3ActuatorPhantom:
    """Enhanced phantom using 3-actuator system from Park et al."""
    phantom_id: int
    virtual_position: Tuple[float, float]
    physical_actuator_1: int
    physical_actuator_2: int
    physical_actuator_3: int
    desired_intensity: int
    required_intensity_1: int
    required_intensity_2: int
    required_intensity_3: int
    triangle_area: float
    energy_efficiency: float
    timestamp: float = 0.0  # For trajectory phantoms

class EnhancedTactileEngine:
    """Enhanced engine with 3-actuator phantoms and trajectory support"""
    
    def __init__(self, api=None, actuator_spacing_mm=63):
        self.api = api
        self.actuator_spacing = actuator_spacing_mm
        self.use_custom_positions = True
        self.custom_positions = {}
        
        # SOA state
        self.soa_steps = []
        self.soa_timer = QTimer()
        self.soa_timer.timeout.connect(self.execute_soa_step)
        self.soa_start_time = 0
        self.soa_next_step_idx = 0
        self.soa_active_actuators = {}
        
        # Enhanced phantom state
        self.enhanced_phantoms = []
        self.actuator_triangles = []
        
        # Trajectory state for Park et al. path following
        self.current_trajectory = []  # Raw trajectory points
        self.trajectory_phantoms = []  # Phantoms created from trajectory
        self.trajectory_mode = False  # Toggle for trajectory creation mode
        self.trajectory_sampling_rate = 70  # ms, respecting Park et al. constraints
        
        # Pattern recording state
        self.is_recording = False
        self.recording_start_time = 0
        self.current_pattern_steps = []
        self.current_pattern_name = ""
        self.saved_patterns = {}
        
        # Mouse interaction state
        self.mouse_hover_actuator = None
        self.mouse_vibration_active = False
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.stop_hover_vibration)
        self.hover_timer.setSingleShot(True)
        
        # Enhanced pattern parameters
        self.pattern_duration = 60
        self.pattern_intensity = 8
        self.use_enhanced_phantoms = True
        
        self.load_user_custom_positions()
        self.update_grid_positions()
        self.compute_actuator_triangles()
    
    def load_user_custom_positions(self):
        """Load the user's specific custom positions"""
        user_positions = {
            3:  (0,   0),   2:  (50,  0),   1:  (110, 0),   0:  (160, 0),
            4:  (0,   60),  5:  (50,  60),  6:  (110, 60),  7:  (160, 60),
            11: (0,   120), 10: (50,  120), 9:  (110, 120), 8:  (160, 120),
            12: (0,   180), 13: (50,  180), 14: (110, 180), 15: (160, 180)
        }
        self.custom_positions = user_positions
        print(f"🎯 Loaded user's custom positions with enhanced 3-actuator phantom support")
    
    def compute_actuator_triangles(self):
        """Systematic triangulation for smooth phantom motion"""
        self.actuator_triangles = []
        positions = self.actuator_positions
        
        print(f"🔺 Computing systematic triangulation for 4x4 grid...")
        
        triangles_added = 0
        
        # Grid-based systematic triangulation
        for row in range(GRID_ROWS - 1):
            for col in range(GRID_COLS - 1):
                top_left = get_actuator_id(row, col)
                top_right = get_actuator_id(row, col + 1)  
                bottom_left = get_actuator_id(row + 1, col)
                bottom_right = get_actuator_id(row + 1, col + 1)
                
                if -1 in [top_left, top_right, bottom_left, bottom_right]:
                    continue
                
                # Two triangles from rectangular cell
                triangle1_acts = [top_left, top_right, bottom_left]
                triangle1_pos = [positions[act] for act in triangle1_acts]
                
                triangle2_acts = [top_right, bottom_left, bottom_right]
                triangle2_pos = [positions[act] for act in triangle2_acts]
                
                for triangle_acts, triangle_pos, tri_name in [
                    (triangle1_acts, triangle1_pos, "upper"),
                    (triangle2_acts, triangle2_pos, "lower")
                ]:
                    area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                              triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                              triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
                    
                    if area > 50:
                        triangle = {
                            'actuators': triangle_acts,
                            'positions': triangle_pos,
                            'area': area,
                            'center': ((triangle_pos[0][0]+triangle_pos[1][0]+triangle_pos[2][0])/3, 
                                     (triangle_pos[0][1]+triangle_pos[1][1]+triangle_pos[2][1])/3),
                            'type': f'grid_{row}_{col}_{tri_name}',
                            'smoothness_score': self.calculate_triangle_smoothness(triangle_pos)
                        }
                        self.actuator_triangles.append(triangle)
                        triangles_added += 1
        
        # Add adjacent triangles for better coverage
        edge_triangles = 0
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                center_act = get_actuator_id(row, col)
                if center_act == -1:
                    continue
                    
                center_pos = positions[center_act]
                
                nearby_actuators = []
                max_distance = 85  # mm
                
                for other_row in range(GRID_ROWS):
                    for other_col in range(GRID_COLS):
                        other_act = get_actuator_id(other_row, other_col)
                        if other_act == -1 or other_act == center_act:
                            continue
                            
                        other_pos = positions[other_act]
                        distance = math.sqrt((center_pos[0]-other_pos[0])**2 + (center_pos[1]-other_pos[1])**2)
                        
                        if distance <= max_distance:
                            nearby_actuators.append((other_act, other_pos, distance))
                
                nearby_actuators.sort(key=lambda x: x[2])
                
                for i in range(len(nearby_actuators)-1):
                    for j in range(i+1, min(i+3, len(nearby_actuators))):
                        act1, pos1, _ = nearby_actuators[i]
                        act2, pos2, _ = nearby_actuators[j]
                        
                        triangle_acts = [center_act, act1, act2]
                        triangle_pos = [center_pos, pos1, pos2]
                        
                        exists = any(set(t['actuators']) == set(triangle_acts) for t in self.actuator_triangles)
                        if exists:
                            continue
                        
                        area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                                  triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                                  triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
                        
                        if area > 50 and area < 3000:
                            triangle = {
                                'actuators': triangle_acts,
                                'positions': triangle_pos,
                                'area': area,
                                'center': ((triangle_pos[0][0]+triangle_pos[1][0]+triangle_pos[2][0])/3, 
                                         (triangle_pos[0][1]+triangle_pos[1][1]+triangle_pos[2][1])/3),
                                'type': f'local_{center_act}_{act1}_{act2}',
                                'smoothness_score': self.calculate_triangle_smoothness(triangle_pos)
                            }
                            self.actuator_triangles.append(triangle)
                            edge_triangles += 1
        
        self.actuator_triangles.sort(key=lambda t: (t['smoothness_score'], t['area']))
        
        print(f"🔺 Total: {len(self.actuator_triangles)} optimized triangles for smooth phantom motion")
    
    def calculate_triangle_smoothness(self, triangle_pos: List[Tuple[float, float]]) -> float:
        """Calculate smoothness score for triangle"""
        perimeter = 0
        for i in range(3):
            j = (i + 1) % 3
            dist = math.sqrt((triangle_pos[i][0] - triangle_pos[j][0])**2 + 
                           (triangle_pos[i][1] - triangle_pos[j][1])**2)
            perimeter += dist
        
        area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                   triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                   triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
        
        if area > 0:
            aspect_penalty = (perimeter ** 2) / (12 * math.sqrt(3) * area)
        else:
            aspect_penalty = 1000
        
        return perimeter * 0.1 + aspect_penalty
    
    def find_best_triangle_for_position(self, pos: Tuple[float, float]) -> Optional[Dict]:
        """Find optimal triangle for smooth phantom motion"""
        # Find triangles that contain the point
        containing_triangles = []
        for triangle in self.actuator_triangles:
            if point_in_triangle(pos, *triangle['positions']):
                containing_triangles.append(triangle)
        
        if containing_triangles:
            best_triangle = min(containing_triangles, key=lambda t: t['smoothness_score'])
            return best_triangle
        
        # Find closest triangles by center distance
        triangle_scores = []
        for triangle in self.actuator_triangles:
            center_dist = math.sqrt((pos[0] - triangle['center'][0])**2 + (pos[1] - triangle['center'][1])**2)
            combined_score = center_dist * 0.5 + triangle['smoothness_score'] * 10
            triangle_scores.append((combined_score, triangle, center_dist))
        
        if triangle_scores:
            triangle_scores.sort(key=lambda x: x[0])
            best_score, best_triangle, distance = triangle_scores[0]
            return best_triangle
        
        return None
    
    def calculate_3actuator_intensities(self, phantom_pos: Tuple[float, float], 
                                      triangle: Dict, desired_intensity: int) -> Tuple[int, int, int]:
        """Calculate intensities for 3-actuator phantom using Park et al. energy model"""
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        positions = triangle['positions']
        
        distances = []
        for pos in positions:
            dist = math.sqrt((phantom_pos[0] - pos[0])**2 + (phantom_pos[1] - pos[1])**2)
            distances.append(max(dist, 1.0))
        
        # Park et al. energy summation model: Ai = sqrt(1/di / sum(1/dj)) * Av
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities_norm = []
        for dist in distances:
            intensity_norm = math.sqrt((1/dist) / sum_inv_distances) * (desired_intensity / 15.0)
            intensities_norm.append(intensity_norm)
        
        device_intensities = []
        for intensity_norm in intensities_norm:
            device_intensity = max(1, min(15, round(intensity_norm * 15)))
            device_intensities.append(device_intensity)
        
        return tuple(device_intensities)
    
    def create_enhanced_phantom(self, phantom_pos: Tuple[float, float], 
                              desired_intensity: int) -> Optional[Enhanced3ActuatorPhantom]:
        """Create enhanced 3-actuator phantom following Park et al. methodology"""
        if desired_intensity < 1 or desired_intensity > 15:
            return None
        
        triangle = self.find_best_triangle_for_position(phantom_pos)
        if not triangle:
            return None
        
        try:
            intensities = self.calculate_3actuator_intensities(phantom_pos, triangle, desired_intensity)
        except ValueError:
            return None
        
        total_energy = sum(i**2 for i in intensities)
        theoretical_energy = desired_intensity**2
        efficiency = theoretical_energy / total_energy if total_energy > 0 else 0
        
        phantom_id = len(self.enhanced_phantoms)
        
        phantom = Enhanced3ActuatorPhantom(
            phantom_id=phantom_id,
            virtual_position=phantom_pos,
            physical_actuator_1=triangle['actuators'][0],
            physical_actuator_2=triangle['actuators'][1],
            physical_actuator_3=triangle['actuators'][2],
            desired_intensity=desired_intensity,
            required_intensity_1=intensities[0],
            required_intensity_2=intensities[1],
            required_intensity_3=intensities[2],
            triangle_area=triangle['area'],
            energy_efficiency=efficiency
        )
        
        self.enhanced_phantoms.append(phantom)
        return phantom
    
    def calculate_enhanced_soa(self, duration_ms: float) -> float:
        """Enhanced SOA calculation with non-overlapping constraint"""
        soa = PAPER_PARAMS['SOA_SLOPE'] * duration_ms + PAPER_PARAMS['SOA_BASE']
        
        if soa <= duration_ms:
            soa = duration_ms + 1
        
        return soa
    
    def update_grid_positions(self):
        """Update actuator positions"""
        self.actuator_positions = {}
        
        if self.use_custom_positions and self.custom_positions:
            for actuator_id in ACTUATORS:
                if actuator_id in self.custom_positions:
                    self.actuator_positions[actuator_id] = self.custom_positions[actuator_id]
                else:
                    x, y = get_grid_position(actuator_id, self.actuator_spacing)
                    self.actuator_positions[actuator_id] = (x, y)
        else:
            for actuator_id in ACTUATORS:
                x, y = get_grid_position(actuator_id, self.actuator_spacing)
                self.actuator_positions[actuator_id] = (x, y)
        
        if hasattr(self, 'actuator_positions'):
            self.compute_actuator_triangles()
    
    # Trajectory methods
    def start_trajectory_mode(self):
        """Enable trajectory drawing mode"""
        self.trajectory_mode = True
        self.current_trajectory = []
        self.trajectory_phantoms = []
        print("🎨 Trajectory mode enabled")
    
    def stop_trajectory_mode(self):
        """Disable trajectory drawing mode"""
        self.trajectory_mode = False
        print("🎨 Trajectory mode disabled")
    
    def add_trajectory_point(self, point: Tuple[float, float]):
        """Add point to current trajectory"""
        if self.trajectory_mode:
            self.current_trajectory.append(point)
    
    def finish_trajectory(self):
        """Finish trajectory and create phantoms along the path"""
        if len(self.current_trajectory) < 2:
            return False
        
        trajectory_samples = self.sample_trajectory_points(
            self.current_trajectory, 
            self.trajectory_sampling_rate
        )
        
        self.trajectory_phantoms = []
        phantom_count = 0
        
        for sample in trajectory_samples:
            phantom = self.create_enhanced_phantom(sample['position'], self.pattern_intensity)
            if phantom:
                phantom.timestamp = sample['timestamp']
                self.trajectory_phantoms.append(phantom)
                phantom_count += 1
        
        print(f"✅ Created {phantom_count} trajectory phantoms")
        return phantom_count > 0
    
    def sample_trajectory_points(self, trajectory: List[Tuple[float, float]], 
                               sampling_rate_ms: float) -> List[Dict]:
        """Sample points along trajectory respecting Park et al. constraints"""
        if len(trajectory) < 2:
            return []
        
        samples = []
        total_length = self.calculate_trajectory_length(trajectory)
        soa = self.calculate_enhanced_soa(self.pattern_duration)
        actual_sampling_rate = min(sampling_rate_ms, soa)
        
        min_spacing = 30
        max_samples = max(2, int(total_length / min_spacing))
        time_based_samples = max(2, int(total_length / 50))
        
        num_samples = min(max_samples, time_based_samples)
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            point = self.interpolate_trajectory(trajectory, t)
            timestamp = i * actual_sampling_rate
            
            samples.append({
                'position': point,
                'timestamp': timestamp,
                'index': i,
                'parameter': t
            })
        
        return samples
    
    def calculate_trajectory_length(self, points: List[Tuple[float, float]]) -> float:
        """Calculate total length of trajectory"""
        if len(points) < 2:
            return 0
        
        length = 0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            length += math.sqrt(dx * dx + dy * dy)
        
        return length
    
    def interpolate_trajectory(self, points: List[Tuple[float, float]], 
                             t: float) -> Tuple[float, float]:
        """Interpolate point along trajectory using parameter t (0 to 1)"""
        if len(points) < 2:
            return points[0] if points else (0, 0)
        if t <= 0:
            return points[0]
        if t >= 1:
            return points[-1]
        
        total_length = self.calculate_trajectory_length(points)
        target_length = t * total_length
        
        current_length = 0
        for i in range(1, len(points)):
            segment_length = math.sqrt(
                (points[i][0] - points[i-1][0])**2 + 
                (points[i][1] - points[i-1][1])**2
            )
            
            if current_length + segment_length >= target_length:
                segment_t = (target_length - current_length) / segment_length if segment_length > 0 else 0
                x = points[i-1][0] + segment_t * (points[i][0] - points[i-1][0])
                y = points[i-1][1] + segment_t * (points[i][1] - points[i-1][1])
                return (x, y)
            
            current_length += segment_length
        
        return points[-1]
    
    def play_trajectory_phantoms(self):
        """Play trajectory phantoms in sequence with SOA timing"""
        if not self.trajectory_phantoms:
            return
        
        soa_steps = []
        for phantom in self.trajectory_phantoms:
            for phys_id, intensity in [
                (phantom.physical_actuator_1, phantom.required_intensity_1),
                (phantom.physical_actuator_2, phantom.required_intensity_2),
                (phantom.physical_actuator_3, phantom.required_intensity_3)
            ]:
                soa_step = SOAStep(
                    actuator_id=phys_id,
                    onset_time=phantom.timestamp,
                    duration=self.pattern_duration,
                    intensity=intensity
                )
                soa_steps.append(soa_step)
        
        soa_steps.sort(key=lambda step: step.onset_time)
        self.execute_soa_sequence(soa_steps)
    
    def clear_trajectory(self):
        """Clear current trajectory and trajectory phantoms"""
        self.current_trajectory = []
        
        if self.trajectory_phantoms:
            trajectory_phantom_ids = {p.phantom_id for p in self.trajectory_phantoms}
            self.enhanced_phantoms = [p for p in self.enhanced_phantoms 
                                   if p.phantom_id not in trajectory_phantom_ids]
            
            for i, phantom in enumerate(self.enhanced_phantoms):
                phantom.phantom_id = i
        
        self.trajectory_phantoms = []
    
    def set_trajectory_sampling_rate(self, rate_ms: int):
        """Set trajectory sampling rate with SOA constraint"""
        soa = self.calculate_enhanced_soa(self.pattern_duration)
        actual_rate = min(rate_ms, soa)
        self.trajectory_sampling_rate = actual_rate
    
    # Mouse interaction and other methods
    def on_mouse_hover(self, target_id: int, is_phantom: bool = False):
        """Handle mouse hover over actuator or phantom"""
        current_target = f"{'P' if is_phantom else 'A'}{target_id}"
        if current_target == self.mouse_hover_actuator:
            return
        
        self.stop_hover_vibration()
        self.mouse_hover_actuator = current_target
        
        if self.api and self.api.connected:
            freq = 4
            
            if is_phantom:
                if target_id < len(self.enhanced_phantoms):
                    phantom = self.enhanced_phantoms[target_id]
                    
                    success1 = self.api.send_command(phantom.physical_actuator_1, phantom.required_intensity_1, freq, 1)
                    success2 = self.api.send_command(phantom.physical_actuator_2, phantom.required_intensity_2, freq, 1)
                    success3 = self.api.send_command(phantom.physical_actuator_3, phantom.required_intensity_3, freq, 1)
                    
                    if success1 and success2 and success3:
                        self.mouse_vibration_active = True
                        self.hover_timer.start(self.pattern_duration)
            else:
                success = self.api.send_command(target_id, self.pattern_intensity, freq, 1)
                if success:
                    self.mouse_vibration_active = True
                    self.hover_timer.start(self.pattern_duration)
        else:
            self.mouse_vibration_active = False
    
    def on_mouse_leave(self):
        """Handle mouse leaving actuator area"""
        self.stop_hover_vibration()
        self.mouse_hover_actuator = None
    
    def stop_hover_vibration(self):
        """Stop current hover vibration"""
        if self.mouse_vibration_active and self.mouse_hover_actuator is not None:
            if self.api and self.api.connected:
                if self.mouse_hover_actuator.startswith('P'):
                    phantom_id = int(self.mouse_hover_actuator[1:])
                    if phantom_id < len(self.enhanced_phantoms):
                        phantom = self.enhanced_phantoms[phantom_id]
                        self.api.send_command(phantom.physical_actuator_1, 0, 0, 0)
                        self.api.send_command(phantom.physical_actuator_2, 0, 0, 0)
                        self.api.send_command(phantom.physical_actuator_3, 0, 0, 0)
                else:
                    actuator_id = int(self.mouse_hover_actuator[1:])
                    self.api.send_command(actuator_id, 0, 0, 0)
                    
            self.mouse_vibration_active = False
    
    def execute_soa_sequence(self, steps: List[SOAStep]):
        """Execute SOA sequence with precise timing"""
        if not self.api or not self.api.connected:
            print("No API connection - running in simulation mode")
            return
        
        self.soa_steps = steps
        self.soa_next_step_idx = 0
        self.soa_active_actuators = {}
        
        if not self.soa_steps:
            return
        
        self.soa_start_time = time.time() * 1000
        self.soa_timer.start(1)
    
    def execute_soa_step(self):
        """Execute SOA step with enhanced timing"""
        current_time = time.time() * 1000 - self.soa_start_time
        
        # Start new steps
        while (self.soa_next_step_idx < len(self.soa_steps) and 
               self.soa_steps[self.soa_next_step_idx].onset_time <= current_time):
            
            step = self.soa_steps[self.soa_next_step_idx]
            device_intensity = max(1, min(15, step.intensity))
            freq = 4
            
            if self.api and self.api.connected:
                success = self.api.send_command(step.actuator_id, device_intensity, freq, 1)
                
                if success:
                    stop_time = current_time + step.duration
                    self.soa_active_actuators[step.actuator_id] = stop_time
            
            self.soa_next_step_idx += 1
        
        # Stop actuators when duration expires
        to_stop = []
        for actuator_id, stop_time in self.soa_active_actuators.items():
            if current_time >= stop_time:
                if self.api and self.api.connected:
                    self.api.send_command(actuator_id, 0, 0, 0)
                to_stop.append(actuator_id)
        
        for actuator_id in to_stop:
            del self.soa_active_actuators[actuator_id]
        
        if (self.soa_next_step_idx >= len(self.soa_steps) and 
            len(self.soa_active_actuators) == 0):
            self.soa_timer.stop()
    
    def set_pattern_parameters(self, duration: int, intensity: int):
        """Set parameters for pattern creation"""
        duration = min(duration, PAPER_PARAMS['MAX_DURATION'])
        self.pattern_duration = duration
        self.pattern_intensity = intensity
    
    def clear_enhanced_phantoms(self):
        """Clear all enhanced phantoms"""
        self.enhanced_phantoms = []
        self.trajectory_phantoms = []

class EnhancedTactileVisualization(QWidget):
    """Enhanced visualization with trajectory drawing support"""
    
    actuator_hovered = pyqtSignal(int)
    phantom_hovered = pyqtSignal(int)
    mouse_left = pyqtSignal()
    trajectory_drawn = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 400)
        self.setMouseTracking(True)
        self.engine = None
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}
        self.hover_radius = 20
        self.phantom_hover_radius = 25
        self.show_triangles = False
        
        # Trajectory drawing state
        self.is_drawing_trajectory = False
        self.trajectory_start_pos = None
        
    def set_engine(self, engine: EnhancedTactileEngine):
        self.engine = engine
        self.update()
    
    def toggle_triangles(self, show: bool):
        self.show_triangles = show
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events for trajectory drawing"""
        if not self.engine:
            return
        
        if self.engine.trajectory_mode and event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing_trajectory = True
            mouse_pos = event.position()
            self.trajectory_start_pos = mouse_pos
            
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.engine.current_trajectory = [physical_pos]
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events for hover detection and trajectory drawing"""
        if not self.engine:
            return
        
        mouse_pos = event.position()
        
        # Handle trajectory drawing
        if self.is_drawing_trajectory and self.engine.trajectory_mode:
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                if (not self.engine.current_trajectory or 
                    self.distance_between_points(physical_pos, self.engine.current_trajectory[-1]) > 5):
                    self.engine.add_trajectory_point(physical_pos)
                    self.update()
            return
        
        # Normal hover detection
        if not self.engine.trajectory_mode:
            hovered_phantom = self.get_phantom_at_position(mouse_pos)
            if hovered_phantom is not None:
                self.phantom_hovered.emit(hovered_phantom)
                return
            
            hovered_actuator = self.get_actuator_at_position(mouse_pos)
            if hovered_actuator is not None:
                self.actuator_hovered.emit(hovered_actuator)
            else:
                self.mouse_left.emit()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events to finish trajectory drawing"""
        if not self.engine:
            return
        
        if (self.is_drawing_trajectory and self.engine.trajectory_mode and 
            event.button() == Qt.MouseButton.LeftButton):
            
            self.is_drawing_trajectory = False
            
            if len(self.engine.current_trajectory) >= 2:
                success = self.engine.finish_trajectory()
                if success:
                    self.trajectory_drawn.emit()
            else:
                self.engine.current_trajectory = []
            
            self.update()
    
    def leaveEvent(self, event):
        """Handle mouse leaving the widget"""
        self.mouse_left.emit()
    
    def distance_between_points(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        """Calculate distance between two points"""
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def screen_to_physical(self, screen_pos: QPointF) -> Optional[Tuple[float, float]]:
        """Convert screen position to physical actuator space position"""
        if not self.engine or not self.engine.actuator_positions:
            return None
        
        positions = list(self.engine.actuator_positions.values())
        if not positions:
            return None
        
        x_coords = [pos[0] for pos in positions]
        y_coords = [pos[1] for pos in positions]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        margin = 60
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 120
        
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.8
        
        physical_x = (screen_pos.x() - margin) / scale + min_x
        physical_y = (screen_pos.y() - margin - 25) / scale + min_y
        
        return (physical_x, physical_y)
    
    def get_actuator_at_position(self, pos: QPointF) -> Optional[int]:
        """Get actuator ID at mouse position"""
        for actuator_id, screen_pos in self.actuator_screen_positions.items():
            distance = math.sqrt((pos.x() - screen_pos[0])**2 + (pos.y() - screen_pos[1])**2)
            if distance <= self.hover_radius:
                return actuator_id
        return None
    
    def get_phantom_at_position(self, pos: QPointF) -> Optional[int]:
        """Get phantom ID at mouse position"""
        for phantom_id, screen_pos in self.phantom_screen_positions.items():
            distance = math.sqrt((pos.x() - screen_pos[0])**2 + (pos.y() - screen_pos[1])**2)
            if distance <= self.phantom_hover_radius:
                return phantom_id
        return None
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.engine:
            painter.drawText(20, 50, "No engine connected")
            return
        
        positions = list(self.engine.actuator_positions.values())
        if not positions:
            painter.drawText(20, 50, "No actuator positions available")
            return
        
        x_coords = [pos[0] for pos in positions]
        y_coords = [pos[1] for pos in positions]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        margin = 60
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 120
        
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.8
        
        def pos_to_screen(pos):
            screen_x = margin + (pos[0] - min_x) * scale
            screen_y = margin + 25 + (pos[1] - min_y) * scale
            return (screen_x, screen_y)
        
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}
        
        # Title
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        
        title_text = "🎨 Enhanced Tactile with Trajectory Creation (Park et al.)"
        painter.drawText(margin, 20, title_text)
        
        # Draw trajectory if being drawn or completed
        if self.engine and self.engine.current_trajectory:
            trajectory_screen_points = []
            for point in self.engine.current_trajectory:
                screen_point = pos_to_screen(point)
                trajectory_screen_points.append(screen_point)
            
            if len(trajectory_screen_points) > 1:
                # Draw trajectory path
                painter.setPen(QPen(QColor(0, 150, 255), 3))
                for i in range(len(trajectory_screen_points) - 1):
                    painter.drawLine(
                        int(trajectory_screen_points[i][0]), int(trajectory_screen_points[i][1]),
                        int(trajectory_screen_points[i+1][0]), int(trajectory_screen_points[i+1][1])
                    )
                
                # Draw start and end markers
                if trajectory_screen_points:
                    # Start marker (green)
                    painter.setPen(QPen(QColor(0, 200, 0), 2))
                    painter.setBrush(QBrush(QColor(0, 255, 0, 100)))
                    start_point = trajectory_screen_points[0]
                    painter.drawEllipse(int(start_point[0] - 8), int(start_point[1] - 8), 16, 16)
                    
                    # End marker (red)
                    painter.setPen(QPen(QColor(200, 0, 0), 2))
                    painter.setBrush(QBrush(QColor(255, 0, 0, 100)))
                    end_point = trajectory_screen_points[-1]
                    painter.drawEllipse(int(end_point[0] - 8), int(end_point[1] - 8), 16, 16)
        
        # Draw triangles if enabled
        if self.show_triangles and hasattr(self.engine, 'actuator_triangles'):
            for triangle in self.engine.actuator_triangles[:8]:
                screen_positions = [pos_to_screen(pos) for pos in triangle['positions']]
                points = [QPointF(pos[0], pos[1]) for pos in screen_positions]
                
                smoothness = triangle.get('smoothness_score', 10)
                if smoothness < 5:
                    color = QColor(100, 255, 100, 40)
                elif smoothness < 10:
                    color = QColor(150, 255, 150, 30)
                else:
                    color = QColor(200, 200, 255, 20)
                
                painter.setPen(QPen(color, 1))
                painter.setBrush(QBrush(color))
                painter.drawPolygon(points)
        
        # Draw actuators
        for actuator_id in ACTUATORS:
            if actuator_id not in self.engine.actuator_positions:
                continue
                
            pos = self.engine.actuator_positions[actuator_id]
            screen_x, screen_y = pos_to_screen(pos)
            self.actuator_screen_positions[actuator_id] = (screen_x, screen_y)
            
            # Determine actuator state
            is_hovered = (self.engine.mouse_hover_actuator == f"A{actuator_id}")
            is_vibrating = (actuator_id in self.engine.soa_active_actuators or 
                          (is_hovered and self.engine.mouse_vibration_active))
            in_phantom = any(
                actuator_id in [p.physical_actuator_1, p.physical_actuator_2, p.physical_actuator_3] 
                for p in self.engine.enhanced_phantoms
            )
            
            # Color coding
            if is_vibrating:
                color = QColor(255, 50, 50)
            elif is_hovered:
                color = QColor(255, 150, 0)
            elif in_phantom:
                color = QColor(150, 0, 255)
            else:
                color = QColor(120, 120, 120)
            
            # Draw actuator
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(color))
            
            radius = 16 if is_hovered else 12
            painter.drawEllipse(int(screen_x - radius), int(screen_y - radius), 
                              radius * 2, radius * 2)
            
            # Actuator ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            text_width = len(str(actuator_id)) * 5
            painter.drawText(int(screen_x - text_width/2), int(screen_y + 3), str(actuator_id))
        
        # Draw phantoms
        for phantom in self.engine.enhanced_phantoms:
            phantom_screen = pos_to_screen(phantom.virtual_position)
            self.phantom_screen_positions[phantom.phantom_id] = phantom_screen
            
            is_phantom_hovered = (self.engine.mouse_hover_actuator == f"P{phantom.phantom_id}")
            is_phantom_vibrating = (is_phantom_hovered and self.engine.mouse_vibration_active)
            
            if is_phantom_vibrating:
                phantom_color = QColor(255, 50, 255)
                radius = 14
            elif is_phantom_hovered:
                phantom_color = QColor(255, 150, 255)
                radius = 12
            else:
                phantom_color = QColor(200, 100, 200)
                radius = 10
            
            # Draw phantom
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(phantom_color))
            painter.drawEllipse(int(phantom_screen[0] - radius), int(phantom_screen[1] - radius),
                              radius * 2, radius * 2)
            
            # Phantom ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(8)
            font.setBold(True)
            painter.setFont(font)
            phantom_text = f"P{phantom.phantom_id}"
            text_width = len(phantom_text) * 4
            painter.drawText(int(phantom_screen[0] - text_width/2), int(phantom_screen[1] + 3), phantom_text)
            
            # Draw connection lines to actuators
            if is_phantom_hovered:
                line_colors = [QColor(255, 0, 255), QColor(200, 0, 200), QColor(150, 0, 150)]
                
                for i, phys_id in enumerate([phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3]):
                    if phys_id in self.engine.actuator_positions:
                        phys_pos = self.engine.actuator_positions[phys_id]
                        phys_screen = pos_to_screen(phys_pos)
                        
                        painter.setPen(QPen(line_colors[i], 2, Qt.PenStyle.DashLine))
                        painter.drawLine(int(phantom_screen[0]), int(phantom_screen[1]),
                                       int(phys_screen[0]), int(phys_screen[1]))
        
        # Legend
        legend_y = self.height() - 60
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        
        # Trajectory mode indicator
        if self.engine and self.engine.trajectory_mode:
            painter.setPen(QPen(QColor(0, 100, 255)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(margin, legend_y - 15, "🎨 TRAJECTORY MODE - Draw path to create phantoms")
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QPen(QColor(0, 0, 0)))
        
        painter.drawText(margin, legend_y, "🔴 Vibrating  🟠 Hovered  🟣 Phantom  ⚫ Inactive")
        
        # Trajectory status
        if self.engine and self.engine.current_trajectory:
            trajectory_length = self.engine.calculate_trajectory_length(self.engine.current_trajectory)
            phantom_count = len(self.engine.trajectory_phantoms)
            trajectory_status = f"🎨 Trajectory: {len(self.engine.current_trajectory)} pts, {trajectory_length:.1f}mm, {phantom_count} phantoms"
            painter.drawText(margin, legend_y + 12, trajectory_status)

class EnhancedTactileGUI(QWidget):
    """Enhanced GUI with trajectory creation support"""
    
    def __init__(self):
        super().__init__()
        self.engine = EnhancedTactileEngine()
        self.api = None
        self.setup_ui()
        self.setup_api()
        self.setup_connections()
    
    def setup_api(self):
        if python_serial_api:
            self.api = python_serial_api()
            self.engine.api = self.api
            self.refresh_devices()
    
    def setup_connections(self):
        """Connect visualization signals to engine"""
        self.viz.actuator_hovered.connect(lambda aid: self.engine.on_mouse_hover(aid, False))
        self.viz.phantom_hovered.connect(lambda pid: self.engine.on_mouse_hover(pid, True))
        self.viz.mouse_left.connect(self.engine.on_mouse_leave)
        self.viz.trajectory_drawn.connect(self.on_trajectory_completed)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("🎨 Enhanced 4x4 Tactile with Trajectory Creation (Park et al. 2016)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2E86AB;")
        layout.addWidget(title)
        
        subtitle = QLabel("Draw curved paths for smooth tactile motion • 3-actuator phantoms • SOA timing")
        subtitle.setStyleSheet("font-style: italic; color: #666; font-size: 10px;")
        layout.addWidget(subtitle)
        
        # Connection
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)
        
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.connect_btn = QPushButton("Connect")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        conn_layout.addWidget(QLabel("Device:"))
        conn_layout.addWidget(self.device_combo)
        conn_layout.addWidget(self.refresh_btn)
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.status_label)
        layout.addWidget(conn_group)
        
        # Pattern Parameters
        pattern_group = QGroupBox("Pattern Parameters")
        pattern_layout = QFormLayout(pattern_group)
        
        self.pattern_duration_spin = QSpinBox()
        self.pattern_duration_spin.setRange(40, PAPER_PARAMS['MAX_DURATION'])
        self.pattern_duration_spin.setValue(60)
        self.pattern_duration_spin.setSuffix(" ms")
        self.pattern_duration_spin.valueChanged.connect(self.update_pattern_parameters)
        pattern_layout.addRow("Duration (≤70ms):", self.pattern_duration_spin)
        
        self.pattern_intensity_spin = QSpinBox()
        self.pattern_intensity_spin.setRange(1, 15)
        self.pattern_intensity_spin.setValue(8)
        self.pattern_intensity_spin.valueChanged.connect(self.update_pattern_parameters)
        pattern_layout.addRow("Intensity:", self.pattern_intensity_spin)
        
        layout.addWidget(pattern_group)
        
        # Trajectory Creation
        trajectory_group = QGroupBox("🎨 Trajectory Creation (Park et al. Smooth Motion)")
        trajectory_layout = QFormLayout(trajectory_group)
        
        # Sampling rate
        self.trajectory_sampling_spin = QSpinBox()
        self.trajectory_sampling_spin.setRange(30, 100)
        self.trajectory_sampling_spin.setValue(70)
        self.trajectory_sampling_spin.setSuffix(" ms")
        self.trajectory_sampling_spin.valueChanged.connect(self.update_trajectory_sampling)
        trajectory_layout.addRow("Sampling Rate:", self.trajectory_sampling_spin)
        
        # Controls
        trajectory_btn_layout = QHBoxLayout()
        
        self.trajectory_mode_btn = QPushButton("🎨 Start Drawing")
        self.trajectory_mode_btn.clicked.connect(self.toggle_trajectory_mode)
        self.trajectory_mode_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        
        self.play_trajectory_btn = QPushButton("▶️ Play Trajectory")
        self.play_trajectory_btn.clicked.connect(self.play_trajectory)
        self.play_trajectory_btn.setEnabled(False)
        
        self.clear_trajectory_btn = QPushButton("🗑️ Clear Path")
        self.clear_trajectory_btn.clicked.connect(self.clear_trajectory)
        
        trajectory_btn_layout.addWidget(self.trajectory_mode_btn)
        trajectory_btn_layout.addWidget(self.play_trajectory_btn)
        trajectory_btn_layout.addWidget(self.clear_trajectory_btn)
        trajectory_layout.addRow("", trajectory_btn_layout)
        
        # Info
        self.trajectory_info_label = QLabel("Draw a curved path to create smooth tactile motion")
        self.trajectory_info_label.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
        trajectory_layout.addRow("", self.trajectory_info_label)
        
        layout.addWidget(trajectory_group)
        
        # Manual Phantom Creation
        phantom_group = QGroupBox("Manual Phantom Creation")
        phantom_layout = QFormLayout(phantom_group)
        
        self.phantom_x_spin = QSpinBox()
        self.phantom_x_spin.setRange(-20, 200)
        self.phantom_x_spin.setValue(80)
        self.phantom_x_spin.setSuffix(" mm")
        phantom_layout.addRow("X Position:", self.phantom_x_spin)
        
        self.phantom_y_spin = QSpinBox()
        self.phantom_y_spin.setRange(-20, 220)
        self.phantom_y_spin.setValue(90)
        self.phantom_y_spin.setSuffix(" mm")
        phantom_layout.addRow("Y Position:", self.phantom_y_spin)
        
        self.phantom_intensity_spin = QSpinBox()
        self.phantom_intensity_spin.setRange(1, 15)
        self.phantom_intensity_spin.setValue(8)
        phantom_layout.addRow("Intensity:", self.phantom_intensity_spin)
        
        self.create_phantom_btn = QPushButton("🔺 Create Phantom")
        self.create_phantom_btn.clicked.connect(self.create_enhanced_phantom)
        phantom_layout.addRow("", self.create_phantom_btn)
        
        layout.addWidget(phantom_group)
        
        # Visualization
        viz_group = QGroupBox("Interactive Visualization")
        viz_layout = QVBoxLayout(viz_group)
        
        self.viz = EnhancedTactileVisualization()
        self.viz.set_engine(self.engine)
        viz_layout.addWidget(self.viz)
        layout.addWidget(viz_group)
        
        # Controls
        control_layout = QHBoxLayout()
        
        self.stop_all_btn = QPushButton("🛑 STOP ALL")
        self.stop_all_btn.clicked.connect(self.stop_all)
        self.stop_all_btn.setStyleSheet("QPushButton { background-color: #FF4444; color: white; font-weight: bold; padding: 8px; }")
        
        control_layout.addStretch()
        control_layout.addWidget(self.stop_all_btn)
        layout.addLayout(control_layout)
        
        # Info display
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(80)
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("🎨 Enhanced tactile system ready! Draw paths for smooth motion or create manual phantoms.")
        layout.addWidget(self.info_text)
        
        # Initialize
        self.update_pattern_parameters()
    
    def refresh_devices(self):
        if not self.api:
            return
        self.device_combo.clear()
        devices = self.api.get_serial_devices()
        if devices:
            self.device_combo.addItems(devices)
    
    def toggle_connection(self):
        if not self.api:
            return
        
        if not self.api.connected:
            if self.device_combo.currentText():
                if self.api.connect_serial_device(self.device_combo.currentText()):
                    self.status_label.setText("Connected ✓")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.connect_btn.setText("Disconnect")
        else:
            if self.api.disconnect_serial_device():
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                self.connect_btn.setText("Connect")
    
    def update_pattern_parameters(self):
        duration = self.pattern_duration_spin.value()
        intensity = self.pattern_intensity_spin.value()
        self.engine.set_pattern_parameters(duration, intensity)
        self.viz.update()
    
    def toggle_trajectory_mode(self):
        """Toggle trajectory drawing mode"""
        if not self.engine.trajectory_mode:
            self.engine.start_trajectory_mode()
            self.trajectory_mode_btn.setText("⏹️ Stop Drawing")
            self.trajectory_mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF5722;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
            self.trajectory_info_label.setText("🎨 DRAWING MODE: Click and drag to draw your path")
            self.trajectory_info_label.setStyleSheet("color: #2196F3; font-weight: bold; font-size: 10px;")
            self.info_text.setPlainText("🎨 Trajectory mode enabled - click and drag on the visualization to draw a curved path")
        else:
            self.engine.stop_trajectory_mode()
            self.trajectory_mode_btn.setText("🎨 Start Drawing")
            self.trajectory_mode_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
            self.trajectory_info_label.setText("Draw a curved path to create smooth tactile motion")
            self.trajectory_info_label.setStyleSheet("color: #666; font-style: italic; font-size: 10px;")
            self.info_text.setPlainText("🎨 Trajectory mode disabled")
        
        self.viz.update()
    
    def on_trajectory_completed(self):
        """Handle trajectory completion"""
        phantom_count = len(self.engine.trajectory_phantoms)
        trajectory_length = self.engine.calculate_trajectory_length(self.engine.current_trajectory)
        
        if phantom_count > 0:
            self.play_trajectory_btn.setEnabled(True)
            self.viz.update()
            
            soa = self.engine.calculate_enhanced_soa(self.engine.pattern_duration)
            total_time = phantom_count * soa
            
            self.info_text.setPlainText(
                f"✅ Trajectory completed: {phantom_count} phantoms created\n"
                f"📏 Path length: {trajectory_length:.1f}mm, Total time: {total_time:.1f}ms\n"
                f"🎯 Click 'Play Trajectory' to see smooth motion along your path"
            )
        else:
            self.info_text.setPlainText("❌ Failed to create phantoms - try drawing closer to actuators")
    
    def play_trajectory(self):
        """Play the trajectory phantoms in sequence"""
        if not self.engine.trajectory_phantoms:
            self.info_text.setPlainText("❌ No trajectory to play")
            return
        
        self.engine.play_trajectory_phantoms()
        phantom_count = len(self.engine.trajectory_phantoms)
        soa = self.engine.calculate_enhanced_soa(self.engine.pattern_duration)
        
        self.info_text.setPlainText(
            f"▶️ Playing trajectory: {phantom_count} phantoms with {soa:.1f}ms SOA\n"
            f"🎯 Smooth tactile motion following your drawn path (Park et al. methodology)"
        )
    
    def clear_trajectory(self):
        """Clear the current trajectory"""
        if not self.engine.current_trajectory and not self.engine.trajectory_phantoms:
            self.info_text.setPlainText("ℹ️ No trajectory to clear")
            return
        
        trajectory_phantom_count = len(self.engine.trajectory_phantoms)
        self.engine.clear_trajectory()
        self.play_trajectory_btn.setEnabled(False)
        self.viz.update()
        
        self.info_text.setPlainText(f"🗑️ Trajectory cleared ({trajectory_phantom_count} phantoms removed)")
    
    def update_trajectory_sampling(self):
        """Update trajectory sampling rate"""
        rate = self.trajectory_sampling_spin.value()
        self.engine.set_trajectory_sampling_rate(rate)
        
        soa = self.engine.calculate_enhanced_soa(self.engine.pattern_duration)
        actual_rate = min(rate, soa)
        
        if actual_rate != rate:
            self.info_text.setPlainText(f"⚠️ Sampling rate limited to {actual_rate}ms (SOA constraint)")
        else:
            self.info_text.setPlainText(f"🎛️ Trajectory sampling rate: {rate}ms")
    
    def create_enhanced_phantom(self):
        """Create manual phantom"""
        x = self.phantom_x_spin.value()
        y = self.phantom_y_spin.value()
        intensity = self.phantom_intensity_spin.value()
        
        phantom = self.engine.create_enhanced_phantom((x, y), intensity)
        
        if phantom:
            self.viz.update()
            self.info_text.setPlainText(
                f"✅ Phantom created at ({x}, {y}) using actuators "
                f"[{phantom.physical_actuator_1}, {phantom.physical_actuator_2}, {phantom.physical_actuator_3}]"
            )
        else:
            self.info_text.setPlainText("❌ Failed to create phantom - try a position closer to actuators")
    
    def stop_all(self):
        """Emergency stop"""
        self.engine.stop_hover_vibration()
        if self.engine.api and self.engine.api.connected:
            for actuator_id in ACTUATORS:
                self.engine.api.send_command(actuator_id, 0, 0, 0)
        self.info_text.setPlainText("🛑 EMERGENCY STOP - All activity stopped")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🎨 Enhanced Tactile Pattern Creator with Trajectory Support")
    
    widget = EnhancedTactileGUI()
    window.setCentralWidget(widget)
    window.resize(700, 900)
    window.show()
    
    sys.exit(app.exec())