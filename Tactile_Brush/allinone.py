# Waveform types
WAVEFORM_TYPES = ["Sine", "Square", "Saw", "Triangle", "Chirp", "FM", "PWM", "Noise"]

# Pattern types
PATTERN_TYPES = ["Buzz", "Pulse", "Motion"]

#!/usr/bin/env python3
"""
Comparative Pattern Interface - Buzz, Pulse, Motion
Interface unifiée pour comparer 3 types de patterns tactiles et démontrer la supériorité du motion avec phantoms

Features:
- 3 onglets: Buzz, Pulse, Motion
- Paramètres globaux partagés (waveform, intensity, frequency)
- Toggle phantoms on/off pour comparaison
- Création de patterns par dessin et sélection
- Visualisation temps réel des actuateurs
- Patterns partagés et personnalisés par type
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
    QCheckBox, QTabWidget, QFileDialog, QListWidget, QMessageBox,
    QSplitter, QScrollArea, QLineEdit, QFrame, QButtonGroup
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QMouseEvent, QCursor

# Import numpy for waveforms
import numpy as np
from scipy import signal

# Import your API (optional)
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found. Running in simulation mode.")
    python_serial_api = None

# Configuration selon le layout du boss
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

# Layout custom du boss (suivant le câblage vert de l'image)
# Ligne 1: 2 actuateurs (0, 1)
# Ligne 2: 4 actuateurs (5, 4, 3, 2) - ordre inversé selon câblage
# Ligne 3: 4 actuateurs (6, 7, 8, 9)
# Ligne 4: 4 actuateurs (13, 12, 11, 10) - ordre inversé selon câblage  
# Ligne 5: 2 actuateurs (14, 15)
BOSS_LAYOUT = {
    # Row 0 (2 actuators, centered)
    0: (1, 0),   
    1: (2, 0),
    
    # Row 1 (4 actuators, suivant le câblage: 5,4,3,2)
    5: (0, 1),   # Left
    4: (1, 1), 
    3: (2, 1),
    2: (3, 1),   # Right
    
    # Row 2 (4 actuators, ordre normal: 6,7,8,9)
    6: (0, 2),
    7: (1, 2),
    8: (2, 2), 
    9: (3, 2),
    
    # Row 3 (4 actuators, suivant le câblage: 13,12,11,10)
    13: (0, 3),  # Left
    12: (1, 3),
    11: (2, 3),
    10: (3, 3),  # Right
    
    # Row 4 (2 actuators, centered)
    14: (1, 4),
    15: (2, 4)
}

def get_boss_layout_position(actuator_id: int, spacing_mm: float = 50) -> Tuple[float, float]:
    """Get position for boss's custom layout"""
    if actuator_id < 0 or actuator_id >= 16:
        raise ValueError(f"Invalid actuator ID {actuator_id}")
    
    if actuator_id not in BOSS_LAYOUT:
        raise ValueError(f"Actuator ID {actuator_id} not found in boss layout")
    
    grid_x, grid_y = BOSS_LAYOUT[actuator_id]
    
    # Convert grid position to mm, centered
    x = grid_x * spacing_mm
    y = grid_y * spacing_mm
    
    return (x, y)

def point_in_triangle(p: Tuple[float, float], a: Tuple[float, float], 
                     b: Tuple[float, float], c: Tuple[float, float]) -> bool:
    """Check if point p is inside triangle abc"""
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    
    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)
    
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    
    return not (has_neg and has_pos)

@dataclass
class PatternStep:
    actuator_id: int
    timestamp: float
    duration: float
    intensity: int
    waveform_type: str = "Sine"
    pattern_type: str = "Buzz"  # Buzz, Pulse, Motion

@dataclass
class SharedPattern:
    name: str
    steps: List[PatternStep]
    pattern_type: str
    total_duration: float
    created_timestamp: float
    description: str = ""

    def to_dict(self):
        return {
            'name': self.name,
            'steps': [asdict(step) for step in self.steps],
            'pattern_type': self.pattern_type,
            'total_duration': self.total_duration,
            'created_timestamp': self.created_timestamp,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data):
        steps = [PatternStep(**step_data) for step_data in data['steps']]
        return cls(
            name=data['name'],
            steps=steps,
            pattern_type=data['pattern_type'],
            total_duration=data['total_duration'],
            created_timestamp=data['created_timestamp'],
            description=data.get('description', '')
        )

@dataclass
class Enhanced3ActuatorPhantom:
    """Enhanced phantom using 3-actuator system"""
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

