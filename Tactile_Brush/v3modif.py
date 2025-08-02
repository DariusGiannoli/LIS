#!/usr/bin/env python3
"""
Enhanced Interactive Tactile Pattern Creator v3.2 with Custom Layout
Modified to match the specific actuator layout from the provided image
Added right-click phantom placement functionality

Features:
- Custom layout matching the image (6cm vertical, 5cm horizontal spacing)
- Layout editor mode for custom actuator positioning
- Multiple waveform types (Sine, Square, Saw, Triangle, Chirp, FM, PWM, Noise)
- Pattern recording and saving to folder
- 3-actuator phantom sensations for arbitrary 2D positioning
- Right-click to place phantoms on grid
- Trajectory drawing with automatic phantom creation
- Non-overlapping SOA constraints (duration ≤ 70ms)
- Save/load custom layouts
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
    QSplitter, QScrollArea, QLineEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QMouseEvent, QCursor

# Import waveform generation
import numpy as np
from scipy import signal

# Import your API (optional)
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found. Running in simulation mode.")
    python_serial_api = None

# Import event data model for waveforms
try:
    from event_data_model import HapticEvent, EventCategory
except ImportError:
    print("Warning: event_data_model not found. Using basic waveforms.")
    HapticEvent = None

# Actuator configuration
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

# Custom layout matching the image
# Layout structure:
#     0   1      (2 actuators, centered)
# 5   4   3   2  (4 actuators)
# 6   7   8   9  (4 actuators)
# 13  12  11  10 (4 actuators)
#     14  15     (2 actuators, centered)

CUSTOM_LAYOUT_POSITIONS = {
    # Top row (y=0): 2 actuators centered
    0: (50, 0),   # 5cm from left edge
    1: (100, 0),  # 10cm from left edge
    
    # Second row (y=60): 4 actuators  
    5: (0, 60),    # Left edge
    4: (50, 60),   # 5cm spacing
    3: (100, 60),  # 10cm spacing  
    2: (150, 60),  # 15cm spacing
    
    # Third row (y=120): 4 actuators
    6: (0, 120),
    7: (50, 120),
    8: (100, 120),
    9: (150, 120),
    
    # Fourth row (y=180): 4 actuators  
    13: (0, 180),
    12: (50, 180),
    11: (100, 180),
    10: (150, 180),
    
    # Bottom row (y=240): 2 actuators centered
    14: (50, 240),
    15: (100, 240)
}

# Park et al. (2016) parameters
PAPER_PARAMS = {
    'SOA_SLOPE': 0.32,
    'SOA_BASE': 47.3,  # in ms (converted from 0.0473s)
    'MIN_DURATION': 40,
    'MAX_DURATION': 70,  # Maximum 70ms to prevent overlapping
    'OPTIMAL_FREQ': 250,  # 250Hz optimal frequency
    'SAMPLING_RATE': 70,  # Maximum sampling rate 70ms
}

# Waveform types available
WAVEFORM_TYPES = [
    "Sine", "Square", "Saw", "Triangle", 
    "Chirp", "FM", "PWM", "Noise"
]

# Patterns and layouts folders
PATTERNS_FOLDER = "saved_patterns"
LAYOUTS_FOLDER = "saved_layouts"

def ensure_folders():
    """Ensure patterns and layouts folders exist"""
    for folder in [PATTERNS_FOLDER, LAYOUTS_FOLDER]:
        if not os.path.exists(folder):
            os.makedirs(folder)
            print(f"📁 Created folder: {folder}")

def get_custom_layout_position(actuator_id: int) -> Tuple[float, float]:
    """Get custom layout position for actuator matching the image"""
    if actuator_id not in CUSTOM_LAYOUT_POSITIONS:
        raise ValueError(f"Invalid actuator ID {actuator_id} for custom layout")
    
    return CUSTOM_LAYOUT_POSITIONS[actuator_id]

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

def generate_waveform(waveform_type: str, frequency: float = 250.0, 
                     duration: float = 0.06, sample_rate: float = 1000.0) -> np.ndarray:
    """Generate waveform signal based on type"""
    t = np.linspace(0.0, duration, int(sample_rate * duration), endpoint=False)
    
    if waveform_type == "Sine":
        y = np.sin(2 * np.pi * frequency * t)
    elif waveform_type == "Square":
        y = np.sign(np.sin(2 * np.pi * frequency * t))
    elif waveform_type == "Saw":
        y = signal.sawtooth(2 * np.pi * frequency * t, 1.0)
    elif waveform_type == "Triangle":
        y = signal.sawtooth(2 * np.pi * frequency * t, 0.5)
    elif waveform_type == "Chirp":
        y = signal.chirp(t, f0=frequency, t1=duration, f1=frequency * 4, method="linear")
    elif waveform_type == "FM":
        carr = 2 * np.pi * frequency * t
        mod = np.sin(2 * np.pi * frequency * 0.25 * t)
        y = np.sin(carr + 2 * mod)
    elif waveform_type == "PWM":
        y = signal.square(2 * np.pi * frequency * t, duty=0.5)
    elif waveform_type == "Noise":
        rng = np.random.default_rng()
        y = rng.uniform(-1.0, 1.0, size=t.shape)
    else:
        # Default to sine
        y = np.sin(2 * np.pi * frequency * t)
    
    return np.clip(y, -1.0, 1.0)

@dataclass
class SOAStep:
    actuator_id: int
    onset_time: float
    duration: float
    intensity: int
    waveform_type: str = "Sine"

@dataclass
class PatternStep:
    actuator_id: int
    timestamp: float
    duration: float
    intensity: int
    waveform_type: str = "Sine"

@dataclass
class TactilePattern:
    name: str
    steps: List[PatternStep]
    total_duration: float
    created_timestamp: float
    description: str = ""

    def to_dict(self):
        return {
            'name': self.name,
            'steps': [asdict(step) for step in self.steps],
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
            total_duration=data['total_duration'],
            created_timestamp=data['created_timestamp'],
            description=data.get('description', '')
        )

@dataclass
class ActuatorLayout:
    name: str
    positions: Dict[int, Tuple[float, float]]
    created_timestamp: float
    description: str = ""

    def to_dict(self):
        return {
            'name': self.name,
            'positions': self.positions,
            'created_timestamp': self.created_timestamp,
            'description': self.description
        }
    
    @classmethod
    def from_dict(cls, data):
        return cls(
            name=data['name'],
            positions=data['positions'],
            created_timestamp=data['created_timestamp'],
            description=data.get('description', '')
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
    timestamp: float = 0.0
    waveform_type: str = "Sine"

class EnhancedTactileEngine:
    """Enhanced engine with custom layout, phantoms, and waveforms"""
    
    def __init__(self, api=None):
        self.api = api
        
        # Layout management
        self.current_layout_name = "Custom Layout (Image Match)"
        self.custom_positions = {}
        self.saved_layouts = {}
        
        # Waveform settings
        self.current_waveform_type = "Sine"
        self.waveform_frequency = 250.0
        
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
        
        # Trajectory state
        self.current_trajectory = []
        self.trajectory_phantoms = []
        self.trajectory_mode = False
        self.trajectory_sampling_rate = 70
        
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
        
        # Initialize with custom layout
        self.load_custom_layout()
        self.update_grid_positions()
        self.compute_actuator_triangles()
        ensure_folders()
    
    def load_custom_layout(self):
        """Load custom layout matching the image"""
        self.custom_positions = CUSTOM_LAYOUT_POSITIONS.copy()
        print(f"🔄 Loaded custom layout matching image")
        print(f"📏 Spacing: 5cm horizontal, 6cm vertical")
    
    def load_default_layout(self):
        """Load default custom layout (same as custom for this implementation)"""
        self.load_custom_layout()
    
    def set_actuator_position(self, actuator_id: int, position: Tuple[float, float]):
        """Set custom position for an actuator"""
        if actuator_id in ACTUATORS:
            self.custom_positions[actuator_id] = position
            self.update_grid_positions()
            self.compute_actuator_triangles()
            print(f"📍 Moved actuator {actuator_id} to ({position[0]:.1f}, {position[1]:.1f})")
    
    def get_actuator_position(self, actuator_id: int) -> Optional[Tuple[float, float]]:
        """Get position of an actuator"""
        return self.custom_positions.get(actuator_id)
    
    def save_layout(self, layout_name: str, description: str = "") -> bool:
        """Save current layout to file"""
        ensure_folders()
        
        layout = ActuatorLayout(
            name=layout_name,
            positions=self.custom_positions.copy(),
            created_timestamp=time.time(),
            description=description
        )
        
        filename = f"{layout_name.replace(' ', '_')}.json"
        filepath = os.path.join(LAYOUTS_FOLDER, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(layout.to_dict(), f, indent=2)
            
            self.saved_layouts[layout_name] = layout
            self.current_layout_name = layout_name
            print(f"💾 Layout saved: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Failed to save layout: {e}")
            return False
    
    def load_layout(self, filepath: str) -> Optional[ActuatorLayout]:
        """Load layout from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            layout = ActuatorLayout.from_dict(data)
            
            # Convert string keys to int keys if needed
            if isinstance(list(layout.positions.keys())[0], str):
                layout.positions = {int(k): v for k, v in layout.positions.items()}
            
            self.custom_positions = layout.positions.copy()
            self.saved_layouts[layout.name] = layout
            self.current_layout_name = layout.name
            
            self.update_grid_positions()
            self.compute_actuator_triangles()
            
            print(f"📂 Layout loaded: {layout.name}")
            return layout
        except Exception as e:
            print(f"❌ Failed to load layout: {e}")
            return None
    
    def get_saved_layouts(self) -> List[str]:
        """Get list of saved layout files"""
        ensure_folders()
        layout_files = []
        
        for filename in os.listdir(LAYOUTS_FOLDER):
            if filename.endswith('.json'):
                layout_files.append(filename)
        
        return sorted(layout_files)
    
    def reset_to_default_layout(self):
        """Reset to custom layout"""
        self.load_custom_layout()
        self.current_layout_name = "Custom Layout (Image Match)"
        print(f"🔄 Reset to custom layout matching image")
    
    def set_waveform_type(self, waveform_type: str):
        """Set the current waveform type"""
        if waveform_type in WAVEFORM_TYPES:
            self.current_waveform_type = waveform_type
            print(f"🌊 Waveform set to: {waveform_type}")
    
    def set_waveform_frequency(self, frequency: float):
        """Set the waveform frequency"""
        self.waveform_frequency = max(50.0, min(1000.0, frequency))
        print(f"🎵 Waveform frequency set to: {self.waveform_frequency}Hz")
    
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
                    if area > 50 and area < 8000:
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
        """Calculate intensities for 3-actuator phantom using Park et al. energy model"""
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        positions = triangle['positions']
        
        distances = []
        for pos in positions:
            dist = math.sqrt((phantom_pos[0] - pos[0])**2 + (phantom_pos[1] - pos[1])**2)
            distances.append(max(dist, 1.0))
        
        # Park et al. energy summation model
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
        """Create enhanced 3-actuator phantom"""
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
            energy_efficiency=efficiency,
            waveform_type=self.current_waveform_type
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
        self.actuator_positions = self.custom_positions.copy()
    
    # Recording methods
    def start_recording(self, pattern_name: str):
        """Start recording a pattern"""
        self.is_recording = True
        self.recording_start_time = time.time() * 1000
        self.current_pattern_steps = []
        self.current_pattern_name = pattern_name
        print(f"🔴 Recording started: {pattern_name}")
    
    def stop_recording(self) -> Optional[TactilePattern]:
        """Stop recording and return the pattern"""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        current_time = time.time() * 1000
        total_duration = current_time - self.recording_start_time
        
        pattern = TactilePattern(
            name=self.current_pattern_name,
            steps=self.current_pattern_steps.copy(),
            total_duration=total_duration,
            created_timestamp=time.time(),
            description=f"Recorded pattern with {len(self.current_pattern_steps)} steps"
        )
        
        print(f"⏹️ Recording stopped: {len(self.current_pattern_steps)} steps recorded")
        return pattern
    
    def add_recording_step(self, actuator_id: int, intensity: int):
        """Add a step to the current recording"""
        if not self.is_recording:
            return
        
        current_time = time.time() * 1000
        timestamp = current_time - self.recording_start_time
        
        step = PatternStep(
            actuator_id=actuator_id,
            timestamp=timestamp,
            duration=self.pattern_duration,
            intensity=intensity,
            waveform_type=self.current_waveform_type
        )
        
        self.current_pattern_steps.append(step)
        print(f"📝 Recorded step {len(self.current_pattern_steps)}: Actuator {actuator_id}, Intensity {intensity}")
    
    def save_pattern(self, pattern: TactilePattern) -> bool:
        """Save pattern to file"""
        ensure_folders()
        filename = f"{pattern.name.replace(' ', '_')}.json"
        filepath = os.path.join(PATTERNS_FOLDER, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(pattern.to_dict(), f, indent=2)
            
            self.saved_patterns[pattern.name] = pattern
            print(f"💾 Pattern saved: {filepath}")
            return True
        except Exception as e:
            print(f"❌ Failed to save pattern: {e}")
            return False
    
    def load_pattern(self, filepath: str) -> Optional[TactilePattern]:
        """Load pattern from file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            
            pattern = TactilePattern.from_dict(data)
            self.saved_patterns[pattern.name] = pattern
            print(f"📂 Pattern loaded: {pattern.name}")
            return pattern
        except Exception as e:
            print(f"❌ Failed to load pattern: {e}")
            return None
    
    def get_saved_patterns(self) -> List[str]:
        """Get list of saved pattern files"""
        ensure_folders()
        pattern_files = []
        
        for filename in os.listdir(PATTERNS_FOLDER):
            if filename.endswith('.json'):
                pattern_files.append(filename)
        
        return sorted(pattern_files)
    
    def play_pattern(self, pattern: TactilePattern):
        """Play a saved pattern"""
        if not pattern.steps:
            return
        
        soa_steps = []
        for step in pattern.steps:
            soa_step = SOAStep(
                actuator_id=step.actuator_id,
                onset_time=step.timestamp,
                duration=step.duration,
                intensity=step.intensity,
                waveform_type=step.waveform_type
            )
            soa_steps.append(soa_step)
        
        soa_steps.sort(key=lambda step: step.onset_time)
        self.execute_soa_sequence(soa_steps)
        print(f"▶️ Playing pattern: {pattern.name} ({len(pattern.steps)} steps)")
    
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
                    intensity=intensity,
                    waveform_type=phantom.waveform_type
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
    
    # Mouse interaction methods
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
                        
                        if self.is_recording:
                            self.add_recording_step(phantom.physical_actuator_1, phantom.required_intensity_1)
                            self.add_recording_step(phantom.physical_actuator_2, phantom.required_intensity_2)
                            self.add_recording_step(phantom.physical_actuator_3, phantom.required_intensity_3)
            else:
                success = self.api.send_command(target_id, self.pattern_intensity, freq, 1)
                if success:
                    self.mouse_vibration_active = True
                    self.hover_timer.start(self.pattern_duration)
                    
                    if self.is_recording:
                        self.add_recording_step(target_id, self.pattern_intensity)
        else:
            # Simulation mode
            if not is_phantom and self.is_recording:
                self.add_recording_step(target_id, self.pattern_intensity)
            elif is_phantom and self.is_recording and target_id < len(self.enhanced_phantoms):
                phantom = self.enhanced_phantoms[target_id]
                self.add_recording_step(phantom.physical_actuator_1, phantom.required_intensity_1)
                self.add_recording_step(phantom.physical_actuator_2, phantom.required_intensity_2)
                self.add_recording_step(phantom.physical_actuator_3, phantom.required_intensity_3)
            
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
    """Enhanced visualization with drag-and-drop layout editing and right-click phantom placement"""
    
    actuator_hovered = pyqtSignal(int)
    phantom_hovered = pyqtSignal(int)
    mouse_left = pyqtSignal()
    trajectory_drawn = pyqtSignal()
    actuator_moved = pyqtSignal(int, float, float)
    phantom_placed = pyqtSignal(float, float)
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 500)
        self.setMouseTracking(True)
        self.engine = None
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}
        self.hover_radius = 25
        self.phantom_hover_radius = 30
        self.show_triangles = False
        
        # Layout editor state
        self.layout_editor_mode = False
        self.dragging_actuator = None
        self.drag_offset = (0, 0)
        self.drag_start_pos = None
        
        # Trajectory drawing state
        self.is_drawing_trajectory = False
        self.trajectory_start_pos = None
        
    def set_engine(self, engine: EnhancedTactileEngine):
        self.engine = engine
        self.update()
    
    def toggle_triangles(self, show: bool):
        self.show_triangles = show
        self.update()
    
    def set_layout_editor_mode(self, enabled: bool):
        """Enable/disable layout editor mode"""
        self.layout_editor_mode = enabled
        if enabled:
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
        else:
            self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events"""
        if not self.engine:
            return
        
        mouse_pos = event.position()
        
        # Right-click for phantom placement (not in layout editor or trajectory mode)
        if (event.button() == Qt.MouseButton.RightButton and 
            not self.layout_editor_mode and 
            not self.engine.trajectory_mode):
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.phantom_placed.emit(physical_pos[0], physical_pos[1])
            return
        
        # Layout editor mode - actuator dragging
        if self.layout_editor_mode and event.button() == Qt.MouseButton.LeftButton:
            hovered_actuator = self.get_actuator_at_position(mouse_pos)
            if hovered_actuator is not None:
                self.dragging_actuator = hovered_actuator
                self.drag_start_pos = mouse_pos
                
                # Calculate offset from actuator center
                actuator_screen_pos = self.actuator_screen_positions[hovered_actuator]
                self.drag_offset = (
                    mouse_pos.x() - actuator_screen_pos[0],
                    mouse_pos.y() - actuator_screen_pos[1]
                )
                
                self.setCursor(QCursor(Qt.CursorShape.ClosedHandCursor))
                return
        
        # Trajectory drawing mode
        if self.engine.trajectory_mode and event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing_trajectory = True
            self.trajectory_start_pos = mouse_pos
            
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.engine.current_trajectory = [physical_pos]
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events"""
        if not self.engine:
            return
        
        mouse_pos = event.position()
        
        # Layout editor mode - actuator dragging
        if self.layout_editor_mode and self.dragging_actuator is not None:
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                # Constrain to reasonable bounds
                x = max(-50, min(200, physical_pos[0]))
                y = max(-50, min(300, physical_pos[1]))
                
                self.engine.set_actuator_position(self.dragging_actuator, (x, y))
                self.actuator_moved.emit(self.dragging_actuator, x, y)
                self.update()
            return
        
        # Trajectory drawing mode
        if self.is_drawing_trajectory and self.engine.trajectory_mode:
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                if (not self.engine.current_trajectory or 
                    self.distance_between_points(physical_pos, self.engine.current_trajectory[-1]) > 5):
                    self.engine.add_trajectory_point(physical_pos)
                    self.update()
            return
        
        # Normal hover detection (only when not in layout editor mode)
        if not self.layout_editor_mode and not self.engine.trajectory_mode:
            hovered_phantom = self.get_phantom_at_position(mouse_pos)
            if hovered_phantom is not None:
                self.phantom_hovered.emit(hovered_phantom)
                return
            
            hovered_actuator = self.get_actuator_at_position(mouse_pos)
            if hovered_actuator is not None:
                self.actuator_hovered.emit(hovered_actuator)
            else:
                self.mouse_left.emit()
        
        # Layout editor mode - cursor changes
        if self.layout_editor_mode:
            hovered_actuator = self.get_actuator_at_position(mouse_pos)
            if hovered_actuator is not None:
                self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            else:
                self.setCursor(QCursor(Qt.CursorShape.ArrowCursor))
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events"""
        if not self.engine:
            return
        
        # Layout editor mode - stop dragging
        if self.layout_editor_mode and self.dragging_actuator is not None:
            self.dragging_actuator = None
            self.drag_offset = (0, 0)
            self.drag_start_pos = None
            self.setCursor(QCursor(Qt.CursorShape.OpenHandCursor))
            return
        
        # Trajectory drawing mode
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
        if not self.layout_editor_mode:
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
        
        margin = 30
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 60
        
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.9
        
        physical_x = (screen_pos.x() - margin) / scale + min_x
        physical_y = (screen_pos.y() - margin - 40) / scale + min_y
        
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
        
        margin = 30
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 60
        
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
        font.setPointSize(10)
        painter.setFont(font)
        
        title_text = f"🎨 Custom Layout Tactile v3.2 - {self.engine.current_layout_name}"
        if self.layout_editor_mode:
            title_text += " [LAYOUT EDITOR]"
        painter.drawText(margin, 20, title_text)
        
        # Spacing info
        spacing_text = "📏 5cm horizontal, 6cm vertical spacing"
        painter.setPen(QPen(QColor(100, 100, 100)))
        font.setPointSize(8)
        font.setBold(False)
        painter.setFont(font)
        painter.drawText(margin, 35, spacing_text)
        
        # Mode indicators
        status_text = ""
        if self.engine.is_recording:
            status_text += f"🔴 REC ({len(self.engine.current_pattern_steps)} steps) "
        if self.engine.trajectory_mode:
            status_text += "🎨 TRAJECTORY MODE "
        if self.layout_editor_mode:
            status_text += "✏️ LAYOUT EDITOR "
        
        if status_text:
            painter.setPen(QPen(QColor(255, 0, 0)))
            font.setBold(True)
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(self.width() - 400, 20, status_text)
        
        # Draw trajectory if being drawn or completed
        if self.engine and self.engine.current_trajectory:
            trajectory_screen_points = []
            for point in self.engine.current_trajectory:
                screen_point = pos_to_screen(point)
                trajectory_screen_points.append(screen_point)
            
            if len(trajectory_screen_points) > 1:
                painter.setPen(QPen(QColor(0, 150, 255), 3))
                for i in range(len(trajectory_screen_points) - 1):
                    painter.drawLine(
                        int(trajectory_screen_points[i][0]), int(trajectory_screen_points[i][1]),
                        int(trajectory_screen_points[i+1][0]), int(trajectory_screen_points[i+1][1])
                    )
                
                if trajectory_screen_points:
                    # Start marker
                    painter.setPen(QPen(QColor(0, 200, 0), 2))
                    painter.setBrush(QBrush(QColor(0, 255, 0, 100)))
                    start_point = trajectory_screen_points[0]
                    painter.drawEllipse(int(start_point[0] - 8), int(start_point[1] - 8), 16, 16)
                    
                    # End marker
                    painter.setPen(QPen(QColor(200, 0, 0), 2))
                    painter.setBrush(QBrush(QColor(255, 0, 0, 100)))
                    end_point = trajectory_screen_points[-1]
                    painter.drawEllipse(int(end_point[0] - 8), int(end_point[1] - 8), 16, 16)
        
        # Draw triangles if enabled
        if self.show_triangles and hasattr(self.engine, 'actuator_triangles'):
            for triangle in self.engine.actuator_triangles[:10]:  # Show only best triangles
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
            is_being_dragged = (self.dragging_actuator == actuator_id)
            
            # Color coding
            if is_being_dragged:
                color = QColor(255, 255, 0)  # Yellow for dragging
            elif is_vibrating:
                color = QColor(255, 50, 50)
            elif is_hovered:
                color = QColor(255, 150, 0)
            elif in_phantom:
                color = QColor(150, 0, 255)
            elif self.layout_editor_mode:
                color = QColor(100, 150, 255)  # Blue tint in editor mode
            else:
                color = QColor(120, 120, 120)
            
            # Draw actuator
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(color))
            
            radius = 22 if is_being_dragged else (20 if is_hovered else 16)
            painter.drawEllipse(int(screen_x - radius), int(screen_y - radius), 
                              radius * 2, radius * 2)
            
            # Actuator ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            text_width = len(str(actuator_id)) * 6
            painter.drawText(int(screen_x - text_width/2), int(screen_y + 4), str(actuator_id))
            
            # Position coordinates in layout editor mode
            if self.layout_editor_mode:
                painter.setPen(QPen(QColor(0, 0, 0)))
                font.setPointSize(7)
                font.setBold(False)
                painter.setFont(font)
                coord_text = f"({pos[0]:.0f},{pos[1]:.0f})"
                text_width = len(coord_text) * 4
                painter.drawText(int(screen_x - text_width/2), int(screen_y + 30), coord_text)
        
        # Draw phantoms
        for phantom in self.engine.enhanced_phantoms:
            phantom_screen = pos_to_screen(phantom.virtual_position)
            self.phantom_screen_positions[phantom.phantom_id] = phantom_screen
            
            is_phantom_hovered = (self.engine.mouse_hover_actuator == f"P{phantom.phantom_id}")
            is_phantom_vibrating = (is_phantom_hovered and self.engine.mouse_vibration_active)
            
            if is_phantom_vibrating:
                phantom_color = QColor(255, 50, 255)
                radius = 18
            elif is_phantom_hovered:
                phantom_color = QColor(255, 150, 255)
                radius = 15
            else:
                phantom_color = QColor(200, 100, 200)
                radius = 12
            
            # Draw phantom
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(phantom_color))
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
        legend_y = self.height() - 20
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(7)
        painter.setFont(font)
        
        if self.layout_editor_mode:
            painter.setPen(QPen(QColor(0, 100, 255)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(margin, legend_y - 35, "✏️ LAYOUT EDITOR - Drag actuators to new positions")
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QPen(QColor(0, 0, 0)))
        elif self.engine and self.engine.trajectory_mode:
            painter.setPen(QPen(QColor(0, 100, 255)))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(margin, legend_y - 35, "🎨 TRAJECTORY MODE - Draw path to create phantoms")
            font.setBold(False)
            painter.setFont(font)
            painter.setPen(QPen(QColor(0, 0, 0)))
        
        painter.drawText(margin, legend_y, "🔴 Vibrating  🟠 Hovered  🟣 Phantom  ⚫ Inactive")

class EnhancedTactileGUI(QWidget):
    """Enhanced GUI with custom layout and waveform selection"""
    
    def __init__(self):
        super().__init__()
        self.engine = EnhancedTactileEngine()
        self.api = None
        self.current_recorded_pattern = None
        
        # Recording update timer
        self.recording_update_timer = QTimer()
        self.recording_update_timer.timeout.connect(self.update_recording_display)
        self.recording_update_timer.setInterval(500)
        
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
        self.viz.actuator_moved.connect(self.on_actuator_moved)
        self.viz.phantom_placed.connect(self.on_phantom_placed)
    
    def setup_ui(self):
        # Use a splitter for better space management
        main_layout = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        
        # Left panel for controls
        left_panel = QWidget()
        left_panel.setMaximumWidth(380)
        left_layout = QVBoxLayout(left_panel)
        
        # Title
        title = QLabel("🎨 Custom Layout Tactile Creator")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2E86AB;")
        left_layout.addWidget(title)
        
        subtitle = QLabel("Custom Layout • 5cm×6cm spacing • Waveforms • Recording • Right-click Phantoms")
        subtitle.setStyleSheet("font-style: italic; color: #666; font-size: 10px;")
        left_layout.addWidget(subtitle)
        
        # Scrollable area for controls
        scroll = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # Connection
        conn_group = QGroupBox("Connection")
        conn_layout = QVBoxLayout(conn_group)
        
        device_layout = QHBoxLayout()
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        device_layout.addWidget(QLabel("Device:"))
        device_layout.addWidget(self.device_combo)
        device_layout.addWidget(self.refresh_btn)
        conn_layout.addLayout(device_layout)
        
        conn_btn_layout = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_btn_layout.addWidget(self.connect_btn)
        conn_btn_layout.addWidget(self.status_label)
        conn_layout.addLayout(conn_btn_layout)
        
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.connect_btn.clicked.connect(self.toggle_connection)
        scroll_layout.addWidget(conn_group)
        
        # Layout Editor
        layout_group = QGroupBox("✏️ Layout Editor")
        layout_layout = QVBoxLayout(layout_group)
        
        # Current layout info
        self.current_layout_label = QLabel(f"Current: {self.engine.current_layout_name}")
        self.current_layout_label.setStyleSheet("font-weight: bold;")
        layout_layout.addWidget(self.current_layout_label)
        
        # Layout editor controls
        layout_btn_layout = QHBoxLayout()
        self.layout_editor_btn = QPushButton("✏️ Edit Layout")
        self.layout_editor_btn.clicked.connect(self.toggle_layout_editor)
        self.layout_editor_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        
        self.reset_layout_btn = QPushButton("🔄 Reset Layout")
        self.reset_layout_btn.clicked.connect(self.reset_layout)
        
        layout_btn_layout.addWidget(self.layout_editor_btn)
        layout_btn_layout.addWidget(self.reset_layout_btn)
        layout_layout.addLayout(layout_btn_layout)
        
        # Save/Load layout
        layout_save_layout = QHBoxLayout()
        self.layout_name_edit = QLineEdit("Custom_Layout")
        self.save_layout_btn = QPushButton("💾 Save")
        self.save_layout_btn.clicked.connect(self.save_layout)
        
        layout_save_layout.addWidget(QLabel("Name:"))
        layout_save_layout.addWidget(self.layout_name_edit)
        layout_save_layout.addWidget(self.save_layout_btn)
        layout_layout.addLayout(layout_save_layout)
        
        # Layout library
        self.layout_list = QListWidget()
        self.layout_list.setMaximumHeight(80)
        self.load_layout_list()
        layout_layout.addWidget(self.layout_list)
        
        layout_lib_layout = QHBoxLayout()
        self.load_layout_btn = QPushButton("📂 Load")
        self.load_layout_btn.clicked.connect(self.load_selected_layout)
        
        self.refresh_layouts_btn = QPushButton("🔄")
        self.refresh_layouts_btn.clicked.connect(self.load_layout_list)
        
        layout_lib_layout.addWidget(self.load_layout_btn)
        layout_lib_layout.addWidget(self.refresh_layouts_btn)
        layout_layout.addLayout(layout_lib_layout)
        
        scroll_layout.addWidget(layout_group)
        
        # Waveform Selection
        waveform_group = QGroupBox("🌊 Waveform Selection")
        waveform_layout = QFormLayout(waveform_group)
        
        self.waveform_combo = QComboBox()
        self.waveform_combo.addItems(WAVEFORM_TYPES)
        self.waveform_combo.currentTextChanged.connect(self.on_waveform_changed)
        waveform_layout.addRow("Type:", self.waveform_combo)
        
        self.frequency_spin = QSpinBox()
        self.frequency_spin.setRange(50, 1000)
        self.frequency_spin.setValue(250)
        self.frequency_spin.setSuffix(" Hz")
        self.frequency_spin.valueChanged.connect(self.on_frequency_changed)
        waveform_layout.addRow("Frequency:", self.frequency_spin)
        
        scroll_layout.addWidget(waveform_group)
        
        # Pattern Parameters
        pattern_group = QGroupBox("Pattern Parameters")
        pattern_layout = QFormLayout(pattern_group)
        
        self.pattern_duration_spin = QSpinBox()
        self.pattern_duration_spin.setRange(40, PAPER_PARAMS['MAX_DURATION'])
        self.pattern_duration_spin.setValue(60)
        self.pattern_duration_spin.setSuffix(" ms")
        self.pattern_duration_spin.valueChanged.connect(self.update_pattern_parameters)
        pattern_layout.addRow("Duration:", self.pattern_duration_spin)
        
        self.pattern_intensity_spin = QSpinBox()
        self.pattern_intensity_spin.setRange(1, 15)
        self.pattern_intensity_spin.setValue(8)
        self.pattern_intensity_spin.valueChanged.connect(self.update_pattern_parameters)
        pattern_layout.addRow("Intensity:", self.pattern_intensity_spin)
        
        scroll_layout.addWidget(pattern_group)
        
        # Pattern Recording
        recording_group = QGroupBox("🔴 Pattern Recording")
        recording_layout = QFormLayout(recording_group)
        
        self.pattern_name_edit_rec = QLineEdit("New Pattern")
        recording_layout.addRow("Name:", self.pattern_name_edit_rec)
        
        record_btn_layout = QHBoxLayout()
        self.record_btn = QPushButton("🔴 Start Recording")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setStyleSheet("""
            QPushButton {
                background-color: #F44336;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        
        self.save_pattern_btn = QPushButton("💾 Save Pattern")
        self.save_pattern_btn.clicked.connect(self.save_current_pattern)
        self.save_pattern_btn.setEnabled(False)
        
        record_btn_layout.addWidget(self.record_btn)
        record_btn_layout.addWidget(self.save_pattern_btn)
        recording_layout.addRow("", record_btn_layout)
        
        scroll_layout.addWidget(recording_group)
        
        # Pattern Library
        library_group = QGroupBox("📚 Pattern Library")
        library_layout = QVBoxLayout(library_group)
        
        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(100)
        self.load_pattern_list()
        library_layout.addWidget(self.pattern_list)
        
        library_btn_layout = QHBoxLayout()
        self.load_pattern_btn = QPushButton("📂 Load")
        self.load_pattern_btn.clicked.connect(self.load_selected_pattern)
        
        self.play_pattern_btn = QPushButton("▶️ Play")
        self.play_pattern_btn.clicked.connect(self.play_selected_pattern)
        
        self.refresh_patterns_btn = QPushButton("🔄")
        self.refresh_patterns_btn.clicked.connect(self.load_pattern_list)
        
        library_btn_layout.addWidget(self.load_pattern_btn)
        library_btn_layout.addWidget(self.play_pattern_btn)
        library_btn_layout.addWidget(self.refresh_patterns_btn)
        library_layout.addLayout(library_btn_layout)
        
        scroll_layout.addWidget(library_group)
        
        # Trajectory Creation
        trajectory_group = QGroupBox("🎨 Trajectory Creation")
        trajectory_layout = QFormLayout(trajectory_group)
        
        self.trajectory_sampling_spin = QSpinBox()
        self.trajectory_sampling_spin.setRange(30, 100)
        self.trajectory_sampling_spin.setValue(70)
        self.trajectory_sampling_spin.setSuffix(" ms")
        self.trajectory_sampling_spin.valueChanged.connect(self.update_trajectory_sampling)
        trajectory_layout.addRow("Sampling:", self.trajectory_sampling_spin)
        
        trajectory_btn_layout = QVBoxLayout()
        
        self.trajectory_mode_btn = QPushButton("🎨 Start Drawing")
        self.trajectory_mode_btn.clicked.connect(self.toggle_trajectory_mode)
        
        traj_controls_layout = QHBoxLayout()
        self.play_trajectory_btn = QPushButton("▶️ Play")
        self.play_trajectory_btn.clicked.connect(self.play_trajectory)
        self.play_trajectory_btn.setEnabled(False)
        
        self.clear_trajectory_btn = QPushButton("🗑️ Clear")
        self.clear_trajectory_btn.clicked.connect(self.clear_trajectory)
        
        traj_controls_layout.addWidget(self.play_trajectory_btn)
        traj_controls_layout.addWidget(self.clear_trajectory_btn)
        
        trajectory_btn_layout.addWidget(self.trajectory_mode_btn)
        trajectory_btn_layout.addLayout(traj_controls_layout)
        trajectory_layout.addRow("", trajectory_btn_layout)
        
        scroll_layout.addWidget(trajectory_group)
        
        # Manual Phantom Creation
        phantom_group = QGroupBox("Manual Phantom")
        phantom_layout = QFormLayout(phantom_group)
        
        phantom_pos_layout = QHBoxLayout()
        self.phantom_x_spin = QSpinBox()
        self.phantom_x_spin.setRange(-20, 200)
        self.phantom_x_spin.setValue(75)  # Set to middle of custom layout
        self.phantom_x_spin.setSuffix(" mm")
        
        self.phantom_y_spin = QSpinBox()
        self.phantom_y_spin.setRange(-20, 280)
        self.phantom_y_spin.setValue(120)  # Set to middle of custom layout
        self.phantom_y_spin.setSuffix(" mm")
        
        phantom_pos_layout.addWidget(QLabel("X:"))
        phantom_pos_layout.addWidget(self.phantom_x_spin)
        phantom_pos_layout.addWidget(QLabel("Y:"))
        phantom_pos_layout.addWidget(self.phantom_y_spin)
        phantom_layout.addRow("Position:", phantom_pos_layout)
        
        self.phantom_intensity_spin = QSpinBox()
        self.phantom_intensity_spin.setRange(1, 15)
        self.phantom_intensity_spin.setValue(13)
        phantom_layout.addRow("Intensity:", self.phantom_intensity_spin)
        
        self.create_phantom_btn = QPushButton("🔺 Create Phantom")
        self.create_phantom_btn.clicked.connect(self.create_enhanced_phantom)
        phantom_layout.addRow("", self.create_phantom_btn)
        
        scroll_layout.addWidget(phantom_group)
        
        # Stop button
        self.stop_all_btn = QPushButton("🛑 STOP ALL")
        self.stop_all_btn.clicked.connect(self.stop_all)
        self.stop_all_btn.setStyleSheet("QPushButton { background-color: #FF4444; color: white; font-weight: bold; padding: 8px; }")
        scroll_layout.addWidget(self.stop_all_btn)
        
        scroll.setWidget(scroll_widget)
        left_layout.addWidget(scroll)
        
        # Right panel for visualization
        viz_panel = QWidget()
        viz_layout = QVBoxLayout(viz_panel)
        
        # Visualization
        self.viz = EnhancedTactileVisualization()
        self.viz.set_engine(self.engine)
        viz_layout.addWidget(self.viz)
        
        # Info display
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(60)
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("🎨 Custom layout tactile system ready! Layout matches image with 5cm×6cm spacing. Right-click to place phantoms, edit layout, choose waveforms, record patterns.")
        viz_layout.addWidget(self.info_text)
        
        # Add panels to splitter
        splitter.addWidget(left_panel)
        splitter.addWidget(viz_panel)
        splitter.setSizes([380, 620])
        
        main_layout.addWidget(splitter)
        
        # Initialize
        self.update_pattern_parameters()
        self.update_layout_display()
    
    def on_waveform_changed(self, waveform_type: str):
        """Handle waveform type change"""
        self.engine.set_waveform_type(waveform_type)
        self.viz.update()
        self.info_text.setPlainText(f"🌊 Waveform changed to: {waveform_type}")
    
    def on_frequency_changed(self, frequency: int):
        """Handle frequency change"""
        self.engine.set_waveform_frequency(float(frequency))
        self.info_text.setPlainText(f"🎵 Frequency set to: {frequency}Hz")
    
    def toggle_layout_editor(self):
        """Toggle layout editor mode"""
        current_mode = self.viz.layout_editor_mode
        new_mode = not current_mode
        
        self.viz.set_layout_editor_mode(new_mode)
        
        if new_mode:
            self.layout_editor_btn.setText("✅ Exit Editor")
            self.layout_editor_btn.setStyleSheet("""
                QPushButton {
                    background-color: #FF5722;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
            self.info_text.setPlainText("✏️ Layout editor enabled - drag actuators to new positions")
        else:
            self.layout_editor_btn.setText("✏️ Edit Layout")
            self.layout_editor_btn.setStyleSheet("""
                QPushButton {
                    background-color: #2196F3;
                    color: white;
                    padding: 8px;
                    font-weight: bold;
                    border-radius: 4px;
                }
            """)
            self.info_text.setPlainText("✏️ Layout editor disabled")
    
    def on_actuator_moved(self, actuator_id: int, x: float, y: float):
        """Handle actuator position change"""
        self.info_text.setPlainText(f"📍 Moved actuator {actuator_id} to ({x:.1f}, {y:.1f})")
    
    def reset_layout(self):
        """Reset to custom layout"""
        self.engine.reset_to_default_layout()
        self.viz.update()
        self.update_layout_display()
        self.info_text.setPlainText("🔄 Reset to custom layout (5cm×6cm spacing)")
    
    def save_layout(self):
        """Save current layout"""
        layout_name = self.layout_name_edit.text().strip()
        if not layout_name:
            self.info