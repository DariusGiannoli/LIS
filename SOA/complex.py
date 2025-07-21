#!/usr/bin/env python3
"""
true_soa_tactile_brush.py

Correct SOA implementation matching the Tactile Brush paper:
- SOA = time between ONSETS of consecutive actuators
- Duration = how long each actuator vibrates
- Overlapping activations create apparent motion
- Based on Neuhaus 1930 and paper's psychophysical experiments
"""
import sys
import math
import time
from dataclasses import dataclass
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox, QSlider,
    QApplication, QMainWindow, QComboBox, QProgressBar, QCheckBox,
    QTextEdit
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

# Import your API
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found. Using mock API.")
    python_serial_api = None

# Configuration for your 3-actuator setup
LINEAR_CONFIG = {
    'ACTUATOR_COUNT': 3,
    'ACTUATOR_IDS': [0, 1, 2],
    'SPACING_MM': 65.0,  # 6.5cm = 65mm
    'TOTAL_LENGTH': 130.0,  # 2 * 65mm = 13cm total span
    'POSITIONS': {
        0: 0.0,    # Left actuator at 0mm
        1: 65.0,   # Middle actuator at 65mm  
        2: 130.0   # Right actuator at 130mm
    }
}

# SOA Parameters from Tactile Brush paper
SOA_PARAMS = {
    'BASE_MS': 47.3,        # Base SOA in milliseconds
    'SLOPE': 0.32,          # SOA slope factor
    'MIN_DURATION': 40,     # Minimum duration (ms)
    'MAX_DURATION': 160,    # Maximum duration (ms)
    'OPTIMAL_FREQ': 200,    # Optimal frequency (Hz)
}

@dataclass
class SOAStep:
    """Single step in SOA sequence"""
    actuator_id: int
    intensity: float        # 0.0 to 1.0
    onset_time: float      # When to START (ms from sequence start)
    duration: float        # How long to vibrate (ms)
    position: float        # Physical position (mm)
    step_type: str         # 'physical' or 'phantom'

@dataclass
class LinearStroke:
    """Stroke definition with SOA parameters"""
    start_position: float
    end_position: float
    intensity: float
    frequency: int
    total_duration_ms: float