class ComparativeEngine:
    """Engine for comparative pattern testing"""
    
    def __init__(self, api=None):
        self.api = api
        
        # Global parameters shared across all tabs
        self.waveform_type = "Sine"
        self.frequency = 250.0
        self.intensity = 8
        self.duration = 60
        
        # Phantom system
        self.phantoms_enabled = True
        self.enhanced_phantoms = []
        self.actuator_triangles = []
        
        # Actuator layout
        self.actuator_positions = {}
        self.init_default_layout()
        
        # Pattern execution
        self.active_actuators = {}
        self.execution_timer = QTimer()
        self.execution_timer.timeout.connect(self.execute_step)
        
        # Pattern storage
        self.shared_patterns = {}
        self.current_pattern_steps = []
        self.execution_start_time = 0
        self.execution_step_idx = 0
        
        # Drawing state
        self.drawing_mode = False
        self.current_trajectory = []
        
        # Selection state
        self.selected_actuators = set()
        
        self.compute_actuator_triangles()

        self.trajectory_collection = [] 
        self.current_trajectory_id = 0
        self.phantom_spacing_ms = 100 
    
    def init_default_layout(self):
        """Initialize boss's custom layout"""
        self.actuator_positions = {}
        for actuator_id in ACTUATORS:
            x, y = get_boss_layout_position(actuator_id, 50)
            self.actuator_positions[actuator_id] = (x, y)
        print(f"🎯 Boss layout initialized: Cable order 0,1|5,4,3,2|6,7,8,9|13,12,11,10|14,15")
    
    def set_phantom_spacing(self, spacing_ms: int):
            """Set spacing between phantoms in trajectory"""
            self.phantom_spacing_ms = max(50, min(500, spacing_ms))
            print(f"👻 Phantom spacing set to {self.phantom_spacing_ms}ms")
    
    def add_new_trajectory(self):
        """Start a new trajectory"""
        if self.current_trajectory:
            # Save current trajectory if it exists
            trajectory_data = {
                'id': self.current_trajectory_id,
                'points': self.current_trajectory.copy(),
                'color': self.get_trajectory_color(self.current_trajectory_id),
                'phantoms': []
            }
            self.trajectory_collection.append(trajectory_data)
            self.current_trajectory_id += 1
        
        # Start new trajectory
        self.current_trajectory = []
        print(f"🎨 Started new trajectory #{self.current_trajectory_id}")
    
    def get_trajectory_color(self, trajectory_id: int) -> Tuple[int, int, int]:
        """Get unique color for each trajectory"""
        colors = [
            (0, 150, 255),    # Blue
            (255, 100, 0),    # Orange  
            (0, 200, 100),    # Green
            (255, 0, 150),    # Pink
            (150, 0, 255),    # Purple
            (255, 200, 0),    # Yellow
            (0, 255, 200),    # Cyan
            (255, 50, 50),    # Red
        ]
        return colors[trajectory_id % len(colors)]
    
    def clear_all_trajectories(self):
        """Clear all trajectories and phantoms"""
        self.trajectory_collection = []
        self.current_trajectory = []
        self.current_trajectory_id = 0
        self.clear_phantoms()
        print("🗑️ All trajectories cleared")
    
    def create_all_trajectory_phantoms(self):
        """Create phantoms for all trajectories with custom spacing"""
        self.clear_phantoms()
        
        total_phantoms = 0
        
        for trajectory_data in self.trajectory_collection:
            trajectory_points = trajectory_data['points']
            if len(trajectory_points) < 2:
                continue
            
            # Sample trajectory with custom spacing
            trajectory_phantoms = self.create_trajectory_phantoms_with_spacing(
                trajectory_points, 
                self.phantom_spacing_ms,
                trajectory_data['id']
            )
            
            trajectory_data['phantoms'] = trajectory_phantoms
            total_phantoms += len(trajectory_phantoms)
        
        # Also process current trajectory if it exists
        if len(self.current_trajectory) >= 2:
            current_phantoms = self.create_trajectory_phantoms_with_spacing(
                self.current_trajectory,
                self.phantom_spacing_ms, 
                self.current_trajectory_id
            )
            total_phantoms += len(current_phantoms)
        
        print(f"✅ Created {total_phantoms} phantoms across {len(self.trajectory_collection) + (1 if self.current_trajectory else 0)} trajectories")
        return total_phantoms > 0
    
    def create_trajectory_phantoms_with_spacing(self, trajectory_points: List[Tuple[float, float]], 
                                              spacing_ms: int, trajectory_id: int) -> List:
        """Create phantoms along trajectory with specified spacing"""
        if len(trajectory_points) < 2:
            return []
        
        trajectory_length = self.calculate_trajectory_length_points(trajectory_points)
        
        # Calculate number of phantoms based on spacing
        # Minimum 2 phantoms, reasonable density based on spacing
        min_phantoms = 2
        max_phantoms = min(20, int(trajectory_length / 30))  # Max based on length
        
        # Calculate based on time spacing (assuming reasonable movement speed)
        time_based_phantoms = max(2, int(trajectory_length / (spacing_ms * 0.1)))  # 0.1 = speed factor
        
        num_phantoms = max(min_phantoms, min(max_phantoms, time_based_phantoms))
        
        phantoms = []
        for i in range(num_phantoms):
            t = i / (num_phantoms - 1)
            point = self.interpolate_trajectory_points(trajectory_points, t)
            timestamp = i * spacing_ms
            
            phantom = self.create_phantom(point, self.intensity)
            if phantom:
                phantom.timestamp = timestamp
                phantom.trajectory_id = trajectory_id
                phantoms.append(phantom)
        
        return phantoms
    
    def calculate_trajectory_length_points(self, points: List[Tuple[float, float]]) -> float:
        """Calculate total length of trajectory from points"""
        if len(points) < 2:
            return 0
        
        length = 0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            length += math.sqrt(dx * dx + dy * dy)
        
        return length
    
    def interpolate_trajectory_points(self, points: List[Tuple[float, float]], t: float) -> Tuple[float, float]:
        """Interpolate point along trajectory using parameter t (0 to 1)"""
        if len(points) < 2:
            return points[0] if points else (0, 0)
        if t <= 0:
            return points[0]
        if t >= 1:
            return points[-1]
        
        total_length = self.calculate_trajectory_length_points(points)
        target_length = t * total_length
        
        current_length = 0
        for i in range(1, len(points)):
            segment_length = math.sqrt(
                (points[i][0] - points[i-1][0])**2 + 
                (points[i][1] - points[i-1][1])**2
            )
            
            if current_length + segment_length >= target_length:
                if segment_length > 0:
                    segment_t = (target_length - current_length) / segment_length
                    x = points[i-1][0] + segment_t * (points[i][0] - points[i-1][0])
                    y = points[i-1][1] + segment_t * (points[i][1] - points[i-1][1])
                    return (x, y)
                else:
                    return points[i-1]
            
            current_length += segment_length
        
        return points[-1]
    
    def execute_all_trajectories(self):
        """Execute all trajectories simultaneously"""
        if not self.trajectory_collection and not self.current_trajectory:
            return []
        
        # First create all phantoms
        self.create_all_trajectory_phantoms()
        
        # Collect all phantom steps
        all_steps = []
        
        # Process saved trajectories
        for trajectory_data in self.trajectory_collection:
            phantoms = trajectory_data['phantoms']
            
            for phantom in phantoms:
                # Add steps for all 3 physical actuators
                for phys_id, intensity in [
                    (phantom.physical_actuator_1, phantom.required_intensity_1),
                    (phantom.physical_actuator_2, phantom.required_intensity_2),
                    (phantom.physical_actuator_3, phantom.required_intensity_3)
                ]:
                    step = PatternStep(
                        actuator_id=phys_id,
                        timestamp=phantom.timestamp,
                        duration=self.duration,
                        intensity=intensity,
                        waveform_type=self.waveform_type,
                        pattern_type="Motion"
                    )
                    all_steps.append(step)
        
        # Process current trajectory if exists
        if len(self.current_trajectory) >= 2:
            current_phantoms = self.create_trajectory_phantoms_with_spacing(
                self.current_trajectory, self.phantom_spacing_ms, self.current_trajectory_id
            )
            
            for phantom in current_phantoms:
                for phys_id, intensity in [
                    (phantom.physical_actuator_1, phantom.required_intensity_1),
                    (phantom.physical_actuator_2, phantom.required_intensity_2),
                    (phantom.physical_actuator_3, phantom.required_intensity_3)
                ]:
                    step = PatternStep(
                        actuator_id=phys_id,
                        timestamp=phantom.timestamp,
                        duration=self.duration,
                        intensity=intensity,
                        waveform_type=self.waveform_type,
                        pattern_type="Motion"
                    )
                    all_steps.append(step)
        
        return all_steps
    
    def compute_actuator_triangles(self):
        """Systematic triangulation for smooth phantom motion"""
        self.actuator_triangles = []
        positions = self.actuator_positions
        
        if len(positions) < 3:
            return
        
        triangles_added = 0
        
        # Create triangles from all possible combinations of 3 actuators
        actuator_ids = list(positions.keys())
        
        for i in range(len(actuator_ids)):
            for j in range(i + 1, len(actuator_ids)):
                for k in range(j + 1, len(actuator_ids)):
                    act1, act2, act3 = actuator_ids[i], actuator_ids[j], actuator_ids[k]
                    pos1, pos2, pos3 = positions[act1], positions[act2], positions[act3]
                    
                    # Calculate triangle area
                    area = abs((pos1[0]*(pos2[1]-pos3[1]) + 
                            pos2[0]*(pos3[1]-pos1[1]) + 
                            pos3[0]*(pos1[1]-pos2[1]))/2)
                    
                    # Only include triangles with reasonable area
                    if area > 50 and area < 5000:
                        triangle = {
                            'actuators': [act1, act2, act3],
                            'positions': [pos1, pos2, pos3],
                            'area': area,
                            'center': ((pos1[0]+pos2[0]+pos3[0])/3, 
                                    (pos1[1]+pos2[1]+pos3[1])/3),
                            'type': f'auto_{act1}_{act2}_{act3}',
                            'smoothness_score': self.calculate_triangle_smoothness([pos1, pos2, pos3])
                        }
                        self.actuator_triangles.append(triangle)
                        triangles_added += 1
        
        # Sort by quality (smoothness and area)
        self.actuator_triangles.sort(key=lambda t: (t['smoothness_score'], t['area']))
        
        # Keep only the best triangles to avoid overwhelming computation
        max_triangles = min(50, len(self.actuator_triangles))
        self.actuator_triangles = self.actuator_triangles[:max_triangles]
        
        print(f"🔺 Generated {len(self.actuator_triangles)} optimized triangles")

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
        """Calculate intensities for 3-actuator phantom"""
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        positions = triangle['positions']
        
        # Calculate distances
        distances = []
        for pos in positions:
            dist = math.sqrt((phantom_pos[0] - pos[0])**2 + (phantom_pos[1] - pos[1])**2)
            distances.append(max(dist, 1.0))
        
        # Energy summation model: Ai = sqrt(1/di / sum(1/dj)) * Av
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
    
    def create_phantom(self, phantom_pos: Tuple[float, float], 
                      desired_intensity: int) -> Optional[Enhanced3ActuatorPhantom]:
        """Create phantom at specified position"""
        if not self.phantoms_enabled:
            return None
            
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
        print(f"✅ Phantom {phantom_id} created at {phantom_pos}")
        return phantom
    
    def clear_phantoms(self):
        """Clear all phantoms"""
        self.enhanced_phantoms = []
        print("🗑️ All phantoms cleared")
    
    def toggle_phantoms(self, enabled: bool):
        """Toggle phantom system on/off"""
        self.phantoms_enabled = enabled
        if not enabled:
            # Stop any phantom-related activity
            self.stop_all_actuators()
        print(f"👻 Phantoms {'enabled' if enabled else 'disabled'}")
    
    def set_global_parameters(self, waveform_type: str, frequency: float, 
                            intensity: int, duration: int):
        """Set global parameters shared across all tabs"""
        self.waveform_type = waveform_type
        self.frequency = frequency
        self.intensity = intensity
        self.duration = duration
        print(f"🎛️ Global params: {waveform_type}, {frequency}Hz, I={intensity}, {duration}ms")
    
    def toggle_actuator_selection(self, actuator_id: int):
        """Toggle actuator selection"""
        if actuator_id in self.selected_actuators:
            self.selected_actuators.remove(actuator_id)
        else:
            self.selected_actuators.add(actuator_id)
    
    def clear_selection(self):
        """Clear actuator selection"""
        self.selected_actuators.clear()
    
    def start_drawing_mode(self):
        """Start trajectory drawing mode"""
        self.drawing_mode = True
        self.current_trajectory = []
        print("🎨 Drawing mode enabled")
    
    def stop_drawing_mode(self):
        """Stop trajectory drawing mode"""
        self.drawing_mode = False
        print("🎨 Drawing mode disabled")
    
    def add_trajectory_point(self, point: Tuple[float, float]):
        """Add point to trajectory"""
        if self.drawing_mode:
            self.current_trajectory.append(point)
    
    def create_buzz_pattern(self) -> List[PatternStep]:
        """Create buzz pattern from selected actuators"""
        steps = []
        
        if not self.selected_actuators:
            return steps
        
        for actuator_id in self.selected_actuators:
            step = PatternStep(
                actuator_id=actuator_id,
                timestamp=0,  # All start at same time for buzz
                duration=self.duration,
                intensity=self.intensity,
                waveform_type=self.waveform_type,
                pattern_type="Buzz"
            )
            steps.append(step)
        
        print(f"🔊 Created buzz pattern with {len(steps)} actuators")
        return steps
    
    def create_pulse_pattern(self, pulse_interval: int = 200) -> List[PatternStep]:
        """Create pulse pattern from selected actuators"""
        steps = []
        
        if not self.selected_actuators:
            return steps
        
        actuator_list = list(self.selected_actuators)
        
        for i, actuator_id in enumerate(actuator_list):
            # Stagger pulses for interesting rhythm
            timestamp = i * pulse_interval
            
            step = PatternStep(
                actuator_id=actuator_id,
                timestamp=timestamp,
                duration=self.duration,
                intensity=self.intensity,
                waveform_type=self.waveform_type,
                pattern_type="Pulse"
            )
            steps.append(step)
        
        print(f"📳 Created pulse pattern with {len(steps)} actuators")
        return steps
    
    def create_motion_pattern(self) -> List[PatternStep]:
        """Create motion pattern from trajectory or selected actuators"""
        steps = []
        
        if self.current_trajectory and len(self.current_trajectory) >= 2:
            # Create motion from trajectory with phantoms
            steps = self.create_trajectory_motion()
        elif self.selected_actuators:
            # Create motion sequence from selected actuators
            steps = self.create_sequential_motion()
        
        print(f"🌊 Created motion pattern with {len(steps)} steps")
        return steps
    
    def create_trajectory_motion(self) -> List[PatternStep]:
        """Create motion pattern from drawn trajectory"""
        steps = []
        
        if not self.phantoms_enabled:
            return steps
        
        # Sample trajectory points
        trajectory_length = self.calculate_trajectory_length()
        num_samples = max(3, min(10, int(trajectory_length / 30)))  # Reasonable number of samples
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            point = self.interpolate_trajectory(t)
            timestamp = i * 100  # 100ms between samples
            
            # Create phantom at this position
            phantom = self.create_phantom(point, self.intensity)
            if phantom:
                # Add steps for all 3 physical actuators
                for phys_id, intensity in [
                    (phantom.physical_actuator_1, phantom.required_intensity_1),
                    (phantom.physical_actuator_2, phantom.required_intensity_2),
                    (phantom.physical_actuator_3, phantom.required_intensity_3)
                ]:
                    step = PatternStep(
                        actuator_id=phys_id,
                        timestamp=timestamp,
                        duration=self.duration,
                        intensity=intensity,
                        waveform_type=self.waveform_type,
                        pattern_type="Motion"
                    )
                    steps.append(step)
        
        return steps
    
    def create_sequential_motion(self) -> List[PatternStep]:
        """Create sequential motion from selected actuators"""
        steps = []
        actuator_list = list(self.selected_actuators)
        
        # Sort by position for logical sequence
        actuator_list.sort(key=lambda aid: (self.actuator_positions[aid][1], 
                                          self.actuator_positions[aid][0]))
        
        soa = 80  # Stimulus onset asynchrony
        
        for i, actuator_id in enumerate(actuator_list):
            timestamp = i * soa
            
            step = PatternStep(
                actuator_id=actuator_id,
                timestamp=timestamp,
                duration=self.duration,
                intensity=self.intensity,
                waveform_type=self.waveform_type,
                pattern_type="Motion"
            )
            steps.append(step)
        
        return steps
    
    def calculate_trajectory_length(self) -> float:
        """Calculate total trajectory length"""
        if len(self.current_trajectory) < 2:
            return 0
        
        length = 0
        for i in range(1, len(self.current_trajectory)):
            dx = self.current_trajectory[i][0] - self.current_trajectory[i-1][0]
            dy = self.current_trajectory[i][1] - self.current_trajectory[i-1][1]
            length += math.sqrt(dx * dx + dy * dy)
        
        return length
    
    def interpolate_trajectory(self, t: float) -> Tuple[float, float]:
        """Interpolate point along trajectory (t from 0 to 1)"""
        if len(self.current_trajectory) < 2:
            return self.current_trajectory[0] if self.current_trajectory else (0, 0)
        
        if t <= 0:
            return self.current_trajectory[0]
        if t >= 1:
            return self.current_trajectory[-1]
        
        total_length = self.calculate_trajectory_length()
        target_length = t * total_length
        
        current_length = 0
        for i in range(1, len(self.current_trajectory)):
            segment_length = math.sqrt(
                (self.current_trajectory[i][0] - self.current_trajectory[i-1][0])**2 + 
                (self.current_trajectory[i][1] - self.current_trajectory[i-1][1])**2
            )
            
            if current_length + segment_length >= target_length:
                if segment_length > 0:
                    segment_t = (target_length - current_length) / segment_length
                    x = self.current_trajectory[i-1][0] + segment_t * (self.current_trajectory[i][0] - self.current_trajectory[i-1][0])
                    y = self.current_trajectory[i-1][1] + segment_t * (self.current_trajectory[i][1] - self.current_trajectory[i-1][1])
                    return (x, y)
                else:
                    return self.current_trajectory[i-1]
            
            current_length += segment_length
        
        return self.current_trajectory[-1]
    
    def execute_pattern(self, steps: List[PatternStep]):
        """Execute pattern with real-time visualization"""
        if not steps:
            return
        
        self.current_pattern_steps = sorted(steps, key=lambda s: s.timestamp)
        self.execution_step_idx = 0
        self.execution_start_time = time.time() * 1000
        self.active_actuators = {}
        
        print(f"🚀 Executing pattern with {len(steps)} steps")
        self.execution_timer.start(1)  # 1ms precision
    
    def execute_step(self):
        """Execute pattern step with precise timing"""
        current_time = time.time() * 1000 - self.execution_start_time
        
        # Start new steps
        while (self.execution_step_idx < len(self.current_pattern_steps) and 
               self.current_pattern_steps[self.execution_step_idx].timestamp <= current_time):
            
            step = self.current_pattern_steps[self.execution_step_idx]
            
            if self.api and self.api.connected:
                success = self.api.send_command(step.actuator_id, step.intensity, 4, 1)
                if success:
                    stop_time = current_time + step.duration
                    self.active_actuators[step.actuator_id] = stop_time
            else:
                # Simulation mode
                stop_time = current_time + step.duration
                self.active_actuators[step.actuator_id] = stop_time
            
            self.execution_step_idx += 1
        
        # Stop actuators when duration expires
        to_stop = []
        for actuator_id, stop_time in self.active_actuators.items():
            if current_time >= stop_time:
                if self.api and self.api.connected:
                    self.api.send_command(actuator_id, 0, 0, 0)
                to_stop.append(actuator_id)
        
        for actuator_id in to_stop:
            del self.active_actuators[actuator_id]
        
        # Check if execution is complete
        if (self.execution_step_idx >= len(self.current_pattern_steps) and 
            len(self.active_actuators) == 0):
            self.execution_timer.stop()
            print("✅ Pattern execution complete")
    
    def stop_all_actuators(self):
        """Emergency stop all actuators"""
        self.execution_timer.stop()
        self.active_actuators = {}
        
        if self.api and self.api.connected:
            for actuator_id in ACTUATORS:
                self.api.send_command(actuator_id, 0, 0, 0)
        
        print("🛑 All actuators stopped")
    
    def save_pattern(self, pattern: SharedPattern, filename: str) -> bool:
        """Save pattern to file"""
        try:
            with open(filename, 'w') as f:
                json.dump(pattern.to_dict(), f, indent=2)
            self.shared_patterns[pattern.name] = pattern
            print(f"💾 Pattern saved: {filename}")
            return True
        except Exception as e:
            print(f"❌ Failed to save pattern: {e}")
            return False
    
    def load_pattern(self, filename: str) -> Optional[SharedPattern]:
        """Load pattern from file"""
        try:
            with open(filename, 'r') as f:
                data = json.load(f)
            pattern = SharedPattern.from_dict(data)
            self.shared_patterns[pattern.name] = pattern
            print(f"📂 Pattern loaded: {pattern.name}")
            return pattern
        except Exception as e:
            print(f"❌ Failed to load pattern: {e}")
            return None

