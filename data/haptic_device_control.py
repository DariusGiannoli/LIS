"""
Haptic Device Control Widget - Interface Modifiée
Déplace le log en bas, la connexion en haut, et supprime "Current Event"
"""

import sys
import time
import asyncio
from typing import List, Dict, Optional
import numpy as np
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGroupBox, QLabel, 
    QLineEdit, QSpinBox, QDoubleSpinBox, QPushButton, QComboBox,
    QTextEdit, QCheckBox, QProgressBar, QMessageBox, QGridLayout
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer
from PyQt6.QtGui import QFont

from event_data_model import HapticEvent
from python_serial_api import python_serial_api


class HapticPlaybackThread(QThread):
    """Thread for playing back haptic events to the device"""
    
    progress_updated = pyqtSignal(int)  # Progress percentage
    playback_finished = pyqtSignal()
    error_occurred = pyqtSignal(str)
    
    def __init__(self, serial_api: python_serial_api, event: HapticEvent, 
                 actuator_addresses: List[int], duration: float, parent=None):
        super().__init__(parent)
        self.serial_api = serial_api
        self.event = event
        self.actuator_addresses = actuator_addresses
        self.duration = duration
        self.should_stop = False
        
    def stop(self):
        self.should_stop = True
        
    def run(self):
        """Main playback loop"""
        try:
            if not self.event.waveform_data:
                self.error_occurred.emit("No waveform data available")
                return
                
            # Get modified waveform data
            amplitude_data = self.event.get_modified_waveform()
            if amplitude_data is None:
                self.error_occurred.emit("Could not generate waveform data")
                return
                
            # Calculate timing
            sample_rate = self.event.waveform_data.sample_rate
            total_samples = len(amplitude_data)
            actual_duration = total_samples / sample_rate
            
            # Scale duration if needed
            time_scale = self.duration / actual_duration if actual_duration > 0 else 1.0
            
            # Send commands to actuators
            start_time = time.time()
            
            for i, amplitude in enumerate(amplitude_data):
                if self.should_stop:
                    break
                    
                # Calculate current time and progress
                current_time = time.time() - start_time
                progress = int((i / total_samples) * 100)
                self.progress_updated.emit(progress)
                
                # Convert amplitude to duty cycle (0-15)
                duty = int(abs(amplitude) * 15)
                duty = max(0, min(15, duty))  # Clamp to valid range
                
                # Fixed frequency for now (could be made configurable)
                freq = 4  # Mid-range frequency
                
                # Send command to all selected actuators
                for addr in self.actuator_addresses:
                    if duty > 0:
                        self.serial_api.send_command(addr, duty, freq, 1)  # Start
                    else:
                        self.serial_api.send_command(addr, 0, freq, 0)    # Stop
                
                # Wait for next sample
                sleep_time = (1.0 / sample_rate) * time_scale
                time.sleep(max(0.001, sleep_time))  # Minimum 1ms sleep
                
            # Stop all actuators at the end
            for addr in self.actuator_addresses:
                self.serial_api.send_command(addr, 0, 4, 0)
                
            self.playback_finished.emit()
            
        except Exception as e:
            self.error_occurred.emit(f"Playback error: {str(e)}")


