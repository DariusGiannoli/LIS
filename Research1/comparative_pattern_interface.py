import sys
import time
import math
import json
import os
from dataclasses import dataclass, asdict
from typing import List, Tuple, Optional, Dict

from PyQt6.QtWidgets import QApplication, QMainWindow, QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QPointF
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QMouseEvent
from PyQt6 import uic
import numpy as np
from scipy import signal

# Import 3-actuator only phantom system
from phantom_actuator_system import (
    Enhanced3ActuatorPhantom,
    PhantomActuatorSystem, 
    TrajectoryPhantomManager,
    point_in_triangle
)

# Import your API (optional)
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found. Running in simulation mode.")
    python_serial_api = None

# Configuration
WAVEFORM_TYPES = ["Sine", "Square", "Saw", "Triangle", "Chirp", "FM", "PWM", "Noise"]
PATTERN_TYPES = ["Buzz", "Pulse", "Motion"]
ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

# Boss Layout (following cable order from original)
BOSS_LAYOUT = {
    # Row 0 (2 actuators, centered)
    0: (1, 0), 1: (2, 0),
    # Row 1 (4 actuators, cable order: 5,4,3,2)
    5: (0, 1), 4: (1, 1), 3: (2, 1), 2: (3, 1),
    # Row 2 (4 actuators, order: 6,7,8,9)
    6: (0, 2), 7: (1, 2), 8: (2, 2), 9: (3, 2),
    # Row 3 (4 actuators, cable order: 13,12,11,10)
    13: (0, 3), 12: (1, 3), 11: (2, 3), 10: (3, 3),
    # Row 4 (2 actuators, centered)
    14: (1, 4), 15: (2, 4)
}

def get_boss_layout_position(actuator_id: int, spacing_mm: float = 50) -> Tuple[float, float]:
    """Get position for boss's custom layout"""
    if actuator_id not in BOSS_LAYOUT:
        raise ValueError(f"Actuator ID {actuator_id} not found in boss layout")
    
    grid_x, grid_y = BOSS_LAYOUT[actuator_id]
    x = grid_x * spacing_mm
    y = grid_y * spacing_mm
    return (x, y)

@dataclass
class PatternStep:
    actuator_id: int
    timestamp: float
    duration: float
    intensity: int
    waveform_type: str = "Sine"
    pattern_type: str = "Buzz"

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

