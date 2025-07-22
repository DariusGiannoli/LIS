#!/usr/bin/env python3
"""
phantom_actuators.py

FIXED phantom actuator implementation - corrected all placement and intensity issues.
"""
import sys
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QApplication, QMainWindow, QComboBox, QTextEdit, QSlider
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

# Import your API
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found.")
    python_serial_api = None

ACTUATORS = [0, 1, 2, 3, 4]

@dataclass
class PhantomActuator:
    """Represents a phantom/virtual actuator"""
    phantom_id: int
    virtual_position: float  # Position in mm
    physical_actuator_1: int  # Left physical actuator
    physical_actuator_2: int  # Right physical actuator 
    beta: float  # Location parameter (0 to 1)
    desired_intensity: int  # What user wants (1-15 device range)
    required_intensity_1: int  # What actuator 1 needs (1-15 device range)
    required_intensity_2: int  # What actuator 2 needs (1-15 device range)
    actual_intensity: float  # Theoretical intensity validation

class PhantomActuatorEngine:
    """FIXED phantom actuator engine with correct positioning and device-range intensity"""
    
    def __init__(self, api=None, actuator_spacing_mm=125):
        self.api = api
        self.phantoms = []
        self.actuator_spacing = actuator_spacing_mm
        
        # Calculate actual positions based on spacing
        self.actuator_positions = {
            i: i * self.actuator_spacing for i in range(5)
        }
        self.max_position = 4 * self.actuator_spacing  # Distance from first to last actuator
        
        print(f"🔧 Phantom Engine initialized:")
        print(f"📏 Spacing: {actuator_spacing_mm}mm")
        print(f"📍 Positions: {self.actuator_positions}")
        print(f"📐 Total range: 0-{self.max_position}mm")
    
    def update_spacing(self, new_spacing_mm):
        """Update spacing and recalculate everything"""
        self.actuator_spacing = new_spacing_mm
        self.actuator_positions = {
            i: i * self.actuator_spacing for i in range(5)
        }
        self.max_position = 4 * self.actuator_spacing
        self.clear_phantoms()  # Clear existing phantoms as positions changed
        print(f"🔄 Updated spacing to {new_spacing_mm}mm, range: 0-{self.max_position}mm")
    
    def calculate_phantom_intensities_device_range(self, desired_intensity: int, beta: float) -> Tuple[int, int]:
        """
        Calculate phantom intensities directly in device range (1-15)
        
        Based on paper's Equation 4: A1 = √(1-β) × Av, A2 = √β × Av
        But working in device units for better control
        """
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        # Convert to normalized 0-1 for calculation
        desired_norm = desired_intensity / 15.0
        
        # Paper's formulas
        intensity_1_norm = math.sqrt(1 - beta) * desired_norm
        intensity_2_norm = math.sqrt(beta) * desired_norm
        
        # Convert back to device range and round
        device_intensity_1 = max(1, min(15, round(intensity_1_norm * 15)))
        device_intensity_2 = max(1, min(15, round(intensity_2_norm * 15)))
        
        print(f"🧮 Intensity calc: desired={desired_intensity}/15, β={beta:.3f}")
        print(f"🧮 Result: Act1={device_intensity_1}/15, Act2={device_intensity_2}/15")
        
        return device_intensity_1, device_intensity_2
    
    def validate_phantom_energy(self, device_intensity_1: int, device_intensity_2: int) -> float:
        """
        Validate using energy summation: Av² = A1² + A2²
        Returns normalized theoretical intensity
        """
        norm_1 = device_intensity_1 / 15.0
        norm_2 = device_intensity_2 / 15.0
        return math.sqrt(norm_1**2 + norm_2**2)
    
    def calculate_beta_from_position(self, phantom_pos: float, left_pos: float, right_pos: float) -> float:
        """
        Calculate beta parameter from positions
        β = 0 means phantom at left actuator position
        β = 1 means phantom at right actuator position  
        β = 0.5 means phantom exactly between them
        """
        total_distance = abs(right_pos - left_pos)
        if total_distance == 0:
            return 0.5
        
        distance_from_left = abs(phantom_pos - left_pos)
        beta = distance_from_left / total_distance
        
        # Clamp to valid range
        beta = max(0.0, min(1.0, beta))
        
        print(f"📐 Beta calc: phantom={phantom_pos:.1f}mm between {left_pos:.1f}mm and {right_pos:.1f}mm")
        print(f"📐 Distance from left: {distance_from_left:.1f}mm / {total_distance:.1f}mm = β={beta:.3f}")
        
        return beta
    
    def find_surrounding_actuators(self, phantom_position: float) -> Tuple[Optional[int], Optional[int], float, float]:
        """Find the two actuators that can create a phantom at given position"""
        left_actuator = None
        right_actuator = None
        left_pos = float('-inf')
        right_pos = float('inf')
        
        for actuator_id, pos in self.actuator_positions.items():
            # Find leftmost actuator that's still <= phantom position
            if pos <= phantom_position and pos > left_pos:
                left_actuator = actuator_id
                left_pos = pos
            # Find rightmost actuator that's still >= phantom position
            if pos >= phantom_position and pos < right_pos:
                right_actuator = actuator_id
                right_pos = pos
        
        print(f"🔍 Position {phantom_position:.1f}mm: found left={left_actuator}@{left_pos:.1f}mm, right={right_actuator}@{right_pos:.1f}mm")
        
        return left_actuator, right_actuator, left_pos, right_pos
    
    def create_phantom_actuator(self, phantom_position: float, desired_intensity: int) -> Optional[PhantomActuator]:
        """
        Create phantom actuator with FIXED positioning and direct device intensity
        
        Args:
            phantom_position: Where to place phantom (in mm, 0 to max_position)
            desired_intensity: How strong (1-15 device range)
        """
        print(f"\n🎯 Creating phantom at {phantom_position:.1f}mm with intensity {desired_intensity}/15")
        
        # Validate inputs
        if desired_intensity < 1 or desired_intensity > 15:
            print(f"❌ Invalid intensity {desired_intensity} - must be 1-15")
            return None
        
        if phantom_position < 0 or phantom_position > self.max_position:
            print(f"❌ Invalid position {phantom_position:.1f}mm - must be 0-{self.max_position}mm")
            return None
        
        # Find surrounding actuators
        left_actuator, right_actuator, left_pos, right_pos = self.find_surrounding_actuators(phantom_position)
        
        if left_actuator is None or right_actuator is None:
            print(f"❌ Cannot find suitable actuators for position {phantom_position:.1f}mm")
            return None
        
        if left_actuator == right_actuator:
            print(f"❌ Position {phantom_position:.1f}mm is exactly on actuator {left_actuator}")
            return None
        
        # Calculate beta parameter  
        beta = self.calculate_beta_from_position(phantom_position, left_pos, right_pos)
        
        # Calculate required device intensities
        try:
            device_intensity_1, device_intensity_2 = self.calculate_phantom_intensities_device_range(
                desired_intensity, beta)
        except ValueError as e:
            print(f"❌ {e}")
            return None
        
        # Validate using energy model
        theoretical_intensity = self.validate_phantom_energy(device_intensity_1, device_intensity_2)
        
        phantom_id = len(self.phantoms)
        
        phantom = PhantomActuator(
            phantom_id=phantom_id,
            virtual_position=phantom_position,
            physical_actuator_1=left_actuator,
            physical_actuator_2=right_actuator,
            beta=beta,
            desired_intensity=desired_intensity,
            required_intensity_1=device_intensity_1,
            required_intensity_2=device_intensity_2,
            actual_intensity=theoretical_intensity
        )
        
        self.phantoms.append(phantom)
        
        print(f"✅ Phantom {phantom_id} created successfully!")
        print(f"📍 Position: {phantom_position:.1f}mm")
        print(f"🎛️  Between: Act{left_actuator}({left_pos:.0f}mm) ↔ Act{right_actuator}({right_pos:.0f}mm)")
        print(f"📐 Beta: {beta:.3f}")
        print(f"⚡ Device commands: Act{left_actuator}={device_intensity_1}/15, Act{right_actuator}={device_intensity_2}/15")
        print(f"🧪 Energy check: {theoretical_intensity:.3f} normalized")
        print("=" * 50)
        
        return phantom
    
    def activate_phantom(self, phantom_id: int) -> bool:
        """Activate phantom with direct device intensities"""
        if phantom_id >= len(self.phantoms):
            print(f"❌ Phantom {phantom_id} does not exist")
            return False
        
        phantom = self.phantoms[phantom_id]
        
        if not self.api or not self.api.connected:
            print("❌ No API connection")
            return False
        
        freq = 4  # Mid-range frequency
        
        # Send commands with the pre-calculated device intensities
        success1 = self.api.send_command(phantom.physical_actuator_1, phantom.required_intensity_1, freq, 1)
        success2 = self.api.send_command(phantom.physical_actuator_2, phantom.required_intensity_2, freq, 1)
        
        if success1 and success2:
            print(f"🚀 Phantom {phantom_id} ACTIVATED at {phantom.virtual_position:.1f}mm")
            print(f"⚡ Commands sent: Act{phantom.physical_actuator_1}={phantom.required_intensity_1}/15, Act{phantom.physical_actuator_2}={phantom.required_intensity_2}/15")
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

