#!/usr/bin/env python3
"""
merged_tactile_4x4_custom.py

Combined SOA and Phantom Actuator implementation for 4x4 tactile grid.
Supports both uniform grid spacing and custom actuator positions.
Following Tactile Brush paper methodology with both apparent motion and phantom illusions.

4x4 Grid Layout (User's specific layout):
Row 0: 3  2  1  0
Row 1: 4  5  6  7  
Row 2: 11 10 9  8
Row 3: 12 13 14 15
"""
import sys
import time
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QApplication, QMainWindow, QComboBox, QTextEdit, QSlider,
    QCheckBox, QTabWidget
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

# Import your API
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found.")
    python_serial_api = None

# 4x4 Grid Configuration - User's Layout
# Row 0: 3, 2, 1, 0
# Row 1: 4, 5, 6, 7  
# Row 2: 11, 10, 9, 8
# Row 3: 12, 13, 14, 15
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
GRID_ROWS = 4
GRID_COLS = 4

# Layout mapping: [row][col] = actuator_id
USER_LAYOUT = [
    [3, 2, 1, 0],      # Row 0
    [4, 5, 6, 7],      # Row 1
    [11, 10, 9, 8],    # Row 2
    [12, 13, 14, 15]   # Row 3
]

# Paper's psychophysical parameters (from Tactile Brush paper)
PAPER_PARAMS = {
    'SOA_SLOPE': 0.32,      # From paper's equation: SOA = 0.32d + 47.3
    'SOA_BASE': 47.3,
    'MIN_DURATION': 40,     # ms
    'MAX_DURATION': 160,    # ms
    'OPTIMAL_FREQ': 200,    # Hz
}

def get_grid_position(actuator_id: int, spacing_mm: float) -> Tuple[float, float]:
    """Convert actuator ID to (x, y) position in mm for user's 4x4 layout with custom spacing"""
    if actuator_id < 0 or actuator_id >= 16:
        raise ValueError(f"Invalid actuator ID {actuator_id} for 4x4 grid")
    
    # Find row and col for this actuator in the user's layout
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            if USER_LAYOUT[row][col] == actuator_id:
                # User's custom spacing: 5cm-6cm-5cm horizontal, 6cm vertical
                x_positions = [0, 50, 110, 160]  # 0, 5cm, 11cm, 16cm
                y_positions = [0, 60, 120, 180]  # 0, 6cm, 12cm, 18cm
                
                x = x_positions[col]
                y = y_positions[row]
                return (x, y)
    
    raise ValueError(f"Actuator ID {actuator_id} not found in layout")

def get_actuator_id(row: int, col: int) -> int:
    """Convert grid (row, col) to actuator ID using user's layout"""
    if row < 0 or row >= GRID_ROWS or col < 0 or col >= GRID_COLS:
        return -1
    return USER_LAYOUT[row][col]

def get_adjacent_actuators(actuator_id: int) -> List[int]:
    """Get list of adjacent actuators (horizontal, vertical, diagonal)"""
    # Find position of this actuator in the layout
    actuator_row, actuator_col = None, None
    for row in range(GRID_ROWS):
        for col in range(GRID_COLS):
            if USER_LAYOUT[row][col] == actuator_id:
                actuator_row, actuator_col = row, col
                break
        if actuator_row is not None:
            break
    
    if actuator_row is None:
        return []
    
    adjacent = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            new_row, new_col = actuator_row + dr, actuator_col + dc
            adj_id = get_actuator_id(new_row, new_col)
            if adj_id != -1:
                adjacent.append(adj_id)
    
    return adjacent

@dataclass
class SOAStep:
    actuator_id: int
    onset_time: float      # When to start (ms)
    duration: float        # How long to vibrate (ms)
    intensity: int         # Intensity (1-15, matching phantom range)

@dataclass
class PhantomActuator:
    phantom_id: int
    virtual_position: Tuple[float, float]  # (x, y) position in mm
    physical_actuator_1: int
    physical_actuator_2: int
    beta: float           # Location parameter (0 to 1)
    desired_intensity: int # Device range (1-15)
    required_intensity_1: int
    required_intensity_2: int
    actual_intensity: float