class SharedVisualization(QWidget):
    """Shared visualization showing real-time actuator activity with 3-actuator phantoms"""
    
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
        self.drawing_trajectory = False
        
    def set_engine(self, engine):
        self.engine = engine
        self.update()
    
    def mousePressEvent(self, event: QMouseEvent):
        if not self.engine:
            return
        
        mouse_pos = event.position()
        
        if self.engine.drawing_mode and event.button() == Qt.MouseButton.LeftButton:
            self.drawing_trajectory = True
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.engine.current_trajectory = [physical_pos]
                self.trajectory_point_added.emit(physical_pos[0], physical_pos[1])
        elif event.button() == Qt.MouseButton.LeftButton:
            clicked_actuator = self.get_actuator_at_position(mouse_pos)
            if clicked_actuator is not None:
                self.actuator_clicked.emit(clicked_actuator)
        elif event.button() == Qt.MouseButton.RightButton and self.engine.phantoms_enabled:
            physical_pos = self.screen_to_physical(mouse_pos)
            if physical_pos:
                self.phantom_requested.emit(physical_pos[0], physical_pos[1])
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.engine:
            return
        
        if self.drawing_trajectory and self.engine.drawing_mode:
            physical_pos = self.screen_to_physical(event.position())
            if physical_pos:
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
            if distance <= 20:
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
        
        # Title with 3-actuator info
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
        
        # Add phantom info (always 3-actuator)
        if self.engine.phantoms_enabled:
            phantom_count = len(self.engine.enhanced_phantoms)
            phantom_info = f" [P:{phantom_count}×3-act only]"
            mode_text += phantom_info
        
        painter.drawText(margin, 25, f"Boss Layout - 3-Actuator Phantoms Only (Park et al.){mode_text}")
        
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
                    
                    # Start/end markers
                    if trajectory_screen_points:
                        painter.setPen(QPen(QColor(0, 200, 0), 2))
                        painter.setBrush(QBrush(QColor(0, 255, 0, 100)))
                        start_point = trajectory_screen_points[0]
                        painter.drawEllipse(int(start_point[0] - 6), int(start_point[1] - 6), 12, 12)
                        
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
            
            painter.setPen(QPen(QColor(0, 150, 255), 4))
            for i in range(len(trajectory_screen_points) - 1):
                painter.drawLine(
                    int(trajectory_screen_points[i][0]), int(trajectory_screen_points[i][1]),
                    int(trajectory_screen_points[i+1][0]), int(trajectory_screen_points[i+1][1])
                )
            
            # Start/end markers for current trajectory
            if trajectory_screen_points:
                painter.setPen(QPen(QColor(0, 200, 0), 2))
                painter.setBrush(QBrush(QColor(0, 255, 0, 150)))
                start_point = trajectory_screen_points[0]
                painter.drawEllipse(int(start_point[0] - 8), int(start_point[1] - 8), 16, 16)
                
                painter.setPen(QPen(QColor(200, 0, 0), 2))
                painter.setBrush(QBrush(QColor(255, 0, 0, 150)))
                end_point = trajectory_screen_points[-1]
                painter.drawEllipse(int(end_point[0] - 8), int(end_point[1] - 8), 16, 16)
                
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
            is_in_phantom = any(actuator_id in self.engine.phantom_system.get_phantom_actuators_safe(p) 
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
        
        # Draw 3-actuator phantoms only
        for phantom in self.engine.enhanced_phantoms:
            phantom_screen = pos_to_screen(phantom.virtual_position)
            self.phantom_screen_positions[phantom.phantom_id] = phantom_screen
            
            # All phantoms are 3-actuator (purple with "3")
            phantom_color = QColor(255, 100, 255)  # Purple for 3-actuator
            phantom_symbol = "3"
            
            # Adjust color based on trajectory if available
            if hasattr(phantom, 'trajectory_id') and phantom.trajectory_id is not None:
                for traj_data in getattr(self.engine, 'trajectory_collection', []):
                    if traj_data['id'] == phantom.trajectory_id:
                        traj_color = traj_data['color']
                        phantom_color = QColor(traj_color[0], traj_color[1], traj_color[2], 200)
                        break
            
            # Draw phantom
            painter.setPen(QPen(QColor(0, 0, 0), 3))
            painter.setBrush(QBrush(phantom_color))
            radius = 15
            painter.drawEllipse(int(phantom_screen[0] - radius), int(phantom_screen[1] - radius),
                            radius * 2, radius * 2)
            
            # Phantom type indicator (always "3")
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(10)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(phantom_screen[0] - 4), int(phantom_screen[1] + 4), phantom_symbol)
            
            # Draw connection lines to physical actuators (3 lines)
            if len(self.engine.enhanced_phantoms) <= 5:
                line_colors = [QColor(255, 0, 255), QColor(200, 0, 200), QColor(150, 0, 150)]
                
                phantom_actuators = self.engine.phantom_system.get_phantom_actuators_safe(phantom)
                for i, phys_id in enumerate(phantom_actuators):
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
        
        painter.drawText(margin, legend_y, "🔴 Active  🔵 Selected  🟣 In Phantom  ⚫ Inactive")
        painter.drawText(margin, legend_y + 15, "Phantoms: 🟣3-act only (Park et al.) | Left: Select | Right: Phantom")
        
        # Show phantom spacing info
        if hasattr(self.engine, 'phantom_spacing_ms'):
            painter.drawText(margin + 400, legend_y, f"Phantom spacing: {self.engine.phantom_spacing_ms}ms")