class HapticDeviceControlWidget(QWidget):
    """Widget for controlling haptic device playback - Interface modifiée"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_api = python_serial_api()
        self.current_event: Optional[HapticEvent] = None
        self.playback_thread: Optional[HapticPlaybackThread] = None
        self.setup_ui()
        
        # Timer for device scanning
        self.scan_timer = QTimer()
        self.scan_timer.timeout.connect(self.scan_devices)
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # 1. DEVICE CONNECTION GROUP - EN HAUT
        connection_group = QGroupBox("Device Connection")
        conn_layout = QVBoxLayout(connection_group)
        
        # Device selection
        device_row = QHBoxLayout()
        device_row.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        self.device_combo.setMinimumWidth(200)
        device_row.addWidget(self.device_combo)
        
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_devices)
        device_row.addWidget(self.scan_button)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        device_row.addWidget(self.connect_button)
        
        conn_layout.addLayout(device_row)
        
        # Connection status
        self.status_label = QLabel("Disconnected")
        self.status_label.setStyleSheet("color: red; font-weight: bold;")
        conn_layout.addWidget(self.status_label)
        
        layout.addWidget(connection_group)
        
        # 2. PLAYBACK CONFIGURATION GROUP
        config_group = QGroupBox("Playback Configuration")
        config_layout = QGridLayout(config_group)
        
        # Actuator addresses
        config_layout.addWidget(QLabel("Actuator Addresses:"), 0, 0)
        self.actuator_edit = QLineEdit("0")
        self.actuator_edit.setPlaceholderText("0, 1, 2, 3 (comma-separated)")
        config_layout.addWidget(self.actuator_edit, 0, 1)
        
        # Duration
        config_layout.addWidget(QLabel("Duration (s):"), 1, 0)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 10.0)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSingleStep(0.1)
        config_layout.addWidget(self.duration_spin, 1, 1)
        
        # Intensity multiplier
        config_layout.addWidget(QLabel("Intensity:"), 2, 0)
        self.intensity_spin = QDoubleSpinBox()
        self.intensity_spin.setRange(0.1, 2.0)
        self.intensity_spin.setValue(1.0)
        self.intensity_spin.setSingleStep(0.1)
        config_layout.addWidget(self.intensity_spin, 2, 1)
        
        layout.addWidget(config_group)
        
        # 3. PLAYBACK CONTROLS
        controls_group = QGroupBox("Playback Controls")
        controls_layout = QVBoxLayout(controls_group)
        
        # Play/Stop buttons
        button_row = QHBoxLayout()
        self.play_button = QPushButton("Play Event")
        self.play_button.clicked.connect(self.play_event)
        self.play_button.setEnabled(False)
        button_row.addWidget(self.play_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.clicked.connect(self.stop_playback)
        self.stop_button.setEnabled(False)
        button_row.addWidget(self.stop_button)
        
        self.test_button = QPushButton("Test Actuators")
        self.test_button.clicked.connect(self.test_actuators)
        self.test_button.setEnabled(False)
        button_row.addWidget(self.test_button)
        
        controls_layout.addLayout(button_row)
        
        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        controls_layout.addWidget(self.progress_bar)
        
        layout.addWidget(controls_group)
        
        # 4. STATUS/LOG AREA - EN BAS
        log_group = QGroupBox("Output Log")
        log_layout = QVBoxLayout(log_group)
        
        self.log_text = QTextEdit()
        self.log_text.setMaximumHeight(150)  # Un peu plus grand
        self.log_text.setReadOnly(True)
        self.log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f8f8;
                border: 1px solid #ccc;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 10px;
            }
        """)
        log_layout.addWidget(self.log_text)
        
        # Bouton pour effacer le log
        clear_log_button = QPushButton("Clear Log")
        clear_log_button.clicked.connect(self.clear_log)
        log_layout.addWidget(clear_log_button)
        
        layout.addWidget(log_group)
        
        # Initial scan
        self.scan_devices()
        
    def clear_log(self):
        """Clear the log text"""
        self.log_text.clear()
        
    def scan_devices(self):
        """Scan for available serial devices"""
        try:
            devices = self.serial_api.get_serial_devices()
            self.device_combo.clear()
            self.device_combo.addItems(devices)
            self.log_message(f"Found {len(devices)} devices")
        except Exception as e:
            self.log_message(f"Error scanning devices: {e}")
            
    def toggle_connection(self):
        """Connect or disconnect from the selected device"""
        if self.serial_api.connected:
            if self.serial_api.disconnect_serial_device():
                self.status_label.setText("Disconnected")
                self.status_label.setStyleSheet("color: red; font-weight: bold;")
                self.connect_button.setText("Connect")
                self.play_button.setEnabled(False)
                self.test_button.setEnabled(False)
                self.log_message("Disconnected from device")
            else:
                self.log_message("Failed to disconnect")
        else:
            device_info = self.device_combo.currentText()
            if device_info and self.serial_api.connect_serial_device(device_info):
                self.status_label.setText("Connected")
                self.status_label.setStyleSheet("color: green; font-weight: bold;")
                self.connect_button.setText("Disconnect")
                self.play_button.setEnabled(self.current_event is not None)
                self.test_button.setEnabled(True)
                self.log_message(f"Connected to {device_info}")
            else:
                self.log_message("Failed to connect to device")
                
    def set_event(self, event: HapticEvent):
        """Set the current event for playback"""
        self.current_event = event
        if event:
            self.play_button.setEnabled(self.serial_api.connected)
            # Set default duration from event
            if event.waveform_data:
                self.duration_spin.setValue(event.waveform_data.duration)
                self.log_message(f"Event loaded: {event.metadata.name}")
        else:
            self.play_button.setEnabled(False)
            
    def get_actuator_addresses(self) -> List[int]:
        """Parse actuator addresses from the input field"""
        try:
            addresses_text = self.actuator_edit.text().strip()
            if not addresses_text:
                return []
            
            addresses = []
            for addr_str in addresses_text.split(','):
                addr_str = addr_str.strip()
                if addr_str:
                    addr = int(addr_str)
                    if 0 <= addr <= 127:  # Valid address range
                        addresses.append(addr)
                    else:
                        self.log_message(f"Invalid address: {addr} (must be 0-127)")
            return addresses
        except ValueError as e:
            self.log_message(f"Error parsing addresses: {e}")
            return []
            
    def play_event(self):
        """Start playing the current event"""
        if not self.current_event or not self.serial_api.connected:
            return
            
        addresses = self.get_actuator_addresses()
        if not addresses:
            self.log_message("No valid actuator addresses specified")
            return
            
        if self.playback_thread and self.playback_thread.isRunning():
            self.log_message("Playback already in progress")
            return
            
        # Apply intensity multiplier to the event
        original_intensity = self.current_event.parameter_modifications.intensity_multiplier
        self.current_event.parameter_modifications.intensity_multiplier = self.intensity_spin.value()
        
        # Start playback
        self.playback_thread = HapticPlaybackThread(
            self.serial_api, self.current_event, addresses, self.duration_spin.value()
        )
        self.playback_thread.progress_updated.connect(self.update_progress)
        self.playback_thread.playback_finished.connect(self.playback_finished)
        self.playback_thread.error_occurred.connect(self.playback_error)
        
        self.playback_thread.start()
        
        self.progress_bar.setVisible(True)
        self.play_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        
        self.log_message(f"Started playback to actuators {addresses}")
        
        # Restore original intensity
        self.current_event.parameter_modifications.intensity_multiplier = original_intensity
        
    def stop_playback(self):
        """Stop the current playback"""
        if self.playback_thread and self.playback_thread.isRunning():
            self.playback_thread.stop()
            self.playback_thread.wait(1000)  # Wait up to 1 second
            
        self.playback_finished()
        
    def test_actuators(self):
        """Test the selected actuators with a simple pulse"""
        if not self.serial_api.connected:
            return
            
        addresses = self.get_actuator_addresses()
        if not addresses:
            self.log_message("No valid actuator addresses specified")
            return
            
        self.log_message(f"Testing actuators {addresses}")
        
        # Send a short pulse to each actuator
        for addr in addresses:
            self.serial_api.send_command(addr, 10, 4, 1)  # Medium intensity, start
            
        # Stop after a short delay
        QTimer.singleShot(500, lambda: self.stop_test_actuators(addresses))
        
    def stop_test_actuators(self, addresses):
        """Stop test actuators"""
        for addr in addresses:
            self.serial_api.send_command(addr, 0, 4, 0)  # Stop
        self.log_message("Test completed")
        
    def update_progress(self, progress):
        """Update the progress bar"""
        self.progress_bar.setValue(progress)
        
    def playback_finished(self):
        """Handle playback completion"""
        self.progress_bar.setVisible(False)
        self.progress_bar.setValue(0)
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.log_message("Playback completed")
        
    def playback_error(self, error_message):
        """Handle playback errors"""
        self.progress_bar.setVisible(False)
        self.play_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.log_message(f"Playback error: {error_message}")
        
    def log_message(self, message):
        """Add a message to the log"""
        timestamp = time.strftime("%H:%M:%S")
        self.log_text.append(f"[{timestamp}] {message}")
        # Auto-scroll to bottom
        scrollbar = self.log_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def closeEvent(self, event):
        """Clean up when closing"""
        if self.playback_thread and self.playback_thread.isRunning():
            self.playback_thread.stop()
            self.playback_thread.wait(1000)
            
        if self.serial_api.connected:
            self.serial_api.disconnect_serial_device()
            
        event.accept()