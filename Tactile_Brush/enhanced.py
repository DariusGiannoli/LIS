#!/usr/bin/env python3
"""
Enhanced Interactive Mouse Pattern Creator for 4x4 Tactile Grid
Extended with 3-actuator phantom sensations and improved SOA algorithms from Park et al. (2016)

New Features Based on "Rendering Moving Tactile Stroke on the Palm Using a Sparse 2D Array":
1. 3-Actuator phantom sensations for arbitrary 2D positioning
2. Non-overlapping SOA constraint (duration ≤ 70ms)
3. Triangle-based phantom positioning
4. Smooth trajectory sampling
5. Improved energy summation model for 3 actuators
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

# Import your API
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found.")
    python_serial_api = None

# 4x4 Grid Configuration - User's Layout
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
GRID_ROWS = 4
GRID_COLS = 4

USER_LAYOUT = [
    [3, 2, 1, 0],      # Row 0
    [4, 5, 6, 7],      # Row 1
    [11, 10, 9, 8],    # Row 2
    [12, 13, 14, 15]   # Row 3
]

# Enhanced parameters based on Park et al. (2016)
PAPER_PARAMS = {
    'SOA_SLOPE': 0.32,
    'SOA_BASE': 47.3,  # in ms (converted from 0.0473s)
    'MIN_DURATION': 40,
    'MAX_DURATION': 70,  # NEW: Maximum 70ms to prevent overlapping (Park et al.)
    'OPTIMAL_FREQ': 250,  # NEW: 250Hz optimal frequency (Park et al.)
    'SAMPLING_RATE': 70,  # NEW: Maximum sampling rate 70ms (Park et al.)
}

def get_grid_position(actuator_id: int, spacing_mm: float) -> Tuple[float, float]:
    """Convert actuator ID to (x, y) position in mm for user's 4x4 layout with custom spacing"""
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
    """NEW: Enhanced phantom using 3-actuator system from Park et al."""
    phantom_id: int
    virtual_position: Tuple[float, float]
    physical_actuator_1: int
    physical_actuator_2: int
    physical_actuator_3: int  # NEW: Third actuator
    desired_intensity: int
    required_intensity_1: int
    required_intensity_2: int
    required_intensity_3: int  # NEW: Third actuator intensity
    triangle_area: float  # NEW: Area of triangle for validation
    energy_efficiency: float  # NEW: Energy efficiency metric