class PhantomVisualization(QWidget):
    """FIXED visualization with correct positioning and scaling"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(800, 400)
        self.phantoms = []
        self.actuator_positions = {}
        self.max_position = 500
        
    def set_phantoms(self, phantoms: List[PhantomActuator], actuator_positions: dict):
        self.phantoms = phantoms
        self.actuator_positions = actuator_positions
        self.max_position = max(actuator_positions.values()) if actuator_positions else 500
        self.update()
        
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.actuator_positions:
            painter.drawText(20, 50, "No actuator positions configured")
            return
        
        # Layout constants
        margin = 80
        width = self.width() - 2 * margin
        y_physical = 100
        y_phantom = 200
        
        # FIXED scaling - use actual max position
        def pos_to_x(pos_mm):
            if self.max_position == 0:
                return margin
            return margin + (pos_mm / self.max_position) * width
        
        # Title with current spacing
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(14)
        painter.setFont(font)
        spacing = list(self.actuator_positions.values())[1] if len(self.actuator_positions) > 1 else 0
        painter.drawText(margin, 30, f"Phantom Actuator Visualization (Spacing: {spacing:.0f}mm)")
        
        # Draw scale ruler
        painter.setPen(QPen(QColor(128, 128, 128), 1))
        font.setPointSize(8)
        painter.setFont(font)
        ruler_y = y_physical - 40
        painter.drawLine(margin, ruler_y, margin + width, ruler_y)
        
        # Ruler marks every 100mm
        for pos in range(0, int(self.max_position) + 1, 100):
            x = pos_to_x(pos)
            painter.drawLine(int(x), ruler_y - 5, int(x), ruler_y + 5)
            painter.drawText(int(x - 15), ruler_y - 10, f"{pos}mm")
        
        # Draw physical actuators with CORRECT positions
        painter.setPen(QPen(QColor(0, 0, 0), 3))
        painter.setBrush(QBrush(QColor(100, 150, 255)))
        
        for actuator_id, pos_mm in self.actuator_positions.items():
            x = pos_to_x(pos_mm)
            painter.drawEllipse(int(x-20), y_physical-20, 40, 40)
            
            # Actuator ID (white text)
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(14)
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(x-8), y_physical+5, str(actuator_id))
            
            # Position label (black text below)
            painter.setPen(QPen(QColor(0, 0, 0)))
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(int(x-25), y_physical+50, f"Act{actuator_id}")
            painter.drawText(int(x-25), y_physical+65, f"{pos_mm:.0f}mm")
        
        # Draw baseline between physical and phantom levels
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        painter.drawLine(margin, y_physical + 80, margin + width, y_physical + 80)
        
        # Draw phantom actuators
        for phantom in self.phantoms:
            x = pos_to_x(phantom.virtual_position)
            
            # Phantom circle (red/translucent)
            painter.setPen(QPen(QColor(255, 0, 0), 4))
            painter.setBrush(QBrush(QColor(255, 100, 100, 200)))
            painter.drawEllipse(int(x-18), y_phantom-18, 36, 36)
            
            # Ghost emoji
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setBold(True)
            font.setPointSize(18)
            painter.setFont(font)
            painter.drawText(int(x-9), y_phantom+6, "👻")
            
            # Phantom details
            painter.setPen(QPen(QColor(255, 0, 0)))
            font.setPointSize(10)
            font.setBold(False)
            painter.setFont(font)
            painter.drawText(int(x-30), y_phantom+40, f"P{phantom.phantom_id}")
            painter.drawText(int(x-30), y_phantom+55, f"{phantom.virtual_position:.0f}mm")
            painter.drawText(int(x-30), y_phantom+70, f"β:{phantom.beta:.2f}")
            painter.drawText(int(x-30), y_phantom+85, f"I:{phantom.desired_intensity}/15")
            
            # Connection lines to physical actuators
            painter.setPen(QPen(QColor(255, 0, 0), 3, Qt.PenStyle.DashLine))
            
            # Line to left actuator
            left_pos = self.actuator_positions.get(phantom.physical_actuator_1, 0)
            x1 = pos_to_x(left_pos)
            painter.drawLine(int(x), y_phantom-18, int(x1), y_physical+20)
            
            # Line to right actuator
            right_pos = self.actuator_positions.get(phantom.physical_actuator_2, 0)
            x2 = pos_to_x(right_pos)
            painter.drawLine(int(x), y_phantom-18, int(x2), y_physical+20)
            
            # Intensity labels on connection lines
            painter.setPen(QPen(QColor(150, 0, 0)))
            font.setPointSize(11)
            font.setBold(True)
            painter.setFont(font)
            
            # Left intensity label
            mid_x1 = (x + x1) / 2
            mid_y1 = (y_phantom + y_physical) / 2
            painter.drawText(int(mid_x1-25), int(mid_y1), f"Act{phantom.physical_actuator_1}:")
            painter.drawText(int(mid_x1-25), int(mid_y1+15), f"{phantom.required_intensity_1}/15")
            
            # Right intensity label
            mid_x2 = (x + x2) / 2
            mid_y2 = (y_phantom + y_physical) / 2
            painter.drawText(int(mid_x2+5), int(mid_y2), f"Act{phantom.physical_actuator_2}:")
            painter.drawText(int(mid_x2+5), int(mid_y2+15), f"{phantom.required_intensity_2}/15")
        
        # Legend and info
        painter.setPen(QPen(QColor(0, 0, 0)))
        font.setBold(False)
        font.setPointSize(10)
        painter.setFont(font)
        
        legend_y = self.height() - 100
        painter.drawText(margin, legend_y, "🔵 Physical Actuators (device range 1-15)")
        painter.drawText(margin, legend_y + 20, "👻 Phantom Actuators - Created using energy summation model")
        painter.drawText(margin, legend_y + 40, f"Active phantoms: {len(self.phantoms)} | Range: 0-{self.max_position:.0f}mm | Model: Av² = A1² + A2²")
        painter.drawText(margin, legend_y + 60, "Red dashed lines show intensity distribution to physical actuators")

class PhantomActuatorGUI(QWidget):
    """FIXED GUI with proper controls and positioning"""
    
    def __init__(self):
        super().__init__()
        self.engine = PhantomActuatorEngine(actuator_spacing_mm=125)  # Your spacing
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
        title = QLabel("🎯 FIXED Phantom Actuator Creator")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #E91E63;")
        layout.addWidget(title)
        
        subtitle = QLabel("Corrected positioning and device-range intensity (1-15)")
        subtitle.setStyleSheet("font-style: italic; color: #666; font-size: 12px;")
        layout.addWidget(subtitle)
        
        # Hardware configuration
        hw_group = QGroupBox("Hardware Configuration")
        hw_layout = QFormLayout(hw_group)
        
        # Spacing control
        self.spacing_spin = QSpinBox()
        self.spacing_spin.setRange(50, 300)
        self.spacing_spin.setValue(125)  # Your actual spacing
        self.spacing_spin.setSuffix(" mm")
        self.spacing_spin.valueChanged.connect(self.update_spacing)
        hw_layout.addRow("Distance Between Actuators:", self.spacing_spin)
        
        # Show actual positions
        self.positions_label = QLabel()
        self.update_positions_display()
        hw_layout.addRow("Actuator Positions:", self.positions_label)
        
        layout.addWidget(hw_group)
        
        # Connection controls
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
        
        # Phantom creation controls
        create_group = QGroupBox("Create Phantom Actuator")
        create_layout = QFormLayout(create_group)
        
        # Position slider - DYNAMIC range based on spacing
        self.position_slider = QSlider(Qt.Orientation.Horizontal)
        self.update_slider_range()
        self.position_slider.valueChanged.connect(self.update_position_display)
        
        self.position_label = QLabel()
        position_layout = QHBoxLayout()
        position_layout.addWidget(self.position_slider)
        position_layout.addWidget(self.position_label)
        create_layout.addRow("Phantom Position:", position_layout)
        
        # Intensity - DIRECT device range (1-15)
        self.intensity_spin = QSpinBox()
        self.intensity_spin.setRange(1, 15)
        self.intensity_spin.setValue(8)  # Strong default
        self.intensity_spin.valueChanged.connect(self.update_position_display)
        create_layout.addRow("Intensity (1=weak, 15=strongest):", self.intensity_spin)
        
        # Real-time calculation preview
        self.calc_preview_label = QLabel()
        create_layout.addRow("Calculation Preview:", self.calc_preview_label)
        
        # Create button
        self.create_phantom_btn = QPushButton("🎯 Create Phantom Actuator")
        self.create_phantom_btn.clicked.connect(self.create_phantom)
        self.create_phantom_btn.setStyleSheet("""
            QPushButton {
                background-color: #E91E63;
                color: white;
                padding: 12px;
                font-weight: bold;
                font-size: 12px;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #C2185B;
            }
        """)
        create_layout.addRow("", self.create_phantom_btn)
        
        layout.addWidget(create_group)
        
        # Control buttons
        control_layout = QHBoxLayout()
        
        self.activate_all_btn = QPushButton("🚀 Activate All Phantoms")
        self.activate_all_btn.clicked.connect(self.activate_all)
        self.activate_all_btn.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; background-color: #4CAF50; color: white; border-radius: 4px; }")
        
        self.deactivate_all_btn = QPushButton("⏹️ Stop All Phantoms")
        self.deactivate_all_btn.clicked.connect(self.deactivate_all)
        self.deactivate_all_btn.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; background-color: #FF9800; color: white; border-radius: 4px; }")
        
        self.clear_all_btn = QPushButton("🗑️ Clear All Phantoms")
        self.clear_all_btn.clicked.connect(self.clear_all)
        self.clear_all_btn.setStyleSheet("QPushButton { padding: 8px; font-weight: bold; background-color: #F44336; color: white; border-radius: 4px; }")
        
        control_layout.addWidget(self.activate_all_btn)
        control_layout.addWidget(self.deactivate_all_btn)
        control_layout.addWidget(self.clear_all_btn)
        layout.addLayout(control_layout)
        
        # Visualization
        viz_group = QGroupBox("Live Phantom Visualization")
        viz_layout = QVBoxLayout(viz_group)
        
        self.viz = PhantomVisualization()
        viz_layout.addWidget(self.viz)
        layout.addWidget(viz_group)
        
        # Info display
        self.info_text = QTextEdit()
        self.info_text.setMaximumHeight(100)
        self.info_text.setReadOnly(True)
        self.info_text.setPlainText("🎯 Ready to create phantoms. Configure position and intensity above.")
        layout.addWidget(self.info_text)
        
        # Initialize displays
        self.update_position_display()
    
    def update_spacing(self):
        """Update spacing and refresh all displays"""
        new_spacing = self.spacing_spin.value()
        self.engine.update_spacing(new_spacing)
        self.update_positions_display()
        self.update_slider_range()
        self.update_position_display()
        # Clear visualization as positions changed
        self.viz.set_phantoms([], self.engine.actuator_positions)
        self.info_text.setPlainText(f"🔄 Updated spacing to {new_spacing}mm. Create new phantoms.")
    
    def update_positions_display(self):
        """Show current actuator positions"""
        positions = [f"Act{i}:{pos:.0f}mm" for i, pos in self.engine.actuator_positions.items()]
        self.positions_label.setText(" | ".join(positions))
    
    def update_slider_range(self):
        """Set slider range based on actual actuator spacing"""
        self.position_slider.setRange(0, self.engine.max_position)
        self.position_slider.setValue(self.engine.max_position // 2)  # Start at center
    
    def update_position_display(self):
        """Update position display and calculation preview"""
        position = self.position_slider.value()
        intensity = self.intensity_spin.value()
        
        self.position_label.setText(f"{position}mm")
        
        # Get preview calculation
        left_act, right_act, left_pos, right_pos = self.engine.find_surrounding_actuators(position)
        
        if left_act is not None and right_act is not None and left_act != right_act:
            beta = self.engine.calculate_beta_from_position(position, left_pos, right_pos)
            try:
                int1, int2 = self.engine.calculate_phantom_intensities_device_range(intensity, beta)
                preview_text = f"✅ Act{left_act}({int1}/15) + Act{right_act}({int2}/15) | β={beta:.3f}"
                self.calc_preview_label.setText(preview_text)
                self.calc_preview_label.setStyleSheet("color: green;")
                self.create_phantom_btn.setEnabled(True)
            except ValueError as e:
                self.calc_preview_label.setText(f"❌ {e}")
                self.calc_preview_label.setStyleSheet("color: red;")
                self.create_phantom_btn.setEnabled(False)
        else:
            if left_act == right_act:
                self.calc_preview_label.setText("⚠️ Position exactly on an actuator")
                self.calc_preview_label.setStyleSheet("color: orange;")
            else:
                self.calc_preview_label.setText("❌ Invalid position - outside actuator range")
                self.calc_preview_label.setStyleSheet("color: red;")
            self.create_phantom_btn.setEnabled(False)
    
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
                    self.status_label.setText("Connected ✅")
                    self.status_label.setStyleSheet("color: green; font-weight: bold;")
                    self.connect_btn.setText("Disconnect")
        else:
            if self.api.disconnect_serial_device():
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                self.connect_btn.setText("Connect")
    
    def create_phantom(self):
        """Create phantom with current settings"""
        position = self.position_slider.value()
        intensity = self.intensity_spin.value()
        
        phantom = self.engine.create_phantom_actuator(position, intensity)
        
        if phantom:
            # Update visualization with correct positions
            self.viz.set_phantoms(self.engine.phantoms, self.engine.actuator_positions)
            
            # Update info display
            info_text = f"✅ Phantom {phantom.phantom_id} created at {position}mm\n"
            info_text += f"⚡ Commands: Act{phantom.physical_actuator_1}={phantom.required_intensity_1}/15, Act{phantom.physical_actuator_2}={phantom.required_intensity_2}/15\n"
            info_text += f"📊 Total phantoms: {len(self.engine.phantoms)}"
            self.info_text.setPlainText(info_text)
        else:
            self.info_text.setPlainText("❌ Failed to create phantom. Check console for details.")
    
    def activate_all(self):
        """Activate all phantoms"""
        self.engine.activate_all_phantoms()
        self.info_text.setPlainText(f"🚀 Activated {len(self.engine.phantoms)} phantoms!")
    
    def deactivate_all(self):
        """Stop all phantoms"""
        self.engine.deactivate_all_phantoms()
        self.info_text.setPlainText("⏹️ All phantoms stopped")
    
    def clear_all(self):
        """Clear all phantoms"""
        self.engine.clear_phantoms()
        self.viz.set_phantoms([], self.engine.actuator_positions)
        self.info_text.setPlainText("🗑️ All phantoms cleared")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("🎯 FIXED Phantom Actuator Creator - Device Range Intensities")
    
    widget = PhantomActuatorGUI()
    window.setCentralWidget(widget)
    window.resize(1000, 900)
    window.show()
    
    sys.exit(app.exec())