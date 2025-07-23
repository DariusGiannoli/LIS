#!/usr/bin/env python3
"""
merged_tactile_3x3.py

Combined SOA and Phantom Actuator implementation for 3x3 tactile grid.
Following Tactile Brush paper methodology with both apparent motion and phantom illusions.

3x3 Grid Layout:
0  1  2
3  4  5
6  7  8
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

# 3x3 Grid Configuration
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8]
GRID_ROWS = 3
GRID_COLS = 3

# Paper's psychophysical parameters (from Tactile Brush paper)
PAPER_PARAMS = {
    'SOA_SLOPE': 0.32,      # From paper's equation: SOA = 0.32d + 47.3
    'SOA_BASE': 47.3,
    'MIN_DURATION': 40,     # ms
    'MAX_DURATION': 160,    # ms
    'OPTIMAL_FREQ': 200,    # Hz
}

def get_grid_position(actuator_id: int, spacing_mm: float) -> Tuple[float, float]:
    """Convert actuator ID to (x, y) position in mm for 3x3 grid"""
    if actuator_id < 0 or actuator_id >= 9:
        raise ValueError(f"Invalid actuator ID {actuator_id} for 3x3 grid")
    
    row = actuator_id // GRID_COLS
    col = actuator_id % GRID_COLS
    
    x = col * spacing_mm
    y = row * spacing_mm
    
    return (x, y)

def get_actuator_id(row: int, col: int) -> int:
    """Convert grid (row, col) to actuator ID"""
    if row < 0 or row >= GRID_ROWS or col < 0 or col >= GRID_COLS:
        return -1
    return row * GRID_COLS + col

def get_adjacent_actuators(actuator_id: int) -> List[int]:
    """Get list of adjacent actuators (horizontal, vertical, diagonal)"""
    row = actuator_id // GRID_COLS
    col = actuator_id % GRID_COLS
    
    adjacent = []
    for dr in [-1, 0, 1]:
        for dc in [-1, 0, 1]:
            if dr == 0 and dc == 0:
                continue
            new_row, new_col = row + dr, col + dc
            adj_id = get_actuator_id(new_row, new_col)
            if adj_id != -1:
                adjacent.append(adj_id)
    
    return adjacent

@dataclass
class SOAStep:
    actuator_id: int
    onset_time: float      # When to start (ms)
    duration: float        # How long to vibrate (ms)
    intensity: float       # Intensity (0.0-1.0)

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
        
        # SOA state
        self.soa_steps = []
        self.soa_timer = QTimer()
        self.soa_timer.timeout.connect(self.execute_soa_step)
        self.soa_start_time = 0
        self.soa_next_step_idx = 0
        self.soa_active_actuators = {}
        
        # Phantom state
        self.phantoms = []
        
        self.update_grid_positions()
        
    def update_grid_positions(self):
        """Update actuator positions for 3x3 grid"""
        self.actuator_positions = {}
        for actuator_id in ACTUATORS:
            x, y = get_grid_position(actuator_id, self.actuator_spacing)
            self.actuator_positions[actuator_id] = (x, y)
        
        print(f"🔧 3x3 Grid initialized:")
        print(f"📏 Spacing: {self.actuator_spacing}mm")
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
                           intensity: float) -> tuple:
        """Create SOA sequence for given actuator path"""
        is_valid, adj_duration, soa, warnings = self.validate_soa_parameters(duration_ms)
        
        steps = []
        print(f"\n=== SOA Analysis (3x3 Grid) ===")
        print(f"Actuator path: {actuator_sequence}")
        print(f"Duration: {adj_duration}ms")
        print(f"Calculated SOA: {soa:.1f}ms")
        print(f"Overlap: {adj_duration - soa:.1f}ms")
        
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
            print(f"Step {i}: Act{actuator_id}@{pos} onset={onset_time:.1f}ms, duration={adj_duration}ms")
        
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
            device_intensity = max(1, min(15, int(step.intensity * 15)))
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
    """Visualization for 3x3 grid with SOA and phantom support"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 600)  # Square for 3x3 grid
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
        
        # Layout constants
        margin = 60
        size = min(self.width(), self.height()) - 2 * margin
        grid_size = size / 3  # For 3x3 grid
        
        # Title
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        painter.drawText(margin, 30, f"3x3 Tactile Grid - Spacing: {self.engine.actuator_spacing}mm")
        
        # Draw grid lines
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        for i in range(4):  # 4 lines for 3x3 grid
            # Vertical lines
            x = margin + i * grid_size
            painter.drawLine(int(x), margin + 40, int(x), margin + 40 + size)
            # Horizontal lines
            y = margin + 40 + i * grid_size
            painter.drawLine(margin, int(y), margin + size, int(y))
        
        # Draw actuators
        for actuator_id in ACTUATORS:
            row = actuator_id // GRID_COLS
            col = actuator_id % GRID_COLS
            
            center_x = margin + col * grid_size + grid_size / 2
            center_y = margin + 40 + row * grid_size + grid_size / 2
            
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
            radius = 20
            painter.drawEllipse(int(center_x - radius), int(center_y - radius), 
                              radius * 2, radius * 2)
            
            # Actuator ID
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(12)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(center_x - 8), int(center_y + 5), str(actuator_id))
        
        # Draw SOA sequence path
        if len(self.soa_steps) > 1:
            painter.setPen(QPen(QColor(0, 100, 255), 4))
            for i in range(len(self.soa_steps) - 1):
                curr_id = self.soa_steps[i].actuator_id
                next_id = self.soa_steps[i + 1].actuator_id
                
                curr_row, curr_col = curr_id // GRID_COLS, curr_id % GRID_COLS
                next_row, next_col = next_id // GRID_COLS, next_id % GRID_COLS
                
                curr_x = margin + curr_col * grid_size + grid_size / 2
                curr_y = margin + 40 + curr_row * grid_size + grid_size / 2
                next_x = margin + next_col * grid_size + grid_size / 2
                next_y = margin + 40 + next_row * grid_size + grid_size / 2
                
                painter.drawLine(int(curr_x), int(curr_y), int(next_x), int(next_y))
        
        # Draw phantoms
        for phantom in self.engine.phantoms:
            # Convert phantom position to screen coordinates
            pos = phantom.virtual_position
            # For simplicity, assume phantom is within grid bounds
            # You might want to add proper coordinate transformation here
            phantom_x = margin + pos[0] / self.engine.actuator_spacing * grid_size + grid_size / 2
            phantom_y = margin + 40 + pos[1] / self.engine.actuator_spacing * grid_size + grid_size / 2
            
            if (phantom_x >= margin and phantom_x <= margin + size and
                phantom_y >= margin + 40 and phantom_y <= margin + 40 + size):
                
                # Draw phantom
                painter.setPen(QPen(QColor(255, 0, 0), 3))
                painter.setBrush(QBrush(QColor(255, 100, 100, 150)))
                radius = 15
                painter.drawEllipse(int(phantom_x - radius), int(phantom_y - radius),
                                  radius * 2, radius * 2)
                
                # Phantom ID
                painter.setPen(QPen(QColor(255, 255, 255)))
                font.setPointSize(10)
                painter.setFont(font)
                painter.drawText(int(phantom_x - 5), int(phantom_y + 3), f"P{phantom.phantom_id}")
        
        # Legend
        legend_y = self.height() - 80
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(10)
        painter.setFont(font)
        
        painter.drawText(margin, legend_y, "🔵 SOA Sequence  🟠 Phantom Support  🟣 Both  ⚫ Inactive")
        painter.drawText(margin, legend_y + 20, f"Active SOA steps: {len(self.soa_steps)} | Active phantoms: {len(self.engine.phantoms) if self.engine else 0}")
        
        # Warnings
        if self.soa_warnings:
            painter.setPen(QPen(QColor(200, 0, 0)))
            painter.drawText(margin, legend_y + 40, f"⚠️ {'; '.join(self.soa_warnings[:2])}")