class EnhancedTactileEngine:
    """Enhanced engine with 3-actuator phantoms and improved SOA algorithms"""
    
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
        self.enhanced_phantoms = []  # NEW: 3-actuator phantoms
        self.actuator_triangles = []  # NEW: Precomputed triangles
        
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
        
        # Enhanced pattern parameters (Park et al. constraints)
        self.pattern_duration = 60  # NEW: Default within 70ms limit
        self.pattern_intensity = 8
        self.use_enhanced_phantoms = True  # NEW: Toggle for 3-actuator phantoms
        
        self.load_user_custom_positions()
        self.update_grid_positions()
        self.compute_actuator_triangles()  # NEW: Precompute triangles
    
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
        """NEW: Systematic triangulation for smooth phantom motion (Park et al. methodology)"""
        self.actuator_triangles = []
        positions = self.actuator_positions
        
        print(f"🔺 Computing systematic triangulation for 4x4 grid (Park et al. approach)...")
        
        # Method 1: Grid-based systematic triangulation for smooth coverage
        # Create triangles from rectangular grid cells (following Park et al.)
        triangles_added = 0
        
        for row in range(GRID_ROWS - 1):
            for col in range(GRID_COLS - 1):
                # Get the 4 corner actuators of current grid cell
                top_left = get_actuator_id(row, col)
                top_right = get_actuator_id(row, col + 1)  
                bottom_left = get_actuator_id(row + 1, col)
                bottom_right = get_actuator_id(row + 1, col + 1)
                
                # Skip if any actuator is invalid
                if -1 in [top_left, top_right, bottom_left, bottom_right]:
                    continue
                
                # Create two triangles from the rectangular cell (systematic triangulation)
                # Triangle 1: top-left, top-right, bottom-left
                triangle1_acts = [top_left, top_right, bottom_left]
                triangle1_pos = [positions[act] for act in triangle1_acts]
                
                # Triangle 2: top-right, bottom-left, bottom-right  
                triangle2_acts = [top_right, bottom_left, bottom_right]
                triangle2_pos = [positions[act] for act in triangle2_acts]
                
                # Add both triangles
                for triangle_acts, triangle_pos, tri_name in [
                    (triangle1_acts, triangle1_pos, "upper"),
                    (triangle2_acts, triangle2_pos, "lower")
                ]:
                    area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                              triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                              triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
                    
                    if area > 50:  # Lower threshold for smaller, smoother triangles
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
        
        print(f"   📐 Added {triangles_added} systematic grid triangles")
        
        # Method 2: Add adjacent triangles for better coverage at edges
        edge_triangles = 0
        
        # Add triangles along edges and diagonals for complete coverage
        for row in range(GRID_ROWS):
            for col in range(GRID_COLS):
                center_act = get_actuator_id(row, col)
                if center_act == -1:
                    continue
                    
                center_pos = positions[center_act]
                
                # Find nearby actuators (within reasonable distance for smoothness)
                nearby_actuators = []
                max_distance = 85  # mm - adjusted for smoother transitions
                
                for other_row in range(GRID_ROWS):
                    for other_col in range(GRID_COLS):
                        other_act = get_actuator_id(other_row, other_col)
                        if other_act == -1 or other_act == center_act:
                            continue
                            
                        other_pos = positions[other_act]
                        distance = math.sqrt((center_pos[0]-other_pos[0])**2 + (center_pos[1]-other_pos[1])**2)
                        
                        if distance <= max_distance:
                            nearby_actuators.append((other_act, other_pos, distance))
                
                # Sort by distance for smooth transitions
                nearby_actuators.sort(key=lambda x: x[2])
                
                # Create triangles with center and pairs of nearby actuators
                for i in range(len(nearby_actuators)-1):
                    for j in range(i+1, min(i+3, len(nearby_actuators))):  # Limit to avoid too many triangles
                        act1, pos1, _ = nearby_actuators[i]
                        act2, pos2, _ = nearby_actuators[j]
                        
                        triangle_acts = [center_act, act1, act2]
                        triangle_pos = [center_pos, pos1, pos2]
                        
                        # Check if this triangle already exists
                        exists = any(set(t['actuators']) == set(triangle_acts) for t in self.actuator_triangles)
                        if exists:
                            continue
                        
                        area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                                  triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                                  triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
                        
                        if area > 50 and area < 3000:  # Avoid too small or too large triangles
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
        
        print(f"   📐 Added {edge_triangles} local coverage triangles")
        
        # Sort by smoothness score (smaller, more local triangles first for smooth motion)
        self.actuator_triangles.sort(key=lambda t: (t['smoothness_score'], t['area']))
        
        print(f"🔺 Total: {len(self.actuator_triangles)} optimized triangles for smooth phantom motion")
        print(f"   📊 Triangle areas range: {min(t['area'] for t in self.actuator_triangles):.1f} - {max(t['area'] for t in self.actuator_triangles):.1f} mm²")
        print(f"   🎯 Optimized for smooth trajectory following (Park et al. methodology)")
    
    def calculate_triangle_smoothness(self, triangle_pos: List[Tuple[float, float]]) -> float:
        """Calculate smoothness score for triangle (lower = better for smooth motion)"""
        # Calculate perimeter (smaller perimeter = more local = smoother)
        perimeter = 0
        for i in range(3):
            j = (i + 1) % 3
            dist = math.sqrt((triangle_pos[i][0] - triangle_pos[j][0])**2 + 
                           (triangle_pos[i][1] - triangle_pos[j][1])**2)
            perimeter += dist
        
        # Calculate aspect ratio penalty (more equilateral = smoother)
        area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                   triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                   triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
        
        # Aspect ratio penalty (equilateral triangles are better)
        if area > 0:
            aspect_penalty = (perimeter ** 2) / (12 * math.sqrt(3) * area)  # Perfect triangle = 1.0
        else:
            aspect_penalty = 1000  # Degenerate triangle
        
        return perimeter * 0.1 + aspect_penalty  # Combine perimeter and aspect ratio
    
    def find_best_triangle_for_position(self, pos: Tuple[float, float]) -> Optional[Dict]:
        """NEW: Find optimal triangle for smooth phantom motion (Park et al. methodology)"""
        # Priority 1: Find triangles that contain the point (most accurate)
        containing_triangles = []
        for triangle in self.actuator_triangles:
            if point_in_triangle(pos, *triangle['positions']):
                containing_triangles.append(triangle)
        
        if containing_triangles:
            # Among containing triangles, choose the one with best smoothness score
            # (smaller, more local triangles for smoother motion)
            best_triangle = min(containing_triangles, key=lambda t: t['smoothness_score'])
            print(f"🔺 Found optimal containing triangle: {best_triangle['type']}")
            print(f"   Area: {best_triangle['area']:.1f}mm², Smoothness: {best_triangle['smoothness_score']:.2f}")
            return best_triangle
        
        # Priority 2: Find closest triangles by center distance (for positions outside all triangles)
        print("⚠️  Position outside all triangles, finding optimal nearby triangle...")
        
        # Calculate distance to each triangle center and weight by smoothness
        triangle_scores = []
        for triangle in self.actuator_triangles:
            center_dist = math.sqrt((pos[0] - triangle['center'][0])**2 + (pos[1] - triangle['center'][1])**2)
            
            # Combined score: distance + smoothness (both should be small)
            combined_score = center_dist * 0.5 + triangle['smoothness_score'] * 10
            triangle_scores.append((combined_score, triangle, center_dist))
        
        if triangle_scores:
            # Sort by combined score (lower is better)
            triangle_scores.sort(key=lambda x: x[0])
            best_score, best_triangle, distance = triangle_scores[0]
            
            print(f"🔺 Selected optimal nearby triangle: {best_triangle['type']}")
            print(f"   Distance: {distance:.1f}mm, Area: {best_triangle['area']:.1f}mm²")
            print(f"   Smoothness score: {best_triangle['smoothness_score']:.2f} (optimized for smooth motion)")
            return best_triangle
        
        return None
    
    def calculate_3actuator_intensities(self, phantom_pos: Tuple[float, float], 
                                      triangle: Dict, desired_intensity: int) -> Tuple[int, int, int]:
        """NEW: Calculate intensities for 3-actuator phantom using Park et al. energy model"""
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        actuators = triangle['actuators']
        positions = triangle['positions']
        
        # Calculate distances from phantom to each actuator
        distances = []
        for pos in positions:
            dist = math.sqrt((phantom_pos[0] - pos[0])**2 + (phantom_pos[1] - pos[1])**2)
            distances.append(max(dist, 1.0))  # Prevent division by zero
        
        # Apply Park et al. energy summation model for 3 actuators
        # Ai = sqrt(1/di / sum(1/dj)) * Av
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities_norm = []
        for dist in distances:
            intensity_norm = math.sqrt((1/dist) / sum_inv_distances) * (desired_intensity / 15.0)
            intensities_norm.append(intensity_norm)
        
        # Convert to device range (1-15)
        device_intensities = []
        for intensity_norm in intensities_norm:
            device_intensity = max(1, min(15, round(intensity_norm * 15)))
            device_intensities.append(device_intensity)
        
        return tuple(device_intensities)
    
    def create_enhanced_phantom(self, phantom_pos: Tuple[float, float], 
                              desired_intensity: int) -> Optional[Enhanced3ActuatorPhantom]:
        """NEW: Create enhanced 3-actuator phantom following Park et al. methodology"""
        print(f"\n🔺 Creating enhanced 3-actuator phantom at {phantom_pos} with intensity {desired_intensity}/15")
        print(f"   Following Park et al. (2016) - 'Rendering Moving Tactile Stroke on the Palm Using a Sparse 2D Array'")
        
        if desired_intensity < 1 or desired_intensity > 15:
            print(f"❌ Invalid intensity {desired_intensity} - must be 1-15")
            return None
        
        # Find best triangle for this position using Park et al. methodology
        triangle = self.find_best_triangle_for_position(phantom_pos)
        if not triangle:
            print("❌ Cannot find suitable triangle")
            return None
        
        print(f"🔺 Selected triangle formed by actuators: {triangle['actuators']}")
        print(f"   Actuator positions: {[f'Act{aid}@{pos}' for aid, pos in zip(triangle['actuators'], triangle['positions'])]}")
        print(f"   Triangle area: {triangle['area']:.1f}mm² (larger = better phantom quality)")
        
        try:
            intensities = self.calculate_3actuator_intensities(phantom_pos, triangle, desired_intensity)
            print(f"🧮 Calculated intensities using Park et al. energy model:")
            for i, (act_id, intensity) in enumerate(zip(triangle['actuators'], intensities)):
                pos = triangle['positions'][i]
                distance = math.sqrt((phantom_pos[0] - pos[0])**2 + (phantom_pos[1] - pos[1])**2)
                print(f"   Act{act_id}: {intensity}/15 (distance: {distance:.1f}mm)")
        except ValueError as e:
            print(f"❌ {e}")
            return None
        
        # Calculate energy efficiency using Park et al. model
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
        
        print(f"✅ Enhanced phantom {phantom_id} created successfully!")
        print(f"📍 Virtual position: {phantom_pos}")
        print(f"⚡ Commands: Act{triangle['actuators'][0]}={intensities[0]}/15, "
              f"Act{triangle['actuators'][1]}={intensities[1]}/15, "
              f"Act{triangle['actuators'][2]}={intensities[2]}/15")
        print(f"📊 Energy efficiency: {efficiency:.3f} (1.0 = perfect, Park et al. energy model)")
        print(f"🖱️  You can now hover over this phantom to activate all 3 physical actuators!")
        print("=" * 70)
        
        return phantom
    
    def activate_enhanced_phantom(self, phantom_id: int) -> bool:
        """NEW: Activate 3-actuator phantom"""
        if phantom_id >= len(self.enhanced_phantoms):
            print(f"❌ Enhanced phantom {phantom_id} does not exist")
            return False
        
        phantom = self.enhanced_phantoms[phantom_id]
        
        if not self.api or not self.api.connected:
            print("❌ No API connection")
            return False
        
        freq = 4  # Using 250Hz would be optimal (Park et al.) but limited by hardware
        success1 = self.api.send_command(phantom.physical_actuator_1, phantom.required_intensity_1, freq, 1)
        success2 = self.api.send_command(phantom.physical_actuator_2, phantom.required_intensity_2, freq, 1)
        success3 = self.api.send_command(phantom.physical_actuator_3, phantom.required_intensity_3, freq, 1)
        
        if success1 and success2 and success3:
            print(f"🚀 Enhanced phantom {phantom_id} ACTIVATED at {phantom.virtual_position}")
            return True
        else:
            print(f"❌ Failed to activate enhanced phantom {phantom_id}")
            return False
    
    def deactivate_enhanced_phantom(self, phantom_id: int) -> bool:
        """NEW: Stop 3-actuator phantom"""
        if phantom_id >= len(self.enhanced_phantoms):
            return False
        
        phantom = self.enhanced_phantoms[phantom_id]
        
        if not self.api or not self.api.connected:
            return False
        
        success1 = self.api.send_command(phantom.physical_actuator_1, 0, 0, 0)
        success2 = self.api.send_command(phantom.physical_actuator_2, 0, 0, 0)
        success3 = self.api.send_command(phantom.physical_actuator_3, 0, 0, 0)
        
        if success1 and success2 and success3:
            print(f"⏹️  Enhanced phantom {phantom_id} stopped")
            return True
        return False
    
    def set_pattern_parameters(self, duration: int, intensity: int):
        """Set parameters for mouse pattern creation with Park et al. constraints"""
        # NEW: Enforce 70ms maximum duration constraint
        duration = min(duration, PAPER_PARAMS['MAX_DURATION'])
        self.pattern_duration = duration
        self.pattern_intensity = intensity
        
        if duration > PAPER_PARAMS['MAX_DURATION']:
            print(f"⚠️  Duration clamped to {PAPER_PARAMS['MAX_DURATION']}ms to prevent overlapping (Park et al.)")
        
        print(f"🎛️  Enhanced pattern parameters: {duration}ms duration, {intensity}/15 intensity")
    
    def calculate_enhanced_soa(self, duration_ms: float) -> float:
        """NEW: Enhanced SOA calculation with non-overlapping constraint"""
        soa = PAPER_PARAMS['SOA_SLOPE'] * duration_ms + PAPER_PARAMS['SOA_BASE']
        
        # NEW: Ensure non-overlapping constraint from Park et al.
        if soa <= duration_ms:
            soa = duration_ms + 1  # Minimum gap to prevent overlap
            print(f"⚠️  SOA adjusted to {soa:.1f}ms to prevent overlapping")
        
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
        
        print(f"🔧 Enhanced grid positions updated: {'Custom' if self.use_custom_positions else f'{self.actuator_spacing}mm'}")
        
        # Recompute triangles when positions change
        if hasattr(self, 'actuator_positions'):
            self.compute_actuator_triangles()
    
    # Mouse interaction methods (enhanced)
    def on_mouse_hover(self, target_id: int, is_phantom: bool = False):
        """Handle mouse hover over actuator or phantom with enhanced support"""
        current_target = f"{'P' if is_phantom else 'A'}{target_id}"
        if current_target == self.mouse_hover_actuator:
            return
        
        # Always stop previous vibration first
        self.stop_hover_vibration()
        self.mouse_hover_actuator = current_target
        
        # Enhanced vibration with SOA constraints
        if self.api and self.api.connected:
            freq = 4
            
            if is_phantom:
                # Handle phantom actuator hover - make it feel like a real actuator
                if target_id < len(self.enhanced_phantoms):
                    phantom = self.enhanced_phantoms[target_id]
                    
                    print(f"🖱️  Phantom hover detected: 3P{target_id} at {phantom.virtual_position}")
                    
                    # Activate all 3 physical actuators for the phantom
                    success1 = self.api.send_command(phantom.physical_actuator_1, phantom.required_intensity_1, freq, 1)
                    success2 = self.api.send_command(phantom.physical_actuator_2, phantom.required_intensity_2, freq, 1)
                    success3 = self.api.send_command(phantom.physical_actuator_3, phantom.required_intensity_3, freq, 1)
                    
                    if success1 and success2 and success3:
                        self.mouse_vibration_active = True
                        self.hover_timer.start(self.pattern_duration)
                        pos = phantom.virtual_position
                        print(f"🖱️  Phantom 3P{target_id}@{pos} ACTIVATED ({self.pattern_duration}ms)")
                        print(f"     Physical actuators: Act{phantom.physical_actuator_1}({phantom.required_intensity_1}/15), "
                              f"Act{phantom.physical_actuator_2}({phantom.required_intensity_2}/15), "
                              f"Act{phantom.physical_actuator_3}({phantom.required_intensity_3}/15)")
                        
                        # Record phantom activation if recording
                        if self.is_recording:
                            current_time = time.time() * 1000
                            relative_time = current_time - self.recording_start_time
                            
                            # Record as a phantom step with special ID
                            step = PatternStep(
                                actuator_id=f"P{target_id}",  # Mark as phantom
                                timestamp=relative_time,
                                duration=self.pattern_duration,
                                intensity=phantom.desired_intensity
                            )
                            self.current_pattern_steps.append(step)
                            print(f"📝 Recorded phantom: 3P{target_id} at {relative_time:.1f}ms")
                    else:
                        print(f"❌ Failed to activate phantom 3P{target_id}")
                        self.mouse_vibration_active = False
                else:
                    print(f"❌ Phantom {target_id} not found (only {len(self.enhanced_phantoms)} phantoms exist)")
            else:
                # Handle regular actuator hover
                success = self.api.send_command(target_id, self.pattern_intensity, freq, 1)
                if success:
                    self.mouse_vibration_active = True
                    self.hover_timer.start(self.pattern_duration)
                    pos = self.actuator_positions.get(target_id, (0, 0))
                    print(f"🖱️  Actuator hover: Act{target_id}@{pos} ON ({self.pattern_duration}ms)")
                    
                    # Record pattern step if recording
                    if self.is_recording:
                        current_time = time.time() * 1000
                        relative_time = current_time - self.recording_start_time
                        
                        step = PatternStep(
                            actuator_id=target_id,
                            timestamp=relative_time,
                            duration=self.pattern_duration,
                            intensity=self.pattern_intensity
                        )
                        self.current_pattern_steps.append(step)
                        print(f"📝 Recorded: Act{target_id} at {relative_time:.1f}ms")
        else:
            if not self.api:
                print("❌ No API available")
            elif not self.api.connected:
                print("❌ API not connected")
            self.mouse_vibration_active = False
    
    def on_mouse_leave(self):
        """Handle mouse leaving actuator area"""
        self.stop_hover_vibration()
        self.mouse_hover_actuator = None
    
    def stop_hover_vibration(self):
        """Stop current hover vibration (actuator or phantom)"""
        if self.mouse_vibration_active and self.mouse_hover_actuator is not None:
            if self.api and self.api.connected:
                
                if self.mouse_hover_actuator.startswith('P'):
                    # Stop phantom hover
                    phantom_id = int(self.mouse_hover_actuator[1:])
                    if phantom_id < len(self.enhanced_phantoms):
                        phantom = self.enhanced_phantoms[phantom_id]
                        self.api.send_command(phantom.physical_actuator_1, 0, 0, 0)
                        self.api.send_command(phantom.physical_actuator_2, 0, 0, 0)
                        self.api.send_command(phantom.physical_actuator_3, 0, 0, 0)
                        print(f"🖱️  Enhanced phantom hover: 3P{phantom_id} OFF")
                else:
                    # Stop regular actuator hover
                    actuator_id = int(self.mouse_hover_actuator[1:])
                    self.api.send_command(actuator_id, 0, 0, 0)
                    print(f"🖱️  Enhanced hover: Act{actuator_id} OFF")
                    
            self.mouse_vibration_active = False
    
    # Pattern recording methods (enhanced)
    def start_recording(self, pattern_name: str):
        """Start recording a new pattern"""
        if self.is_recording:
            self.stop_recording()
        
        self.is_recording = True
        self.recording_start_time = time.time() * 1000
        self.current_pattern_steps = []
        self.current_pattern_name = pattern_name
        print(f"🔴 Enhanced recording started: '{pattern_name}' (3-actuator phantom support)")
    
    def stop_recording(self) -> Optional[TactilePattern]:
        """Stop recording and return the pattern"""
        if not self.is_recording:
            return None
        
        self.is_recording = False
        current_time = time.time() * 1000
        total_duration = current_time - self.recording_start_time
        
        if self.current_pattern_steps:
            pattern = TactilePattern(
                name=self.current_pattern_name,
                steps=self.current_pattern_steps.copy(),
                total_duration=total_duration,
                created_timestamp=time.time()
            )
            
            self.saved_patterns[pattern.name] = pattern
            print(f"⏹️  Enhanced recording stopped: '{pattern.name}' - {len(pattern.steps)} steps, {total_duration:.1f}ms")
            return pattern
        else:
            print("⏹️  Recording stopped: No steps recorded")
            return None
    
    def save_pattern_to_file(self, pattern: TactilePattern, filepath: str):
        """Save pattern to JSON file"""
        try:
            with open(filepath, 'w') as f:
                json.dump(pattern.to_dict(), f, indent=2)
            print(f"💾 Enhanced pattern saved to {filepath}")
            return True
        except Exception as e:
            print(f"❌ Failed to save pattern: {e}")
            return False
    
    def load_pattern_from_file(self, filepath: str) -> Optional[TactilePattern]:
        """Load pattern from JSON file"""
        try:
            with open(filepath, 'r') as f:
                data = json.load(f)
            pattern = TactilePattern.from_dict(data)
            self.saved_patterns[pattern.name] = pattern
            print(f"📁 Enhanced pattern loaded: '{pattern.name}' - {len(pattern.steps)} steps")
            return pattern
        except Exception as e:
            print(f"❌ Failed to load pattern: {e}")
            return None
    
    def play_recorded_pattern(self, pattern_name: str):
        """Play a recorded pattern using enhanced SOA timing with phantom support"""
        if pattern_name not in self.saved_patterns:
            print(f"❌ Pattern '{pattern_name}' not found")
            return
        
        pattern = self.saved_patterns[pattern_name]
        
        # Convert pattern steps to SOA steps with enhanced timing
        soa_steps = []
        for step in pattern.steps:
            if isinstance(step.actuator_id, str) and step.actuator_id.startswith('P'):
                # Handle phantom step
                phantom_id = int(step.actuator_id[1:])
                if phantom_id < len(self.enhanced_phantoms):
                    phantom = self.enhanced_phantoms[phantom_id]
                    
                    # Create SOA steps for all 3 physical actuators
                    for phys_id, intensity in [(phantom.physical_actuator_1, phantom.required_intensity_1),
                                             (phantom.physical_actuator_2, phantom.required_intensity_2),
                                             (phantom.physical_actuator_3, phantom.required_intensity_3)]:
                        soa_step = SOAStep(
                            actuator_id=phys_id,
                            onset_time=step.timestamp,
                            duration=step.duration,
                            intensity=intensity
                        )
                        soa_steps.append(soa_step)
            else:
                # Regular actuator step
                soa_step = SOAStep(
                    actuator_id=step.actuator_id,
                    onset_time=step.timestamp,
                    duration=step.duration,
                    intensity=step.intensity
                )
                soa_steps.append(soa_step)
        
        print(f"🎬 Playing enhanced pattern: '{pattern_name}' - {len(soa_steps)} steps (including phantoms)")
        self.execute_soa_sequence(soa_steps)
    
    # Enhanced SOA methods
    def create_soa_sequence(self, actuator_sequence: List[int], duration_ms: float, 
                           intensity: int) -> tuple:
        """Create enhanced SOA sequence with non-overlapping constraint"""
        steps = []
        soa = self.calculate_enhanced_soa(duration_ms)
        warnings = []
        
        # NEW: Check for overlapping constraint
        if duration_ms > PAPER_PARAMS['MAX_DURATION']:
            warnings.append(f"Duration {duration_ms}ms > {PAPER_PARAMS['MAX_DURATION']}ms limit (Park et al.)")
        
        if soa <= duration_ms:
            warnings.append(f"SOA {soa:.1f}ms ≤ duration {duration_ms}ms - potential overlap!")
        
        for i, actuator_id in enumerate(actuator_sequence):
            onset_time = i * soa
            step = SOAStep(
                actuator_id=actuator_id,
                onset_time=onset_time,
                duration=duration_ms,
                intensity=intensity
            )
            steps.append(step)
        
        return steps, warnings
    
    def execute_soa_sequence(self, steps: List[SOAStep]):
        """Execute enhanced SOA sequence with precise timing"""
        if not self.api or not self.api.connected:
            print("No API connection")
            return
        
        self.soa_steps = steps
        self.soa_next_step_idx = 0
        self.soa_active_actuators = {}
        
        if not self.soa_steps:
            return
        
        print(f"🚀 Executing enhanced SOA sequence ({len(self.soa_steps)} steps)")
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
            
            success = self.api.send_command(step.actuator_id, device_intensity, freq, 1)
            
            if success:
                stop_time = current_time + step.duration
                self.soa_active_actuators[step.actuator_id] = stop_time
                pos = self.actuator_positions.get(step.actuator_id, (0, 0))
                print(f"⚡ Enhanced Act{step.actuator_id}@{pos} ON at {current_time:.1f}ms")
            
            self.soa_next_step_idx += 1
        
        # Stop actuators when duration expires
        to_stop = []
        for actuator_id, stop_time in self.soa_active_actuators.items():
            if current_time >= stop_time:
                self.api.send_command(actuator_id, 0, 0, 0)
                print(f"⏹️  Enhanced Act{actuator_id} OFF at {current_time:.1f}ms")
                to_stop.append(actuator_id)
        
        for actuator_id in to_stop:
            del self.soa_active_actuators[actuator_id]
        
        if (self.soa_next_step_idx >= len(self.soa_steps) and 
            len(self.soa_active_actuators) == 0):
            self.soa_timer.stop()
            print("✅ Enhanced SOA sequence complete\n")
    
    def activate_all_enhanced_phantoms(self):
        """NEW: Activate all enhanced phantoms"""
        print(f"🚀 Activating {len(self.enhanced_phantoms)} enhanced phantoms...")
        for phantom in self.enhanced_phantoms:
            self.activate_enhanced_phantom(phantom.phantom_id)
    
    def deactivate_all_enhanced_phantoms(self):
        """NEW: Stop all enhanced phantoms"""
        print(f"⏹️  Stopping {len(self.enhanced_phantoms)} enhanced phantoms...")
        for phantom in self.enhanced_phantoms:
            self.deactivate_enhanced_phantom(phantom.phantom_id)
    
    def delete_enhanced_phantom(self, phantom_id: int) -> bool:
        """NEW: Delete a specific phantom by ID"""
        if phantom_id < 0 or phantom_id >= len(self.enhanced_phantoms):
            print(f"❌ Phantom {phantom_id} does not exist")
            return False
        
        # First deactivate if it's currently active
        self.deactivate_enhanced_phantom(phantom_id)
        
        # Stop hover if this phantom is being hovered
        if self.mouse_hover_actuator == f"P{phantom_id}":
            self.stop_hover_vibration()
            self.mouse_hover_actuator = None
        
        # Remove the phantom
        phantom = self.enhanced_phantoms.pop(phantom_id)
        
        # Reassign IDs for remaining phantoms to maintain continuity
        for i, remaining_phantom in enumerate(self.enhanced_phantoms):
            remaining_phantom.phantom_id = i
        
        print(f"🗑️  Deleted phantom {phantom_id} at {phantom.virtual_position}")
        print(f"   Remaining phantoms: {len(self.enhanced_phantoms)}")
        return True
    
    def clear_enhanced_phantoms(self):
        """NEW: Clear all enhanced phantoms"""
        self.deactivate_all_enhanced_phantoms()
        # Stop hover if any phantom is being hovered
        if self.mouse_hover_actuator and self.mouse_hover_actuator.startswith('P'):
            self.stop_hover_vibration()
            self.mouse_hover_actuator = None
        self.enhanced_phantoms = []
        print("🗑️  All enhanced phantoms cleared")
    
    def stop_all(self):
        """Emergency stop all activity"""
        self.soa_timer.stop()
        self.stop_hover_vibration()
        self.deactivate_all_enhanced_phantoms()
        if self.api and self.api.connected:
            for actuator_id in ACTUATORS:
                self.api.send_command(actuator_id, 0, 0, 0)
        self.soa_active_actuators = {}
        print("🛑 All enhanced activity stopped")

