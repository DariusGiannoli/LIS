#!/usr/bin/env python3
"""
paper_accurate_soa.py

SOA implementation exactly matching the Tactile Brush paper methodology:
- Based on Neuhaus 1930 experiments
- SOA = Inter-stimulus onset asynchrony 
- Duration and SOA relationship from psychophysical experiments
- Proper overlapping for continuous apparent motion
- Modified for 5 actuators instead of 3
"""
import sys
import time
from dataclasses import dataclass
from typing import List
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QSpinBox, QDoubleSpinBox, QFormLayout, QGroupBox,
    QApplication, QMainWindow, QComboBox, QTextEdit, QSlider,
    QCheckBox
)
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont

# Import your API
try:
    from python_serial_api import python_serial_api
except ImportError:
    print("Warning: python_serial_api not found.")
    python_serial_api = None

# Your 5-actuator configuration
ACTUATORS = [0, 1, 2, 3, 4]

# Paper's psychophysical parameters (from Figure 4)
PAPER_PARAMS = {
    # From paper's equation: SOA = 0.32d + 47.3
    'SOA_SLOPE': 0.32,
    'SOA_BASE': 47.3,
    
    # From paper's experiments (Figure 4)
    # These are the validated ranges for robust apparent motion
    'MIN_DURATION': 40,    # ms
    'MAX_DURATION': 160,   # ms
    'OPTIMAL_FREQ': 200,   # Hz
    
    # Critical: For continuous motion, duration must be > SOA
    # This ensures overlap between consecutive stimuli
}

@dataclass
class SOAStep:
    actuator_id: int
    onset_time: float      # When to start (ms)
    duration: float        # How long to vibrate (ms)
    intensity: float       # Constant for apparent motion