class SharedVisualization(QWidget):
    """Shared visualization showing real-time actuator activity"""
    
    actuator_clicked = pyqtSignal(int)
    phantom_requested = pyqtSignal(float, float)
    trajectory_point_added = pyqtSignal(float, float)
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(500, 400)
        self.setMouseTracking(True)
        self.engine = None
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}
        
        # Interaction state
        self.drawing_trajectory = False
        
    def set_engine(self, engine: ComparativeEngine):
        self.engine = engine
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        if not self.engine:
            return
        
        mouse_pos = event.position()
        
        if self.engine.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            # Start drawing trajectory
            self.drawing_trajectory = True
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.engine.current_trajectory = [physical_pos]
                self.trajectory_point_added.emit(physical_pos[0], physical_pos[1])
        elif event.button() == Qt.MouseButton.LeftButton:
            # Check for actuator click
            clicked_actuator = self.get_actuator_at_position(mouse_pos)
            if clicked_actuator is not None:
                self.actuator_clicked.emit(clicked_actuator)
        elif event.button() == Qt.MouseButton.RightButton and self.engine.phantoms_enabled:
            # Request phantom creation
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.phantom_requested.emit(physical_pos[0], physical_pos[1])
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.engine:
            return
        
        if self.drawing_trajectory and self.engine.drawing_mode:
            physical_pos = self.screen_to_physical(event.position())
            if physical_pos:
                # Add point if far enough from last point
                if (not self.engine.current_trajectory or 
                    self.distance_between_points(physical_pos, self.engine.current_trajectory[-1]) > 5):
                    self.engine.add_trajectory_point(physical_pos)
                    self.trajectory_point_added.emit(physical_pos[0], physical_pos[1])
                    self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.drawing_trajectory and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_trajectory = False
    
    def distance_between_points(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return math.sqrt((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)
    
    def screen_to_physical(self, screen_pos: QPointF) -> Optional[Tuple[float, float]]:
        """Convert screen position to physical position"""
        if not self.engine or not self.engine.actuator_positions:
            return None
        
        positions = list(self.engine.actuator_positions.values())
        if not positions:
            return None
        
        x_coords = [pos[0] for pos in positions]
        y_coords = [pos[1] for pos in positions]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        margin = 30
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 80
        
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.9
        
        physical_x = (screen_pos.x() - margin) / scale + min_x
        physical_y = (screen_pos.y() - margin - 40) / scale + min_y
        
        return (physical_x, physical_y)
    
    def get_actuator_at_position(self, pos: QPointF) -> Optional[int]:
        """Get actuator ID at screen position"""
        for actuator_id, screen_pos in self.actuator_screen_positions.items():
            distance = math.sqrt((pos.x() - screen_pos[0])**2 + (pos.y() - screen_pos[1])**2)
            if distance <= 20:  # Click radius
                return actuator_id
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
        
        margin = 30
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 80
        
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.9
        
        def pos_to_screen(pos):
            screen_x = margin + (pos[0] - min_x) * scale
            screen_y = margin + 40 + (pos[1] - min_y) * scale
            return (screen_x, screen_y)
        
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}
        
        # Title
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        
        mode_text = ""
        if self.engine.drawing_mode:
            mode_text = " [DRAWING MODE]"
        elif self.engine.selected_actuators:
            mode_text = f" [{len(self.engine.selected_actuators)} SELECTED]"
        
        # Add trajectory count to title
        traj_count = len(getattr(self.engine, 'trajectory_collection', []))
        current_traj = " (+current)" if getattr(self.engine, 'current_trajectory', []) else ""
        if traj_count > 0 or current_traj:
            mode_text += f" [{traj_count} trajectories{current_traj}]"
        
        painter.drawText(margin, 25, f"Boss Layout Multi-Trajectory{mode_text}")
        
        # Draw all saved trajectories with different colors
        if hasattr(self.engine, 'trajectory_collection') and self.engine.trajectory_collection:
            for trajectory_data in self.engine.trajectory_collection:
                trajectory_points = trajectory_data['points']
                color = trajectory_data['color']
                trajectory_id = trajectory_data['id']
                
                if len(trajectory_points) > 1:
                    trajectory_screen_points = [pos_to_screen(point) for point in trajectory_points]
                    
                    # Draw trajectory line
                    painter.setPen(QPen(QColor(*color), 3))
                    for i in range(len(trajectory_screen_points) - 1):
                        painter.drawLine(
                            int(trajectory_screen_points[i][0]), int(trajectory_screen_points[i][1]),
                            int(trajectory_screen_points[i+1][0]), int(trajectory_screen_points[i+1][1])
                        )
                    
                    # Start marker (green)
                    if trajectory_screen_points:
                        painter.setPen(QPen(QColor(0, 200, 0), 2))
                        painter.setBrush(QBrush(QColor(0, 255, 0, 100)))
                        start_point = trajectory_screen_points[0]
                        painter.drawEllipse(int(start_point[0] - 6), int(start_point[1] - 6), 12, 12)
                        
                        # End marker (red)
                        painter.setPen(QPen(QColor(200, 0, 0), 2))
                        painter.setBrush(QBrush(QColor(255, 0, 0, 100)))
                        end_point = trajectory_screen_points[-1]
                        painter.drawEllipse(int(end_point[0] - 6), int(end_point[1] - 6), 12, 12)
                        
                        # Trajectory ID label
                        painter.setPen(QPen(QColor(*color)))
                        font.setPointSize(8)
                        font.setBold(True)
                        painter.setFont(font)
                        painter.drawText(int(start_point[0] + 10), int(start_point[1] - 5), f"T{trajectory_id}")
        
        # Draw current trajectory being drawn (bright blue)
        if hasattr(self.engine, 'current_trajectory') and self.engine.current_trajectory and len(self.engine.current_trajectory) > 1:
            trajectory_screen_points = [pos_to_screen(point) for point in self.engine.current_trajectory]
            
            painter.setPen(QPen(QColor(0, 150, 255), 4))  # Thicker and brighter for current
            for i in range(len(trajectory_screen_points) - 1):
                painter.drawLine(
                    int(trajectory_screen_points[i][0]), int(trajectory_screen_points[i][1]),
                    int(trajectory_screen_points[i+1][0]), int(trajectory_screen_points[i+1][1])
                )
            
            # Start/end markers for current trajectory
            if trajectory_screen_points:
                # Start marker
                painter.setPen(QPen(QColor(0, 200, 0), 2))
                painter.setBrush(QBrush(QColor(0, 255, 0, 150)))
                start_point = trajectory_screen_points[0]
                painter.drawEllipse(int(start_point[0] - 8), int(start_point[1] - 8), 16, 16)
                
                # End marker
                painter.setPen(QPen(QColor(200, 0, 0), 2))
                painter.setBrush(QBrush(QColor(255, 0, 0, 150)))
                end_point = trajectory_screen_points[-1]
                painter.drawEllipse(int(end_point[0] - 8), int(end_point[1] - 8), 16, 16)
                
                # "CURRENT" label
                painter.setPen(QPen(QColor(0, 150, 255)))
                font.setPointSize(8)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(int(start_point[0] + 10), int(start_point[1] - 10), "CURRENT")
        
        # Draw actuators
        for actuator_id in ACTUATORS:
            if actuator_id not in self.engine.actuator_positions:
                continue
                
            pos = self.engine.actuator_positions[actuator_id]
            screen_x, screen_y = pos_to_screen(pos)
            self.actuator_screen_positions[actuator_id] = (screen_x, screen_y)
            
            # Determine actuator state
            is_selected = actuator_id in self.engine.selected_actuators
            is_active = actuator_id in self.engine.active_actuators
            is_in_phantom = any(actuator_id in [p.physical_actuator_1, p.physical_actuator_2, p.physical_actuator_3] 
                            for p in self.engine.enhanced_phantoms)
            
            # Color coding based on state
            if is_active:
                color = QColor(255, 50, 50)  # Red - currently vibrating
                radius = 22
            elif is_selected:
                color = QColor(0, 150, 255)  # Blue - selected
                radius = 20
            elif is_in_phantom:
                color = QColor(150, 0, 255)  # Purple - part of phantom
                radius = 18
            else:
                color = QColor(120, 120, 120)  # Gray - inactive
                radius = 16
            
            # Draw actuator
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(color))
            painter.drawEllipse(int(screen_x - radius), int(screen_y - radius), 
                            radius * 2, radius * 2)
            
            # Actuator ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            text_width = len(str(actuator_id)) * 6
            painter.drawText(int(screen_x - text_width/2), int(screen_y + 4), str(actuator_id))
        
        # Draw phantoms
        for phantom in self.engine.enhanced_phantoms:
            phantom_screen = pos_to_screen(phantom.virtual_position)
            self.phantom_screen_positions[phantom.phantom_id] = phantom_screen
            
            # Color phantom based on trajectory if available
            phantom_color = QColor(255, 100, 255)  # Default purple
            if hasattr(phantom, 'trajectory_id'):
                # Find trajectory color
                for traj_data in getattr(self.engine, 'trajectory_collection', []):
                    if traj_data['id'] == phantom.trajectory_id:
                        traj_color = traj_data['color']
                        phantom_color = QColor(traj_color[0], traj_color[1], traj_color[2], 200)
                        break
            
            # Draw phantom
            painter.setPen(QPen(QColor(255, 0, 255), 3))
            painter.setBrush(QBrush(phantom_color))
            radius = 15
            painter.drawEllipse(int(phantom_screen[0] - radius), int(phantom_screen[1] - radius),
                            radius * 2, radius * 2)
            
            # Phantom ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(9)
            font.setBold(True)
            painter.setFont(font)
            phantom_text = f"P{phantom.phantom_id}"
            text_width = len(phantom_text) * 5
            painter.drawText(int(phantom_screen[0] - text_width/2), int(phantom_screen[1] + 3), phantom_text)
            
            # Draw connection lines to physical actuators (only for selected phantoms)
            # Show connections only if we have few phantoms to avoid clutter
            if len(self.engine.enhanced_phantoms) <= 5:
                line_colors = [QColor(255, 0, 255), QColor(200, 0, 200), QColor(150, 0, 150)]
                
                for i, phys_id in enumerate([phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3]):
                    if phys_id in self.engine.actuator_positions:
                        phys_pos = self.engine.actuator_positions[phys_id]
                        phys_screen = pos_to_screen(phys_pos)
                        
                        painter.setPen(QPen(line_colors[i], 1, Qt.PenStyle.DashLine))
                        painter.drawLine(int(phantom_screen[0]), int(phantom_screen[1]),
                                    int(phys_screen[0]), int(phys_screen[1]))
        
        # Legend
        legend_y = self.height() - 40
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(8)
        painter.setFont(font)
        
        painter.drawText(margin, legend_y, "🔴 Active  🔵 Selected  🟣 Phantom  ⚫ Inactive")
        painter.drawText(margin, legend_y + 15, "Left click: Select | Right click: Phantom | Draw: Multi-trajectories")
        
        # Show phantom spacing info if in motion mode
        if hasattr(self.engine, 'phantom_spacing_ms'):
            painter.drawText(margin + 400, legend_y, f"Phantom spacing: {self.engine.phantom_spacing_ms}ms")