class ComparativeEngine:
    """Engine for comparative pattern testing with 3-actuator only phantom system"""
    
    def __init__(self, api=None):
        self.api = api
        
        # Global parameters shared across all tabs
        self.waveform_type = "Sine"
        self.frequency = 250.0
        self.intensity = 8
        self.duration = 60
        
        # Actuator layout
        self.actuator_positions = {}
        self.init_default_layout()
        
        # Initialize 3-actuator only phantom system
        self.phantom_system = PhantomActuatorSystem(self.actuator_positions)
        self.trajectory_manager = TrajectoryPhantomManager(self.phantom_system)
        
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
        
        # Selection state
        self.selected_actuators = set()
    
    # Legacy property accessors for compatibility
    @property
    def enhanced_phantoms(self):
        return self.phantom_system.enhanced_phantoms
    
    @property 
    def phantoms_enabled(self):
        return self.phantom_system.phantoms_enabled
    
    @property
    def phantom_spacing_ms(self):
        return self.trajectory_manager.phantom_spacing_ms
    
    @property
    def trajectory_collection(self):
        return self.trajectory_manager.trajectory_collection
    
    @property
    def current_trajectory(self):
        return self.trajectory_manager.current_trajectory
    
    @current_trajectory.setter
    def current_trajectory(self, value):
        self.trajectory_manager.current_trajectory = value
    
    @property
    def current_trajectory_id(self):
        return self.trajectory_manager.current_trajectory_id 
    
    def init_default_layout(self):
        """Initialize boss's custom layout"""
        self.actuator_positions = {}
        for actuator_id in ACTUATORS:
            x, y = get_boss_layout_position(actuator_id, 50)
            self.actuator_positions[actuator_id] = (x, y)
        print(f"🎯 Boss layout initialized for 3-actuator phantoms: Cable order 0,1|5,4,3,2|6,7,8,9|13,12,11,10|14,15")
        
        # Update phantom system with new positions
        if hasattr(self, 'phantom_system'):
            self.phantom_system.update_actuator_positions(self.actuator_positions)
    
    def set_phantom_spacing(self, spacing_ms: int):
        """Set spacing between phantoms in trajectory"""
        self.trajectory_manager.set_phantom_spacing(spacing_ms)
    
    def add_new_trajectory(self):
        """Start a new trajectory"""
        self.trajectory_manager.add_new_trajectory()
    
    def get_trajectory_color(self, trajectory_id: int) -> Tuple[int, int, int]:
        """Get unique color for each trajectory"""
        return self.trajectory_manager.get_trajectory_color(trajectory_id)
    
    def clear_all_trajectories(self):
        """Clear all trajectories and phantoms"""
        self.trajectory_manager.clear_all_trajectories()
    
    def create_phantom(self, phantom_pos: Tuple[float, float], 
                      desired_intensity: int) -> Optional[Enhanced3ActuatorPhantom]:
        """Create 3-actuator phantom at specified position following Park et al."""
        return self.phantom_system.create_phantom(phantom_pos, desired_intensity)
    
    def clear_phantoms(self):
        """Clear all phantoms"""
        self.phantom_system.clear_phantoms()
    
    def toggle_phantoms(self, enabled: bool):
        """Toggle phantom system on/off"""
        self.phantom_system.toggle_phantoms(enabled)
        if not enabled:
            self.stop_all_actuators()
    
    def add_trajectory_point(self, point: Tuple[float, float]):
        """Add point to trajectory"""
        if self.drawing_mode:
            self.trajectory_manager.add_trajectory_point(point)
    
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
        print("🎨 Drawing mode enabled (3-actuator phantoms)")
    
    def stop_drawing_mode(self):
        """Stop trajectory drawing mode"""
        self.drawing_mode = False
        print("🎨 Drawing mode disabled")
    
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
            # Create motion from trajectory with 3-actuator phantoms
            steps = self.create_trajectory_motion()
        elif self.selected_actuators:
            # Create motion sequence from selected actuators
            steps = self.create_sequential_motion()
        
        print(f"🌊 Created motion pattern with {len(steps)} steps")
        return steps
    
    def create_trajectory_motion(self) -> List[PatternStep]:
        """Create motion pattern from drawn trajectory using 3-actuator phantoms"""
        steps = []
        
        if not self.phantoms_enabled:
            return steps
        
        # Sample trajectory points
        trajectory_length = self.calculate_trajectory_length()
        num_samples = max(3, min(10, int(trajectory_length / 30)))
        
        for i in range(num_samples):
            t = i / (num_samples - 1)
            point = self.interpolate_trajectory(t)
            timestamp = i * 100
            
            # Create 3-actuator phantom at this position
            phantom = self.create_phantom(point, self.intensity)
            if phantom:
                # Add steps for all 3 physical actuators
                actuators = self.phantom_system.get_phantom_actuators_safe(phantom)
                intensities = self.phantom_system.get_phantom_intensities_safe(phantom)
                
                for phys_id, intensity in zip(actuators, intensities):
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
        return self.trajectory_manager.calculate_trajectory_length_points(self.current_trajectory)
    
    def interpolate_trajectory(self, t: float) -> Tuple[float, float]:
        """Interpolate point along trajectory (t from 0 to 1)"""
        return self.trajectory_manager.interpolate_trajectory_points(self.current_trajectory, t)
    
    def create_all_trajectory_phantoms(self):
        """Create 3-actuator phantoms for all trajectories"""
        return self.trajectory_manager.create_all_trajectory_phantoms(self.intensity)
    
    def execute_all_trajectories(self):
        """Execute all trajectories simultaneously using 3-actuator phantoms"""
        if not self.trajectory_collection and not self.current_trajectory:
            return []
        
        # First create all phantoms
        self.create_all_trajectory_phantoms()
        
        # Collect all phantom steps
        all_steps = []
        
        # Process saved trajectories
        for trajectory_data in self.trajectory_collection:
            phantoms = trajectory_data.get('phantoms', [])
            
            for phantom in phantoms:
                # Add steps for all 3 physical actuators
                actuators = self.phantom_system.get_phantom_actuators_safe(phantom)
                intensities = self.phantom_system.get_phantom_intensities_safe(phantom)
                
                for phys_id, intensity in zip(actuators, intensities):
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
            current_phantoms = self.trajectory_manager.create_trajectory_phantoms_with_spacing(
                self.current_trajectory, self.phantom_spacing_ms, self.current_trajectory_id, self.intensity
            )
            
            for phantom in current_phantoms:
                actuators = self.phantom_system.get_phantom_actuators_safe(phantom)
                intensities = self.phantom_system.get_phantom_intensities_safe(phantom)
                
                for phys_id, intensity in zip(actuators, intensities):
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
    
    def execute_pattern(self, steps: List[PatternStep]):
        """Execute pattern with real-time visualization"""
        if not steps:
            return
        
        self.current_pattern_steps = sorted(steps, key=lambda s: s.timestamp)
        self.execution_step_idx = 0
        self.execution_start_time = time.time() * 1000
        self.active_actuators = {}
        
        print(f"🚀 Executing pattern with {len(steps)} steps")
        self.execution_timer.start(1)
    
    def execute_step(self):
        """Execute pattern step with precise timing"""
        current_time = time.time() * 1000 - self.execution_start_time
        
        # Start new steps
        while (self.execution_step_idx < len(self.current_pattern_steps) and 
               self.current_pattern_steps[self.execution_step_idx].timestamp <= current_time):
            
            step = self.current_pattern_steps[self.execution_step_idx]
            
            if self.api and hasattr(self.api, 'connected') and self.api.connected:
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
                if self.api and hasattr(self.api, 'connected') and self.api.connected:
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
        
        if self.api and hasattr(self.api, 'connected') and self.api.connected:
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