class PaperSOATester:
    """SOA implementation following paper's exact methodology"""
    
    def __init__(self, api=None):
        self.api = api
        
        # Execution state
        self.steps = []
        self.timer = QTimer()
        self.timer.timeout.connect(self.execute_step)
        self.start_time = 0
        self.next_step_idx = 0
        self.active_actuators = {}  # {actuator_id: stop_time}
        
    def calculate_paper_soa(self, duration_ms: float) -> float:
        """
        Calculate SOA using paper's validated equation:
        SOA = 0.32 × duration + 47.3
        
        This comes from psychophysical experiments (Neuhaus 1930, Figure 4)
        """
        soa = PAPER_PARAMS['SOA_SLOPE'] * duration_ms + PAPER_PARAMS['SOA_BASE']
        return soa
    
    def validate_parameters(self, duration_ms: float) -> tuple:
        """
        Validate parameters according to paper's findings
        Returns: (is_valid, adjusted_duration, calculated_soa, warning_msg)
        """
        soa = self.calculate_paper_soa(duration_ms)
        warnings = []
        
        # Critical validation from paper:
        # For apparent motion, duration MUST be longer than SOA for overlap
        if duration_ms <= soa:
            warnings.append(f"Duration ({duration_ms}ms) <= SOA ({soa:.1f}ms) - No overlap! Motion will be discrete.")
        
        # Paper's validated range
        if duration_ms < PAPER_PARAMS['MIN_DURATION']:
            warnings.append(f"Duration below paper's minimum ({PAPER_PARAMS['MIN_DURATION']}ms)")
        elif duration_ms > PAPER_PARAMS['MAX_DURATION']:
            warnings.append(f"Duration above paper's maximum ({PAPER_PARAMS['MAX_DURATION']}ms)")
        
        # Calculate overlap duration
        overlap_ms = duration_ms - soa
        if overlap_ms > 0:
            overlap_pct = (overlap_ms / duration_ms) * 100
            warnings.append(f"Overlap: {overlap_ms:.1f}ms ({overlap_pct:.0f}% of duration)")
        
        return (len(warnings) == 0 or overlap_ms > 0, duration_ms, soa, warnings)
    
    def create_paper_soa_sequence(self, actuator_sequence: List[int], duration_ms: float, 
                                intensity: float) -> tuple:
        """
        Create SOA sequence following paper's methodology
        Returns: (steps, validation_info)
        """
        is_valid, adj_duration, soa, warnings = self.validate_parameters(duration_ms)
        
        steps = []
        print(f"\n=== Paper SOA Analysis ===")
        print(f"Duration: {adj_duration}ms")
        print(f"Calculated SOA: {soa:.1f}ms")
        print(f"Overlap: {adj_duration - soa:.1f}ms")
        
        if warnings:
            print("Warnings:")
            for warning in warnings:
                print(f"  - {warning}")
        
        # Create sequence with proper SOA timing
        for i, actuator_id in enumerate(actuator_sequence):
            onset_time = i * soa
            
            step = SOAStep(
                actuator_id=actuator_id,
                onset_time=onset_time,
                duration=adj_duration,
                intensity=intensity
            )
            steps.append(step)
            
            print(f"Step {i}: Act{actuator_id} onset={onset_time:.1f}ms, duration={adj_duration}ms")
        
        # Calculate total sequence time
        total_time = (len(actuator_sequence) - 1) * soa + adj_duration
        print(f"Total sequence: {total_time:.1f}ms")
        
        # Analyze overlaps
        print("\nOverlap Analysis:")
        for i in range(len(steps) - 1):
            curr_step = steps[i]
            next_step = steps[i + 1]
            
            curr_end = curr_step.onset_time + curr_step.duration
            next_start = next_step.onset_time
            
            if curr_end > next_start:
                overlap = curr_end - next_start
                print(f"  Act{curr_step.actuator_id}↔Act{next_step.actuator_id}: {overlap:.1f}ms overlap")
            else:
                gap = next_start - curr_end
                print(f"  Act{curr_step.actuator_id}↔Act{next_step.actuator_id}: {gap:.1f}ms GAP (motion will be discrete!)")
        
        print("=" * 40)
        
        return steps, warnings
    
    def execute_sequence(self, steps: List[SOAStep]):
        """Execute SOA sequence with precise timing"""
        if not self.api or not self.api.connected:
            print("No API connection")
            return
        
        self.steps = steps
        self.next_step_idx = 0
        self.active_actuators = {}
        
        if not self.steps:
            return
        
        print(f"\n🚀 Executing SOA sequence ({len(self.steps)} steps)")
        self.start_time = time.time() * 1000
        self.timer.start(1)  # 1ms precision
    
    def execute_step(self):
        """Execute with precise timing"""
        current_time = time.time() * 1000 - self.start_time
        
        # Start new steps
        while (self.next_step_idx < len(self.steps) and 
               self.steps[self.next_step_idx].onset_time <= current_time):
            
            step = self.steps[self.next_step_idx]
            
            # Convert intensity to device range (1-15)
            device_intensity = max(1, min(15, int(step.intensity * 15)))
            freq = 4  # Mid-range
            
            # Start actuator
            success = self.api.send_command(step.actuator_id, device_intensity, freq, 1)
            
            if success:
                stop_time = current_time + step.duration
                self.active_actuators[step.actuator_id] = stop_time
                
                print(f"⚡ Act{step.actuator_id} ON at {current_time:.1f}ms "
                      f"(will stop at {stop_time:.1f}ms)")
            
            self.next_step_idx += 1
        
        # Stop actuators when duration expires
        to_stop = []
        for actuator_id, stop_time in self.active_actuators.items():
            if current_time >= stop_time:
                self.api.send_command(actuator_id, 0, 0, 0)
                print(f"⏹️  Act{actuator_id} OFF at {current_time:.1f}ms")
                to_stop.append(actuator_id)
        
        for actuator_id in to_stop:
            del self.active_actuators[actuator_id]
        
        # Check completion
        if (self.next_step_idx >= len(self.steps) and 
            len(self.active_actuators) == 0):
            self.timer.stop()
            print("✅ SOA sequence complete\n")
    
    def stop_all(self):
        """Emergency stop"""
        self.timer.stop()
        if self.api and self.api.connected:
            for actuator_id in ACTUATORS:
                self.api.send_command(actuator_id, 0, 0, 0)
        self.active_actuators = {}
        print("🛑 All stopped")