class EnhancedTactileVisualization(QWidget):
    """Enhanced visualization with 3-actuator phantom support"""
    
    actuator_hovered = pyqtSignal(int)
    phantom_hovered = pyqtSignal(int)  # NEW: Signal for phantom hover
    mouse_left = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(350, 350)  # Smaller visualization
        self.setMouseTracking(True)
        self.engine = None
        self.soa_steps = []
        self.soa_warnings = []
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}  # NEW: Cache phantom screen positions
        self.hover_radius = 20  # Smaller hover radius
        self.phantom_hover_radius = 25  # Smaller phantom hover radius
        self.show_triangles = True  # NEW: Show triangulation
        
    def set_engine(self, engine: EnhancedTactileEngine):
        self.engine = engine
        self.update()
    
    def toggle_triangles(self, show: bool):
        """NEW: Toggle triangle visualization"""
        self.show_triangles = show
        self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events for hover detection (actuators and phantoms)"""
        if not self.engine:
            return
        
        mouse_pos = event.position()
        
        # Check for phantom hover first (higher priority)
        hovered_phantom = self.get_phantom_at_position(mouse_pos)
        if hovered_phantom is not None:
            self.phantom_hovered.emit(hovered_phantom)
            return
        
        # Check for actuator hover
        hovered_actuator = self.get_actuator_at_position(mouse_pos)
        if hovered_actuator is not None:
            self.actuator_hovered.emit(hovered_actuator)
        else:
            self.mouse_left.emit()
    
    def leaveEvent(self, event):
        """Handle mouse leaving the widget"""
        self.mouse_left.emit()
    
    def get_actuator_at_position(self, pos: QPointF) -> Optional[int]:
        """Get actuator ID at mouse position"""
        for actuator_id, screen_pos in self.actuator_screen_positions.items():
            distance = math.sqrt((pos.x() - screen_pos[0])**2 + (pos.y() - screen_pos[1])**2)
            if distance <= self.hover_radius:
                return actuator_id
        return None
    
    def get_phantom_at_position(self, pos: QPointF) -> Optional[int]:
        """NEW: Get phantom ID at mouse position with debug info"""
        for phantom_id, screen_pos in self.phantom_screen_positions.items():
            distance = math.sqrt((pos.x() - screen_pos[0])**2 + (pos.y() - screen_pos[1])**2)
            if distance <= self.phantom_hover_radius:
                print(f"🖱️  Mouse over phantom 3P{phantom_id} (distance: {distance:.1f}px, limit: {self.phantom_hover_radius}px)")
                return phantom_id
        return None
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.engine:
            painter.drawText(20, 50, "No enhanced engine connected")
            return
        
        positions = list(self.engine.actuator_positions.values())
        if not positions:
            painter.drawText(20, 50, "No actuator positions available")
            return
        
        x_coords = [pos[0] for pos in positions]
        y_coords = [pos[1] for pos in positions]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        margin = 60  # Larger margin for enhanced view
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 120
        
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.8
        
        def pos_to_screen(pos):
            screen_x = margin + (pos[0] - min_x) * scale
            screen_y = margin + 25 + (pos[1] - min_y) * scale  # Less offset
            return (screen_x, screen_y)
        
        self.actuator_screen_positions = {}
        self.phantom_screen_positions = {}  # NEW: Clear phantom positions cache
        
        # Title
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(11)  # Smaller title font
        painter.setFont(font)
        
        title_text = "🔺 Smooth 4x4 Tactile - Optimized Triangulation (Park et al.)"
        painter.drawText(margin, 20, title_text)  # Closer to top
        
        # Recording indicator
        if self.engine and self.engine.is_recording:
            painter.setPen(QPen(QColor(255, 0, 0)))
            font.setPointSize(10)  # Smaller recording font
            painter.setFont(font)
            painter.drawText(margin, self.height() - 10, f"🔴 RECORDING: {self.engine.current_pattern_name}")  # Bottom of screen
        
        # NEW: Draw optimized triangles with smoothness visualization - more subtle
        if self.show_triangles and hasattr(self.engine, 'actuator_triangles'):
            # Draw triangles with color coding based on smoothness
            for i, triangle in enumerate(self.engine.actuator_triangles[:8]):  # Show fewer triangles
                screen_positions = [pos_to_screen(pos) for pos in triangle['positions']]
                points = [QPointF(pos[0], pos[1]) for pos in screen_positions]
                
                # Color based on smoothness score (green = smooth, red = less smooth)
                smoothness = triangle.get('smoothness_score', 10)
                if smoothness < 5:
                    color = QColor(100, 255, 100, 60)  # Green - very smooth (more transparent)
                elif smoothness < 10:
                    color = QColor(150, 255, 150, 40)  # Light green - smooth  
                elif smoothness < 20:
                    color = QColor(200, 200, 255, 30)  # Blue - moderate
                else:
                    color = QColor(255, 150, 150, 20)  # Red - less smooth
                
                painter.setPen(QPen(color, 1))
                painter.setBrush(QBrush(color))
                painter.drawPolygon(points)
                
                # Skip triangle labels to reduce clutter
                if False:  # Disable triangle labeling for cleaner look
                    center_screen = pos_to_screen(triangle['center'])
                    painter.setPen(QPen(QColor(0, 0, 0)))
                    font.setPointSize(6)
                    painter.setFont(font)
                    triangle_type = triangle.get('type', 'unknown')[:8]
                    painter.drawText(int(center_screen[0]-15), int(center_screen[1]), triangle_type)
        
        # Draw actuators
        for actuator_id in ACTUATORS:
            if actuator_id not in self.engine.actuator_positions:
                continue
                
            pos = self.engine.actuator_positions[actuator_id]
            screen_x, screen_y = pos_to_screen(pos)
            self.actuator_screen_positions[actuator_id] = (screen_x, screen_y)
            
            # Determine actuator state and color
            is_hovered = (self.engine.mouse_hover_actuator == f"A{actuator_id}")
            is_vibrating = (actuator_id in self.engine.soa_active_actuators or 
                          (is_hovered and self.engine.mouse_vibration_active))
            in_recording = (self.engine.is_recording and 
                          any((isinstance(step.actuator_id, int) and step.actuator_id == actuator_id) 
                              for step in self.engine.current_pattern_steps))
            in_phantom = any(
                actuator_id in [p.physical_actuator_1, p.physical_actuator_2, p.physical_actuator_3] 
                for p in self.engine.enhanced_phantoms
            )
            
            # Enhanced color coding
            if is_vibrating:
                color = QColor(255, 50, 50)    # Bright red - currently vibrating
            elif is_hovered:
                color = QColor(255, 150, 0)    # Orange - hovered
            elif in_recording:
                color = QColor(100, 255, 100)  # Light green - recorded
            elif in_phantom:
                color = QColor(150, 0, 255)    # Purple - part of 3-actuator phantom
            else:
                color = QColor(120, 120, 120)  # Gray - inactive
            
            # Draw actuator
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(color))
            
            radius = 16 if is_hovered else 12  # Smaller actuators
            painter.drawEllipse(int(screen_x - radius), int(screen_y - radius), 
                              radius * 2, radius * 2)
            
            # Hover detection area
            if is_hovered:
                painter.setPen(QPen(QColor(255, 0, 0, 100), 2, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(255, 0, 0, 30)))
                painter.drawEllipse(int(screen_x - self.hover_radius), int(screen_y - self.hover_radius),
                                  self.hover_radius * 2, self.hover_radius * 2)
            
            # Actuator ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(9)  # Smaller font
            font.setBold(True)
            painter.setFont(font)
            text_width = len(str(actuator_id)) * 5
            painter.drawText(int(screen_x - text_width/2), int(screen_y + 3), str(actuator_id))
            
            # Position label
            painter.setPen(QPen(QColor(0, 0, 0)))
            font.setPointSize(6)  # Much smaller position labels
            font.setBold(False)
            painter.setFont(font)
            pos_text = f"({pos[0]:.0f},{pos[1]:.0f})"
            painter.drawText(int(screen_x - 20), int(screen_y + radius + 10), pos_text)
        
        # NEW: Draw enhanced phantoms with hover detection
        for phantom in self.engine.enhanced_phantoms:
            phantom_screen = pos_to_screen(phantom.virtual_position)
            
            # Cache phantom screen position for hover detection
            self.phantom_screen_positions[phantom.phantom_id] = phantom_screen
            
            # Check if phantom is hovered
            is_phantom_hovered = (self.engine.mouse_hover_actuator == f"P{phantom.phantom_id}")
            is_phantom_vibrating = (is_phantom_hovered and self.engine.mouse_vibration_active)
            in_phantom_recording = (self.engine.is_recording and 
                                  any((isinstance(step.actuator_id, str) and step.actuator_id == f"P{phantom.phantom_id}") 
                                      for step in self.engine.current_pattern_steps))
            
            # Phantom color coding - make it more obvious when hoverable
            if is_phantom_vibrating:
                phantom_color = QColor(255, 50, 255)    # Bright magenta - vibrating
                radius = 14  # Smaller
            elif is_phantom_hovered:
                phantom_color = QColor(255, 150, 255)   # Light magenta - hovered
                radius = 12  # Smaller
            elif in_phantom_recording:
                phantom_color = QColor(150, 255, 150)   # Light green - recorded
                radius = 10  # Smaller
            else:
                phantom_color = QColor(200, 100, 200)   # Default magenta - hoverable
                radius = 10  # Smaller
            
            # Draw phantom with more prominent appearance
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(phantom_color))
            painter.drawEllipse(int(phantom_screen[0] - radius), int(phantom_screen[1] - radius),
                              radius * 2, radius * 2)
            
            # Phantom hover detection area - make it larger for easier hovering
            if is_phantom_hovered:
                painter.setPen(QPen(QColor(255, 0, 255, 120), 2, Qt.PenStyle.DashLine))
                painter.setBrush(QBrush(QColor(255, 0, 255, 40)))
                painter.drawEllipse(int(phantom_screen[0] - self.phantom_hover_radius), 
                                  int(phantom_screen[1] - self.phantom_hover_radius),
                                  self.phantom_hover_radius * 2, self.phantom_hover_radius * 2)
            
            # Phantom ID - more prominent
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(8)  # Smaller font
            font.setBold(True)
            painter.setFont(font)
            phantom_text = f"3P{phantom.phantom_id}"
            text_width = len(phantom_text) * 5
            painter.drawText(int(phantom_screen[0] - text_width/2), int(phantom_screen[1] + 3), phantom_text)
            
            # Draw connection lines to all 3 physical actuators with different styles
            line_colors = [QColor(255, 0, 255), QColor(200, 0, 200), QColor(150, 0, 150)]
            
            for i, phys_id in enumerate([phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3]):
                if phys_id in self.engine.actuator_positions:
                    phys_pos = self.engine.actuator_positions[phys_id]
                    phys_screen = pos_to_screen(phys_pos)
                    
                    painter.setPen(QPen(line_colors[i], 1 + i, Qt.PenStyle.DashLine))
                    painter.drawLine(int(phantom_screen[0]), int(phantom_screen[1]),
                                   int(phys_screen[0]), int(phys_screen[1]))
                    
                    # Show intensity values near connection lines when hovered
                    if is_phantom_hovered:
                        mid_x = (phantom_screen[0] + phys_screen[0]) / 2
                        mid_y = (phantom_screen[1] + phys_screen[1]) / 2
                        intensities = [phantom.required_intensity_1, phantom.required_intensity_2, phantom.required_intensity_3]
                        
                        painter.setPen(QPen(QColor(0, 0, 0)))
                        font.setPointSize(8)
                        painter.setFont(font)
                        painter.drawText(int(mid_x - 5), int(mid_y + 3), f"{intensities[i]}")
            
            # Add hoverable indicator for better UX
            if not is_phantom_hovered and not is_phantom_vibrating:
                # Small hover hint circle
                painter.setPen(QPen(QColor(255, 255, 255, 150), 1, Qt.PenStyle.DotLine))
                painter.setBrush(QBrush(QColor(0, 0, 0, 0)))  # Transparent
                hint_radius = self.phantom_hover_radius
                painter.drawEllipse(int(phantom_screen[0] - hint_radius), 
                                  int(phantom_screen[1] - hint_radius),
                                  hint_radius * 2, hint_radius * 2)
        
        # Enhanced legend - more compact
        legend_y = self.height() - 90  # Less space for legend
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(8)  # Smaller legend font
        painter.setFont(font)
        
        painter.drawText(margin, legend_y, "🔴 Vibrating  🟠 Hovered  🟢 Recorded  🟣 3-Phantom  ⚫ Inactive")
        painter.drawText(margin, legend_y + 12, "💡 Hover over actuators OR phantoms • Optimized triangulation for smooth motion")
        
        triangle_info = ""
        if self.engine and hasattr(self.engine, 'actuator_triangles'):
            total_triangles = len(self.engine.actuator_triangles)
            if total_triangles > 0:
                avg_smoothness = sum(t.get('smoothness_score', 0) for t in self.engine.actuator_triangles[:10]) / min(10, total_triangles)
                triangle_info = f"🔺 {total_triangles} triangles (avg smoothness: {avg_smoothness:.1f})"
            else:
                triangle_info = "🔺 No triangles computed"
        
        painter.drawText(margin, legend_y + 24, triangle_info)
        
        phantom_count = len(self.engine.enhanced_phantoms) if self.engine else 0
        painter.drawText(margin, legend_y + 36, f"👻 {phantom_count} phantoms • 🟢=smooth 🔵=moderate 🔴=rough triangles")
        
        # Pattern info
        if self.engine and self.engine.current_pattern_steps:
            painter.drawText(margin, legend_y + 48, 
                           f"📝 Pattern: {len(self.engine.current_pattern_steps)} steps")
        
        painter.drawText(margin, legend_y + 60, 
                        f"⚙️ {self.engine.pattern_duration if self.engine else 60}ms, "
                        f"I={self.engine.pattern_intensity if self.engine else 8}/15")
        
        # Show phantom details on hover - more compact
        if self.engine and self.engine.mouse_hover_actuator and self.engine.mouse_hover_actuator.startswith('P'):
            phantom_id = int(self.engine.mouse_hover_actuator[1:])
            if phantom_id < len(self.engine.enhanced_phantoms):
                phantom = self.engine.enhanced_phantoms[phantom_id]
                painter.drawText(margin, legend_y + 72, 
                               f"👻 3P{phantom_id}: [{phantom.physical_actuator_1},{phantom.physical_actuator_2},{phantom.physical_actuator_3}] "
                               f"I=[{phantom.required_intensity_1},{phantom.required_intensity_2},{phantom.required_intensity_3}]")
        
        # Warnings (compact)
        if self.soa_warnings:
            painter.setPen(QPen(QColor(200, 0, 0)))
            painter.drawText(margin, legend_y + 84, f"⚠️ {self.soa_warnings[0][:30]}...")

class EnhancedTactileGUI(QWidget):
    """Enhanced GUI with 3-actuator phantom controls"""
    
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
        self.viz.phantom_hovered.connect(lambda pid: self.engine.on_mouse_hover(pid, True))  # NEW: Phantom hover
        self.viz.mouse_left.connect(self.engine.on_mouse_leave)
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Enhanced title
        title = QLabel("🔺 Enhanced 4x4 Tactile Pattern Creator (Park et al. 2016)")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2E86AB;")  # Smaller title
        layout.addWidget(title)
        
        subtitle = QLabel("Smooth 3-actuator phantoms • Optimized triangulation • Non-overlapping SOA")
        subtitle.setStyleSheet("font-style: italic; color: #666; font-size: 10px;")  # Smaller subtitle
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
        
        # Enhanced Pattern Creation Controls
        pattern_group = QGroupBox("Enhanced Pattern Creation (Park et al.)")
        pattern_layout = QFormLayout(pattern_group)
        
        # Enhanced duration with constraint
        self.pattern_duration_spin = QSpinBox()
        self.pattern_duration_spin.setRange(40, PAPER_PARAMS['MAX_DURATION'])  # NEW: Max 70ms
        self.pattern_duration_spin.setValue(60)
        self.pattern_duration_spin.setSuffix(" ms")
        self.pattern_duration_spin.valueChanged.connect(self.update_pattern_parameters)
        pattern_layout.addRow("Hover Duration (≤70ms):", self.pattern_duration_spin)
        
        self.pattern_intensity_spin = QSpinBox()
        self.pattern_intensity_spin.setRange(1, 15)
        self.pattern_intensity_spin.setValue(8)
        self.pattern_intensity_spin.valueChanged.connect(self.update_pattern_parameters)
        pattern_layout.addRow("Hover Intensity:", self.pattern_intensity_spin)
        
        # Recording controls
        record_layout = QHBoxLayout()
        
        self.pattern_name_combo = QComboBox()
        self.pattern_name_combo.setEditable(True)
        self.pattern_name_combo.setPlaceholderText("Enter pattern name...")
        
        self.record_btn = QPushButton("🔴 Record")
        self.record_btn.clicked.connect(self.toggle_recording)
        self.record_btn.setStyleSheet("QPushButton { background-color: #FF4444; color: white; font-weight: bold; }")
        
        record_layout.addWidget(QLabel("Pattern Name:"))
        record_layout.addWidget(self.pattern_name_combo)
        record_layout.addWidget(self.record_btn)
        
        pattern_layout.addRow("", record_layout)
        layout.addWidget(pattern_group)
        
        # Enhanced Phantom Creation
        phantom_group = QGroupBox("3-Actuator Phantom Creation (Park et al.)")
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
        
        phantom_btn_layout = QHBoxLayout()
        
        self.create_phantom_btn = QPushButton("🔺 Create 3-Phantom")
        self.create_phantom_btn.clicked.connect(self.create_enhanced_phantom)
        self.create_phantom_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        
        self.show_triangles_btn = QCheckBox("Show Triangles")
        self.show_triangles_btn.setChecked(True)
        self.show_triangles_btn.toggled.connect(self.toggle_triangle_view)
        
        phantom_btn_layout.addWidget(self.create_phantom_btn)
        phantom_btn_layout.addWidget(self.show_triangles_btn)
        phantom_layout.addRow("", phantom_btn_layout)
        
        layout.addWidget(phantom_group)
        
        # NEW: Phantom Management
        phantom_mgmt_group = QGroupBox("Phantom Management")
        phantom_mgmt_layout = QVBoxLayout(phantom_mgmt_group)
        
        # Phantom list
        self.phantom_list = QListWidget()
        self.phantom_list.setMaximumHeight(60)  # Smaller height
        phantom_mgmt_layout.addWidget(self.phantom_list)
        
        # Phantom management buttons
        phantom_mgmt_btn_layout = QHBoxLayout()
        
        self.test_phantom_btn = QPushButton("🧪 Test Selected")
        self.delete_phantom_btn = QPushButton("🗑️ Delete Selected")
        self.activate_phantoms_btn = QPushButton("🚀 Activate All")
        self.deactivate_phantoms_btn = QPushButton("⏹️ Stop All")
        self.clear_phantoms_btn = QPushButton("🗑️ Clear All")
        
        self.test_phantom_btn.clicked.connect(self.test_selected_phantom)
        self.delete_phantom_btn.clicked.connect(self.delete_selected_phantom)
        self.activate_phantoms_btn.clicked.connect(self.activate_all_phantoms)
        self.deactivate_phantoms_btn.clicked.connect(self.deactivate_all_phantoms)
        self.clear_phantoms_btn.clicked.connect(self.clear_all_phantoms)
        
        phantom_mgmt_btn_layout.addWidget(self.test_phantom_btn)
        phantom_mgmt_btn_layout.addWidget(self.delete_phantom_btn)
        phantom_mgmt_btn_layout.addWidget(self.activate_phantoms_btn)
        phantom_mgmt_btn_layout.addWidget(self.deactivate_phantoms_btn)
        phantom_mgmt_btn_layout.addWidget(self.clear_phantoms_btn)
        phantom_mgmt_layout.addLayout(phantom_mgmt_btn_layout)
        
        layout.addWidget(phantom_mgmt_group)
        
        # Pattern Management
        mgmt_group = QGroupBox("Pattern Management")
        mgmt_layout = QVBoxLayout(mgmt_group)
        
        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(100)
        mgmt_layout.addWidget(self.pattern_list)
        
        mgmt_btn_layout = QHBoxLayout()
        
        self.play_btn = QPushButton("▶️ Play")
        self.save_btn = QPushButton("💾 Save")
        self.load_btn = QPushButton("📁 Load")
        self.delete_btn = QPushButton("🗑️ Delete")
        
        self.play_btn.clicked.connect(self.play_selected_pattern)
        self.save_btn.clicked.connect(self.save_selected_pattern)
        self.load_btn.clicked.connect(self.load_pattern_file)
        self.delete_btn.clicked.connect(self.delete_selected_pattern)
        
        mgmt_btn_layout.addWidget(self.play_btn)
        mgmt_btn_layout.addWidget(self.save_btn)
        mgmt_btn_layout.addWidget(self.load_btn)
        mgmt_btn_layout.addWidget(self.delete_btn)
        mgmt_layout.addLayout(mgmt_btn_layout)
        
        layout.addWidget(mgmt_group)
        
        # Enhanced Interactive Visualization
        viz_group = QGroupBox("Enhanced Interactive Grid (3-Actuator Phantoms)")
        viz_layout = QVBoxLayout(viz_group)
        
        self.viz = EnhancedTactileVisualization()
        self.viz.set_engine(self.engine)
        viz_layout.addWidget(self.viz)
        layout.addWidget(viz_group)
        
        # Global controls
        control_layout = QHBoxLayout()
        
        self.stop_all_btn = QPushButton("🛑 STOP ALL")
        self.stop_all_btn.clicked.connect(self.stop_all)
        self.stop_all_btn.setStyleSheet("QPushButton { background-color: #FF4444; color: white; font-weight: bold; padding: 8px; }")
        
        control_layout.addStretch()
        control_layout.addWidget(self.stop_all_btn)
        layout.addLayout(control_layout)
        
        # Enhanced info display
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(50)  # Smaller height
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("🔺 Smooth motion system ready! Features from Park et al. (2016):\n• Optimized triangulation for smooth patterns\n• 3-actuator phantoms with hover support • Non-overlapping SOA (≤70ms)")
        layout.addWidget(self.info_text)
        
        # Initialize
        self.update_pattern_parameters()
        self.update_pattern_list()
        self.update_phantom_list()  # NEW: Initialize phantom list
    
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
        """Update enhanced pattern creation parameters"""
        duration = self.pattern_duration_spin.value()
        intensity = self.pattern_intensity_spin.value()
        self.engine.set_pattern_parameters(duration, intensity)
        self.viz.update()
    
    def toggle_triangle_view(self, show: bool):
        """NEW: Toggle triangle visualization"""
        self.viz.toggle_triangles(show)
    
    def create_enhanced_phantom(self):
        """NEW: Create 3-actuator phantom with smooth motion optimization"""
        x = self.phantom_x_spin.value()
        y = self.phantom_y_spin.value()
        intensity = self.phantom_intensity_spin.value()
        
        phantom = self.engine.create_enhanced_phantom((x, y), intensity)
        
        if phantom:
            self.viz.update()
            self.update_phantom_list()  # NEW: Update phantom list
            
            # Get triangle info for display
            triangle_info = "Optimized triangle selected for smooth motion"
            for triangle in self.engine.actuator_triangles:
                if set(triangle['actuators']) == {phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3}:
                    smoothness = triangle.get('smoothness_score', 0)
                    triangle_type = triangle.get('type', 'unknown')
                    triangle_info = f"Triangle: {triangle_type} (smoothness: {smoothness:.2f})"
                    break
            
            # Show detailed information about which actuators are used
            actuator_info = f"Uses actuators: {phantom.physical_actuator_1}, {phantom.physical_actuator_2}, {phantom.physical_actuator_3}"
            intensity_info = f"Intensities: {phantom.required_intensity_1}/15, {phantom.required_intensity_2}/15, {phantom.required_intensity_3}/15"
            efficiency_info = f"Area: {phantom.triangle_area:.1f}mm², Energy efficiency: {phantom.energy_efficiency:.3f}"
            
            self.info_text.setPlainText(f"✅ Smooth 3-actuator phantom {phantom.phantom_id} created at ({x}, {y})\n"
                                      f"{triangle_info}\n{actuator_info}\n{intensity_info}\n{efficiency_info}\n"
                                      f"💡 Optimized for smooth pattern creation - hover to test!")
        else:
            self.info_text.setPlainText("❌ Failed to create phantom - try a position closer to actuators")
    
    def update_phantom_list(self):
        """NEW: Update the phantom list widget"""
        self.phantom_list.clear()
        for phantom in self.engine.enhanced_phantoms:
            item_text = (f"3P{phantom.phantom_id}: ({phantom.virtual_position[0]:.0f},{phantom.virtual_position[1]:.0f}) "
                        f"Acts[{phantom.physical_actuator_1},{phantom.physical_actuator_2},{phantom.physical_actuator_3}] "
                        f"I={phantom.desired_intensity}/15")
            self.phantom_list.addItem(item_text)
    
    def test_selected_phantom(self):
        """NEW: Test the selected phantom by activating it briefly"""
        current_item = self.phantom_list.currentItem()
        if not current_item:
            self.info_text.setPlainText("❌ No phantom selected for testing")
            return
        
        # Extract phantom ID from the item text
        phantom_id = int(current_item.text().split(':')[0].replace('3P', ''))
        
        if phantom_id < len(self.engine.enhanced_phantoms):
            phantom = self.engine.enhanced_phantoms[phantom_id]
            
            # Activate for test duration
            if self.engine.activate_enhanced_phantom(phantom_id):
                self.info_text.setPlainText(f"🧪 Testing phantom 3P{phantom_id} at {phantom.virtual_position}")
                
                # Auto-deactivate after 500ms
                def stop_test():
                    self.engine.deactivate_enhanced_phantom(phantom_id)
                    self.info_text.setPlainText(f"✅ Phantom 3P{phantom_id} test completed")
                
                QTimer.singleShot(500, stop_test)
            else:
                self.info_text.setPlainText(f"❌ Failed to test phantom 3P{phantom_id}")
    
    def delete_selected_phantom(self):
        """NEW: Delete the selected phantom"""
        current_item = self.phantom_list.currentItem()
        if not current_item:
            self.info_text.setPlainText("❌ No phantom selected for deletion")
            return
        
        # Extract phantom ID from the item text
        phantom_id = int(current_item.text().split(':')[0].replace('3P', ''))
        
        # Confirm deletion
        reply = QMessageBox.question(
            self, 
            "Delete Phantom", 
            f"Are you sure you want to delete phantom 3P{phantom_id}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.engine.delete_enhanced_phantom(phantom_id):
                self.update_phantom_list()
                self.viz.update()
                self.info_text.setPlainText(f"🗑️ Phantom 3P{phantom_id} deleted successfully")
            else:
                self.info_text.setPlainText(f"❌ Failed to delete phantom 3P{phantom_id}")
    
    def toggle_recording(self):
        """Toggle pattern recording"""
        if not self.engine.is_recording:
            pattern_name = self.pattern_name_combo.currentText().strip()
            if not pattern_name:
                pattern_name = f"Enhanced_Pattern_{int(time.time())}"
            
            self.engine.start_recording(pattern_name)
            self.record_btn.setText("⏹️ Stop")
            self.record_btn.setStyleSheet("QPushButton { background-color: #FF0000; color: white; font-weight: bold; }")
            self.info_text.setPlainText(f"🔴 Enhanced recording '{pattern_name}' - Hover over actuators!")
        else:
            pattern = self.engine.stop_recording()
            self.record_btn.setText("🔴 Record")
            self.record_btn.setStyleSheet("QPushButton { background-color: #FF4444; color: white; font-weight: bold; }")
            
            if pattern:
                self.update_pattern_list()
                self.info_text.setPlainText(f"✅ Enhanced pattern '{pattern.name}' recorded with {len(pattern.steps)} steps!")
            else:
                self.info_text.setPlainText("❌ No pattern recorded")
        
        self.viz.update()
    
    def update_pattern_list(self):
        """Update the pattern list widget"""
        self.pattern_list.clear()
        for pattern_name in self.engine.saved_patterns.keys():
            pattern = self.engine.saved_patterns[pattern_name]
            item_text = f"{pattern_name} ({len(pattern.steps)} steps, {pattern.total_duration:.1f}ms)"
            self.pattern_list.addItem(item_text)
    
    def play_selected_pattern(self):
        """Play the selected pattern"""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            self.info_text.setPlainText("❌ No pattern selected")
            return
        
        pattern_name = current_item.text().split(' (')[0]
        self.engine.play_recorded_pattern(pattern_name)
        self.info_text.setPlainText(f"▶️ Playing enhanced pattern: {pattern_name}")
    
    def save_selected_pattern(self):
        """Save selected pattern to file"""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            self.info_text.setPlainText("❌ No pattern selected")
            return
        
        pattern_name = current_item.text().split(' (')[0]
        if pattern_name not in self.engine.saved_patterns:
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, 
            "Save Enhanced Pattern", 
            f"{pattern_name}.json", 
            "JSON files (*.json)"
        )
        
        if filename:
            pattern = self.engine.saved_patterns[pattern_name]
            if self.engine.save_pattern_to_file(pattern, filename):
                self.info_text.setPlainText(f"💾 Enhanced pattern saved to {filename}")
            else:
                self.info_text.setPlainText("❌ Failed to save pattern")
    
    def load_pattern_file(self):
        """Load pattern from file"""
        filename, _ = QFileDialog.getOpenFileName(
            self, 
            "Load Enhanced Pattern", 
            "", 
            "JSON files (*.json)"
        )
        
        if filename:
            pattern = self.engine.load_pattern_from_file(filename)
            if pattern:
                self.update_pattern_list()
                self.info_text.setPlainText(f"📁 Enhanced pattern '{pattern.name}' loaded!")
            else:
                self.info_text.setPlainText("❌ Failed to load pattern")
    
    def delete_selected_pattern(self):
        """Delete selected pattern"""
        current_item = self.pattern_list.currentItem()
        if not current_item:
            self.info_text.setPlainText("❌ No pattern selected")
            return
        
        pattern_name = current_item.text().split(' (')[0]
        
        reply = QMessageBox.question(
            self, 
            "Delete Enhanced Pattern", 
            f"Are you sure you want to delete pattern '{pattern_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if pattern_name in self.engine.saved_patterns:
                del self.engine.saved_patterns[pattern_name]
                self.update_pattern_list()
                self.info_text.setPlainText(f"🗑️ Enhanced pattern '{pattern_name}' deleted")
    
    def activate_all_phantoms(self):
        self.engine.activate_all_enhanced_phantoms()
        phantom_count = len(self.engine.enhanced_phantoms)
        self.info_text.setPlainText(f"🚀 Activated {phantom_count} enhanced phantoms - they are now vibrating")
    
    def deactivate_all_phantoms(self):
        self.engine.deactivate_all_enhanced_phantoms()
        self.info_text.setPlainText("⏹️ All enhanced phantoms stopped")
    
    def clear_all_phantoms(self):
        if len(self.engine.enhanced_phantoms) == 0:
            self.info_text.setPlainText("ℹ️ No phantoms to clear")
            return
            
        # Confirm clearing all phantoms
        reply = QMessageBox.question(
            self, 
            "Clear All Phantoms", 
            f"Are you sure you want to delete all {len(self.engine.enhanced_phantoms)} phantoms?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            phantom_count = len(self.engine.enhanced_phantoms)
            self.engine.clear_enhanced_phantoms()
            self.update_phantom_list()
            self.viz.update()
            self.info_text.setPlainText(f"🗑️ All {phantom_count} enhanced phantoms cleared")
    
    def stop_all(self):
        self.engine.stop_all()
        self.info_text.setPlainText("🛑 EMERGENCY STOP - All enhanced activity stopped")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🔺 Smooth 4x4 Tactile Pattern Creator (Park et al. 2016)")
    
    widget = EnhancedTactileGUI()
    window.setCentralWidget(widget)
    window.resize(600, 800)  # Much smaller window
    window.show()
    
    sys.exit(app.exec())