class GlobalParametersPanel(QWidget):
    """Panel for global parameters shared across all tabs"""
    
    parameters_changed = pyqtSignal(str, float, int, int)  # waveform, frequency, intensity, duration
    phantoms_toggled = pyqtSignal(bool)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Title
        title = QLabel("🌐 Global Parameters")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #FFFFFF;")
        layout.addWidget(title)
        
        # Parameters form (more compact)
        form_layout = QFormLayout()
        form_layout.setVerticalSpacing(3)
        
        # Waveform
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(WAVEFORM_TYPES)
        self.waveform_combo.setCurrentText("Sine")
        self.waveform_combo.setMaximumHeight(25)
        self.waveform_combo.setStyleSheet("""
            QComboBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
            QComboBox::drop-down {
                border: none;
            }
            QComboBox::down-arrow {
                border: none;
            }
        """)
        self.waveform_combo.currentTextChanged.connect(self.on_parameters_changed)
        
        waveform_label = QLabel("Waveform:")
        waveform_label.setStyleSheet("color: white; font-weight: bold;")
        form_layout.addRow(waveform_label, self.waveform_combo)
        
        # Frequency
        self.frequency_spin = QSpinBox()
        self.frequency_spin.setRange(50, 1000)
        self.frequency_spin.setValue(250)
        self.frequency_spin.setSuffix(" Hz")
        self.frequency_spin.setMaximumHeight(25)
        self.frequency_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
        """)
        self.frequency_spin.valueChanged.connect(self.on_parameters_changed)
        
        frequency_label = QLabel("Frequency:")
        frequency_label.setStyleSheet("color: white; font-weight: bold;")
        form_layout.addRow(frequency_label, self.frequency_spin)
        
        # Intensity
        self.intensity_spin = QSpinBox()
        self.intensity_spin.setRange(1, 15)
        self.intensity_spin.setValue(8)
        self.intensity_spin.setMaximumHeight(25)
        self.intensity_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
        """)
        self.intensity_spin.valueChanged.connect(self.on_parameters_changed)
        
        intensity_label = QLabel("Intensity:")
        intensity_label.setStyleSheet("color: white; font-weight: bold;")
        form_layout.addRow(intensity_label, self.intensity_spin)
        
        # Duration
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(40, 200)
        self.duration_spin.setValue(60)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.setMaximumHeight(25)
        self.duration_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
        """)
        self.duration_spin.valueChanged.connect(self.on_parameters_changed)
        
        duration_label = QLabel("Duration:")
        duration_label.setStyleSheet("color: white; font-weight: bold;")
        form_layout.addRow(duration_label, self.duration_spin)
        
        layout.addLayout(form_layout)
        
        # Phantom toggle
        self.phantom_checkbox = QCheckBox("Enable Phantoms")
        self.phantom_checkbox.setChecked(True)
        self.phantom_checkbox.toggled.connect(self.phantoms_toggled.emit)
        self.phantom_checkbox.setStyleSheet("""
            QCheckBox {
                font-weight: bold; 
                color: #9C27B0; 
                font-size: 10px;
            }
            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                background-color: #3E3E3E;
                border: 1px solid #555;
            }
            QCheckBox::indicator:checked {
                background-color: #9C27B0;
            }
        """)
        layout.addWidget(self.phantom_checkbox)
    
    def on_parameters_changed(self):
        """Emit parameters changed signal"""
        self.parameters_changed.emit(
            self.waveform_combo.currentText(),
            float(self.frequency_spin.value()),
            self.intensity_spin.value(),
            self.duration_spin.value()
        )

# Pattern Library Panel Class
class PatternLibraryPanel(QWidget):
    """Panel for managing saved patterns"""
    
    pattern_selected = pyqtSignal(str, list)  # pattern_name, steps
    
    def __init__(self):
        super().__init__()
        self.engine = None
        self.setup_ui()
        self.load_patterns_from_disk()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Title
        title = QLabel("📚 Pattern Library")
        title.setStyleSheet("font-weight: bold; font-size: 11px; color: #FFFFFF;")
        layout.addWidget(title)
        
        # Pattern list
        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(120)
        self.pattern_list.setStyleSheet("""
            QListWidget {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                font-size: 10px;
            }
            QListWidget::item {
                padding: 3px;
                border-bottom: 1px solid #555;
            }
            QListWidget::item:selected {
                background-color: #2196F3;
            }
        """)
        self.pattern_list.itemDoubleClicked.connect(self.replay_selected_pattern)
        layout.addWidget(self.pattern_list)
        
        # Pattern info
        self.pattern_info = QLabel("No pattern selected")
        self.pattern_info.setStyleSheet("font-size: 9px; color: #CCCCCC;")
        self.pattern_info.setWordWrap(True)
        layout.addWidget(self.pattern_info)
        
        # Buttons
        btn_layout1 = QHBoxLayout()
        
        self.save_current_btn = QPushButton("💾 Save")
        self.save_current_btn.setMaximumHeight(22)
        self.save_current_btn.clicked.connect(self.save_current_pattern)
        self.save_current_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: 1px solid #388E3C;
                font-weight: bold;
                font-size: 9px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        
        self.replay_btn = QPushButton("▶️ Play")
        self.replay_btn.setMaximumHeight(22)
        self.replay_btn.clicked.connect(self.replay_selected_pattern)
        self.replay_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: 1px solid #1976D2;
                font-weight: bold;
                font-size: 9px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        btn_layout1.addWidget(self.save_current_btn)
        btn_layout1.addWidget(self.replay_btn)
        layout.addLayout(btn_layout1)
        
        btn_layout2 = QHBoxLayout()
        
        self.load_btn = QPushButton("📂 Load")
        self.load_btn.setMaximumHeight(22)
        self.load_btn.clicked.connect(self.load_pattern_file)
        self.load_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                font-size: 9px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        self.delete_btn = QPushButton("🗑️ Del")
        self.delete_btn.setMaximumHeight(22)
        self.delete_btn.clicked.connect(self.delete_selected_pattern)
        self.delete_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                border: 1px solid #D32F2F;
                font-weight: bold;
                font-size: 9px;
                padding: 2px;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        
        btn_layout2.addWidget(self.load_btn)
        btn_layout2.addWidget(self.delete_btn)
        layout.addLayout(btn_layout2)
        
        # Current pattern storage
        self.current_pattern_steps = []
        self.current_pattern_type = ""
        
        # Connect selection change
        self.pattern_list.currentItemChanged.connect(self.on_pattern_selection_changed)
    
    def set_engine(self, engine: ComparativeEngine):
        self.engine = engine
    
    def store_current_pattern(self, pattern_type: str, steps: List[PatternStep]):
        """Store the current pattern for potential saving"""
        self.current_pattern_steps = steps.copy()
        self.current_pattern_type = pattern_type
        
        # Enable save button
        self.save_current_btn.setEnabled(len(steps) > 0)
        
        if steps:
            actuator_count = len(set(step.actuator_id for step in steps))
            total_duration = max(step.timestamp + step.duration for step in steps) if steps else 0
            self.save_current_btn.setText(f"💾 Save ({actuator_count}a, {total_duration:.0f}ms)")
        else:
            self.save_current_btn.setText("💾 Save")
    
    def save_current_pattern(self):
        """Save the current pattern to library"""
        if not self.current_pattern_steps:
            return
        
        # Get pattern name from user
        from PyQt6.QtWidgets import QInputDialog
        name, ok = QInputDialog.getText(
            self, 
            "Save Pattern",
            f"Name for {self.current_pattern_type} pattern:",
            text=f"{self.current_pattern_type}_{len(self.engine.shared_patterns) + 1}"
        )
        
        if not ok or not name.strip():
            return
        
        name = name.strip()
        
        # Create pattern object
        total_duration = max(step.timestamp + step.duration for step in self.current_pattern_steps)
        pattern = SharedPattern(
            name=name,
            steps=self.current_pattern_steps,
            pattern_type=self.current_pattern_type,
            total_duration=total_duration,
            created_timestamp=time.time(),
            description=f"{self.current_pattern_type} pattern with {len(set(step.actuator_id for step in self.current_pattern_steps))} actuators"
        )
        
        # Save to engine and file
        self.engine.shared_patterns[name] = pattern
        filename = f"patterns/{name.replace(' ', '_')}.json"
        
        # Create patterns directory if it doesn't exist
        os.makedirs("patterns", exist_ok=True)
        
        if self.engine.save_pattern(pattern, filename):
            self.refresh_pattern_list()
            print(f"✅ Pattern '{name}' saved successfully")
        else:
            print(f"❌ Failed to save pattern '{name}'")
    
    def load_patterns_from_disk(self):
        """Load all patterns from the patterns directory"""
        patterns_dir = "patterns"
        if not os.path.exists(patterns_dir):
            os.makedirs(patterns_dir, exist_ok=True)
            return
        
        for filename in os.listdir(patterns_dir):
            if filename.endswith('.json'):
                filepath = os.path.join(patterns_dir, filename)
                try:
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                    pattern = SharedPattern.from_dict(data)
                    if self.engine:
                        self.engine.shared_patterns[pattern.name] = pattern
                except Exception as e:
                    print(f"❌ Failed to load pattern from {filepath}: {e}")
        
        self.refresh_pattern_list()
    
    def refresh_pattern_list(self):
        """Refresh the pattern list display"""
        self.pattern_list.clear()
        
        if not self.engine:
            return
        
        # Group patterns by type
        by_type = {"Buzz": [], "Pulse": [], "Motion": []}
        
        for pattern in self.engine.shared_patterns.values():
            if pattern.pattern_type in by_type:
                by_type[pattern.pattern_type].append(pattern)
        
        # Add patterns to list grouped by type
        for pattern_type, patterns in by_type.items():
            if patterns:
                # Add type header
                header_item = QListWidget.addItem(self.pattern_list, f"═══ {pattern_type} ═══")
                header_item = self.pattern_list.item(self.pattern_list.count() - 1)
                header_item.setData(Qt.ItemDataRole.UserRole, None)  # No pattern data
                
                # Add patterns of this type
                for pattern in sorted(patterns, key=lambda p: p.created_timestamp, reverse=True):
                    actuator_count = len(set(step.actuator_id for step in pattern.steps))
                    item_text = f"  {pattern.name} ({actuator_count}a, {pattern.total_duration:.0f}ms)"
                    
                    item = QListWidget.addItem(self.pattern_list, item_text)
                    item = self.pattern_list.item(self.pattern_list.count() - 1)
                    item.setData(Qt.ItemDataRole.UserRole, pattern)  # Store pattern object
    
    def on_pattern_selection_changed(self, current, previous):
        """Handle pattern selection change"""
        if not current:
            self.pattern_info.setText("No pattern selected")
            return
        
        pattern = current.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            self.pattern_info.setText("Pattern type header")
            return
        
        # Show pattern info
        actuator_ids = sorted(set(step.actuator_id for step in pattern.steps))
        actuator_list = ", ".join(map(str, actuator_ids))
        
        created_time = time.strftime("%Y-%m-%d %H:%M", time.localtime(pattern.created_timestamp))
        
        info_text = (
            f"Type: {pattern.pattern_type}\n"
            f"Actuators: {actuator_list}\n"
            f"Duration: {pattern.total_duration:.0f}ms\n"
            f"Created: {created_time}"
        )
        
        if pattern.description:
            info_text += f"\nDesc: {pattern.description}"
        
        self.pattern_info.setText(info_text)
    
    def replay_selected_pattern(self):
        """Replay the selected pattern"""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            return
        
        pattern = current_item.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            return
        
        # Emit signal to main GUI to execute pattern
        self.pattern_selected.emit(pattern.name, pattern.steps)
        print(f"🔄 Replaying pattern: {pattern.name}")
    
    def load_pattern_file(self):
        """Load pattern from file dialog"""
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Pattern",
            "patterns",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename and self.engine:
            pattern = self.engine.load_pattern(filename)
            if pattern:
                self.refresh_pattern_list()
                print(f"📂 Pattern loaded: {pattern.name}")
            else:
                print(f"❌ Failed to load pattern from {filename}")
    
    def delete_selected_pattern(self):
        """Delete the selected pattern"""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            return
        
        pattern = current_item.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            return
        
        # Confirm deletion
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Delete Pattern",
            f"Delete pattern '{pattern.name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            # Remove from engine
            if pattern.name in self.engine.shared_patterns:
                del self.engine.shared_patterns[pattern.name]
            
            # Remove file
            filename = f"patterns/{pattern.name.replace(' ', '_')}.json"
            if os.path.exists(filename):
                os.remove(filename)
            
            # Refresh list
            self.refresh_pattern_list()
            print(f"🗑️ Pattern '{pattern.name}' deleted")


# Ajouts dans setup_ui() de ComparativePatternGUI :
# Après self.global_params :
        # Pattern Library
        self.pattern_library = PatternLibraryPanel()
        self.pattern_library.set_engine(self.engine)


# Ajouts dans setup_connections() de ComparativePatternGUI :
# Après phantoms_toggled :
        # Pattern library
        self.pattern_library.pattern_selected.connect(self.replay_library_pattern)


# Modification de execute_pattern() dans ComparativePatternGUI :
    def execute_pattern(self, pattern_type: str, steps: List[PatternStep]):
        """Execute pattern and show comparison info"""
        self.engine.execute_pattern(steps)
        
        # Store pattern in library for potential saving
        self.pattern_library.store_current_pattern(pattern_type, steps)
        
        # Update visualization
        self.viz.update()
        
        # Show pattern comparison info
        phantom_info = ""
        if pattern_type == "Motion" and self.engine.phantoms_enabled:
            phantom_count = len(self.engine.enhanced_phantoms)
            phantom_info = f" using {phantom_count} phantoms"
        elif pattern_type == "Motion" and not self.engine.phantoms_enabled:
            phantom_info = " (phantoms disabled - limited smoothness)"
        
        self.info_text.setPlainText(
            f"▶️ Executing {pattern_type} pattern{phantom_info}\n"
            f"Steps: {len(steps)}, Waveform: {self.engine.waveform_type} @ {self.engine.frequency}Hz\n"
            f"💡 Compare with other pattern types to see motion superiority!"
        )


# Nouvelle méthode à ajouter dans ComparativePatternGUI :
    def replay_library_pattern(self, pattern_name: str, steps: List[PatternStep]):
        """Replay a pattern from the library"""
        self.engine.execute_pattern(steps)
        
        # Update visualization
        self.viz.update()
        
        # Show replay info
        pattern_type = steps[0].pattern_type if steps else "Unknown"
        actuator_count = len(set(step.actuator_id for step in steps))
        total_duration = max(step.timestamp + step.duration for step in steps) if steps else 0
        
        self.info_text.setPlainText(
            f"🔄 Replaying library pattern: {pattern_name}\n"
            f"Type: {pattern_type}, Actuators: {actuator_count}, Duration: {total_duration:.0f}ms\n"
            f"📚 Pattern loaded from library and executed successfully!"
        )

class ComparativePatternGUI(QWidget):
    """Main GUI for comparative pattern testing"""
    
    def __init__(self):
        super().__init__()
        self.engine = ComparativeEngine()
        self.api = None
        self.setup_ui()
        self.setup_api()
        self.setup_connections()

class PatternTabBase(QWidget):
    """Base class for pattern tabs"""
    
    pattern_executed = pyqtSignal(str, list)  # pattern_type, steps
    
    def __init__(self, pattern_type: str):
        super().__init__()
        self.pattern_type = pattern_type
        self.engine = None
        
    def set_engine(self, engine: ComparativeEngine):
        self.engine = engine

class BuzzPatternTab(PatternTabBase):
    """Tab for Buzz patterns - static vibration"""

    def __init__(self):
        super().__init__("Buzz")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(3)

        # Description
        desc = QLabel("🔊 BUZZ - Static vibration")
        desc.setStyleSheet("font-weight: bold; font-size: 12px; color: #FF5722;")
        layout.addWidget(desc)

        # Controls
        controls_group = QGroupBox("Controls")
        controls_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        controls_layout = QVBoxLayout(controls_group)
        controls_layout.setSpacing(3)

        self.selection_info = QLabel("No actuators selected")
        self.selection_info.setStyleSheet("font-weight: bold; font-size: 10px; color: #FFFFFF;")
        controls_layout.addWidget(self.selection_info)

        button_layout = QHBoxLayout()

        self.clear_selection_btn = QPushButton("Clear")
        self.clear_selection_btn.setMaximumHeight(25)
        self.clear_selection_btn.clicked.connect(self.clear_selection)

        self.select_all_btn = QPushButton("All")
        self.select_all_btn.setMaximumHeight(25)
        self.select_all_btn.clicked.connect(self.select_all)

        self.create_buzz_btn = QPushButton("🔊 Buzz")
        self.create_buzz_btn.setMaximumHeight(25)
        self.create_buzz_btn.clicked.connect(self.create_buzz_pattern)

        button_layout.addWidget(self.clear_selection_btn)
        button_layout.addWidget(self.select_all_btn)
        button_layout.addWidget(self.create_buzz_btn)
        controls_layout.addLayout(button_layout)

        layout.addWidget(controls_group)

        # Presets
        presets_group = QGroupBox("Presets")
        presets_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        presets_layout = QVBoxLayout(presets_group)
        presets_layout.setSpacing(2)

        preset_buttons = [
            ("Top (2)", [0, 1]),
            ("Row 2 (4)", [5, 4, 3, 2]),
            ("Row 3 (4)", [6, 7, 8, 9]),
            ("Row 4 (4)", [13, 12, 11, 10]),
            ("Bottom (2)", [14, 15]),
            ("Center", [1, 4, 7, 12, 15]),
            ("Outer Ring", [0, 1, 2, 9, 10, 15, 14, 13, 6, 5])
        ]

        for name, actuators in preset_buttons:
            btn = QPushButton(name)
            btn.setMaximumHeight(22)
            btn.clicked.connect(lambda checked, acts=actuators: self.select_preset(acts))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3E3E3E;
                    color: white;
                    border: 1px solid #555;
                    padding: 2px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #4E4E4E;
                }
            """)
            presets_layout.addWidget(btn)

        layout.addWidget(presets_group)

        # Phantoms section (identique Motion)
        phantom_group = QGroupBox("Phantoms")
        phantom_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        phantom_layout = QVBoxLayout(phantom_group)
        phantom_layout.setSpacing(3)

        phantom_info_layout = QHBoxLayout()
        self.phantom_info = QLabel("0 phantoms")
        self.phantom_info.setStyleSheet("font-size: 10px; color: #FFFFFF;")

        self.clear_phantoms_btn = QPushButton("Clear")
        self.clear_phantoms_btn.setMaximumHeight(25)
        self.clear_phantoms_btn.clicked.connect(self.clear_phantoms)
        self.clear_phantoms_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)

        phantom_info_layout.addWidget(self.phantom_info)
        phantom_info_layout.addWidget(self.clear_phantoms_btn)
        phantom_layout.addLayout(phantom_info_layout)
        layout.addWidget(phantom_group)

        layout.addStretch()

    def update_selection_info(self):
        if not self.engine:
            return
        count = len(self.engine.selected_actuators)
        if count == 0:
            self.selection_info.setText("No actuators selected")
        else:
            actuator_list = ", ".join(map(str, sorted(self.engine.selected_actuators)))
            self.selection_info.setText(f"Selected: {actuator_list}")

    def clear_selection(self):
        if self.engine:
            self.engine.clear_selection()
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def select_all(self):
        if self.engine:
            self.engine.selected_actuators = set(ACTUATORS)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def select_preset(self, actuators: List[int]):
        if self.engine:
            self.engine.selected_actuators = set(actuators)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def create_buzz_pattern(self):
        if not self.engine or not self.engine.selected_actuators:
            return

        steps = self.engine.create_buzz_pattern()
        if steps:
            self.pattern_executed.emit("Buzz", steps)

    def clear_phantoms(self):
        if self.engine:
            self.engine.clear_phantoms()
            self.update_phantom_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def update_phantom_info(self):
        if self.engine:
            count = len(self.engine.enhanced_phantoms)
            self.phantom_info.setText(f"{count} phantoms")


    def update_selection_info(self):
        if not self.engine:
            return
        count = len(self.engine.selected_actuators)
        if count == 0:
            self.selection_info.setText("No actuators selected")
        else:
            actuator_list = ", ".join(map(str, sorted(self.engine.selected_actuators)))
            self.selection_info.setText(f"Selected: {actuator_list}")

    def clear_selection(self):
        if self.engine:
            self.engine.clear_selection()
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def select_all(self):
        if self.engine:
            self.engine.selected_actuators = set(ACTUATORS)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def select_preset(self, actuators: List[int]):
        if self.engine:
            self.engine.selected_actuators = set(actuators)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def create_buzz_pattern(self):
        if not self.engine or not self.engine.selected_actuators:
            return

        steps = self.engine.create_buzz_pattern()
        if steps:
            self.pattern_executed.emit("Buzz", steps)

    def clear_phantoms(self):
        if self.engine:
            self.engine.clear_phantoms()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    
    def update_selection_info(self):
        if not self.engine:
            return
        count = len(self.engine.selected_actuators)
        if count == 0:
            self.selection_info.setText("No actuators selected")
        else:
            actuator_list = ", ".join(map(str, sorted(self.engine.selected_actuators)))
            self.selection_info.setText(f"Selected: {actuator_list}")
    
    def clear_selection(self):
        if self.engine:
            self.engine.clear_selection()
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def select_all(self):
        if self.engine:
            self.engine.selected_actuators = set(ACTUATORS)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def select_preset(self, actuators: List[int]):
        if self.engine:
            self.engine.selected_actuators = set(actuators)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def create_buzz_pattern(self):
        if not self.engine or not self.engine.selected_actuators:
            return
        
        steps = self.engine.create_buzz_pattern()
        if steps:
            self.pattern_executed.emit("Buzz", steps)