class PaperSOAVisualization(QWidget):
    """Accurate visualization of SOA timing"""
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(700, 300)  # Increased height for 5 actuators
        self.steps = []
        self.warnings = []
        
    def set_sequence(self, steps: List[SOAStep], warnings: List[str]):
        self.steps = steps
        self.warnings = warnings
        self.update()
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        if not self.steps:
            painter.drawText(20, 50, "No sequence - click 'Preview' to generate")
            return
        
        # Calculate bounds
        max_time = max(step.onset_time + step.duration for step in self.steps)
        if max_time <= 0:
            return
        
        margin = 80
        width = self.width() - 2 * margin
        height = self.height() - 100  # Space for warnings
        time_scale = width / max_time
        
        # Draw title
        painter.setPen(QPen(QColor(0, 0, 0)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(margin, 25, "SOA Timing Visualization (5 Actuators)")
        
        # Draw time axis
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        y_base = margin + height - 20
        painter.drawLine(margin, y_base, margin + width, y_base)
        
        # Time labels
        for i in range(6):
            x = margin + (i * width / 5)
            time_val = i * max_time / 5
            painter.drawLine(int(x), y_base - 5, int(x), y_base + 5)
            painter.drawText(int(x - 25), y_base + 20, f"{time_val:.0f}ms")
        
        # Draw actuator lanes and steps
        actuator_ids = sorted(set(step.actuator_id for step in self.steps))
        lane_height = (height - 40) / len(actuator_ids)
        
        # Extended color palette for 5 actuators
        colors = [
            QColor(100, 150, 255),  # Blue
            QColor(255, 150, 100),  # Orange  
            QColor(150, 255, 100),  # Green
            QColor(255, 100, 150),  # Pink
            QColor(150, 100, 255)   # Purple
        ]
        
        for step in self.steps:
            actuator_idx = actuator_ids.index(step.actuator_id)
            y = margin + actuator_idx * lane_height
            
            x_start = margin + step.onset_time * time_scale
            x_width = step.duration * time_scale
            rect_height = lane_height * 0.6
            
            # Draw step bar
            color = colors[step.actuator_id % len(colors)]
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(QColor(0, 0, 0), 2))
            painter.drawRect(int(x_start), int(y + lane_height*0.2), 
                           int(x_width), int(rect_height))
            
            # Actuator label
            painter.setPen(QPen(QColor(0, 0, 0)))
            font.setBold(True)
            font.setPointSize(11)
            painter.setFont(font)
            painter.drawText(10, int(y + lane_height/2 + 5), f"Act {step.actuator_id}")
            
            # Timing info on bar
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(9)
            painter.setFont(font)
            painter.drawText(int(x_start + 5), int(y + lane_height/2 + 3), 
                           f"⏰{step.onset_time:.0f}ms")
        
        # Draw overlap indicators
        painter.setPen(QPen(QColor(255, 0, 0), 3))
        for i in range(len(self.steps) - 1):
            curr = self.steps[i]
            next_step = self.steps[i + 1]
            
            curr_end_time = curr.onset_time + curr.duration
            next_start_time = next_step.onset_time
            
            if curr_end_time > next_start_time:  # Overlap
                overlap_start = margin + next_start_time * time_scale
                overlap_end = margin + curr_end_time * time_scale
                
                # Draw overlap region
                painter.fillRect(int(overlap_start), margin + 10, 
                               int(overlap_end - overlap_start), height - 50, 
                               QColor(255, 0, 0, 50))
                
                # Label
                painter.setPen(QPen(QColor(255, 0, 0)))
                font.setBold(True)
                painter.setFont(font)
                overlap_ms = curr_end_time - next_start_time
                painter.drawText(int((overlap_start + overlap_end)/2 - 25), margin + 30, 
                               f"Overlap: {overlap_ms:.0f}ms")
        
        # Draw warnings
        if self.warnings:
            y_warn = self.height() - 60
            painter.setPen(QPen(QColor(200, 0, 0)))
            font.setBold(False)
            font.setPointSize(10)
            painter.setFont(font)
            
            for i, warning in enumerate(self.warnings[:3]):  # Show max 3 warnings
                painter.drawText(10, y_warn + i * 15, f"⚠️  {warning}")

class PaperSOAGUI(QWidget):
    """GUI following paper's exact SOA methodology"""
    
    def __init__(self):
        super().__init__()
        self.tester = PaperSOATester()
        self.api = None
        self.setup_ui()
        self.setup_api()
    
    def setup_api(self):
        if python_serial_api:
            self.api = python_serial_api()
            self.tester.api = self.api
            self.refresh_devices()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Title
        title = QLabel("Paper-Accurate SOA Implementation (5 Actuators)")
        title.setStyleSheet("font-weight: bold; font-size: 16px; color: #2E86AB;")
        layout.addWidget(title)
        
        subtitle = QLabel("Following Tactile Brush paper's psychophysical parameters")
        subtitle.setStyleSheet("font-style: italic; color: #666;")
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
        
        # Paper Parameters
        paper_group = QGroupBox("Paper's Psychophysical Parameters")
        paper_layout = QFormLayout(paper_group)
        
        # Duration with paper's range
        self.duration_spin = QSpinBox()
        self.duration_spin.setRange(40, 2000)   # Extended range to allow 1 second
        self.duration_spin.setValue(80)         # Changed to 80ms (within paper's range)
        self.duration_spin.setSuffix(" ms")
        self.duration_spin.valueChanged.connect(self.update_analysis)
        paper_layout.addRow("Duration (paper: 40-160ms, extended):", self.duration_spin)
        
        # Calculated SOA (read-only)
        self.soa_label = QLabel()
        paper_layout.addRow("SOA (0.32×d + 47.3):", self.soa_label)
        
        # Overlap analysis
        self.overlap_label = QLabel()
        paper_layout.addRow("Overlap (duration - SOA):", self.overlap_label)
        
        # Intensity
        self.intensity_spin = QDoubleSpinBox()
        self.intensity_spin.setRange(0.2, 1.0)
        self.intensity_spin.setValue(0.8)
        self.intensity_spin.setDecimals(2)
        paper_layout.addRow("Intensity:", self.intensity_spin)
        
        layout.addWidget(paper_group)
        
        # Test Sequences
        test_group = QGroupBox("Test Sequences (5 Actuators)")
        test_layout = QVBoxLayout(test_group)
        
        # Quick tests - first row
        quick_layout1 = QHBoxLayout()
        
        self.left_right_btn = QPushButton("Left→Right\n(0→1→2→3→4)")
        self.right_left_btn = QPushButton("Right→Left\n(4→3→2→1→0)")
        self.preview_btn = QPushButton("Preview Only\n(no execution)")
        
        self.left_right_btn.clicked.connect(lambda: self.test_sequence([0, 1, 2, 3, 4]))
        self.right_left_btn.clicked.connect(lambda: self.test_sequence([4, 3, 2, 1, 0]))
        self.preview_btn.clicked.connect(lambda: self.preview_sequence([0, 1, 2, 3, 4]))
        
        quick_layout1.addWidget(self.left_right_btn)
        quick_layout1.addWidget(self.right_left_btn)
        quick_layout1.addWidget(self.preview_btn)
        
        # Additional test patterns - second row
        quick_layout2 = QHBoxLayout()
        
        self.odd_even_btn = QPushButton("Odd→Even\n(0→2→4→1→3)")
        self.center_out_btn = QPushButton("Center Out\n(2→1→3→0→4)")
        self.bounce_btn = QPushButton("Bounce\n(0→4→0→4)")
        
        self.odd_even_btn.clicked.connect(lambda: self.test_sequence([0, 2, 4, 1, 3]))
        self.center_out_btn.clicked.connect(lambda: self.test_sequence([2, 1, 3, 0, 4]))
        self.bounce_btn.clicked.connect(lambda: self.test_sequence([0, 4, 0, 4]))
        
        quick_layout2.addWidget(self.odd_even_btn)
        quick_layout2.addWidget(self.center_out_btn)
        quick_layout2.addWidget(self.bounce_btn)
        
        # Style buttons
        button_style = """
        QPushButton {
            padding: 10px;
            font-size: 10px;
            border-radius: 5px;
            background-color: #E8F4FD;
            border: 2px solid #2E86AB;
        }
        QPushButton:hover {
            background-color: #2E86AB;
            color: white;
        }
        """
        for btn in [self.left_right_btn, self.right_left_btn, self.preview_btn,
                   self.odd_even_btn, self.center_out_btn, self.bounce_btn]:
            btn.setStyleSheet(button_style)
        
        test_layout.addLayout(quick_layout1)
        test_layout.addLayout(quick_layout2)
        layout.addWidget(test_group)
        
        # Visualization
        viz_group = QGroupBox("SOA Timing Analysis")
        viz_layout = QVBoxLayout(viz_group)
        
        self.viz = PaperSOAVisualization()
        viz_layout.addWidget(self.viz)
        layout.addWidget(viz_group)
        
        # Controls
        control_layout = QHBoxLayout()
        
        self.stop_btn = QPushButton("🛑 STOP ALL")
        self.stop_btn.clicked.connect(self.stop_all)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #FF6B6B; color: white; font-weight: bold; padding: 8px; }")
        
        control_layout.addStretch()
        control_layout.addWidget(self.stop_btn)
        layout.addLayout(control_layout)
        
        # Paper explanation
        explanation = QTextEdit()
        explanation.setMaximumHeight(100)
        explanation.setReadOnly(True)
        explanation.setPlainText("""
Paper's Key Finding: For continuous apparent motion, stimuli MUST overlap in time.
• Duration > SOA ensures overlap between consecutive actuators
• SOA = 0.32 × duration + 47.3 (from psychophysical experiments)
• Red regions show overlaps - these create the motion illusion
• No overlap = discrete sensations, not smooth motion
• Now testing with 5 actuators for longer motion sequences
        """.strip())
        layout.addWidget(explanation)
        
        self.update_analysis()
    
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
    
    def update_analysis(self):
        """Update SOA analysis display"""
        duration = self.duration_spin.value()
        soa = PAPER_PARAMS['SOA_SLOPE'] * duration + PAPER_PARAMS['SOA_BASE']
        overlap = duration - soa
        
        self.soa_label.setText(f"{soa:.1f} ms")
        
        if overlap > 0:
            self.overlap_label.setText(f"{overlap:.1f} ms ✓ (will create motion)")
            self.overlap_label.setStyleSheet("color: green; font-weight: bold;")
        else:
            self.overlap_label.setText(f"{overlap:.1f} ms ✗ (discrete, not continuous)")
            self.overlap_label.setStyleSheet("color: red; font-weight: bold;")
    
    def preview_sequence(self, actuator_ids):
        """Preview without executing"""
        duration = self.duration_spin.value()
        intensity = self.intensity_spin.value()
        
        steps, warnings = self.tester.create_paper_soa_sequence(actuator_ids, duration, intensity)
        self.viz.set_sequence(steps, warnings)
    
    def test_sequence(self, actuator_ids):
        """Execute SOA test"""
        duration = self.duration_spin.value()
        intensity = self.intensity_spin.value()
        
        steps, warnings = self.tester.create_paper_soa_sequence(actuator_ids, duration, intensity)
        self.viz.set_sequence(steps, warnings)
        self.tester.execute_sequence(steps)
    
    def stop_all(self):
        self.tester.stop_all()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Paper-Accurate SOA Implementation (5 Actuators)")
    
    widget = PaperSOAGUI()
    window.setCentralWidget(widget)
    window.resize(900, 900)  # Increased height for additional buttons
    window.show()
    
    sys.exit(app.exec())