class MergedTactileGUI(QWidget):
    """Combined GUI for SOA and Phantom functionality with 3x3 grid"""
    
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
        
        # Title
        title = QLabel("🎯 Merged Tactile Display - 3x3 Grid with SOA & Phantom")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2E86AB;")
        layout.addWidget(title)
        
        subtitle = QLabel("Combined apparent motion (SOA) and phantom actuator control")
        subtitle.setStyleSheet("font-style: italic; color: #666;")
        layout.addWidget(subtitle)
        
        # Connection
        conn_group = QGroupBox("Hardware Connection")
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
        
        # Hardware config
        hw_group = QGroupBox("3x3 Grid Configuration")
        hw_layout = QFormLayout(hw_group)
        
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(30, 200)
        self.spacing_spin.setValue(63)  # Paper's spacing
        self.spacing_spin.setSuffix(" mm")
        self.spacing_spin.valueChanged.connect(self.update_spacing)
        hw_layout.addRow("Actuator Spacing:", self.spacing_spin)
        
        layout.addWidget(hw_group)
        
        # Tab widget for SOA and Phantom controls
        self.tab_widget = QTabWidget()
        
        # SOA Tab
        soa_tab = self.create_soa_tab()
        self.tab_widget.addTab(soa_tab, "SOA (Apparent Motion)")
        
        # Phantom Tab
        phantom_tab = self.create_phantom_tab()
        self.tab_widget.addTab(phantom_tab, "Phantom Actuators")
        
        layout.addWidget(self.tab_widget)
        
        # Visualization
        viz_group = QGroupBox("3x3 Grid Visualization")
        viz_layout = QVBoxLayout(viz_group)
        
        self.viz = TactileVisualization()
        self.viz.set_engine(self.engine)
        viz_layout.addWidget(self.viz)
        layout.addWidget(viz_group)
        
        # Global controls
        control_layout = QHBoxLayout()
        
        self.stop_all_btn = QPushButton("🛑 EMERGENCY STOP")
        self.stop_all_btn.clicked.connect(self.stop_all)
        self.stop_all_btn.setStyleSheet("QPushButton { background-color: #FF4444; color: white; font-weight: bold; padding: 10px; font-size: 14px; }")
        
        control_layout.addStretch()
        control_layout.addWidget(self.stop_all_btn)
        layout.addLayout(control_layout)
        
        # Info display
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(80)
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("🎯 Ready! Use tabs above to control SOA sequences or create phantom actuators.")
        layout.addWidget(self.info_text)
    
    def create_soa_tab(self):
        """Create SOA control tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # SOA Parameters
        soa_group = QGroupBox("SOA Parameters (Paper's Methodology)")
        soa_layout = QFormLayout(soa_group)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(40, 1000)
        self.duration_spin.setValue(80)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.valueChanged.connect(self.update_soa_analysis)
        soa_layout.addRow("Duration:", self.duration_spin)
        
        self.soa_label = QLabel()
        soa_layout.addRow("Calculated SOA:", self.soa_label)
        
        self.overlap_label = QLabel()
        soa_layout.addRow("Overlap:", self.overlap_label)
        
        self.soa_intensity_spin = QDoubleSpinBox()
        self.soa_intensity_spin.setRange(0.2, 1.0)
        self.soa_intensity_spin.setValue(0.8)
        self.soa_intensity_spin.setDecimals(2)
        soa_layout.addRow("Intensity:", self.soa_intensity_spin)
        
        layout.addWidget(soa_group)
        
        # SOA Test Patterns
        patterns_group = QGroupBox("3x3 Grid SOA Patterns")
        patterns_layout = QVBoxLayout(patterns_group)
        
        # Row 1
        row1_layout = QHBoxLayout()
        self.soa_horizontal_btn = QPushButton("Horizontal\n(0→1→2)")
        self.soa_vertical_btn = QPushButton("Vertical\n(0→3→6)")
        self.soa_diagonal_btn = QPushButton("Diagonal\n(0→4→8)")
        
        self.soa_horizontal_btn.clicked.connect(lambda: self.test_soa_sequence([0, 1, 2]))
        self.soa_vertical_btn.clicked.connect(lambda: self.test_soa_sequence([0, 3, 6]))
        self.soa_diagonal_btn.clicked.connect(lambda: self.test_soa_sequence([0, 4, 8]))
        
        row1_layout.addWidget(self.soa_horizontal_btn)
        row1_layout.addWidget(self.soa_vertical_btn)
        row1_layout.addWidget(self.soa_diagonal_btn)
        
        # Row 2
        row2_layout = QHBoxLayout()
        self.soa_clockwise_btn = QPushButton("Clockwise\n(0→1→2→5→8→7→6→3)")
        self.soa_spiral_btn = QPushButton("Spiral In\n(0→1→2→5→8→7→6→3→4)")
        self.soa_preview_btn = QPushButton("Preview Only\n(no execution)")
        
        self.soa_clockwise_btn.clicked.connect(lambda: self.test_soa_sequence([0, 1, 2, 5, 8, 7, 6, 3]))
        self.soa_spiral_btn.clicked.connect(lambda: self.test_soa_sequence([0, 1, 2, 5, 8, 7, 6, 3, 4]))
        self.soa_preview_btn.clicked.connect(lambda: self.preview_soa_sequence([0, 1, 2, 5, 8, 7, 6, 3, 4]))
        
        row2_layout.addWidget(self.soa_clockwise_btn)
        row2_layout.addWidget(self.soa_spiral_btn)
        row2_layout.addWidget(self.soa_preview_btn)
        
        # Style buttons
        button_style = """
        QPushButton {
            padding: 8px;
            font-size: 10px;
            border-radius: 4px;
            background-color: #E8F4FD;
            border: 2px solid #2E86AB;
        }
        QPushButton:hover {
            background-color: #2E86AB;
            color: white;
        }
        """
        for btn in [self.soa_horizontal_btn, self.soa_vertical_btn, self.soa_diagonal_btn,
                   self.soa_clockwise_btn, self.soa_spiral_btn, self.soa_preview_btn]:
            btn.setStyleSheet(button_style)
        
        patterns_layout.addLayout(row1_layout)
        patterns_layout.addLayout(row2_layout)
        layout.addWidget(patterns_group)
        
        self.update_soa_analysis()
        return tab
    
    def create_phantom_tab(self):
        """Create phantom control tab"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Phantom creation
        create_group = QGroupBox("Create Phantom Actuator")
        create_layout = QFormLayout(create_group)
        
        # Position controls
        self.phantom_x_spin = QSpinBox()
        self.phantom_x_spin.setRange(0, 126)  # 0 to 2*63mm
        self.phantom_x_spin.setValue(63)      # Center
        self.phantom_x_spin.setSuffix(" mm")
        create_layout.addRow("X Position:", self.phantom_x_spin)
        
        self.phantom_y_spin = QSpinBox()
        self.phantom_y_spin.setRange(0, 126)  # 0 to 2*63mm
        self.phantom_y_spin.setValue(63)      # Center
        self.phantom_y_spin.setSuffix(" mm")
        create_layout.addRow("Y Position:", self.phantom_y_spin)
        
        self.phantom_intensity_spin = QSpinBox()
        self.phantom_intensity_spin.setRange(1, 15)
        self.phantom_intensity_spin.setValue(8)
        create_layout.addRow("Intensity (1-15):", self.phantom_intensity_spin)
        
        self.create_phantom_btn = QPushButton("🎯 Create Phantom")
        self.create_phantom_btn.clicked.connect(self.create_phantom)
        self.create_phantom_btn.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                padding: 10px;
                font-weight: bold;
                border-radius: 5px;
            }
        """)
        create_layout.addRow("", self.create_phantom_btn)
        
        layout.addWidget(create_group)
        
        # Phantom controls
        phantom_control_layout = QHBoxLayout()
        
        self.activate_phantoms_btn = QPushButton("🚀 Activate All Phantoms")
        self.deactivate_phantoms_btn = QPushButton("⏹️ Stop All Phantoms")
        self.clear_phantoms_btn = QPushButton("🗑️ Clear All Phantoms")
        
        self.activate_phantoms_btn.clicked.connect(self.activate_all_phantoms)
        self.deactivate_phantoms_btn.clicked.connect(self.deactivate_all_phantoms)
        self.clear_phantoms_btn.clicked.connect(self.clear_all_phantoms)
        
        phantom_control_layout.addWidget(self.activate_phantoms_btn)
        phantom_control_layout.addWidget(self.deactivate_phantoms_btn)
        phantom_control_layout.addWidget(self.clear_phantoms_btn)
        layout.addLayout(phantom_control_layout)
        
        return tab
    
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
        new_spacing = self.spacing_spin.value()
        self.engine.update_spacing(new_spacing)
        self.viz.update()
        self.info_text.setPlainText(f"🔄 Updated spacing to {new_spacing}mm. Grid recalculated.")
    
    def update_soa_analysis(self):
        duration = self.duration_spin.value()
        soa = self.engine.calculate_paper_soa(duration)
        overlap = duration - soa
        
        self.soa_label.setText(f"{soa:.1f} ms")
        
        if overlap > 0:
            self.overlap_label.setText(f"{overlap:.1f} ms ✓ (continuous motion)")
            self.overlap_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.overlap_label.setText(f"{overlap:.1f} ms ✗ (discrete)")
            self.overlap_label.setStyleSheet("color: red; font-weight: bold;")
    
    def preview_soa_sequence(self, actuator_ids):
        duration = self.duration_spin.value()
        intensity = self.soa_intensity_spin.value()
        
        steps, warnings = self.engine.create_soa_sequence(actuator_ids, duration, intensity)
        self.viz.set_soa_sequence(steps, warnings)
        self.info_text.setPlainText(f"📊 Preview: {len(steps)} steps, {len(warnings)} warnings")
    
    def test_soa_sequence(self, actuator_ids):
        duration = self.duration_spin.value()
        intensity = self.soa_intensity_spin.value()
        
        steps, warnings = self.engine.create_soa_sequence(actuator_ids, duration, intensity)
        self.viz.set_soa_sequence(steps, warnings)
        self.engine.execute_soa_sequence(steps)
        self.info_text.setPlainText(f"🚀 Executing SOA sequence: {actuator_ids}")
    
    def create_phantom(self):
        x = self.phantom_x_spin.value()
        y = self.phantom_y_spin.value()
        intensity = self.phantom_intensity_spin.value()
        
        phantom = self.engine.create_phantom_actuator((x, y), intensity)
        
        if phantom:
            self.viz.update()
            self.info_text.setPlainText(f"✅ Phantom {phantom.phantom_id} created at ({x}, {y})mm")
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
        self.info_text.setPlainText("🛑 EMERGENCY STOP - All activity halted")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🎯 Merged Tactile Display - 3x3 Grid with SOA & Phantom")
    
    widget = MergedTactileGUI()
    window.setCentralWidget(widget)
    window.resize(1000, 1000)
    window.show()
    
    sys.exit(app.exec())