class PulsePatternTab(PatternTabBase):
    """Tab for Pulse patterns - rhythmic vibration"""

    def __init__(self):
        super().__init__("Pulse")
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(3)

        # Description
        desc = QLabel("📳 PULSE - Rhythmic patterns")
        desc.setStyleSheet("font-weight: bold; font-size: 12px; color: #FF9800;")
        layout.addWidget(desc)

        # Controls
        controls_group = QGroupBox("Controls")
        controls_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        controls_layout = QFormLayout(controls_group)
        controls_layout.setVerticalSpacing(3)

        # Pulse interval
        self.pulse_interval_spin = QSpinBox()
        self.pulse_interval_spin.setRange(50, 1000)
        self.pulse_interval_spin.setValue(200)
        self.pulse_interval_spin.setSuffix(" ms")
        self.pulse_interval_spin.setMaximumHeight(25)
        self.pulse_interval_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
        """)

        interval_label = QLabel("Interval:")
        interval_label.setStyleSheet("color: white; font-weight: bold;")
        controls_layout.addRow(interval_label, self.pulse_interval_spin)

        # Selection info
        self.selection_info = QLabel("No actuators selected")
        self.selection_info.setStyleSheet("font-weight: bold; font-size: 10px; color: #FFFFFF;")
        selection_label = QLabel("Selection:")
        selection_label.setStyleSheet("color: white; font-weight: bold;")
        controls_layout.addRow(selection_label, self.selection_info)

        layout.addWidget(controls_group)

        # Buttons
        button_layout = QHBoxLayout()

        self.clear_selection_btn = QPushButton("Clear")
        self.clear_selection_btn.setMaximumHeight(25)
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)

        self.create_pulse_btn = QPushButton("📳 Pulse")
        self.create_pulse_btn.setMaximumHeight(25)
        self.create_pulse_btn.clicked.connect(self.create_pulse_pattern)
        self.create_pulse_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 5px;
                font-weight: bold;
                border-radius: 3px;
                border: 1px solid #F57C00;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)

        button_layout.addWidget(self.clear_selection_btn)
        button_layout.addWidget(self.create_pulse_btn)
        layout.addLayout(button_layout)

        # Presets
        presets_group = QGroupBox("Presets")
        presets_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        presets_layout = QVBoxLayout(presets_group)
        presets_layout.setSpacing(2)

        preset_buttons = [
            ("Cable Wave", [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]),
            ("Center Flow", [1, 4, 7, 12, 15]),
            ("Side Waves", [5, 6, 13, 14]),
            ("Zigzag", [0, 2, 6, 10, 14]),
            ("Cross", [0, 4, 8, 12, 15])
        ]

        for name, actuators in preset_buttons:
            btn = QPushButton(name)
            btn.setMaximumHeight(22)
            btn.clicked.connect(lambda checked, acts=actuators: self.select_preset(acts))
            btn.setStyleSheet("""
                QPushButton {
                    background-color: #3E3E3E;
                    color: white;
                    border: 1px solid #555;
                    padding: 2px;
                    text-align: left;
                }
                QPushButton:hover {
                    background-color: #4E4E4E;
                }
            """)
            presets_layout.addWidget(btn)

        layout.addWidget(presets_group)

        # Phantoms section (identique Motion)
        phantom_group = QGroupBox("Phantoms")
        phantom_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        phantom_layout = QVBoxLayout(phantom_group)
        phantom_layout.setSpacing(3)

        phantom_info_layout = QHBoxLayout()
        self.phantom_info = QLabel("0 phantoms")
        self.phantom_info.setStyleSheet("font-size: 10px; color: #FFFFFF;")

        self.clear_phantoms_btn = QPushButton("Clear")
        self.clear_phantoms_btn.setMaximumHeight(25)
        self.clear_phantoms_btn.clicked.connect(self.clear_phantoms)
        self.clear_phantoms_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)

        phantom_info_layout.addWidget(self.phantom_info)
        phantom_info_layout.addWidget(self.clear_phantoms_btn)
        phantom_layout.addLayout(phantom_info_layout)
        layout.addWidget(phantom_group)

        layout.addStretch()

    def update_selection_info(self):
        if not self.engine:
            return
        count = len(self.engine.selected_actuators)
        if count == 0:
            self.selection_info.setText("No selection")
        else:
            self.selection_info.setText(f"{count} selected")

    def clear_selection(self):
        if self.engine:
            self.engine.clear_selection()
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def select_preset(self, actuators: List[int]):
        if self.engine:
            self.engine.selected_actuators = set(actuators)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def create_pulse_pattern(self):
        if not self.engine or not self.engine.selected_actuators:
            return

        pulse_interval = self.pulse_interval_spin.value()
        steps = self.engine.create_pulse_pattern(pulse_interval)
        if steps:
            self.pattern_executed.emit("Pulse", steps)

    def clear_phantoms(self):
        if self.engine:
            self.engine.clear_phantoms()
            self.update_phantom_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()

    def update_phantom_info(self):
        if self.engine:
            count = len(self.engine.enhanced_phantoms)
            self.phantom_info.setText(f"{count} phantoms")

    
    def update_selection_info(self):
        if not self.engine:
            return
        count = len(self.engine.selected_actuators)
        if count == 0:
            self.selection_info.setText("No selection")
        else:
            self.selection_info.setText(f"{count} selected")
    
    def clear_selection(self):
        if self.engine:
            self.engine.clear_selection()
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def select_preset(self, actuators: List[int]):
        if self.engine:
            self.engine.selected_actuators = set(actuators)
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def create_pulse_pattern(self):
        if not self.engine or not self.engine.selected_actuators:
            return
        
        pulse_interval = self.pulse_interval_spin.value()
        steps = self.engine.create_pulse_pattern(pulse_interval)
        if steps:
            self.pattern_executed.emit("Pulse", steps)

class MotionPatternTab(PatternTabBase):
    """Tab for Motion patterns - smooth movement with multi-trajectory phantoms"""
    
    def __init__(self):
        super().__init__("Motion")
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(3)
        
        # Description (compact)
        desc = QLabel("🌊 MOTION - Multi-trajectory phantoms")
        desc.setStyleSheet("font-weight: bold; font-size: 12px; color: #4CAF50;")
        layout.addWidget(desc)
        
        # Multi-trajectory controls
        multi_traj_group = QGroupBox("Multi-Trajectory Drawing")
        multi_traj_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        multi_traj_layout = QVBoxLayout(multi_traj_group)
        multi_traj_layout.setSpacing(3)
        
        # Phantom spacing control
        spacing_layout = QHBoxLayout()
        spacing_label = QLabel("Phantom spacing:")
        spacing_label.setStyleSheet("color: white; font-weight: bold; font-size: 10px;")
        spacing_layout.addWidget(spacing_label)
        
        self.phantom_spacing_spin = QSpinBox()
        self.phantom_spacing_spin.setRange(50, 500)
        self.phantom_spacing_spin.setValue(100)
        self.phantom_spacing_spin.setSuffix(" ms")
        self.phantom_spacing_spin.setMaximumHeight(25)
        self.phantom_spacing_spin.setStyleSheet("""
            QSpinBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
        """)
        self.phantom_spacing_spin.valueChanged.connect(self.update_phantom_spacing)
        
        spacing_layout.addWidget(self.phantom_spacing_spin)
        multi_traj_layout.addLayout(spacing_layout)
        
        # Trajectory info
        self.trajectory_info = QLabel("0 trajectories")
        self.trajectory_info.setStyleSheet("font-size: 10px; color: #FFFFFF;")
        multi_traj_layout.addWidget(self.trajectory_info)
        
        # Multi-trajectory buttons row 1
        multi_btn_layout1 = QHBoxLayout()
        
        self.start_drawing_btn = QPushButton("🎨 Draw")
        self.start_drawing_btn.setMaximumHeight(25)
        self.start_drawing_btn.clicked.connect(self.toggle_drawing_mode)
        self.start_drawing_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 5px;
                font-weight: bold;
                border-radius: 3px;
                border: 1px solid #1976D2;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        self.new_trajectory_btn = QPushButton("➕ New")
        self.new_trajectory_btn.setMaximumHeight(25)
        self.new_trajectory_btn.clicked.connect(self.start_new_trajectory)
        self.new_trajectory_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                padding: 5px;
                font-weight: bold;
                border-radius: 3px;
                border: 1px solid #388E3C;
            }
            QPushButton:hover {
                background-color: #388E3C;
            }
        """)
        
        multi_btn_layout1.addWidget(self.start_drawing_btn)
        multi_btn_layout1.addWidget(self.new_trajectory_btn)
        multi_traj_layout.addLayout(multi_btn_layout1)
        
        # Multi-trajectory buttons row 2
        multi_btn_layout2 = QHBoxLayout()
        
        self.play_all_btn = QPushButton("▶️ Play All")
        self.play_all_btn.setMaximumHeight(25)
        self.play_all_btn.clicked.connect(self.play_all_trajectories)
        self.play_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #FF9800;
                color: white;
                padding: 5px;
                font-weight: bold;
                border-radius: 3px;
                border: 1px solid #F57C00;
            }
            QPushButton:hover {
                background-color: #F57C00;
            }
        """)
        
        self.clear_all_btn = QPushButton("🗑️ Clear All")
        self.clear_all_btn.setMaximumHeight(25)
        self.clear_all_btn.clicked.connect(self.clear_all_trajectories)
        self.clear_all_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 5px;
                font-weight: bold;
                border-radius: 3px;
                border: 1px solid #D32F2F;
            }
            QPushButton:hover {
                background-color: #D32F2F;
            }
        """)
        
        multi_btn_layout2.addWidget(self.play_all_btn)
        multi_btn_layout2.addWidget(self.clear_all_btn)
        multi_traj_layout.addLayout(multi_btn_layout2)
        
        layout.addWidget(multi_traj_group)
        
        # Drawing state info
        drawing_group = QGroupBox("Drawing State")
        drawing_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        drawing_layout = QVBoxLayout(drawing_group)
        drawing_layout.setSpacing(3)
        
        self.drawing_info = QLabel("Ready to draw")
        self.drawing_info.setStyleSheet("font-size: 10px; color: #FFFFFF;")
        drawing_layout.addWidget(self.drawing_info)
        
        # Current trajectory controls
        current_traj_layout = QHBoxLayout()
        
        self.clear_current_btn = QPushButton("Clear Current")
        self.clear_current_btn.setMaximumHeight(25)
        self.clear_current_btn.clicked.connect(self.clear_current_trajectory)
        self.clear_current_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        self.play_current_btn = QPushButton("▶️ Current")
        self.play_current_btn.setMaximumHeight(25)
        self.play_current_btn.clicked.connect(self.play_current_trajectory)
        self.play_current_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        current_traj_layout.addWidget(self.clear_current_btn)
        current_traj_layout.addWidget(self.play_current_btn)
        drawing_layout.addLayout(current_traj_layout)
        
        layout.addWidget(drawing_group)
        
        # Sequential motion (existing functionality)
        sequence_group = QGroupBox("Sequential")
        sequence_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        sequence_layout = QVBoxLayout(sequence_group)
        sequence_layout.setSpacing(3)
        
        self.selection_info = QLabel("No actuators selected")
        self.selection_info.setStyleSheet("font-weight: bold; font-size: 10px; color: #FFFFFF;")
        sequence_layout.addWidget(self.selection_info)
        
        seq_btn_layout = QHBoxLayout()
        
        self.clear_selection_btn = QPushButton("Clear")
        self.clear_selection_btn.setMaximumHeight(25)
        self.clear_selection_btn.clicked.connect(self.clear_selection)
        self.clear_selection_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        self.create_sequence_btn = QPushButton("⚡ Sequence")
        self.create_sequence_btn.setMaximumHeight(25)
        self.create_sequence_btn.clicked.connect(self.create_motion_pattern)
        self.create_sequence_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        seq_btn_layout.addWidget(self.clear_selection_btn)
        seq_btn_layout.addWidget(self.create_sequence_btn)
        sequence_layout.addLayout(seq_btn_layout)
        
        layout.addWidget(sequence_group)
        
        # Phantom management
        phantom_group = QGroupBox("Phantoms")
        phantom_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        phantom_layout = QVBoxLayout(phantom_group)
        phantom_layout.setSpacing(3)
        
        phantom_info_layout = QHBoxLayout()
        self.phantom_info = QLabel("0 phantoms")
        self.phantom_info.setStyleSheet("font-size: 10px; color: #FFFFFF;")
        
        self.clear_phantoms_btn = QPushButton("Clear")
        self.clear_phantoms_btn.setMaximumHeight(25)
        self.clear_phantoms_btn.clicked.connect(self.clear_phantoms)
        self.clear_phantoms_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        phantom_info_layout.addWidget(self.phantom_info)
        phantom_info_layout.addWidget(self.clear_phantoms_btn)
        phantom_layout.addLayout(phantom_info_layout)
        
        layout.addWidget(phantom_group)
        layout.addStretch()
    
    def update_phantom_spacing(self):
        """Update phantom spacing in engine"""
        if self.engine:
            spacing = self.phantom_spacing_spin.value()
            self.engine.set_phantom_spacing(spacing)
    
    def update_trajectory_info(self):
        """Update trajectory count display"""
        if not self.engine:
            return
        
        count = len(self.engine.trajectory_collection)
        current = " (+1 current)" if self.engine.current_trajectory else ""
        self.trajectory_info.setText(f"{count} trajectories{current}")
    
    def update_drawing_info(self):
        """Update drawing state info"""
        if not self.engine:
            return
        
        if self.engine.drawing_mode:
            trajectory_length = len(self.engine.current_trajectory)
            self.drawing_info.setText(f"Drawing: {trajectory_length} pts")
        else:
            trajectory_length = len(self.engine.current_trajectory)
            if trajectory_length > 0:
                self.drawing_info.setText(f"Current: {trajectory_length} points")
            else:
                self.drawing_info.setText("Ready to draw")
    
    def update_selection_info(self):
        """Update selection info"""
        if not self.engine:
            return
        count = len(self.engine.selected_actuators)
        if count == 0:
            self.selection_info.setText("No selection")
        else:
            self.selection_info.setText(f"{count} selected")
    
    def update_phantom_info(self):
        """Update phantom count info"""
        if not self.engine:
            return
        count = len(self.engine.enhanced_phantoms)
        self.phantom_info.setText(f"{count} phantoms")
    
    def toggle_drawing_mode(self):
        """Toggle trajectory drawing mode"""
        if not self.engine:
            return
        
        if not self.engine.drawing_mode:
            self.engine.start_drawing_mode()
            self.start_drawing_btn.setText("⏹️ Stop")
            self.start_drawing_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF5722;
                    color: white;
                    padding: 5px;
                    font-weight: bold;
                    border-radius: 3px;
                }
            """)
        else:
            self.engine.stop_drawing_mode()
            self.start_drawing_btn.setText("🎨 Draw")
            self.start_drawing_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 5px;
                    font-weight: bold;
                    border-radius: 3px;
                }
            """)
        
        self.update_drawing_info()
    
    def start_new_trajectory(self):
        """Start a new trajectory"""
        if self.engine:
            self.engine.add_new_trajectory()
            self.update_trajectory_info()
            self.update_drawing_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def play_all_trajectories(self):
        """Play all trajectories simultaneously"""
        if not self.engine:
            return
        
        steps = self.engine.execute_all_trajectories()
        if steps:
            self.pattern_executed.emit("Motion", steps)
        else:
            # No trajectories to play
            print("No trajectories to play")
    
    def play_current_trajectory(self):
        """Play only the current trajectory"""
        if not self.engine or len(self.engine.current_trajectory) < 2:
            return
        
        # Create motion pattern from current trajectory only
        steps = self.engine.create_motion_pattern()
        if steps:
            self.pattern_executed.emit("Motion", steps)
    
    def clear_all_trajectories(self):
        """Clear all trajectories"""
        if self.engine:
            self.engine.clear_all_trajectories()
            self.update_trajectory_info()
            self.update_drawing_info()
            self.update_phantom_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def clear_current_trajectory(self):
        """Clear only the current trajectory"""
        if self.engine:
            self.engine.current_trajectory = []
            self.update_drawing_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def clear_selection(self):
        """Clear actuator selection"""
        if self.engine:
            self.engine.clear_selection()
            self.update_selection_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def clear_phantoms(self):
        """Clear all phantoms"""
        if self.engine:
            self.engine.clear_phantoms()
            self.update_phantom_info()
            if hasattr(self, 'parent_gui') and hasattr(self.parent_gui, 'viz'):
                self.parent_gui.viz.update()
    
    def create_motion_pattern(self):
        """Create motion pattern (legacy - for sequential motion)"""
        if not self.engine:
            return
        
        steps = self.engine.create_motion_pattern()
        if steps:
            self.pattern_executed.emit("Motion", steps)