class TactileEngine:
    """Combined engine for SOA and Phantom functionality"""
    
    def __init__(self, api=None, actuator_spacing_mm=63):
        self.api = api
        self.actuator_spacing = actuator_spacing_mm
        self.use_custom_positions = True  # Start with custom positions
        self.custom_positions = {}
        
        # SOA state
        self.soa_steps = []
        self.soa_timer = QTimer()
        self.soa_timer.timeout.connect(self.execute_soa_step)
        self.soa_start_time = 0
        self.soa_next_step_idx = 0
        self.soa_active_actuators = {}
        
        # Phantom state
        self.phantoms = []
        
        # Load user's custom positions by default
        self.load_user_custom_positions()
        self.update_grid_positions()
    
    def load_user_custom_positions(self):
        """Load the user's specific custom positions: 5cm-6cm-5cm horizontal, 6cm vertical"""
        user_positions = {
            # Row 0 (y=0)
            3:  (0,   0),   # Top-left
            2:  (50,  0),   # 5cm right
            1:  (110, 0),   # 6cm right (center spacing)  
            0:  (160, 0),   # 5cm right
            
            # Row 1 (y=60) 
            4:  (0,   60),
            5:  (50,  60),
            6:  (110, 60),
            7:  (160, 60),
            
            # Row 2 (y=120)
            11: (0,   120),
            10: (50,  120), 
            9:  (110, 120),
            8:  (160, 120),
            
            # Row 3 (y=180)
            12: (0,   180),
            13: (50,  180),
            14: (110, 180), 
            15: (160, 180)
        }
        
        self.custom_positions = user_positions
        print(f"🎯 Loaded user's custom positions: 5cm-6cm-5cm horizontal, 6cm vertical")
    
    def set_custom_positions(self, positions_dict):
        """Set custom positions for actuators"""
        self.custom_positions = positions_dict.copy()
        self.use_custom_positions = True
        self.update_grid_positions()
        self.clear_phantoms()
        print(f"🔧 Custom positions set: {self.custom_positions}")
    
    def use_uniform_grid(self):
        """Switch back to uniform grid spacing"""
        self.use_custom_positions = False
        self.custom_positions = {}
        self.update_grid_positions()
        self.clear_phantoms()
        print(f"🔧 Switched to uniform grid spacing: {self.actuator_spacing}mm")
        
    def update_grid_positions(self):
        """Update actuator positions for 4x4 grid (uniform or custom)"""
        self.actuator_positions = {}
        
        if self.use_custom_positions and self.custom_positions:
            # Use custom positions
            for actuator_id in ACTUATORS:
                if actuator_id in self.custom_positions:
                    self.actuator_positions[actuator_id] = self.custom_positions[actuator_id]
                else:
                    # Fallback to calculated position if custom not specified
                    x, y = get_grid_position(actuator_id, self.actuator_spacing)
                    self.actuator_positions[actuator_id] = (x, y)
            print(f"🔧 4x4 Grid with CUSTOM positions:")
        else:
            # Use uniform spacing with user's layout
            for actuator_id in ACTUATORS:
                x, y = get_grid_position(actuator_id, self.actuator_spacing)
                self.actuator_positions[actuator_id] = (x, y)
            print(f"🔧 4x4 Grid with UNIFORM spacing (User's Layout):")
        
        print(f"📏 Spacing/Mode: {'Custom' if self.use_custom_positions else f'{self.actuator_spacing}mm'}")
        print(f"📍 Positions: {self.actuator_positions}")
    
    def update_spacing(self, new_spacing_mm):
        """Update spacing and recalculate positions"""
        self.actuator_spacing = new_spacing_mm
        self.update_grid_positions()
        self.clear_phantoms()
        print(f"🔄 Updated spacing to {new_spacing_mm}mm")
    
    # SOA Methods
    def calculate_paper_soa(self, duration_ms: float) -> float:
        """Calculate SOA using paper's equation: SOA = 0.32 × duration + 47.3"""
        return PAPER_PARAMS['SOA_SLOPE'] * duration_ms + PAPER_PARAMS['SOA_BASE']
    
    def validate_soa_parameters(self, duration_ms: float) -> tuple:
        """Validate SOA parameters according to paper's findings"""
        soa = self.calculate_paper_soa(duration_ms)
        warnings = []
        
        if duration_ms <= soa:
            warnings.append(f"Duration ({duration_ms}ms) <= SOA ({soa:.1f}ms) - No overlap!")
        
        if duration_ms < PAPER_PARAMS['MIN_DURATION']:
            warnings.append(f"Duration below paper's minimum ({PAPER_PARAMS['MIN_DURATION']}ms)")
        elif duration_ms > PAPER_PARAMS['MAX_DURATION']:
            warnings.append(f"Duration above paper's maximum ({PAPER_PARAMS['MAX_DURATION']}ms)")
        
        overlap_ms = duration_ms - soa
        if overlap_ms > 0:
            overlap_pct = (overlap_ms / duration_ms) * 100
            warnings.append(f"Overlap: {overlap_ms:.1f}ms ({overlap_pct:.0f}% of duration)")
        
        return (overlap_ms > 0, duration_ms, soa, warnings)
    
    def create_soa_sequence(self, actuator_sequence: List[int], duration_ms: float, 
                           intensity: int) -> tuple:
        """Create SOA sequence for given actuator path"""
        is_valid, adj_duration, soa, warnings = self.validate_soa_parameters(duration_ms)
        
        steps = []
        print(f"\n=== SOA Analysis (4x4 Grid - User Layout) ===")
        print(f"Actuator path: {actuator_sequence}")
        print(f"Duration: {adj_duration}ms")
        print(f"Calculated SOA: {soa:.1f}ms")
        print(f"Overlap: {adj_duration - soa:.1f}ms")
        print(f"Intensity: {intensity}/15")
        
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        for i, actuator_id in enumerate(actuator_sequence):
            onset_time = i * soa
            
            step = SOAStep(
                actuator_id=actuator_id,
                onset_time=onset_time,
                duration=adj_duration,
                intensity=intensity
            )
            steps.append(step)
            
            pos = self.actuator_positions.get(actuator_id, (0, 0))
            print(f"Step {i}: Act{actuator_id}@{pos} onset={onset_time:.1f}ms, duration={adj_duration}ms, intensity={intensity}/15")
        
        total_time = (len(actuator_sequence) - 1) * soa + adj_duration
        print(f"Total sequence: {total_time:.1f}ms")
        print("=" * 50)
        
        return steps, warnings
    
    def execute_soa_sequence(self, steps: List[SOAStep]):
        """Execute SOA sequence with precise timing"""
        if not self.api or not self.api.connected:
            print("No API connection")
            return
        
        self.soa_steps = steps
        self.soa_next_step_idx = 0
        self.soa_active_actuators = {}
        
        if not self.soa_steps:
            return
        
        print(f"\n🚀 Executing SOA sequence ({len(self.soa_steps)} steps)")
        self.soa_start_time = time.time() * 1000
        self.soa_timer.start(1)  # 1ms precision
    
    def execute_soa_step(self):
        """Execute SOA step with precise timing"""
        current_time = time.time() * 1000 - self.soa_start_time
        
        # Start new steps
        while (self.soa_next_step_idx < len(self.soa_steps) and 
               self.soa_steps[self.soa_next_step_idx].onset_time <= current_time):
            
            step = self.soa_steps[self.soa_next_step_idx]
            device_intensity = max(1, min(15, step.intensity))  # Already in 1-15 range
            freq = 4
            
            success = self.api.send_command(step.actuator_id, device_intensity, freq, 1)
            
            if success:
                stop_time = current_time + step.duration
                self.soa_active_actuators[step.actuator_id] = stop_time
                pos = self.actuator_positions.get(step.actuator_id, (0, 0))
                print(f"⚡ Act{step.actuator_id}@{pos} ON at {current_time:.1f}ms")
            
            self.soa_next_step_idx += 1
        
        # Stop actuators when duration expires
        to_stop = []
        for actuator_id, stop_time in self.soa_active_actuators.items():
            if current_time >= stop_time:
                self.api.send_command(actuator_id, 0, 0, 0)
                print(f"⏹️  Act{actuator_id} OFF at {current_time:.1f}ms")
                to_stop.append(actuator_id)
        
        for actuator_id in to_stop:
            del self.soa_active_actuators[actuator_id]
        
        if (self.soa_next_step_idx >= len(self.soa_steps) and 
            len(self.soa_active_actuators) == 0):
            self.soa_timer.stop()
            print("✅ SOA sequence complete\n")
    
    # Phantom Methods
    def calculate_distance(self, pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate Euclidean distance between two positions"""
        return math.sqrt((pos1[0] - pos2[0])**2 + (pos1[1] - pos2[1])**2)
    
    def find_closest_actuator_pair(self, phantom_pos: Tuple[float, float]) -> Tuple[Optional[int], Optional[int]]:
        """Find the two closest actuators for creating a phantom"""
        distances = []
        
        for actuator_id in ACTUATORS:
            pos = self.actuator_positions[actuator_id]
            dist = self.calculate_distance(phantom_pos, pos)
            distances.append((dist, actuator_id))
        
        distances.sort()
        
        if len(distances) >= 2:
            return distances[0][1], distances[1][1]
        return None, None
    
    def calculate_phantom_beta(self, phantom_pos: Tuple[float, float], 
                              pos1: Tuple[float, float], pos2: Tuple[float, float]) -> float:
        """Calculate beta parameter for phantom positioning"""
        total_distance = self.calculate_distance(pos1, pos2)
        if total_distance == 0:
            return 0.5
        
        distance_from_1 = self.calculate_distance(phantom_pos, pos1)
        beta = distance_from_1 / total_distance
        return max(0.0, min(1.0, beta))
    
    def calculate_phantom_intensities(self, desired_intensity: int, beta: float) -> Tuple[int, int]:
        """Calculate phantom intensities using energy summation model"""
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        desired_norm = desired_intensity / 15.0
        intensity_1_norm = math.sqrt(1 - beta) * desired_norm
        intensity_2_norm = math.sqrt(beta) * desired_norm
        
        device_intensity_1 = max(1, min(15, round(intensity_1_norm * 15)))
        device_intensity_2 = max(1, min(15, round(intensity_2_norm * 15)))
        
        return device_intensity_1, device_intensity_2
    
    def create_phantom_actuator(self, phantom_pos: Tuple[float, float], 
                               desired_intensity: int) -> Optional[PhantomActuator]:
        """Create phantom actuator at specified position"""
        print(f"\n🎯 Creating phantom at {phantom_pos} with intensity {desired_intensity}/15")
        
        if desired_intensity < 1 or desired_intensity > 15:
            print(f"❌ Invalid intensity {desired_intensity} - must be 1-15")
            return None
        
        # Find closest actuator pair
        act1, act2 = self.find_closest_actuator_pair(phantom_pos)
        if act1 is None or act2 is None:
            print("❌ Cannot find suitable actuators")
            return None
        
        if act1 == act2:
            print(f"❌ Position is exactly on actuator {act1}")
            return None
        
        pos1 = self.actuator_positions[act1]
        pos2 = self.actuator_positions[act2]
        
        # Calculate beta parameter
        beta = self.calculate_phantom_beta(phantom_pos, pos1, pos2)
        
        # Calculate required intensities
        try:
            int1, int2 = self.calculate_phantom_intensities(desired_intensity, beta)
        except ValueError as e:
            print(f"❌ {e}")
            return None
        
        # Validate using energy model
        norm_1 = int1 / 15.0
        norm_2 = int2 / 15.0
        theoretical_intensity = math.sqrt(norm_1**2 + norm_2**2)
        
        phantom_id = len(self.phantoms)
        
        phantom = PhantomActuator(
            phantom_id=phantom_id,
            virtual_position=phantom_pos,
            physical_actuator_1=act1,
            physical_actuator_2=act2,
            beta=beta,
            desired_intensity=desired_intensity,
            required_intensity_1=int1,
            required_intensity_2=int2,
            actual_intensity=theoretical_intensity
        )
        
        self.phantoms.append(phantom)
        
        print(f"✅ Phantom {phantom_id} created!")
        print(f"📍 Position: {phantom_pos}")
        print(f"🎛️  Between: Act{act1}@{pos1} ↔ Act{act2}@{pos2}")
        print(f"📐 Beta: {beta:.3f}")
        print(f"⚡ Commands: Act{act1}={int1}/15, Act{act2}={int2}/15")
        print("=" * 50)
        
        return phantom
    
    def activate_phantom(self, phantom_id: int) -> bool:
        """Activate phantom actuator"""
        if phantom_id >= len(self.phantoms):
            print(f"❌ Phantom {phantom_id} does not exist")
            return False
        
        phantom = self.phantoms[phantom_id]
        
        if not self.api or not self.api.connected:
            print("❌ No API connection")
            return False
        
        freq = 4
        success1 = self.api.send_command(phantom.physical_actuator_1, phantom.required_intensity_1, freq, 1)
        success2 = self.api.send_command(phantom.physical_actuator_2, phantom.required_intensity_2, freq, 1)
        
        if success1 and success2:
            print(f"🚀 Phantom {phantom_id} ACTIVATED at {phantom.virtual_position}")
            return True
        else:
            print(f"❌ Failed to activate phantom {phantom_id}")
            return False
    
    def deactivate_phantom(self, phantom_id: int) -> bool:
        """Stop phantom actuator"""
        if phantom_id >= len(self.phantoms):
            return False
        
        phantom = self.phantoms[phantom_id]
        
        if not self.api or not self.api.connected:
            return False
        
        success1 = self.api.send_command(phantom.physical_actuator_1, 0, 0, 0)
        success2 = self.api.send_command(phantom.physical_actuator_2, 0, 0, 0)
        
        if success1 and success2:
            print(f"⏹️  Phantom {phantom_id} stopped")
            return True
        return False
    
    def activate_all_phantoms(self):
        """Activate all phantoms"""
        print(f"🚀 Activating {len(self.phantoms)} phantoms...")
        for phantom in self.phantoms:
            self.activate_phantom(phantom.phantom_id)
    
    def deactivate_all_phantoms(self):
        """Stop all phantoms"""
        print(f"⏹️  Stopping {len(self.phantoms)} phantoms...")
        for phantom in self.phantoms:
            self.deactivate_phantom(phantom.phantom_id)
    
    def clear_phantoms(self):
        """Clear all phantoms"""
        self.deactivate_all_phantoms()
        self.phantoms = []
        print("🗑️  All phantoms cleared")
    
    def stop_all(self):
        """Emergency stop all activity"""
        self.soa_timer.stop()
        self.deactivate_all_phantoms()
        if self.api and self.api.connected:
            for actuator_id in ACTUATORS:
                self.api.send_command(actuator_id, 0, 0, 0)
        self.soa_active_actuators = {}
        print("🛑 All stopped")

class TactileVisualization(QWidget):
    """Visualization for 4x4 grid with SOA and phantom support"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(350, 350)  # Reduced size
        self.engine = None
        self.soa_steps = []
        self.soa_warnings = []
        
    def set_engine(self, engine: TactileEngine):
        self.engine = engine
        self.update()
    
    def set_soa_sequence(self, steps: List[SOAStep], warnings: List[str]):
        self.soa_steps = steps
        self.soa_warnings = warnings
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.engine:
            painter.drawText(20, 50, "No engine connected")
            return
        
        # Calculate bounds from actual actuator positions
        positions = list(self.engine.actuator_positions.values())
        if not positions:
            painter.drawText(20, 50, "No actuator positions available")
            return
        
        x_coords = [pos[0] for pos in positions]
        y_coords = [pos[1] for pos in positions]
        
        min_x, max_x = min(x_coords), max(x_coords)
        min_y, max_y = min(y_coords), max(y_coords)
        
        # Layout constants
        margin = 40  # Reduced margin
        available_width = self.width() - 2 * margin
        available_height = self.height() - 2 * margin - 80  # Space for title and legend
        
        # Calculate scale to fit all actuators
        data_width = max_x - min_x if max_x > min_x else 100
        data_height = max_y - min_y if max_y > min_y else 100
        
        scale_x = available_width / data_width if data_width > 0 else 1
        scale_y = available_height / data_height if data_height > 0 else 1
        scale = min(scale_x, scale_y) * 0.8  # 80% to leave some margin
        
        def pos_to_screen(pos):
            """Convert actuator position to screen coordinates"""
            screen_x = margin + (pos[0] - min_x) * scale
            screen_y = margin + 30 + (pos[1] - min_y) * scale
            return (screen_x, screen_y)
        
        # Title
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)  # Reduced font size
        painter.setFont(font)
        
        mode_text = "Custom Layout" if self.engine.use_custom_positions else f"Standard Grid ({self.engine.actuator_spacing}mm)"
        painter.drawText(margin, 25, f"4x4 Tactile - {mode_text}")
        
        # Draw reference grid lines only for uniform mode
        if not self.engine.use_custom_positions:
            painter.setPen(QPen(QColor(220, 220, 220), 1))
            # Draw light grid lines for reference
            for i in range(5):  # 5 lines for 4x4 grid
                # Vertical lines
                x = margin + i * (available_width / 4)
                painter.drawLine(int(x), margin + 30, int(x), margin + 30 + available_height)
                # Horizontal lines  
                y = margin + 30 + i * (available_height / 4)
                painter.drawLine(margin, int(y), margin + available_width, int(y))
        
        # Draw actuators
        for actuator_id in ACTUATORS:
            if actuator_id not in self.engine.actuator_positions:
                continue
                
            pos = self.engine.actuator_positions[actuator_id]
            screen_x, screen_y = pos_to_screen(pos)
            
            # Check if this actuator is part of SOA sequence
            in_soa = any(step.actuator_id == actuator_id for step in self.soa_steps)
            
            # Check if this actuator is part of phantom
            in_phantom = any(
                actuator_id in [p.physical_actuator_1, p.physical_actuator_2] 
                for p in self.engine.phantoms
            )
            
            # Color coding
            if in_soa and in_phantom:
                color = QColor(255, 0, 255)  # Magenta - both
            elif in_soa:
                color = QColor(0, 150, 255)  # Blue - SOA
            elif in_phantom:
                color = QColor(255, 150, 0)  # Orange - phantom
            else:
                color = QColor(100, 100, 100)  # Gray - inactive
            
            # Draw actuator
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.setBrush(QBrush(color))
            radius = max(10, int(scale * 0.05))  # Adaptive radius
            painter.drawEllipse(int(screen_x - radius), int(screen_y - radius), 
                              radius * 2, radius * 2)
            
            # Actuator ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(max(7, int(radius * 0.6)))
            font.setBold(True)
            painter.setFont(font)
            text_width = len(str(actuator_id)) * font.pointSize() * 0.4
            painter.drawText(int(screen_x - text_width), int(screen_y + font.pointSize() * 0.3), str(actuator_id))
            
            # Position label (small, below actuator)
            painter.setPen(QPen(QColor(0, 0, 0)))
            font.setPointSize(7)  # Smaller font
            font.setBold(False)
            painter.setFont(font)
            pos_text = f"({pos[0]:.0f},{pos[1]:.0f})"
            painter.drawText(int(screen_x - 20), int(screen_y + radius + 12), pos_text)
        
        # Draw SOA sequence path
        if len(self.soa_steps) > 1:
            painter.setPen(QPen(QColor(0, 100, 255), 3))
            for i in range(len(self.soa_steps) - 1):
                curr_id = self.soa_steps[i].actuator_id
                next_id = self.soa_steps[i + 1].actuator_id
                
                if (curr_id in self.engine.actuator_positions and 
                    next_id in self.engine.actuator_positions):
                    
                    curr_pos = self.engine.actuator_positions[curr_id]
                    next_pos = self.engine.actuator_positions[next_id]
                    
                    curr_screen = pos_to_screen(curr_pos)
                    next_screen = pos_to_screen(next_pos)
                    
                    painter.drawLine(int(curr_screen[0]), int(curr_screen[1]), 
                                   int(next_screen[0]), int(next_screen[1]))
        
        # Draw phantoms
        for phantom in self.engine.phantoms:
            phantom_screen = pos_to_screen(phantom.virtual_position)
            
            # Draw phantom
            painter.setPen(QPen(QColor(255, 0, 0), 3))
            painter.setBrush(QBrush(QColor(255, 100, 100, 150)))
            radius = max(8, int(scale * 0.04))
            painter.drawEllipse(int(phantom_screen[0] - radius), int(phantom_screen[1] - radius),
                              radius * 2, radius * 2)
            
            # Phantom ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(max(7, int(radius * 0.6)))
            painter.setFont(font)
            painter.drawText(int(phantom_screen[0] - 5), int(phantom_screen[1] + 3), f"P{phantom.phantom_id}")
            
            # Draw connection lines to physical actuators
            painter.setPen(QPen(QColor(255, 0, 0), 2, Qt.PenStyle.DashLine))
            
            for phys_id in [phantom.physical_actuator_1, phantom.physical_actuator_2]:
                if phys_id in self.engine.actuator_positions:
                    phys_pos = self.engine.actuator_positions[phys_id]
                    phys_screen = pos_to_screen(phys_pos)
                    painter.drawLine(int(phantom_screen[0]), int(phantom_screen[1]),
                                   int(phys_screen[0]), int(phys_screen[1]))
        
        # Legend (compact)
        legend_y = self.height() - 60
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(8)  # Smaller legend
        painter.setFont(font)
        
        painter.drawText(margin, legend_y, "🔵 SOA  🟠 Phantom  🟣 Both  ⚫ Inactive  👻 Virtual")
        painter.drawText(margin, legend_y + 15, f"SOA: {len(self.soa_steps)} steps | Phantoms: {len(self.engine.phantoms) if self.engine else 0}")
        
        # Layout info
        layout_info = f"Grid: {max_x-min_x:.0f}×{max_y-min_y:.0f}mm"
        painter.drawText(margin, legend_y + 30, layout_info)
        
        # Warnings (compact)
        if self.soa_warnings:
            painter.setPen(QPen(QColor(200, 0, 0)))
            painter.drawText(margin, legend_y + 45, f"⚠️ {self.soa_warnings[0][:40]}...")

