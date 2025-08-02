
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
            
            painter.setPen(QPen(QColor(0, 150, 255), 4))
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
        min_phantoms = 2
        max_phantoms = min(20, int(trajectory_length / 30))
        
        # Calculate based on time spacing
        time_based_phantoms = max(2, int(trajectory_length / (spacing_ms * 0.1)))
        
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
            phantoms = trajectory_data.get('phantoms', [])
            
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
    """Main GUI for comparative pattern testing using UI file"""
    
    def __init__(self):
        super().__init__()
        
        # Load the UI file
        self.ui = uic.loadUi('comparative_pattern_interface.ui', self)
        
        # Initialize engine
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
        self.update_timer.start(100)  # Update every 100ms
    
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
        
        # Insert at the beginning of the right layout (before info_text)
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
        
        # Buzz tab
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
                    self.ui.info_text.setPlainText("✅ Device connected - ready for pattern testing!")
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
        """Handle phantom creation request"""
        if not self.engine.phantoms_enabled:
            self.ui.info_text.setPlainText("❌ Phantoms are disabled - enable in Global Parameters")
            return
        
        phantom = self.engine.create_phantom((x, y), self.engine.intensity)
        if phantom:
            self.viz.update()
            self.update_displays()
            self.ui.info_text.setPlainText(
                f"✅ Phantom created at ({x:.0f}, {y:.0f})\n"
                f"Using actuators: {phantom.physical_actuator_1}, {phantom.physical_actuator_2}, {phantom.physical_actuator_3}"
            )
        else:
            self.ui.info_text.setPlainText(
                f"❌ Failed to create phantom at ({x:.0f}, {y:.0f})\n"
                f"Try closer to actuators or enable phantoms"
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
        """Play all trajectories simultaneously"""
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
        """Execute pattern and show comparison info"""
        self.engine.execute_pattern(steps)
        self.store_current_pattern(pattern_type, steps)
        
        # Update visualization
        self.viz.update()
        
        # Show pattern comparison info
        phantom_info = ""
        if pattern_type == "Motion" and self.engine.phantoms_enabled:
            phantom_count = len(self.engine.enhanced_phantoms)
            phantom_info = f" using {phantom_count} phantoms"
        elif pattern_type == "Motion" and not self.engine.phantoms_enabled:
            phantom_info = " (phantoms disabled - limited smoothness)"
        
        self.ui.info_text.setPlainText(
            f"▶️ Executing {pattern_type} pattern{phantom_info}\n"
            f"Steps: {len(steps)}, Waveform: {self.engine.waveform_type} @ {self.engine.frequency}Hz\n"
            f"💡 Compare with other pattern types to see motion superiority!"
        )
    
    def store_current_pattern(self, pattern_type: str, steps: List[PatternStep]):
        """Store the current pattern for potential saving"""
        self.current_pattern_steps = steps.copy()
        self.current_pattern_type = pattern_type
        
        # Enable save button
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
                    self.engine.shared_patterns[pattern.name] = pattern
                except Exception as e:
                    print(f"❌ Failed to load pattern from {filepath}: {e}")
        
        self.refresh_pattern_list()
    
    def refresh_pattern_list(self):
        """Refresh the pattern list display"""
        self.ui.pattern_list.clear()
        
        # Group patterns by type
        by_type = {"Buzz": [], "Pulse": [], "Motion": []}
        
        for pattern in self.engine.shared_patterns.values():
            if pattern.pattern_type in by_type:
                by_type[pattern.pattern_type].append(pattern)
        
        # Add patterns to list grouped by type
        for pattern_type, patterns in by_type.items():
            if patterns:
                # Add type header
                header_item = self.ui.pattern_list.addItem(f"═══ {pattern_type} ═══")
                header_item = self.ui.pattern_list.item(self.ui.pattern_list.count() - 1)
                header_item.setData(Qt.ItemDataRole.UserRole, None)  # No pattern data
                
                # Add patterns of this type
                for pattern in sorted(patterns, key=lambda p: p.created_timestamp, reverse=True):
                    actuator_count = len(set(step.actuator_id for step in pattern.steps))
                    item_text = f"  {pattern.name} ({actuator_count}a, {pattern.total_duration:.0f}ms)"
                    
                    item = self.ui.pattern_list.addItem(item_text)
                    item = self.ui.pattern_list.item(self.ui.pattern_list.count() - 1)
                    item.setData(Qt.ItemDataRole.UserRole, pattern)  # Store pattern object
    
    def on_pattern_selection_changed(self, current, previous):
        """Handle pattern selection change"""
        if not current:
            self.ui.pattern_info.setText("No pattern selected")
            return
        
        pattern = current.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            self.ui.pattern_info.setText("Pattern type header")
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
        
        self.ui.pattern_info.setText(info_text)
    
    def replay_selected_pattern(self):
        """Replay the selected pattern"""
        current_item = self.ui.pattern_list.currentItem()
        if not current_item:
            return
        
        pattern = current_item.data(Qt.ItemDataRole.UserRole)
        if not pattern:
            return
        
        # Execute pattern
        self.engine.execute_pattern(pattern.steps)
        self.viz.update()
        
        # Show replay info
        actuator_count = len(set(step.actuator_id for step in pattern.steps))
        
        self.ui.info_text.setPlainText(
            f"🔄 Replaying library pattern: {pattern.name}\n"
            f"Type: {pattern.pattern_type}, Actuators: {actuator_count}, Duration: {pattern.total_duration:.0f}ms\n"
            f"📚 Pattern loaded from library and executed successfully!"
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
    
    def update_displays(self):
        """Update all UI displays with current state"""
        # Update selection info in all tabs
        count = len(self.engine.selected_actuators)
        if count == 0:
            selection_text = "No actuators selected"
            buzz_selection_text = "No actuators selected"
            pulse_selection_text = "No actuators selected"
            motion_selection_text = "No actuators selected"
        else:
            actuator_list = ", ".join(map(str, sorted(self.engine.selected_actuators)))
            selection_text = f"Selected: {actuator_list}"
            buzz_selection_text = f"Selected: {actuator_list}"
            pulse_selection_text = f"{count} selected"
            motion_selection_text = f"{count} selected"
        
        self.ui.buzz_selection_info.setText(buzz_selection_text)
        self.ui.pulse_selection_info.setText(pulse_selection_text)
        self.ui.motion_selection_info.setText(motion_selection_text)
        
        # Update phantom info
        phantom_count = len(self.engine.enhanced_phantoms)
        phantom_text = f"{phantom_count} phantoms"
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
            "All actuators stopped. System ready for new patterns."
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
    
    # Check if UI file exists
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