class ComparativePatternGUI(QWidget):
    """Main GUI for comparative pattern testing"""
    
    def __init__(self):
        super().__init__()
        self.engine = ComparativeEngine()
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
        """Connect all signals"""
        # Global parameters
        self.global_params.parameters_changed.connect(self.on_global_parameters_changed)
        self.global_params.phantoms_toggled.connect(self.engine.toggle_phantoms)
        self.pattern_library.pattern_selected.connect(self.replay_library_pattern)
        
        # Visualization
        self.viz.actuator_clicked.connect(self.on_actuator_clicked)
        self.viz.phantom_requested.connect(self.on_phantom_requested)
        self.viz.trajectory_point_added.connect(self.on_trajectory_point_added)
        
        # Pattern tabs
        self.buzz_tab.pattern_executed.connect(self.execute_pattern)
        self.pulse_tab.pattern_executed.connect(self.execute_pattern)
        self.motion_tab.pattern_executed.connect(self.execute_pattern)
        
        # Update timer for UI refreshes
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_displays)
        self.update_timer.start(100)  # Update every 100ms
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Left panel for controls in scroll area
        left_scroll = QScrollArea()
        left_scroll.setMaximumWidth(380)
        left_scroll.setMinimumWidth(380)
        left_scroll.setWidgetResizable(True)
        
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setSpacing(5)
        
        # Title (compact)
        title = QLabel("🎯 Comparative Pattern Interface")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #FFFFFF;")
        left_layout.addWidget(title)
        
        subtitle = QLabel("Boss's Layout (2-4-4-4-2)")
        subtitle.setStyleSheet("font-style: italic; color: #CCCCCC; font-size: 10px;")
        left_layout.addWidget(subtitle)
        
        # Connection (compact)
        conn_group = QGroupBox("Connection")
        conn_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                color: #FFFFFF;
                border: 1px solid #555;
                margin-top: 5px;
                padding-top: 5px;
            }
            QGroupBox::title {
                color: #FFFFFF;
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
        """)
        conn_layout = QVBoxLayout(conn_group)
        conn_layout.setSpacing(3)
        
        # First row: device and refresh
        conn_row1 = QHBoxLayout()
        
        device_label = QLabel("Device:")
        device_label.setStyleSheet("color: white; font-weight: bold;")
        
        self.device_combo = QComboBox()
        self.device_combo.setMaximumHeight(25)
        self.device_combo.setStyleSheet("""
            QComboBox {
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 2px;
            }
        """)
        
        self.refresh_btn = QPushButton("↻")
        self.refresh_btn.setMaximumWidth(30)
        self.refresh_btn.setMaximumHeight(25)
        self.refresh_btn.setStyleSheet("""
            QPushButton {
                background-color: #555;
                color: white;
                border: 1px solid #777;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #666;
            }
        """)
        
        conn_row1.addWidget(device_label)
        conn_row1.addWidget(self.device_combo)
        conn_row1.addWidget(self.refresh_btn)
        
        # Second row: connect and status
        conn_row2 = QHBoxLayout()
        
        self.connect_btn = QPushButton("Connect")
        self.connect_btn.setMaximumHeight(25)
        self.connect_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: 1px solid #1976D2;
                font-weight: bold;
                padding: 3px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
        """)
        
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #FF5722; font-weight: bold; font-size: 10px;")
        
        conn_row2.addWidget(self.connect_btn)
        conn_row2.addWidget(self.status_label)
        
        conn_layout.addLayout(conn_row1)
        conn_layout.addLayout(conn_row2)
        
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.connect_btn.clicked.connect(self.toggle_connection)
        left_layout.addWidget(conn_group)
        
        # Global parameters (compact)
        self.global_params = GlobalParametersPanel()
        left_layout.addWidget(self.global_params)
        self.pattern_library = PatternLibraryPanel()
        self.pattern_library.set_engine(self.engine)
        left_layout.addWidget(self.pattern_library)
                
        # Tab widget for pattern types
        self.tab_widget = QTabWidget()
        
        # Pattern tabs with parent reference for visualization updates
        self.buzz_tab = BuzzPatternTab()
        self.buzz_tab.set_engine(self.engine)
        self.buzz_tab.parent_gui = self  # Reference to main GUI for viz updates
        self.tab_widget.addTab(self.buzz_tab, "🔊 Buzz")
        
        self.pulse_tab = PulsePatternTab()
        self.pulse_tab.set_engine(self.engine)
        self.pulse_tab.parent_gui = self  # Reference to main GUI for viz updates
        self.tab_widget.addTab(self.pulse_tab, "📳 Pulse")
        
        self.motion_tab = MotionPatternTab()
        self.motion_tab.set_engine(self.engine)
        self.motion_tab.parent_gui = self  # Reference to main GUI for viz updates
        self.tab_widget.addTab(self.motion_tab, "🌊 Motion")
        
        left_layout.addWidget(self.tab_widget)
        
        # Emergency stop (compact)
        self.stop_btn = QPushButton("🛑 EMERGENCY STOP")
        self.stop_btn.clicked.connect(self.emergency_stop)
        self.stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
                border-radius: 4px;
            }
        """)
        left_layout.addWidget(self.stop_btn)
        
        left_scroll.setWidget(left_panel)
        
        # Right panel for visualization
        right_panel = QWidget()
        right_panel.setMinimumWidth(600)  # Ensure minimum width for visualization
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # Visualization
        self.viz = SharedVisualization()
        self.viz.set_engine(self.engine)
        self.viz.setMinimumHeight(500)
        self.viz.setMinimumWidth(580)  # Ensure visualization is visible
        right_layout.addWidget(self.viz)
        
        # Status and info (compact)
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(60)
        self.info_text.setReadOnly(True)
        self.info_text.setStyleSheet("""
            QTextEdit {
                font-size: 10px;
                background-color: #3E3E3E;
                color: white;
                border: 1px solid #555;
                padding: 5px;
            }
        """)
        self.info_text.setPlainText(
            "🎯 Boss's Layout Ready! • Buzz: Static • Pulse: Rhythmic • Motion: Smooth phantoms"
        )
        right_layout.addWidget(self.info_text)
        
        # Add panels to layout with proper sizing
        layout.addWidget(left_scroll, 0)  # Fixed size
        layout.addWidget(right_panel, 1)  # Expandable
        
        # Initialize displays
        self.update_displays()
    
    def refresh_devices(self):
        """Refresh serial device list"""
        if not self.api:
            return
        self.device_combo.clear()
        devices = self.api.get_serial_devices()
        if devices:
            self.device_combo.addItems(devices)
    
    def toggle_connection(self):
        """Toggle serial connection"""
        if not self.api:
            return
        
        if not self.api.connected:
            if self.device_combo.currentText():
                if self.api.connect_serial_device(self.device_combo.currentText()):
                    self.status_label.setText("Connected ✓")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.connect_btn.setText("Disconnect")
                    self.info_text.setPlainText("✅ Device connected - ready for pattern testing!")
        else:
            if self.api.disconnect_serial_device():
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                self.connect_btn.setText("Connect")
                self.info_text.setPlainText("❌ Device disconnected")
    
    def on_global_parameters_changed(self, waveform_type: str, frequency: float, 
                                   intensity: int, duration: int):
        """Handle global parameter changes"""
        self.engine.set_global_parameters(waveform_type, frequency, intensity, duration)
        self.info_text.setPlainText(
            f"🎛️ Global parameters updated:\n"
            f"Waveform: {waveform_type}, Frequency: {frequency}Hz, "
            f"Intensity: {intensity}, Duration: {duration}ms"
        )
    
    def on_actuator_clicked(self, actuator_id: int):
        """Handle actuator click for selection"""
        self.engine.toggle_actuator_selection(actuator_id)
        self.update_displays()
        self.viz.update()
        
        # Update info based on current tab
        current_tab = self.tab_widget.currentWidget()
        if isinstance(current_tab, (BuzzPatternTab, PulsePatternTab, MotionPatternTab)):
            selected_count = len(self.engine.selected_actuators)
            self.info_text.setPlainText(
                f"🖱️ Actuator {actuator_id} {'selected' if actuator_id in self.engine.selected_actuators else 'deselected'}\n"
                f"Total selected: {selected_count} actuators"
            )
    
    def on_phantom_requested(self, x: float, y: float):
        """Handle phantom creation request"""
        if not self.engine.phantoms_enabled:
            self.info_text.setPlainText("❌ Phantoms are disabled - enable in Global Parameters")
            return
        
        phantom = self.engine.create_phantom((x, y), self.engine.intensity)
        if phantom:
            self.viz.update()
            self.update_displays()
            self.info_text.setPlainText(
                f"✅ Phantom created at ({x:.0f}, {y:.0f})\n"
                f"Using actuators: {phantom.physical_actuator_1}, {phantom.physical_actuator_2}, {phantom.physical_actuator_3}"
            )
        else:
            self.info_text.setPlainText(
                f"❌ Failed to create phantom at ({x:.0f}, {y:.0f})\n"
                f"Try closer to actuators or enable phantoms"
            )
    
    def on_trajectory_point_added(self, x: float, y: float):
        """Handle trajectory point addition"""
        self.viz.update()
        if hasattr(self.motion_tab, 'update_drawing_info'):
            self.motion_tab.update_drawing_info()
    
    def execute_pattern(self, pattern_type: str, steps: List[PatternStep]):
        """Execute pattern and show comparison info"""
        self.engine.execute_pattern(steps)
        self.pattern_library.store_current_pattern(pattern_type, steps)
        
        # Update visualization
        self.viz.update()
        
        # Show pattern comparison info
        phantom_info = ""
        if pattern_type == "Motion" and self.engine.phantoms_enabled:
            phantom_count = len(self.engine.enhanced_phantoms)
            phantom_info = f" using {phantom_count} phantoms"
        elif pattern_type == "Motion" and not self.engine.phantoms_enabled:
            phantom_info = " (phantoms disabled - limited smoothness)"
        
        self.info_text.setPlainText(
            f"▶️ Executing {pattern_type} pattern{phantom_info}\n"
            f"Steps: {len(steps)}, Waveform: {self.engine.waveform_type} @ {self.engine.frequency}Hz\n"
            f"💡 Compare with other pattern types to see motion superiority!"
        )
    
    # Dans la classe ComparativePatternGUI, ajoutez cette méthode :

    def replay_library_pattern(self, pattern_name: str, steps: List[PatternStep]):
        """Replay a pattern from the library"""
        self.engine.execute_pattern(steps)
        
        # Update visualization
        self.viz.update()
        
        # Show replay info
        pattern_type = steps[0].pattern_type if steps else "Unknown"
        actuator_count = len(set(step.actuator_id for step in steps))
        total_duration = max(step.timestamp + step.duration for step in steps) if steps else 0
        
        self.info_text.setPlainText(
            f"🔄 Replaying library pattern: {pattern_name}\n"
            f"Type: {pattern_type}, Actuators: {actuator_count}, Duration: {total_duration:.0f}ms\n"
            f"📚 Pattern loaded from library and executed successfully!"
        )
    
    def update_displays(self):
        """Update all tab displays"""
        if hasattr(self.buzz_tab, 'update_selection_info'):
            self.buzz_tab.update_selection_info()
        if hasattr(self.pulse_tab, 'update_selection_info'):
            self.pulse_tab.update_selection_info()
        if hasattr(self.motion_tab, 'update_selection_info'):
            self.motion_tab.update_selection_info()
        if hasattr(self.motion_tab, 'update_drawing_info'):
            self.motion_tab.update_drawing_info()
        if hasattr(self.motion_tab, 'update_phantom_info'):
            self.motion_tab.update_phantom_info()
    
    def emergency_stop(self):
        """Emergency stop all activity"""
        self.engine.stop_all_actuators()
        self.viz.update()
        self.info_text.setPlainText(
            "🛑 EMERGENCY STOP ACTIVATED\n"
            "All actuators stopped. System ready for new patterns."
        )
    
    def closeEvent(self, event):
        """Clean shutdown"""
        self.emergency_stop()
        if self.api and self.api.connected:
            self.api.disconnect_serial_device()
        event.accept()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🎯 Boss Layout - Buzz vs Pulse vs Motion Comparison")
    
    widget = ComparativePatternGUI()
    window.setCentralWidget(widget)
    window.resize(1200, 700)
    window.show()
    
    sys.exit(app.exec())