class ComparativePatternGUI(QMainWindow):
    """Main GUI for comparative pattern testing with 3-actuator only phantoms"""
    
    def __init__(self):
        super().__init__()
        
        # Load the UI file
        self.ui = uic.loadUi('comparative_pattern_interface.ui', self)
        
        # Initialize engine with 3-actuator only system
        self.engine = ComparativeEngine()
        self.api = None
        
        # Replace visualization widget with custom one
        self.setup_visualization()
        
        # Setup API and connections
        self.setup_api()
        self.setup_connections()
        
        # Initialize displays
        self.update_displays()
        
        # Pattern library management
        self.current_pattern_steps = []
        self.current_pattern_type = ""
        self.load_patterns_from_disk()
        
        # Update timer for UI refreshes
        self.update_timer = QTimer()
        self.update_timer.timeout.connect(self.update_displays)
        self.update_timer.start(100)
    
    def setup_visualization(self):
        """Replace the placeholder widget with custom visualization"""
        # Remove the placeholder widget
        self.ui.right_layout.removeWidget(self.ui.visualization_widget)
        self.ui.visualization_widget.deleteLater()
        
        # Create and add custom visualization
        self.viz = SharedVisualization()
        self.viz.set_engine(self.engine)
        self.viz.setMinimumHeight(500)
        self.viz.setMinimumWidth(580)
        
        # Insert at the beginning of the right layout
        self.ui.right_layout.insertWidget(0, self.viz)
    
    def setup_api(self):
        """Setup serial API connection"""
        if python_serial_api:
            self.api = python_serial_api()
            self.engine.api = self.api
            self.refresh_devices()
    
    def setup_connections(self):
        """Connect all UI signals to handlers"""
        # Connection controls
        self.ui.refresh_btn.clicked.connect(self.refresh_devices)
        self.ui.connect_btn.clicked.connect(self.toggle_connection)
        
        # Global parameters
        self.ui.waveform_combo.currentTextChanged.connect(self.on_global_parameters_changed)
        self.ui.frequency_spin.valueChanged.connect(self.on_global_parameters_changed)
        self.ui.intensity_spin.valueChanged.connect(self.on_global_parameters_changed)
        self.ui.duration_spin.valueChanged.connect(self.on_global_parameters_changed)
        self.ui.phantom_checkbox.toggled.connect(self.engine.toggle_phantoms)
        
        # Pattern library
        self.ui.pattern_list.itemDoubleClicked.connect(self.replay_selected_pattern)
        self.ui.pattern_list.currentItemChanged.connect(self.on_pattern_selection_changed)
        self.ui.save_current_btn.clicked.connect(self.save_current_pattern)
        self.ui.replay_btn.clicked.connect(self.replay_selected_pattern)
        self.ui.load_btn.clicked.connect(self.load_pattern_file)
        self.ui.delete_btn.clicked.connect(self.delete_selected_pattern)
        
        # Tab controls (same as before but now 3-actuator only)
        self.ui.buzz_clear_selection_btn.clicked.connect(lambda: self.clear_selection())
        self.ui.buzz_select_all_btn.clicked.connect(lambda: self.select_all())
        self.ui.create_buzz_btn.clicked.connect(lambda: self.create_pattern("Buzz"))
        self.ui.buzz_clear_phantoms_btn.clicked.connect(lambda: self.clear_phantoms())
        
        # Buzz presets
        self.ui.buzz_preset_top.clicked.connect(lambda: self.select_preset([0, 1]))
        self.ui.buzz_preset_row2.clicked.connect(lambda: self.select_preset([5, 4, 3, 2]))
        self.ui.buzz_preset_row3.clicked.connect(lambda: self.select_preset([6, 7, 8, 9]))
        self.ui.buzz_preset_row4.clicked.connect(lambda: self.select_preset([13, 12, 11, 10]))
        self.ui.buzz_preset_bottom.clicked.connect(lambda: self.select_preset([14, 15]))
        self.ui.buzz_preset_center.clicked.connect(lambda: self.select_preset([1, 4, 7, 12, 15]))
        self.ui.buzz_preset_outer.clicked.connect(lambda: self.select_preset([0, 1, 2, 9, 10, 15, 14, 13, 6, 5]))
        
        # Pulse tab
        self.ui.pulse_clear_selection_btn.clicked.connect(lambda: self.clear_selection())
        self.ui.create_pulse_btn.clicked.connect(lambda: self.create_pattern("Pulse"))
        self.ui.pulse_clear_phantoms_btn.clicked.connect(lambda: self.clear_phantoms())
        
        # Pulse presets
        self.ui.pulse_preset_cable_wave.clicked.connect(lambda: self.select_preset([0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]))
        self.ui.pulse_preset_center_flow.clicked.connect(lambda: self.select_preset([1, 4, 7, 12, 15]))
        self.ui.pulse_preset_side_waves.clicked.connect(lambda: self.select_preset([5, 6, 13, 14]))
        self.ui.pulse_preset_zigzag.clicked.connect(lambda: self.select_preset([0, 2, 6, 10, 14]))
        self.ui.pulse_preset_cross.clicked.connect(lambda: self.select_preset([0, 4, 8, 12, 15]))
        
        # Motion tab
        self.ui.phantom_spacing_spin.valueChanged.connect(self.update_phantom_spacing)
        self.ui.start_drawing_btn.clicked.connect(self.toggle_drawing_mode)
        self.ui.new_trajectory_btn.clicked.connect(self.start_new_trajectory)
        self.ui.play_all_btn.clicked.connect(self.play_all_trajectories)
        self.ui.clear_all_btn.clicked.connect(self.clear_all_trajectories)
        self.ui.clear_current_btn.clicked.connect(self.clear_current_trajectory)
        self.ui.play_current_btn.clicked.connect(self.play_current_trajectory)
        self.ui.motion_clear_selection_btn.clicked.connect(lambda: self.clear_selection())
        self.ui.create_sequence_btn.clicked.connect(lambda: self.create_pattern("Motion"))
        self.ui.motion_clear_phantoms_btn.clicked.connect(lambda: self.clear_phantoms())
        
        # Visualization
        self.viz.actuator_clicked.connect(self.on_actuator_clicked)
        self.viz.phantom_requested.connect(self.on_phantom_requested)
        self.viz.trajectory_point_added.connect(self.on_trajectory_point_added)
        
        # Emergency stop
        self.ui.stop_btn.clicked.connect(self.emergency_stop)
    
    def refresh_devices(self):
        """Refresh serial device list"""
        if not self.api:
            return
        self.ui.device_combo.clear()
        if hasattr(self.api, 'get_serial_devices'):
            devices = self.api.get_serial_devices()
            if devices:
                self.ui.device_combo.addItems(devices)
    
    def toggle_connection(self):
        """Toggle serial connection"""
        if not self.api:
            return
        
        if not hasattr(self.api, 'connected') or not self.api.connected:
            if self.ui.device_combo.currentText():
                if hasattr(self.api, 'connect_serial_device') and self.api.connect_serial_device(self.ui.device_combo.currentText()):
                    self.ui.status_label.setText("Connected ✓")
                    self.ui.status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.ui.connect_btn.setText("Disconnect")
                    self.ui.info_text.setPlainText("✅ Device connected - ready for 3-actuator phantom testing!")
        else:
            if hasattr(self.api, 'disconnect_serial_device') and self.api.disconnect_serial_device():
                self.ui.status_label.setText("Disconnected")
                self.ui.status_label.setStyleSheet("color: red; font-weight: bold;")
                self.ui.connect_btn.setText("Connect")
                self.ui.info_text.setPlainText("❌ Device disconnected")
    
    def on_global_parameters_changed(self):
        """Handle global parameter changes"""
        self.engine.set_global_parameters(
            self.ui.waveform_combo.currentText(),
            float(self.ui.frequency_spin.value()),
            self.ui.intensity_spin.value(),
            self.ui.duration_spin.value()
        )
        self.ui.info_text.setPlainText(
            f"🎛️ Global parameters updated:\n"
            f"Waveform: {self.ui.waveform_combo.currentText()}, "
            f"Frequency: {self.ui.frequency_spin.value()}Hz, "
            f"Intensity: {self.ui.intensity_spin.value()}, "
            f"Duration: {self.ui.duration_spin.value()}ms"
        )
    
    def on_actuator_clicked(self, actuator_id: int):
        """Handle actuator click for selection"""
        self.engine.toggle_actuator_selection(actuator_id)
        self.update_displays()
        self.viz.update()
        
        selected_count = len(self.engine.selected_actuators)
        self.ui.info_text.setPlainText(
            f"🖱️ Actuator {actuator_id} {'selected' if actuator_id in self.engine.selected_actuators else 'deselected'}\n"
            f"Total selected: {selected_count} actuators"
        )
    
    def on_phantom_requested(self, x: float, y: float):
        """Handle 3-actuator phantom creation request"""
        if not self.engine.phantoms_enabled:
            self.ui.info_text.setPlainText("❌ Phantoms are disabled - enable in Global Parameters")
            return
        
        phantom = self.engine.create_phantom((x, y), self.engine.intensity)
        if phantom:
            self.viz.update()
            self.update_displays()
            
            phantom_info = self.engine.phantom_system.get_phantom_display_info(phantom)
            
            self.ui.info_text.setPlainText(
                f"✅ 3-Actuator phantom created at ({x:.0f}, {y:.0f}) - Park et al. method\n"
                f"Using 3 actuators: {phantom_info['actuators_str']}\n"
                f"Intensities: {phantom_info['intensities_str']}\n"
                f"Triangle area: {phantom.triangle_area:.1f}\n"
                f"Energy efficiency: {phantom.energy_efficiency:.1%}"
            )
        else:
            stats = self.engine.phantom_system.get_phantom_statistics()
            self.ui.info_text.setPlainText(
                f"❌ Cannot create phantom at ({x:.0f}, {y:.0f})\n"
                f"Following Park et al.: phantoms can ONLY exist inside triangular areas\n"
                f"• Available triangular areas: {stats['triangles_available']}\n"
                f"• Position must be inside triangle formed by 3 actuators\n"
                f"Try positioning inside actuator triangular boundaries"
            )
    
    def on_trajectory_point_added(self, x: float, y: float):
        """Handle trajectory point addition"""
        self.viz.update()
        self.update_displays()
    
    def clear_selection(self):
        """Clear actuator selection"""
        self.engine.clear_selection()
        self.update_displays()
        self.viz.update()
    
    def select_all(self):
        """Select all actuators"""
        self.engine.selected_actuators = set(ACTUATORS)
        self.update_displays()
        self.viz.update()
    
    def select_preset(self, actuators: List[int]):
        """Select preset actuators"""
        self.engine.selected_actuators = set(actuators)
        self.update_displays()
        self.viz.update()
    
    def clear_phantoms(self):
        """Clear all phantoms"""
        self.engine.clear_phantoms()
        self.update_displays()
        self.viz.update()
    
    def update_phantom_spacing(self):
        """Update phantom spacing in engine"""
        spacing = self.ui.phantom_spacing_spin.value()
        self.engine.set_phantom_spacing(spacing)
    
    def toggle_drawing_mode(self):
        """Toggle trajectory drawing mode"""
        if not self.engine.drawing_mode:
            self.engine.start_drawing_mode()
            self.ui.start_drawing_btn.setText("⏹️ Stop")
            self.ui.start_drawing_btn.setStyleSheet("background-color: #FF5722; color: white; padding: 5px; font-weight: bold; border-radius: 3px;")
        else:
            self.engine.stop_drawing_mode()
            self.ui.start_drawing_btn.setText("🎨 Draw")
            self.ui.start_drawing_btn.setStyleSheet("background-color: #2196F3; border: 1px solid #1976D2;")
        
        self.update_displays()
    
    def start_new_trajectory(self):
        """Start a new trajectory"""
        self.engine.add_new_trajectory()
        self.update_displays()
        self.viz.update()
    
    def play_all_trajectories(self):
        """Play all trajectories simultaneously using 3-actuator phantoms"""
        steps = self.engine.execute_all_trajectories()
        if steps:
            self.execute_pattern("Motion", steps)
        else:
            self.ui.info_text.setPlainText("No trajectories to play")
    
    def play_current_trajectory(self):
        """Play only the current trajectory"""
        if len(self.engine.current_trajectory) < 2:
            return
        
        steps = self.engine.create_motion_pattern()
        if steps:
            self.execute_pattern("Motion", steps)
    
    def clear_all_trajectories(self):
        """Clear all trajectories"""
        self.engine.clear_all_trajectories()
        self.update_displays()
        self.viz.update()
    
    def clear_current_trajectory(self):
        """Clear only the current trajectory"""
        self.engine.current_trajectory = []
        self.update_displays()
        self.viz.update()
    
    def create_pattern(self, pattern_type: str):
        """Create pattern based on type"""
        if pattern_type == "Buzz":
            steps = self.engine.create_buzz_pattern()
        elif pattern_type == "Pulse":
            pulse_interval = self.ui.pulse_interval_spin.value()
            steps = self.engine.create_pulse_pattern(pulse_interval)
        elif pattern_type == "Motion":
            steps = self.engine.create_motion_pattern()
        else:
            return
        
        if steps:
            self.execute_pattern(pattern_type, steps)
    
    def execute_pattern(self, pattern_type: str, steps: List[PatternStep]):
        """Execute pattern and show info with 3-actuator phantom details"""
        self.engine.execute_pattern(steps)
        self.store_current_pattern(pattern_type, steps)
        
        self.viz.update()
        
        # Show pattern info with 3-actuator phantom details
        phantom_info = ""
        if pattern_type == "Motion" and self.engine.phantoms_enabled:
            phantom_count = len(self.engine.enhanced_phantoms)
            phantom_info = f" using {phantom_count} 3-actuator phantoms (Park et al.)"
        elif pattern_type == "Motion" and not self.engine.phantoms_enabled:
            phantom_info = " (phantoms disabled - using discrete actuators)"
        
        self.ui.info_text.setPlainText(
            f"▶️ Executing {pattern_type} pattern{phantom_info}\n"
            f"Steps: {len(steps)}, Waveform: {self.engine.waveform_type} @ {self.engine.frequency}Hz\n"
            f"💡 Using 3-actuator phantom method following Park et al. research"
        )
    
    def store_current_pattern(self, pattern_type: str, steps: List[PatternStep]):
        """Store the current pattern for potential saving"""
        self.current_pattern_steps = steps.copy()
        self.current_pattern_type = pattern_type
        
        self.ui.save_current_btn.setEnabled(len(steps) > 0)
        
        if steps:
            actuator_count = len(set(step.actuator_id for step in steps))
            total_duration = max(step.timestamp + step.duration for step in steps) if steps else 0
            self.ui.save_current_btn.setText(f"💾 Save ({actuator_count}a, {total_duration:.0f}ms)")
        else:
            self.ui.save_current_btn.setText("💾 Save")
    
    def save_current_pattern(self):
        """Save the current pattern to library"""
        if not self.current_pattern_steps:
            return
        
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
        
        total_duration = max(step.timestamp + step.duration for step in self.current_pattern_steps)
        pattern = SharedPattern(
            name=name,
            steps=self.current_pattern_steps,
            pattern_type=self.current_pattern_type,
            total_duration=total_duration,
            created_timestamp=time.time(),
            description=f"{self.current_pattern_type} pattern with {len(set(step.actuator_id for step in self.current_pattern_steps))} actuators (3-act phantoms)"
        )
        
        self.engine.shared_patterns[name] = pattern
        filename = f"patterns/{name.replace(' ', '_')}.json"
        
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
                    self.engine.shared_patterns[pattern.name] = pattern
                except Exception as e:
                    print(f"❌ Failed to load pattern from {filepath}: {e}")
        
        self.refresh_pattern_list()
    
    def refresh_pattern_list(self):
        """Refresh the pattern list display"""
        self.ui.pattern_list.clear()
        
        by_type = {"Buzz": [], "Pulse": [], "Motion": []}
        
        for pattern in self.engine.shared_patterns.values():
            if pattern.pattern_type in by_type:
                by_type[pattern.pattern_type].append(pattern)
        
        for pattern_type, patterns in by_type.items():
            if patterns:
                header_item = self.ui.pattern_list.addItem(f"═══ {pattern_type} ═══")
                header_item = self.ui.pattern_list.item(self.ui.pattern_list.count() - 1)
                header_item.setData(Qt.ItemDataRole.UserRole, None)
                
                for pattern in sorted(patterns, key=lambda p: p.created_timestamp, reverse=True):
                    actuator_count = len(set(step.actuator_id for step in pattern.steps))
                    item_text = f"  {pattern.name} ({actuator_count}a, {pattern.total_duration:.0f}ms)"
                    
                    item = self.ui.pattern_list.addItem(item_text)
                    item = self.ui.pattern_list.item(self.ui.pattern_list.count() - 1)
                    item.setData(Qt.ItemDataRole.UserRole, pattern)
    
    def on_pattern_selection_changed(self, current, previous):
        """Handle pattern selection change"""
        if not current:
            self.ui.pattern_info.setText("No pattern selected")
            return
        
        pattern = current.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            self.ui.pattern_info.setText("Pattern type header")
            return
        
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
        
        self.ui.pattern_info.setText(info_text)
    
    def replay_selected_pattern(self):
        """Replay the selected pattern"""
        current_item = self.ui.pattern_list.currentItem()
        if not current_item:
            return
        
        pattern = current_item.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            return
        
        self.engine.execute_pattern(pattern.steps)
        self.viz.update()
        
        actuator_count = len(set(step.actuator_id for step in pattern.steps))
        
        self.ui.info_text.setPlainText(
            f"🔄 Replaying library pattern: {pattern.name}\n"
            f"Type: {pattern.pattern_type}, Actuators: {actuator_count}, Duration: {pattern.total_duration:.0f}ms\n"
            f"📚 Pattern loaded from library and executed with 3-actuator phantom support!"
        )
        
        print(f"🔄 Replaying pattern: {pattern.name}")
    
    def load_pattern_file(self):
        """Load pattern from file dialog"""
        from PyQt6.QtWidgets import QFileDialog
        filename, _ = QFileDialog.getOpenFileName(
            self,
            "Load Pattern",
            "patterns",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if filename:
            pattern = self.engine.load_pattern(filename)
            if pattern:
                self.refresh_pattern_list()
                print(f"📂 Pattern loaded: {pattern.name}")
            else:
                print(f"❌ Failed to load pattern from {filename}")
    
    def delete_selected_pattern(self):
        """Delete the selected pattern"""
        current_item = self.ui.pattern_list.currentItem()
        if not current_item:
            return
        
        pattern = current_item.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            return
        
        from PyQt6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Delete Pattern",
            f"Delete pattern '{pattern.name}'?\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if pattern.name in self.engine.shared_patterns:
                del self.engine.shared_patterns[pattern.name]
            
            filename = f"patterns/{pattern.name.replace(' ', '_')}.json"
            if os.path.exists(filename):
                os.remove(filename)
            
            self.refresh_pattern_list()
            print(f"🗑️ Pattern '{pattern.name}' deleted")
    
    def update_displays(self):
        """Update all UI displays with 3-actuator phantom info"""
        count = len(self.engine.selected_actuators)
        if count == 0:
            selection_text = "No actuators selected"
        else:
            actuator_list = ", ".join(map(str, sorted(self.engine.selected_actuators)))
            selection_text = f"Selected: {actuator_list}"
        
        self.ui.buzz_selection_info.setText(selection_text)
        self.ui.pulse_selection_info.setText(f"{count} selected" if count > 0 else selection_text)
        self.ui.motion_selection_info.setText(f"{count} selected" if count > 0 else selection_text)
        
        # Update phantom info (always 3-actuator)
        if self.engine.phantoms_enabled:
            phantom_count = len(self.engine.enhanced_phantoms)
            phantom_text = f"{phantom_count} 3-actuator phantoms (Park et al.)"
        else:
            phantom_text = "3-Actuator phantoms disabled"
        
        self.ui.buzz_phantom_info.setText(phantom_text)
        self.ui.pulse_phantom_info.setText(phantom_text)
        self.ui.motion_phantom_info.setText(phantom_text)
        
        # Update trajectory info
        traj_count = len(self.engine.trajectory_collection)
        current_traj = " (+1 current)" if self.engine.current_trajectory else ""
        self.ui.trajectory_info.setText(f"{traj_count} trajectories{current_traj}")
        
        # Update drawing info
        if self.engine.drawing_mode:
            trajectory_length = len(self.engine.current_trajectory)
            self.ui.drawing_info.setText(f"Drawing: {trajectory_length} pts")
        else:
            trajectory_length = len(self.engine.current_trajectory)
            if trajectory_length > 0:
                self.ui.drawing_info.setText(f"Current: {trajectory_length} points")
            else:
                self.ui.drawing_info.setText("Ready to draw")
    
    def emergency_stop(self):
        """Emergency stop all activity"""
        self.engine.stop_all_actuators()
        self.viz.update()
        self.ui.info_text.setPlainText(
            "🛑 EMERGENCY STOP ACTIVATED\n"
            "All actuators stopped. 3-actuator phantom system ready for new patterns."
        )
    
    def closeEvent(self, event):
        """Clean shutdown"""
        self.emergency_stop()
        if self.api and hasattr(self.api, 'connected') and self.api.connected:
            if hasattr(self.api, 'disconnect_serial_device'):
                self.api.disconnect_serial_device()
        event.accept()

def main():
    """Main application entry point"""
    app = QApplication(sys.argv)
    
    if not os.path.exists('comparative_pattern_interface.ui'):
        print("❌ Error: comparative_pattern_interface.ui file not found!")
        print("Please ensure the UI file is in the same directory as this script.")
        return 1
    
    try:
        window = ComparativePatternGUI()
        window.show()
        return app.exec()
    except Exception as e:
        print(f"❌ Error starting application: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())