class TrueSOATactileBrush:
    """SOA implementation matching the Tactile Brush paper exactly"""
    
    def __init__(self, api=None):
        self.api = api
        self.config = LINEAR_CONFIG
        
        # SOA execution state
        self.soa_sequence = []
        self.sequence_timer = QTimer()
        self.sequence_timer.timeout.connect(self.execute_soa_sequence)
        self.sequence_start_time = 0
        self.active_steps = {}  # {step_id: (actuator_id, stop_time)}
        self.next_step_index = 0
        
        # Hover feedback
        self.hover_timer = QTimer()
        self.hover_timer.timeout.connect(self.stop_hover_feedback)
        self.hover_active_actuators = set()
    
    def calculate_soa_from_duration(self, duration_ms: float) -> float:
        """
        Calculate SOA from duration using paper's equation:
        SOA = 0.32 * duration + 47.3
        
        This is the time between ONSETS of consecutive actuators
        """
        soa = SOA_PARAMS['SLOPE'] * duration_ms + SOA_PARAMS['BASE_MS']
        return max(50, soa)  # Minimum 50ms SOA for stability
    
    def calculate_duration_from_soa(self, soa_ms: float) -> float:
        """
        Reverse calculation: given SOA, what duration gives optimal motion?
        duration = (SOA - 47.3) / 0.32
        """
        duration = (soa_ms - SOA_PARAMS['BASE_MS']) / SOA_PARAMS['SLOPE']
        return max(SOA_PARAMS['MIN_DURATION'], 
                  min(SOA_PARAMS['MAX_DURATION'], duration))
    
    def find_phantom_pair(self, position_mm: float) -> Optional[Tuple[int, int, float]]:
        """Find actuators for phantom sensation"""
        position_mm = max(0, min(self.config['TOTAL_LENGTH'], position_mm))
        
        for i in range(len(self.config['ACTUATOR_IDS']) - 1):
            actuator1_id = self.config['ACTUATOR_IDS'][i]
            actuator2_id = self.config['ACTUATOR_IDS'][i + 1]
            
            pos1 = self.config['POSITIONS'][actuator1_id]
            pos2 = self.config['POSITIONS'][actuator2_id]
            
            if pos1 <= position_mm <= pos2:
                total_distance = pos2 - pos1
                distance_from_first = position_mm - pos1
                beta = distance_from_first / total_distance if total_distance > 0 else 0.0
                return (actuator1_id, actuator2_id, beta)
        
        return None
    
    def calculate_phantom_intensities(self, beta: float, target_intensity: float) -> Tuple[float, float]:
        """Energy model from paper: sqrt method"""
        beta = max(0.0, min(1.0, beta))
        intensity1 = math.sqrt(max(0.0, 1.0 - beta)) * target_intensity
        intensity2 = math.sqrt(beta) * target_intensity
        return (max(0.0, min(1.0, intensity1)), max(0.0, min(1.0, intensity2)))
    
    def create_soa_sequence(self, stroke: LinearStroke) -> List[SOAStep]:
        """
        Create SOA sequence following the paper's methodology:
        1. Determine positions along stroke
        2. Calculate optimal duration for smooth motion
        3. Calculate SOA from duration
        4. Create overlapping activations
        """
        sequence = []
        
        # Calculate stroke parameters
        stroke_distance = abs(stroke.end_position - stroke.start_position)
        if stroke_distance < 1.0:
            stroke_distance = 1.0
        
        # Determine number of steps for smooth motion
        # Paper suggests steps should create smooth apparent motion
        min_steps = 3
        optimal_step_distance = 15.0  # mm - good for 3-actuator 65mm spacing
        num_steps = max(min_steps, int(stroke_distance / optimal_step_distance) + 1)
        
        print(f"\n=== SOA Sequence Generation ===")
        print(f"Stroke: {stroke.start_position:.1f} → {stroke.end_position:.1f}mm ({stroke_distance:.1f}mm)")
        print(f"Steps: {num_steps}")
        
        # Calculate timing parameters
        # Each step should trigger at intervals that create smooth motion
        step_interval = stroke.total_duration_ms / max(1, num_steps - 1)
        
        # For apparent motion, duration should be long enough to overlap with next step
        # but not too long to cause confusion
        optimal_duration = min(SOA_PARAMS['MAX_DURATION'], 
                             max(SOA_PARAMS['MIN_DURATION'], step_interval * 1.5))
        
        # Calculate SOA from this duration
        calculated_soa = self.calculate_soa_from_duration(optimal_duration)
        
        # Adjust if needed for smooth motion
        actual_soa = min(calculated_soa, step_interval)
        final_duration = self.calculate_duration_from_soa(actual_soa)
        
        print(f"Step interval: {step_interval:.1f}ms")
        print(f"Optimal duration: {optimal_duration:.1f}ms")
        print(f"Calculated SOA: {calculated_soa:.1f}ms")
        print(f"Final SOA: {actual_soa:.1f}ms, Duration: {final_duration:.1f}ms")
        
        # Generate steps along stroke path
        for i in range(num_steps):
            progress = i / (num_steps - 1) if num_steps > 1 else 0
            current_position = stroke.start_position + progress * (stroke.end_position - stroke.start_position)
            onset_time = i * actual_soa
            
            # Check if position is at physical actuator
            physical_actuator = None
            for actuator_id, pos in self.config['POSITIONS'].items():
                if abs(current_position - pos) < 5.0:  # 5mm tolerance
                    physical_actuator = actuator_id
                    break
            
            if physical_actuator is not None:
                # Physical actuator step
                step = SOAStep(
                    actuator_id=physical_actuator,
                    intensity=stroke.intensity,
                    onset_time=onset_time,
                    duration=final_duration,
                    position=current_position,
                    step_type='physical'
                )
                sequence.append(step)
                print(f"Step {i}: Physical Act{physical_actuator} at {current_position:.1f}mm, onset={onset_time:.1f}ms")
                
            else:
                # Phantom actuator steps
                phantom_info = self.find_phantom_pair(current_position)
                if phantom_info:
                    actuator1_id, actuator2_id, beta = phantom_info
                    intensity1, intensity2 = self.calculate_phantom_intensities(beta, stroke.intensity)
                    
                    # Create two simultaneous steps for phantom sensation
                    if intensity1 > 0.05:  # Only if significant intensity
                        step1 = SOAStep(
                            actuator_id=actuator1_id,
                            intensity=intensity1,
                            onset_time=onset_time,
                            duration=final_duration,
                            position=current_position,
                            step_type='phantom'
                        )
                        sequence.append(step1)
                    
                    if intensity2 > 0.05:  # Only if significant intensity
                        step2 = SOAStep(
                            actuator_id=actuator2_id,
                            intensity=intensity2,
                            onset_time=onset_time,  # SAME onset time for phantom
                            duration=final_duration,
                            position=current_position,
                            step_type='phantom'
                        )
                        sequence.append(step2)
                    
                    print(f"Step {i}: Phantom at {current_position:.1f}mm (β={beta:.3f}), onset={onset_time:.1f}ms")
                    print(f"  → Act{actuator1_id}@{intensity1:.3f}, Act{actuator2_id}@{intensity2:.3f}")
        
        print(f"Total sequence steps: {len(sequence)}")
        print("=" * 40)
        
        return sequence
    
    def execute_stroke(self, stroke: LinearStroke):
        """Execute stroke using true SOA methodology"""
        if not self.api or not self.api.connected:
            print("No API connection - cannot execute stroke")
            return
        
        # Stop any previous execution
        self.stop_all_actuators()
        
        # Generate SOA sequence
        self.soa_sequence = self.create_soa_sequence(stroke)
        self.next_step_index = 0
        self.active_steps = {}
        
        if not self.soa_sequence:
            print("No SOA sequence generated")
            return
        
        print(f"\n=== Executing SOA Sequence ===")
        print(f"Total steps: {len(self.soa_sequence)}")
        
        # Start execution
        self.sequence_start_time = time.time() * 1000  # ms
        self.sequence_timer.start(1)  # Check every 1ms for precise timing
    
    def execute_soa_sequence(self):
        """Execute SOA sequence with precise timing"""
        current_time = time.time() * 1000 - self.sequence_start_time
        
        # Check for new steps to start
        while (self.next_step_index < len(self.soa_sequence) and 
               self.soa_sequence[self.next_step_index].onset_time <= current_time):
            
            step = self.soa_sequence[self.next_step_index]
            
            # Start this step
            if self.api and self.api.connected:
                device_intensity = max(1, min(15, int(step.intensity * 15)))
                freq = max(0, min(7, 200 // 50))  # Convert 200Hz to device range
                
                # Send start command
                success = self.api.send_command(step.actuator_id, device_intensity, freq, 1)
                
                if success:
                    # Schedule stop time
                    stop_time = current_time + step.duration
                    step_id = f"{self.next_step_index}_{step.actuator_id}"
                    self.active_steps[step_id] = (step.actuator_id, stop_time)
                    
                    print(f"SOA Step {self.next_step_index}: Act{step.actuator_id} ON "
                          f"(intensity={device_intensity}, duration={step.duration:.1f}ms) "
                          f"at {current_time:.1f}ms")
            
            self.next_step_index += 1
        
        # Check for steps to stop
        steps_to_remove = []
        for step_id, (actuator_id, stop_time) in self.active_steps.items():
            if current_time >= stop_time:
                if self.api and self.api.connected:
                    self.api.send_command(actuator_id, 0, 0, 0)
                    print(f"SOA Step: Act{actuator_id} OFF at {current_time:.1f}ms")
                steps_to_remove.append(step_id)
        
        # Remove completed steps
        for step_id in steps_to_remove:
            del self.active_steps[step_id]
        
        # Check if sequence is complete
        if (self.next_step_index >= len(self.soa_sequence) and 
            len(self.active_steps) == 0):
            self.sequence_timer.stop()
            print("=== SOA Sequence Complete ===\n")
    
    def activate_position_feedback(self, position_mm: float, intensity: float = 0.6):
        """Immediate position feedback (not SOA-based)"""
        if not self.api or not self.api.connected:
            return
        
        # Stop previous hover feedback
        self.stop_hover_feedback()
        
        # Check for physical actuator
        for actuator_id, pos in self.config['POSITIONS'].items():
            if abs(position_mm - pos) < 5.0:
                device_intensity = max(1, min(15, int(intensity * 15)))
                self.api.send_command(actuator_id, device_intensity, 4, 1)
                self.hover_active_actuators.add(actuator_id)
                self.hover_timer.start(100)
                return
        
        # Try phantom sensation
        phantom_info = self.find_phantom_pair(position_mm)
        if phantom_info:
            actuator1_id, actuator2_id, beta = phantom_info
            intensity1, intensity2 = self.calculate_phantom_intensities(beta, intensity)
            
            if intensity1 > 0.05:
                device_intensity1 = max(1, min(15, int(intensity1 * 15)))
                self.api.send_command(actuator1_id, device_intensity1, 4, 1)
                self.hover_active_actuators.add(actuator1_id)
            
            if intensity2 > 0.05:
                device_intensity2 = max(1, min(15, int(intensity2 * 15)))
                self.api.send_command(actuator2_id, device_intensity2, 4, 1)
                self.hover_active_actuators.add(actuator2_id)
            
            self.hover_timer.start(100)
    
    def stop_hover_feedback(self):
        """Stop hover feedback"""
        if self.api and self.api.connected:
            for actuator_id in self.hover_active_actuators:
                self.api.send_command(actuator_id, 0, 0, 0)
        self.hover_active_actuators.clear()
        self.hover_timer.stop()
    
    def stop_all_actuators(self):
        """Stop everything immediately"""
        if self.sequence_timer.isActive():
            self.sequence_timer.stop()
        
        if self.api and self.api.connected:
            for actuator_id in self.config['ACTUATOR_IDS']:
                self.api.send_command(actuator_id, 0, 0, 0)
        
        self.active_steps.clear()
        self.stop_hover_feedback()

class SOAVisualizationWidget(QWidget):
    """Visualization showing SOA timing and overlaps"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 300)
        self.soa_sequence = []
        self.current_time = 0
        
    def set_soa_sequence(self, sequence: List[SOAStep]):
        """Update the SOA sequence to visualize"""
        self.soa_sequence = sequence
        self.update()
    
    def set_current_time(self, time_ms: float):
        """Update current execution time"""
        self.current_time = time_ms
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.soa_sequence:
            painter.drawText(20, 50, "No SOA sequence to display")
            return
        
        # Calculate timing bounds
        max_time = max(step.onset_time + step.duration for step in self.soa_sequence)
        if max_time <= 0:
            return
        
        # Drawing parameters
        margin = 40
        width = self.width() - 2 * margin
        height = self.height() - 2 * margin
        time_scale = width / max_time
        
        # Actuator lanes
        actuator_ids = sorted(set(step.actuator_id for step in self.soa_sequence))
        lane_height = height / len(actuator_ids) if actuator_ids else 1
        
        # Draw actuator lanes
        for i, actuator_id in enumerate(actuator_ids):
            y = margin + i * lane_height
            
            # Lane background
            painter.setPen(QPen(QColor(200, 200, 200), 1))
            painter.drawLine(margin, int(y + lane_height/2), 
                           margin + width, int(y + lane_height/2))
            
            # Actuator label
            painter.setPen(QPen(QColor(0, 0, 0)))
            font = QFont()
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(5, int(y + lane_height/2 + 5), f"Act{actuator_id}")
        
        # Draw SOA steps
        for step in self.soa_sequence:
            actuator_index = actuator_ids.index(step.actuator_id)
            y = margin + actuator_index * lane_height
            
            x_start = margin + step.onset_time * time_scale
            x_width = step.duration * time_scale
            
            # Choose color based on step type
            if step.step_type == 'physical':
                color = QColor(100, 150, 255)  # Blue for physical
            else:
                color = QColor(255, 150, 100)  # Orange for phantom
            
            # Draw step rectangle
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(0, 0, 0), 1))
            rect_height = lane_height * 0.6
            painter.drawRect(int(x_start), int(y + lane_height*0.2), 
                           int(x_width), int(rect_height))
            
            # Draw intensity as opacity
            alpha = int(255 * step.intensity)
            overlay_color = QColor(color.red(), color.green(), color.blue(), alpha)
            painter.setBrush(QBrush(overlay_color))
            painter.setPen(QPen())
            painter.drawRect(int(x_start), int(y + lane_height*0.2), 
                           int(x_width), int(rect_height))
        
        # Draw current time indicator
        if self.current_time > 0:
            x_current = margin + self.current_time * time_scale
            painter.setPen(QPen(QColor(255, 0, 0), 3))
            painter.drawLine(int(x_current), margin, int(x_current), margin + height)
        
        # Draw time axis
        painter.setPen(QPen(QColor(0, 0, 0), 1))
        painter.drawLine(margin, margin + height, margin + width, margin + height)
        
        # Time labels
        num_labels = 5
        for i in range(num_labels + 1):
            x = margin + (i * width / num_labels)
            time_val = i * max_time / num_labels
            painter.drawText(int(x - 20), margin + height + 20, f"{time_val:.0f}ms")

class TrueSOAGUI(QWidget):
    """GUI showing true SOA implementation"""
    
    def __init__(self):
        super().__init__()
        self.engine = TrueSOATactileBrush()
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
        title = QLabel("True SOA Implementation - Tactile Brush Paper")
        title.setStyleSheet("font-weight: bold; font-size: 14px;")
        layout.addWidget(title)
        
        # Connection
        conn_group = QGroupBox("Connection")
        conn_layout = QHBoxLayout(conn_group)
        
        self.device_combo = QComboBox()
        self.refresh_btn = QPushButton("Refresh")
        self.connect_btn = QPushButton("Connect")
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red;")
        
        self.refresh_btn.clicked.connect(self.refresh_devices)
        self.connect_btn.clicked.connect(self.toggle_connection)
        
        conn_layout.addWidget(QLabel("Device:"))
        conn_layout.addWidget(self.device_combo)
        conn_layout.addWidget(self.refresh_btn)
        conn_layout.addWidget(self.connect_btn)
        conn_layout.addWidget(self.status_label)
        layout.addWidget(conn_group)
        
        # SOA Visualization
        viz_group = QGroupBox("SOA Timing Visualization")
        viz_layout = QVBoxLayout(viz_group)
        
        self.soa_viz = SOAVisualizationWidget()
        viz_layout.addWidget(self.soa_viz)
        layout.addWidget(viz_group)
        
        # SOA Parameters
        soa_group = QGroupBox("SOA Parameters (from Paper)")
        soa_layout = QFormLayout(soa_group)
        
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(40, 160)
        self.duration_spin.setValue(100)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.valueChanged.connect(self.update_soa_info)
        soa_layout.addRow("Duration (per step):", self.duration_spin)
        
        self.calculated_soa_label = QLabel()
        soa_layout.addRow("Calculated SOA:", self.calculated_soa_label)
        
        layout.addWidget(soa_group)
        
        # Stroke Parameters
        stroke_group = QGroupBox("Stroke Parameters")
        stroke_layout = QFormLayout(stroke_group)
        
        self.start_pos_spin = QDoubleSpinBox()
        self.start_pos_spin.setRange(0, 130)
        self.start_pos_spin.setValue(0)
        self.start_pos_spin.setSuffix(" mm")
        stroke_layout.addRow("Start Position:", self.start_pos_spin)
        
        self.end_pos_spin = QDoubleSpinBox()
        self.end_pos_spin.setRange(0, 130)
        self.end_pos_spin.setValue(130)
        self.end_pos_spin.setSuffix(" mm")
        stroke_layout.addRow("End Position:", self.end_pos_spin)
        
        self.intensity_spin = QDoubleSpinBox()
        self.intensity_spin.setRange(0.1, 1.0)
        self.intensity_spin.setValue(0.8)
        self.intensity_spin.setDecimals(2)
        stroke_layout.addRow("Intensity:", self.intensity_spin)
        
        self.total_duration_spin = QSpinBox()
        self.total_duration_spin.setRange(500, 5000)
        self.total_duration_spin.setValue(1500)
        self.total_duration_spin.setSuffix(" ms")
        stroke_layout.addRow("Total Duration:", self.total_duration_spin)
        
        layout.addWidget(stroke_group)
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.preview_btn = QPushButton("Preview SOA")
        self.execute_btn = QPushButton("Execute Stroke")
        self.stop_btn = QPushButton("Stop All")
        
        self.preview_btn.clicked.connect(self.preview_soa)
        self.execute_btn.clicked.connect(self.execute_stroke)
        self.stop_btn.clicked.connect(self.stop_all)
        
        btn_layout.addWidget(self.preview_btn)
        btn_layout.addWidget(self.execute_btn)
        btn_layout.addWidget(self.stop_btn)
        layout.addLayout(btn_layout)
        
        # SOA Explanation
        explanation = QTextEdit()
        explanation.setMaximumHeight(120)
        explanation.setReadOnly(True)
        explanation.setPlainText("""
SOA (Stimulus Onset Asynchrony) from Tactile Brush paper:
• SOA = time between ONSETS of consecutive actuators
• Formula: SOA = 0.32 × duration + 47.3 (from psychophysical experiments)
• Actuators overlap in time to create apparent motion illusion
• Longer duration = longer SOA = slower perceived motion
• Blue bars = physical actuators, Orange bars = phantom sensations
        """.strip())
        layout.addWidget(explanation)
        
        self.update_soa_info()
    
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
                    self.status_label.setText("Connected")
                    self.status_label.setStyleSheet("color: green;")
                    self.connect_btn.setText("Disconnect")
        else:
            if self.api.disconnect_serial_device():
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: red;")
                self.connect_btn.setText("Connect")
    
    def update_soa_info(self):
        """Update SOA calculation display"""
        duration = self.duration_spin.value()
        soa = SOA_PARAMS['SLOPE'] * duration + SOA_PARAMS['BASE_MS']
        self.calculated_soa_label.setText(f"{soa:.1f} ms")
    
    def preview_soa(self):
        """Preview the SOA sequence without executing"""
        stroke = LinearStroke(
            start_position=self.start_pos_spin.value(),
            end_position=self.end_pos_spin.value(),
            intensity=self.intensity_spin.value(),
            frequency=200,
            total_duration_ms=self.total_duration_spin.value()
        )
        
        sequence = self.engine.create_soa_sequence(stroke)
        self.soa_viz.set_soa_sequence(sequence)
    
    def execute_stroke(self):
        """Execute stroke with SOA"""
        stroke = LinearStroke(
            start_position=self.start_pos_spin.value(),
            end_position=self.end_pos_spin.value(),
            intensity=self.intensity_spin.value(),
            frequency=200,
            total_duration_ms=self.total_duration_spin.value()
        )
        
        # Preview first
        sequence = self.engine.create_soa_sequence(stroke)
        self.soa_viz.set_soa_sequence(sequence)
        
        # Then execute
        self.engine.execute_stroke(stroke)
    
    def stop_all(self):
        """Stop all execution"""
        self.engine.stop_all_actuators()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("True SOA Implementation - Tactile Brush")
    
    widget = TrueSOAGUI()
    window.setCentralWidget(widget)
    window.resize(900, 800)
    window.show()
    
    sys.exit(app.exec())