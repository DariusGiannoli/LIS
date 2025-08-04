# launcher.py
import sys
import os
import subprocess
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox
from PyQt6.QtCore import Qt
from PyQt6 import uic

# Import the serial connection widget for device selection dialog
from serial_connection_widget import DeviceSelectionDialog

# Import the serial API directly
from python_serial_api import python_serial_api

class LauncherWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Load UI from .ui file
        uic.loadUi('launcher_window.ui', self)
        
        # Initialize serial API
        self.serial_api = python_serial_api()
        self.current_device = None
        
        # Track opened applications
        self.opened_processes = {
            'drone_control': None,
            'waveform_designer': None,
            'pattern_gui': None
        }
        
        # ─── Initialize Components ────────────────────────────────────────
        self.setup_ui_connections()
        self.setup_connections()
        
    def setup_ui_connections(self):
        """Setup UI element connections"""
        # Connect the connection button
        self.connectionButton.clicked.connect(self.toggle_connection)
        
    def setup_connections(self):
        """Set up signal connections and button events"""
        # Connect launcher buttons
        self.droneControlButton.clicked.connect(self.open_drone_control_gui)
        self.waveformDesignerButton.clicked.connect(self.open_waveform_designer)
        self.patternGuiButton.clicked.connect(self.open_pattern_gui)
    
    def toggle_connection(self):
        """Toggle connection state - connect if disconnected, disconnect if connected"""
        if not self.serial_api.connected:
            # Show device selection dialog
            self.show_device_selection_dialog()
        else:
            # Disconnect
            try:
                if self.serial_api.disconnect_serial_device():
                    self.update_connection_status(False)
                    print(f"Disconnected from {self.current_device}")
                    self.current_device = None
                else:
                    print("Failed to disconnect")
            except Exception as e:
                print(f"Disconnect error: {str(e)}")
    
    def show_device_selection_dialog(self):
        """Show dialog to select USB device"""
        while True:  # Loop to handle refresh
            try:
                # Get available devices
                devices = self.serial_api.get_serial_devices()
                
                # Show selection dialog
                dialog = DeviceSelectionDialog(devices, self)
                result = dialog.exec()
                
                if result == QMessageBox.StandardButton.Accepted and dialog.selected_device:
                    # User selected a device
                    selected_device = dialog.selected_device
                    if self.connect_to_device(selected_device):
                        break  # Successfully connected, exit loop
                    else:
                        # Connection failed, ask if user wants to try again
                        reply = QMessageBox.question(
                            self, 
                            "Connection Failed", 
                            f"Failed to connect to {selected_device}.\n\nWould you like to try another device?",
                            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                        )
                        if reply == QMessageBox.StandardButton.No:
                            break
                        # Continue loop to show dialog again
                
                elif result == 2:  # Refresh requested
                    continue  # Refresh and show dialog again
                
                else:
                    # User cancelled
                    break
                    
            except Exception as e:
                print(f"Error in device selection: {str(e)}")
                self.show_error_message("Error", f"Error getting device list: {str(e)}")
                break
    
    def connect_to_device(self, device_info):
        """Connect to a specific device"""
        try:
            if self.serial_api.connect_serial_device(device_info):
                self.current_device = device_info
                self.update_connection_status(True)
                print(f"Connected to {device_info}")
                return True
            else:
                print(f"Failed to connect to {device_info}")
                return False
        except Exception as e:
            print(f"Connection error: {str(e)}")
            self.show_error_message("Connection Error", str(e))
            return False
    
    def show_error_message(self, title, message):
        """Show error message to user"""
        try:
            QMessageBox.critical(self, title, message)
        except:
            # If QMessageBox fails, just print to console
            print(f"{title}: {message}")
    
    def update_connection_status(self, connected):
        """Update UI elements based on connection status"""
        if connected:
            self.statusIndicator.setStyleSheet("color: #4CAF50; font-size: 16px; font-weight: bold;")
            self.statusText.setText("Connected")
            self.statusText.setStyleSheet("color: #4CAF50; font-size: 12px; margin-left: 5px; margin-right: 10px;")
            self.connectionButton.setText("Disconnect")
            self.connectionButton.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #da190b;
                }
                QPushButton:pressed {
                    background-color: #c1170a;
                }
            """)
            # Update tooltip
            device_name = self.current_device.split(' - ')[0] if self.current_device else "Unknown"
            self.statusIndicator.setToolTip(f"Connected to {device_name}")
            # Enable module buttons when connected
            self.droneControlButton.setEnabled(True)
            self.waveformDesignerButton.setEnabled(True)
            self.patternGuiButton.setEnabled(True)
        else:
            self.statusIndicator.setStyleSheet("color: #f44336; font-size: 16px; font-weight: bold;")
            self.statusText.setText("Disconnected")
            self.statusText.setStyleSheet("color: #666; font-size: 12px; margin-left: 5px; margin-right: 10px;")
            self.connectionButton.setText("Connect USB Device")
            self.connectionButton.setStyleSheet("""
                QPushButton {
                    background-color: #4CAF50;
                    color: white;
                    font-weight: bold;
                    border: none;
                    border-radius: 6px;
                    padding: 8px 16px;
                }
                QPushButton:hover {
                    background-color: #45a049;
                }
                QPushButton:pressed {
                    background-color: #3d8b40;
                }
            """)
            self.statusIndicator.setToolTip("No device connected")
            # Keep buttons enabled even when disconnected for testing
            
        # Update window title
        if connected:
            self.setWindowTitle("Haptic Interface Launcher - CONNECTED")
        else:
            self.setWindowTitle("Haptic Interface Launcher - DISCONNECTED")
    
    def check_process_status(self, process_key):
        """Check if a process is still running"""
        if self.opened_processes[process_key] is not None:
            # Check if process is still running
            if self.opened_processes[process_key].poll() is None:
                return True  # Process is still running
            else:
                # Process has terminated, clean up
                self.opened_processes[process_key] = None
                return False
        return False
    
    def bring_window_to_front(self, process_key):
        """Attempt to bring the existing window to front (platform-specific)"""
        if sys.platform.startswith('win'):
            # On Windows, we can't easily bring subprocess windows to front
            # Show a message to the user instead
            app_names = {
                'drone_control': 'Drone Control GUI',
                'waveform_designer': 'Waveform Designer',
                'pattern_gui': 'Pattern GUI'
            }
            QMessageBox.information(
                self, 
                "Application Already Open", 
                f"{app_names[process_key]} is already running.\n\nPlease check your taskbar or open windows."
            )
        else:
            # On Unix-like systems, we could try to use window management commands
            # For now, just show the same message
            app_names = {
                'drone_control': 'Drone Control GUI',
                'waveform_designer': 'Waveform Designer',
                'pattern_gui': 'Pattern GUI'
            }
            QMessageBox.information(
                self, 
                "Application Already Open", 
                f"{app_names[process_key]} is already running.\n\nPlease check your open windows."
            )
    
    def open_drone_control_gui(self):
        """Open the Drone Control GUI"""
        # Check if already running
        if self.check_process_status('drone_control'):
            self.bring_window_to_front('drone_control')
            return
        
        try:
            # Path to the drone control main file in the drone folder
            drone_control_path = os.path.join("drone", "main.py")
            
            # Check if the file exists
            if not os.path.exists(drone_control_path):
                QMessageBox.warning(
                    self, 
                    "File Not Found", 
                    f"Could not find main.py (Drone Control GUI) in the drone folder.\nExpected path: {drone_control_path}"
                )
                return
            
            # Get the absolute path to the drone directory and main.py
            drone_dir = os.path.abspath("drone")
            main_py_path = os.path.join(drone_dir, "main.py")
            
            # Try to run the drone control GUI as a separate process
            # Set the working directory to the drone folder
            if sys.platform.startswith('win'):
                # Windows
                process = subprocess.Popen([sys.executable, main_py_path], 
                                         cwd=drone_dir,
                                         creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Unix/Linux/Mac
                process = subprocess.Popen([sys.executable, main_py_path], 
                                         cwd=drone_dir)
            
            # Store the process reference
            self.opened_processes['drone_control'] = process
            print(f"Opened Drone Control GUI: {drone_control_path}")
            
        except FileNotFoundError:
            QMessageBox.critical(
                self, 
                "Error", 
                "Python interpreter not found. Cannot launch Drone Control GUI."
            )
        except subprocess.SubprocessError as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to launch Drone Control GUI:\n{str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Unexpected error when launching Drone Control GUI:\n{str(e)}"
            )
    
    def open_waveform_designer(self):
        """Open the Waveform Designer (Universal Event Designer)"""
        # Check if already running
        if self.check_process_status('waveform_designer'):
            self.bring_window_to_front('waveform_designer')
            return
        
        try:
            # Path to the waveform designer in the data subfolder
            waveform_designer_path = os.path.join("data", "universal_event_designer.py")
            
            # Check if the file exists
            if not os.path.exists(waveform_designer_path):
                QMessageBox.warning(
                    self, 
                    "File Not Found", 
                    f"Could not find universal_event_designer.py in the data folder.\nExpected path: {waveform_designer_path}"
                )
                return
            
            # Try to run the waveform designer as a separate process
            if sys.platform.startswith('win'):
                # Windows
                process = subprocess.Popen([sys.executable, waveform_designer_path], 
                                         creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Unix/Linux/Mac
                process = subprocess.Popen([sys.executable, waveform_designer_path])
            
            # Store the process reference
            self.opened_processes['waveform_designer'] = process
            print(f"Opened Waveform Designer: {waveform_designer_path}")
            
        except FileNotFoundError:
            QMessageBox.critical(
                self, 
                "Error", 
                "Python interpreter not found. Cannot launch Waveform Designer."
            )
        except subprocess.SubprocessError as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to launch Waveform Designer:\n{str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Unexpected error when launching Waveform Designer:\n{str(e)}"
            )
    
    def open_pattern_gui(self):
        """Open the Pattern GUI (Haptic Pattern GUI)"""
        # Check if already running
        if self.check_process_status('pattern_gui'):
            self.bring_window_to_front('pattern_gui')
            return
        
        try:
            # Path to the pattern GUI in the Pattern_Generator subfolder
            pattern_gui_path = os.path.join("Pattern_Generator", "haptic_pattern_gui.py")
            
            # Check if the file exists
            if not os.path.exists(pattern_gui_path):
                QMessageBox.warning(
                    self, 
                    "File Not Found", 
                    f"Could not find haptic_pattern_gui.py in the Pattern_Generator folder.\nExpected path: {pattern_gui_path}"
                )
                return
            
            # Try to run the pattern GUI as a separate process
            if sys.platform.startswith('win'):
                # Windows
                process = subprocess.Popen([sys.executable, pattern_gui_path], 
                                         creationflags=subprocess.CREATE_NEW_CONSOLE)
            else:
                # Unix/Linux/Mac
                process = subprocess.Popen([sys.executable, pattern_gui_path])
            
            # Store the process reference
            self.opened_processes['pattern_gui'] = process
            print(f"Opened Pattern GUI: {pattern_gui_path}")
            
        except FileNotFoundError:
            QMessageBox.critical(
                self, 
                "Error", 
                "Python interpreter not found. Cannot launch Pattern GUI."
            )
        except subprocess.SubprocessError as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Failed to launch Pattern GUI:\n{str(e)}"
            )
        except Exception as e:
            QMessageBox.critical(
                self, 
                "Error", 
                f"Unexpected error when launching Pattern GUI:\n{str(e)}"
            )
    
    def get_serial_api(self):
        """Get the serial API instance for use by other components"""
        return self.serial_api
    
    def is_connected(self):
        """Check if currently connected to a device"""
        return self.serial_api.connected
    
    def get_current_device(self):
        """Get the currently connected device name"""
        return self.current_device
    
    def closeEvent(self, event):
        """Clean up when the main window is closed"""
        # Ensure serial connection is properly closed
        if self.serial_api.connected:
            self.serial_api.disconnect_serial_device()
        
        # Terminate any running processes
        for process_key, process in self.opened_processes.items():
            if process is not None and process.poll() is None:
                try:
                    process.terminate()
                    print(f"Terminated {process_key} process")
                except:
                    pass
        
        super().closeEvent(event)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = LauncherWindow()
    w.resize(500, 400)
    w.show()
    sys.exit(app.exec())