class MergedTactileGUI(QWidget):
    """Combined GUI for SOA and Phantom functionality with 4x4 grid"""
    
    def __init__(self):
        super().__init__()
        self.engine = TactileEngine()
        self.api = None
        self.setup_ui()
        self.setup_api()
    
    def setup_api(self):
        if python_serial_api:
            self.api = python_serial_api()
            self.engine.api = self.api
            self.refresh_devices()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title (compact)
        title = QLabel("🎯 4x4 Tactile Display - SOA & Phantom")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2E86AB;")
        layout.addWidget(title)
        
        subtitle = QLabel("User's custom layout with apparent motion and phantom actuators")
        subtitle.setStyleSheet("font-style: italic; color: #666; font-size: 10px;")
        layout.addWidget(subtitle)
        
        # Connection (compact)
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
        
        # Tab widget for SOA, Phantom, and Position controls
        self.tab_widget = QTabWidget()
        
        # Position Configuration Tab
        position_tab = self.create_position_tab()
        self.tab_widget.addTab(position_tab, "Positions")
        
        # SOA Tab
        soa_tab = self.create_soa_tab()
        self.tab_widget.addTab(soa_tab, "SOA Motion")
        
        # Phantom Tab
        phantom_tab = self.create_phantom_tab()
        self.tab_widget.addTab(phantom_tab, "Phantoms")
        
        layout.addWidget(self.tab_widget)
        
        # Visualization (compact)
        viz_group = QGroupBox("Grid Visualization")
        viz_layout = QVBoxLayout(viz_group)
        
        self.viz = TactileVisualization()
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
        
        # Info display (compact)
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(50)
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("🎯 Ready! User's custom layout loaded (5cm-6cm-5cm horizontal, 6cm vertical).")
        layout.addWidget(self.info_text)
    
    def create_position_tab(self):
        """Create actuator position configuration tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Position mode selection
        mode_group = QGroupBox("Position Mode")
        mode_layout = QVBoxLayout(mode_group)
        
        self.uniform_radio = QCheckBox("Uniform Grid (Standard Layout)")
        self.custom_radio = QCheckBox("Custom Positions (User's Layout)")
        self.custom_radio.setChecked(True)  # Start with custom positions
        
        self.uniform_radio.toggled.connect(self.on_position_mode_changed)
        self.custom_radio.toggled.connect(self.on_position_mode_changed)
        
        mode_layout.addWidget(self.uniform_radio)
        mode_layout.addWidget(self.custom_radio)
        layout.addWidget(mode_group)
        
        # User layout diagram
        layout_group = QGroupBox("Your Layout Reference")
        layout_info_layout = QVBoxLayout(layout_group)
        
        layout_info = QLabel()
        layout_info.setText("""User's Custom 4x4 Layout:
Row 0:  3(0,0) ←5cm→ 2(50,0) ←6cm→ 1(110,0) ←5cm→ 0(160,0)
         ↓6cm         ↓6cm          ↓6cm          ↓6cm
Row 1:  4(0,60) ←5cm→ 5(50,60) ←6cm→ 6(110,60) ←5cm→ 7(160,60)  
         ↓6cm         ↓6cm          ↓6cm          ↓6cm
Row 2: 11(0,120) ←5cm→ 10(50,120) ←6cm→ 9(110,120) ←5cm→ 8(160,120)
         ↓6cm         ↓6cm          ↓6cm          ↓6cm  
Row 3: 12(0,180) ←5cm→ 13(50,180) ←6cm→ 14(110,180) ←5cm→ 15(160,180)

Horizontal spacing: 5cm - 6cm - 5cm  |  Vertical spacing: 6cm uniform
        """)
        layout_info.setStyleSheet("QLabel { font-family: monospace; font-size: 9px; color: #444; background-color: #f5f5f5; padding: 8px; }")
        layout_info_layout.addWidget(layout_info)
        layout.addWidget(layout_group)
        
        # Uniform spacing control
        uniform_group = QGroupBox("Uniform Grid Settings")
        uniform_layout = QFormLayout(uniform_group)
        
        self.spacing_spin_tab = QSpinBox()
        self.spacing_spin_tab.setRange(30, 200)
        self.spacing_spin_tab.setValue(63)
        self.spacing_spin_tab.setSuffix(" mm")
        self.spacing_spin_tab.valueChanged.connect(self.update_spacing)
        uniform_layout.addRow("Spacing:", self.spacing_spin_tab)
        
        layout.addWidget(uniform_group)
        
        # Current positions display (compact)
        current_group = QGroupBox("Current Positions")
        current_layout = QVBoxLayout(current_group)
        
        self.current_positions_text = QTextEdit()
        self.current_positions_text.setMaximumHeight(80)
        self.current_positions_text.setReadOnly(True)
        current_layout.addWidget(self.current_positions_text)
        
        layout.addWidget(current_group)
        
        # Initialize display
        self.update_position_mode_ui()
        self.update_current_positions_display()
        
        return tab

    def create_soa_tab(self):
        """Create SOA control tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # SOA Parameters (compact)
        soa_group = QGroupBox("SOA Parameters")
        soa_layout = QFormLayout(soa_group)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(40, 1000)
        self.duration_spin.setValue(80)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.valueChanged.connect(self.update_soa_analysis)
        soa_layout.addRow("Duration:", self.duration_spin)
        
        self.soa_label = QLabel()
        soa_layout.addRow("SOA:", self.soa_label)
        
        self.overlap_label = QLabel()
        soa_layout.addRow("Overlap:", self.overlap_label)
        
        # Changed from QDoubleSpinBox to QSpinBox with 1-15 range
        self.soa_intensity_spin = QSpinBox()
        self.soa_intensity_spin.setRange(1, 15)
        self.soa_intensity_spin.setValue(8)
        soa_layout.addRow("Intensity (1-15):", self.soa_intensity_spin)
        
        layout.addWidget(soa_group)
        
        # SOA Test Patterns (User's layout specific)
        patterns_group = QGroupBox("SOA Patterns (User's Layout)")
        patterns_layout = QVBoxLayout(patterns_group)
        
        # Row 1 - Row patterns
        row1_layout = QHBoxLayout()
        self.soa_row0_btn = QPushButton("Row 0\n(3→2→1→0)")
        self.soa_row1_btn = QPushButton("Row 1\n(4→5→6→7)")
        self.soa_row2_btn = QPushButton("Row 2\n(11→10→9→8)")
        self.soa_row3_btn = QPushButton("Row 3\n(12→13→14→15)")
        
        self.soa_row0_btn.clicked.connect(lambda: self.test_soa_sequence([3, 2, 1, 0]))
        self.soa_row1_btn.clicked.connect(lambda: self.test_soa_sequence([4, 5, 6, 7]))
        self.soa_row2_btn.clicked.connect(lambda: self.test_soa_sequence([11, 10, 9, 8]))
        self.soa_row3_btn.clicked.connect(lambda: self.test_soa_sequence([12, 13, 14, 15]))
        
        row1_layout.addWidget(self.soa_row0_btn)
        row1_layout.addWidget(self.soa_row1_btn)
        row1_layout.addWidget(self.soa_row2_btn)
        row1_layout.addWidget(self.soa_row3_btn)
        
        # Row 2 - Column and diagonal patterns
        row2_layout = QHBoxLayout()
        self.soa_col0_btn = QPushButton("Col 0\n(3→4→11→12)")  
        self.soa_col1_btn = QPushButton("Col 1\n(2→5→10→13)")
        self.soa_col2_btn = QPushButton("Col 2\n(1→6→9→14)")
        self.soa_diagonal_btn = QPushButton("Diagonal\n(3→5→9→15)")
        
        self.soa_col0_btn.clicked.connect(lambda: self.test_soa_sequence([3, 4, 11, 12]))
        self.soa_col1_btn.clicked.connect(lambda: self.test_soa_sequence([2, 5, 10, 13]))
        self.soa_col2_btn.clicked.connect(lambda: self.test_soa_sequence([1, 6, 9, 14]))
        self.soa_diagonal_btn.clicked.connect(lambda: self.test_soa_sequence([3, 5, 9, 15]))
        
        row2_layout.addWidget(self.soa_col0_btn)
        row2_layout.addWidget(self.soa_col1_btn)
        row2_layout.addWidget(self.soa_col2_btn)
        row2_layout.addWidget(self.soa_diagonal_btn)
        
        # Row 3 - Complex patterns
        row3_layout = QHBoxLayout()
        self.soa_perimeter_btn = QPushButton("Perimeter\n(0→1→2→3→4→11→12→13→14→15→8→7→0)")
        self.soa_all_actuators_btn = QPushButton("All Actuators\n(0→1→2→...→15)")
        
        perimeter_sequence = [0, 1, 2, 3, 4, 11, 12, 13, 14, 15, 8, 7, 0]
        all_actuators_sequence = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]
        
        self.soa_perimeter_btn.clicked.connect(lambda: self.test_soa_sequence(perimeter_sequence))
        self.soa_all_actuators_btn.clicked.connect(lambda: self.test_soa_sequence(all_actuators_sequence))
        
        row3_layout.addWidget(self.soa_perimeter_btn)
        row3_layout.addWidget(self.soa_all_actuators_btn)
        
        # Row 4 - Preview
        row4_layout = QHBoxLayout()
        self.soa_preview_btn = QPushButton("Preview Only\n(no execution)")
        self.soa_preview_btn.clicked.connect(lambda: self.preview_soa_sequence(all_actuators_sequence))
        
        row4_layout.addWidget(self.soa_preview_btn)
        row4_layout.addStretch()  # Add stretch to center the preview button
        
        # Style buttons (high contrast, visible colors)
        button_style = """
        QPushButton {
            padding: 8px;
            font-size: 10px;
            font-weight: bold;
            border-radius: 4px;
            background-color: #4CAF50;
            color: white;
            border: 2px solid #2E7D32;
        }
        QPushButton:hover {
            background-color: #66BB6A;
            border: 2px solid #1B5E20;
        }
        QPushButton:pressed {
            background-color: #2E7D32;
        }
        """
        for btn in [self.soa_row0_btn, self.soa_row1_btn, self.soa_row2_btn, self.soa_row3_btn,
                   self.soa_col0_btn, self.soa_col1_btn, self.soa_col2_btn, self.soa_diagonal_btn,
                   self.soa_perimeter_btn, self.soa_all_actuators_btn, self.soa_preview_btn]:
            btn.setStyleSheet(button_style)
        
        patterns_layout.addLayout(row1_layout)
        patterns_layout.addLayout(row2_layout)
        patterns_layout.addLayout(row3_layout)
        patterns_layout.addLayout(row4_layout)
        layout.addWidget(patterns_group)
        
        self.update_soa_analysis()
        return tab
    
    def create_phantom_tab(self):
        """Create phantom control tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Phantom creation (compact)
        create_group = QGroupBox("Create Phantom")
        create_layout = QFormLayout(create_group)
        
        # Position controls
        self.phantom_x_spin = QSpinBox()
        self.phantom_x_spin.setRange(0, 180)  # 0 to 160mm + margin
        self.phantom_x_spin.setValue(80)      # Center
        self.phantom_x_spin.setSuffix(" mm")
        create_layout.addRow("X:", self.phantom_x_spin)
        
        self.phantom_y_spin = QSpinBox()
        self.phantom_y_spin.setRange(0, 200)  # 0 to 180mm + margin
        self.phantom_y_spin.setValue(90)      # Center
        self.phantom_y_spin.setSuffix(" mm")
        create_layout.addRow("Y:", self.phantom_y_spin)
        
        self.phantom_intensity_spin = QSpinBox()
        self.phantom_intensity_spin.setRange(1, 15)
        self.phantom_intensity_spin.setValue(8)
        create_layout.addRow("Intensity:", self.phantom_intensity_spin)
        
        self.create_phantom_btn = QPushButton("🎯 Create")
        self.create_phantom_btn.clicked.connect(self.create_phantom)
        self.create_phantom_btn.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                padding: 8px;
                font-weight: bold;
                border-radius: 4px;
            }
        """)
        create_layout.addRow("", self.create_phantom_btn)
        
        layout.addWidget(create_group)
        
        # Phantom controls (compact)
        phantom_control_layout = QHBoxLayout()
        
        self.activate_phantoms_btn = QPushButton("🚀 Activate All")
        self.deactivate_phantoms_btn = QPushButton("⏹️ Stop All")
        self.clear_phantoms_btn = QPushButton("🗑️ Clear All")
        
        self.activate_phantoms_btn.clicked.connect(self.activate_all_phantoms)
        self.deactivate_phantoms_btn.clicked.connect(self.deactivate_all_phantoms)
        self.clear_phantoms_btn.clicked.connect(self.clear_all_phantoms)
        
        phantom_control_layout.addWidget(self.activate_phantoms_btn)
        phantom_control_layout.addWidget(self.deactivate_phantoms_btn)
        phantom_control_layout.addWidget(self.clear_phantoms_btn)
        layout.addLayout(phantom_control_layout)
        
        # Initialize phantom position ranges
        self.update_phantom_position_ranges()
        
        return tab
    
    def on_position_mode_changed(self):
        """Handle position mode radio button changes"""
        # Ensure only one is checked at a time
        if self.uniform_radio.isChecked():
            self.custom_radio.setChecked(False)
        elif self.custom_radio.isChecked():
            self.uniform_radio.setChecked(False)
        
        self.update_position_mode_ui()
    
    def update_position_mode_ui(self):
        """Update UI based on selected position mode"""
        uniform_mode = self.uniform_radio.isChecked()
        
        # Enable/disable appropriate sections
        self.spacing_spin_tab.setEnabled(uniform_mode)
    
    def update_current_positions_display(self):
        """Update the current positions display"""
        if hasattr(self, 'current_positions_text'):
            positions_text = "Current Actuator Positions:\n"
            mode = "Custom" if self.engine.use_custom_positions else f"User Layout ({self.engine.actuator_spacing}mm)"
            positions_text += f"Mode: {mode}\n\n"
            
            # Show positions organized by user's layout
            for row in range(GRID_ROWS):
                for col in range(GRID_COLS):
                    actuator_id = USER_LAYOUT[row][col]
                    pos = self.engine.actuator_positions.get(actuator_id, (0, 0))
                    positions_text += f"Act{actuator_id:2d}: ({pos[0]:3.0f},{pos[1]:3.0f})  "
                positions_text += "\n"
            
            self.current_positions_text.setPlainText(positions_text)
    
    def update_phantom_position_ranges(self):
        """Update phantom position input ranges based on current actuator positions"""
        if hasattr(self, 'phantom_x_spin') and hasattr(self, 'phantom_y_spin'):
            # Calculate bounds from current actuator positions
            x_positions = [pos[0] for pos in self.engine.actuator_positions.values()]
            y_positions = [pos[1] for pos in self.engine.actuator_positions.values()]
            
            min_x, max_x = min(x_positions), max(x_positions)
            min_y, max_y = min(y_positions), max(y_positions)
            
            # Add some margin
            margin = 20
            self.phantom_x_spin.setRange(int(min_x - margin), int(max_x + margin))
            self.phantom_y_spin.setRange(int(min_y - margin), int(max_y + margin))
            
            # Set to center
            self.phantom_x_spin.setValue(int((min_x + max_x) / 2))
            self.phantom_y_spin.setValue(int((min_y + max_y) / 2))

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
    
    def update_spacing(self):
        # Get spacing from the tab control
        new_spacing = self.spacing_spin_tab.value() if hasattr(self, 'spacing_spin_tab') else 63
        self.engine.update_spacing(new_spacing)
        
        self.viz.update()
        self.update_current_positions_display()
        self.update_phantom_position_ranges()
        self.info_text.setPlainText(f"🔄 Updated spacing to {new_spacing}mm.")
    
    def update_soa_analysis(self):
        duration = self.duration_spin.value()
        soa = self.engine.calculate_paper_soa(duration)
        overlap = duration - soa
        
        self.soa_label.setText(f"{soa:.1f} ms")
        
        if overlap > 0:
            self.overlap_label.setText(f"{overlap:.1f} ms ✓")
            self.overlap_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.overlap_label.setText(f"{overlap:.1f} ms ✗")
            self.overlap_label.setStyleSheet("color: red; font-weight: bold;")
    
    def preview_soa_sequence(self, actuator_ids):
        duration = self.duration_spin.value()
        intensity = self.soa_intensity_spin.value()  # Now 1-15 range
        
        steps, warnings = self.engine.create_soa_sequence(actuator_ids, duration, intensity)
        self.viz.set_soa_sequence(steps, warnings)
        self.info_text.setPlainText(f"📊 Preview: {len(steps)} steps")
    
    def test_soa_sequence(self, actuator_ids):
        duration = self.duration_spin.value()
        intensity = self.soa_intensity_spin.value()  # Now 1-15 range
        
        steps, warnings = self.engine.create_soa_sequence(actuator_ids, duration, intensity)
        self.viz.set_soa_sequence(steps, warnings)
        self.engine.execute_soa_sequence(steps)
        self.info_text.setPlainText(f"🚀 Executing: {actuator_ids}")
    
    def create_phantom(self):
        x = self.phantom_x_spin.value()
        y = self.phantom_y_spin.value()
        intensity = self.phantom_intensity_spin.value()
        
        phantom = self.engine.create_phantom_actuator((x, y), intensity)
        
        if phantom:
            self.viz.update()
            self.update_current_positions_display()
            self.info_text.setPlainText(f"✅ Phantom {phantom.phantom_id} created at ({x}, {y})")
        else:
            self.info_text.setPlainText("❌ Failed to create phantom")
    
    def activate_all_phantoms(self):
        self.engine.activate_all_phantoms()
        self.info_text.setPlainText(f"🚀 Activated {len(self.engine.phantoms)} phantoms")
    
    def deactivate_all_phantoms(self):
        self.engine.deactivate_all_phantoms()
        self.info_text.setPlainText("⏹️ All phantoms stopped")
    
    def clear_all_phantoms(self):
        self.engine.clear_phantoms()
        self.viz.update()
        self.info_text.setPlainText("🗑️ All phantoms cleared")
    
    def stop_all(self):
        self.engine.stop_all()
        self.info_text.setPlainText("🛑 EMERGENCY STOP")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🎯 4x4 Tactile Display - User Layout")
    
    widget = MergedTactileGUI()
    window.setCentralWidget(widget)
    window.resize(600, 600)  # Reduced window size
    window.show()
    
    sys.exit(app.exec())