import tkinter as tk
from tkinter import ttk, messagebox
import time
import sys
import os
import random
from threading import Thread

######
# Add root directory to path (from interface_ble/ directory, go up one level to reach root)
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)
from core.hardware.ble.python_ble_api import python_ble_api
from core.study_params import DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES

class SinglePointTesterGUI:
    """
    GUI Interface for Single Point Haptic Testing - Bluetooth Version
    
    Allows testing individual actuators with buzz and pulse patterns
    in both manual and automatic randomized modes.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Single Point Haptic Tester - Bluetooth")
        self.root.geometry("900x700")
        self.root.configure(bg='white')
        
        # API and connection
        self.api = python_ble_api()
        self.connected_device = None
        
        # Pattern management
        self.actuator_addresses = list(range(16))  # Actuators 0-15
        self.pattern_list = []
        self.current_pattern_index = 0
        
        # Current pattern being played
        self.current_actuator = None
        self.current_pattern_type = None
        
        # GUI setup
        self.setup_gui()
        self.create_all_patterns()
        
    def setup_gui(self):
        """Setup the main GUI interface"""
        # Main container
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=20)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.title_label = ttk.Label(
            header_frame, 
            text="Single Point Haptic Tester - Bluetooth",
            font=('Arial', 16, 'bold')
        )
        self.title_label.pack()
        
        self.status_label = ttk.Label(
            header_frame, 
            text="Status: Not connected",
            font=('Arial', 12)
        )
        self.status_label.pack(pady=5)
        
        # Connection frame
        conn_frame = ttk.Frame(header_frame)
        conn_frame.pack(pady=10)
        
        # BLE device selection
        ttk.Label(conn_frame, text="BLE Device:").pack(side=tk.LEFT, padx=5)
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(conn_frame, textvariable=self.device_var, 
                                        width=25, state="readonly")
        self.device_combo.pack(side=tk.LEFT, padx=5)
        
        self.scan_button = ttk.Button(
            conn_frame, text="Scan BLE", command=self.scan_ble_devices
        )
        self.scan_button.pack(side=tk.LEFT, padx=5)
        
        self.connect_button = ttk.Button(
            conn_frame, text="Connect", command=self.connect_device, state=tk.DISABLED
        )
        self.connect_button.pack(side=tk.LEFT, padx=5)
        
        self.emergency_button = ttk.Button(
            conn_frame, text="Emergency Stop", command=self.emergency_stop_all, state=tk.DISABLED
        )
        self.emergency_button.pack(side=tk.LEFT, padx=10)
        
        # Mode selection frame
        mode_frame = ttk.LabelFrame(main_frame, text="Testing Mode", padding=10)
        mode_frame.pack(fill=tk.X, pady=(0, 20))
        
        # Manual mode
        manual_frame = ttk.Frame(mode_frame)
        manual_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Label(manual_frame, text="Manual Testing:", font=('Arial', 12, 'bold')).pack(anchor='w')
        
        manual_controls = ttk.Frame(manual_frame)
        manual_controls.pack(fill=tk.X, pady=5)
        
        ttk.Label(manual_controls, text="Pattern Type:").pack(side=tk.LEFT, padx=5)
        self.pattern_type_var = tk.StringVar(value="buzz")
        buzz_radio = ttk.Radiobutton(manual_controls, text="Buzz", variable=self.pattern_type_var, value="buzz")
        pulse_radio = ttk.Radiobutton(manual_controls, text="Pulse", variable=self.pattern_type_var, value="pulse")
        buzz_radio.pack(side=tk.LEFT, padx=5)
        pulse_radio.pack(side=tk.LEFT, padx=5)
        
        # Actuator grid
        grid_frame = ttk.Frame(mode_frame)
        grid_frame.pack(pady=10)
        
        ttk.Label(grid_frame, text="Click actuator to test:", font=('Arial', 10)).pack()
        
        # Create 4x4 grid of actuator buttons
        self.actuator_buttons = []
        actuator_grid = ttk.Frame(grid_frame)
        actuator_grid.pack(pady=5)
        
        for i in range(16):
            row = i // 4
            col = i % 4
            
            button = tk.Button(
                actuator_grid,
                text=f"A{i}",
                command=lambda addr=i: self.test_single_actuator(addr),
                state=tk.DISABLED,
                width=6,
                height=2,
                font=('Arial', 10, 'bold')
            )
            button.grid(row=row, column=col, padx=2, pady=2)
            self.actuator_buttons.append(button)
        
        # Separator
        ttk.Separator(mode_frame, orient='horizontal').pack(fill=tk.X, pady=10)
        
        # Auto mode
        auto_frame = ttk.Frame(mode_frame)
        auto_frame.pack(fill=tk.X)
        
        ttk.Label(auto_frame, text="Automatic Testing:", font=('Arial', 12, 'bold')).pack(anchor='w')
        
        auto_controls = ttk.Frame(auto_frame)
        auto_controls.pack(fill=tk.X, pady=5)
        
        self.play_next_button = ttk.Button(
            auto_controls, text="Play Next Pattern", command=self.play_next_pattern, state=tk.DISABLED
        )
        self.play_next_button.pack(side=tk.LEFT, padx=5)
        
        self.repeat_button = ttk.Button(
            auto_controls, text="Repeat Current", command=self.repeat_current_pattern, state=tk.DISABLED
        )
        self.repeat_button.pack(side=tk.LEFT, padx=5)
        
        self.shuffle_button = ttk.Button(
            auto_controls, text="Shuffle Patterns", command=self.shuffle_patterns, state=tk.DISABLED
        )
        self.shuffle_button.pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.progress_label = ttk.Label(progress_frame, text="Progress: 0/32", font=('Arial', 12))
        self.progress_label.pack()
        
        self.current_pattern_label = ttk.Label(
            progress_frame, text="Current: None", font=('Arial', 10), foreground='blue'
        )
        self.current_pattern_label.pack(pady=2)
        
        # Instructions
        instructions_frame = ttk.Frame(main_frame)
        instructions_frame.pack(fill=tk.X)
        
        self.instruction_text = ttk.Label(
            instructions_frame,
            text="Click 'Scan BLE' to find devices, then connect to start testing.\n"
                 "Manual: Select pattern type and click actuator buttons\n"
                 "Auto: Use 'Play Next Pattern' to cycle through all combinations",
            font=('Arial', 10),
            foreground='gray'
        )
        self.instruction_text.pack()
        
    def scan_ble_devices(self):
        """Scan for available BLE devices"""
        self.instruction_text.config(text="Scanning for BLE devices...")
        self.scan_button.config(state=tk.DISABLED)
        
        def scan_thread():
            try:
                devices = self.api.get_ble_devices()
                filtered_devices = [d for d in devices if d and d != '']
                self.root.after(0, lambda: self._update_device_list(filtered_devices))
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Scan Error", f"Failed to scan BLE devices: {e}"))
                self.root.after(0, lambda: self.scan_button.config(state=tk.NORMAL))
        
        Thread(target=scan_thread, daemon=True).start()
    
    def _update_device_list(self, devices):
        """Update the device combo box with found devices"""
        self.scan_button.config(state=tk.NORMAL)
        
        if not devices:
            messagebox.showinfo("BLE Scan", "No BLE devices found.")
            self.instruction_text.config(text="No BLE devices found. Try scanning again.")
            return
        
        self.device_combo['values'] = devices
        if devices:
            self.device_combo.current(0)
            self.connect_button.config(state=tk.NORMAL)
        
        self.instruction_text.config(text=f"Found {len(devices)} BLE device(s). Select and click 'Connect'.")
    
    def connect_device(self):
        """Connect to the selected BLE device"""
        selected_device = self.device_var.get()
        if not selected_device:
            messagebox.showwarning("Device Selection", "Please select a BLE device first.")
            return
        
        self.instruction_text.config(text=f"Connecting to {selected_device}...")
        self.connect_button.config(state=tk.DISABLED)
        
        def connect_thread():
            try:
                connected = self.api.connect_ble_device(selected_device)
                self.root.after(0, lambda: self._handle_connection_result(connected, selected_device))
            except Exception as e:
                self.root.after(0, lambda: self._handle_connection_error(e))
        
        Thread(target=connect_thread, daemon=True).start()
    
    def _handle_connection_result(self, connected, device_name):
        """Handle the result of BLE connection attempt"""
        if connected:
            self.connected_device = device_name
            self.status_label.config(text=f"Status: Connected to {device_name}")
            self.device_combo.config(state=tk.DISABLED)
            self.scan_button.config(state=tk.DISABLED)
            self.emergency_button.config(state=tk.NORMAL)
            
            # Enable testing controls
            for button in self.actuator_buttons:
                button.config(state=tk.NORMAL)
            self.play_next_button.config(state=tk.NORMAL)
            self.repeat_button.config(state=tk.NORMAL)
            self.shuffle_button.config(state=tk.NORMAL)
            
            self.instruction_text.config(text=f"Connected to {device_name}! Ready to test actuators.")
            messagebox.showinfo("Connection", f"Successfully connected to {device_name}!")
        else:
            self.connect_button.config(state=tk.NORMAL)
            self.instruction_text.config(text="Failed to connect. Try a different device.")
            messagebox.showerror("Connection", f"Failed to connect to {device_name}.")
    
    def _handle_connection_error(self, error):
        """Handle connection error"""
        self.connect_button.config(state=tk.NORMAL)
        self.instruction_text.config(text="Connection error occurred.")
        messagebox.showerror("Connection Error", f"Error during connection: {error}")
    
    def create_all_patterns(self):
        """Create all buzz and pulse patterns for all actuators and randomize them"""
        patterns = []
        
        # Create buzz patterns for all actuators
        for addr in self.actuator_addresses:
            patterns.append({
                'addr': addr,
                'type': 'buzz',
                'name': f"Actuator {addr} (Buzz)"
            })
            
        # Create pulse patterns for all actuators
        for addr in self.actuator_addresses:
            patterns.append({
                'addr': addr,
                'type': 'pulse',
                'name': f"Actuator {addr} (Pulse)"
            })
            
        # Randomize the order
        random.shuffle(patterns)
        self.pattern_list = patterns
        self.current_pattern_index = 0
        self.update_progress_display()
    
    def shuffle_patterns(self):
        """Shuffle the pattern list and reset to beginning"""
        random.shuffle(self.pattern_list)
        self.current_pattern_index = 0
        self.update_progress_display()
        self.instruction_text.config(text="Patterns shuffled! Ready to test in new random order.")
    
    def update_progress_display(self):
        """Update the progress and current pattern display"""
        total = len(self.pattern_list)
        current = self.current_pattern_index + 1
        self.progress_label.config(text=f"Progress: {current}/{total}")
        
        if self.pattern_list:
            current_pattern = self.pattern_list[self.current_pattern_index]
            self.current_pattern_label.config(text=f"Next: {current_pattern['name']}")
    
    def test_single_actuator(self, addr):
        """Test a single actuator with the selected pattern type"""
        if not self.connected_device:
            messagebox.showwarning("Not Connected", "Please connect to a BLE device first.")
            return
        
        pattern_type = self.pattern_type_var.get()
        self.current_actuator = addr
        self.current_pattern_type = pattern_type
        
        # Update status
        self.instruction_text.config(text=f"Testing Actuator {addr} ({pattern_type})...")
        
        # Disable button temporarily
        self.actuator_buttons[addr].config(state=tk.DISABLED, bg='yellow')
        
        def test_thread():
            try:
                if pattern_type == "buzz":
                    success = self.send_buzz_pattern(addr)
                else:
                    success = self.send_pulse_pattern(addr)
                
                self.root.after(0, lambda: self._pattern_finished(addr, success))
            except Exception as e:
                self.root.after(0, lambda: self._pattern_error(addr, e))
        
        Thread(target=test_thread, daemon=True).start()
    
    def _pattern_finished(self, addr, success):
        """Called when pattern finishes"""
        if success:
            self.actuator_buttons[addr].config(state=tk.NORMAL, bg='lightgreen')
            self.instruction_text.config(text=f"Actuator {addr} test completed successfully!")
        else:
            self.actuator_buttons[addr].config(state=tk.NORMAL, bg='lightcoral')
            self.instruction_text.config(text=f"Actuator {addr} test failed!")
        
        # Reset color after 2 seconds
        self.root.after(2000, lambda: self.actuator_buttons[addr].config(bg='SystemButtonFace'))
    
    def _pattern_error(self, addr, error):
        """Called when pattern encounters error"""
        self.actuator_buttons[addr].config(state=tk.NORMAL, bg='red')
        self.instruction_text.config(text=f"Error testing Actuator {addr}: {error}")
        messagebox.showerror("Pattern Error", f"Error testing Actuator {addr}: {error}")
        
        # Reset color after 3 seconds
        self.root.after(3000, lambda: self.actuator_buttons[addr].config(bg='SystemButtonFace'))
    
    def play_next_pattern(self):
        """Play the next pattern in the automatic sequence"""
        if not self.connected_device:
            messagebox.showwarning("Not Connected", "Please connect to a BLE device first.")
            return
        
        if not self.pattern_list:
            messagebox.showwarning("No Patterns", "No patterns available.")
            return
        
        current_pattern = self.pattern_list[self.current_pattern_index]
        addr = current_pattern['addr']
        pattern_type = current_pattern['type']
        
        self.current_actuator = addr
        self.current_pattern_type = pattern_type
        
        # Update displays
        self.instruction_text.config(text=f"Playing: {current_pattern['name']}...")
        self.actuator_buttons[addr].config(bg='yellow')
        
        def play_thread():
            try:
                if pattern_type == "buzz":
                    success = self.send_buzz_pattern(addr)
                else:
                    success = self.send_pulse_pattern(addr)
                
                self.root.after(0, lambda: self._auto_pattern_finished(addr, success))
            except Exception as e:
                self.root.after(0, lambda: self._auto_pattern_error(addr, e))
        
        Thread(target=play_thread, daemon=True).start()
    
    def _auto_pattern_finished(self, addr, success):
        """Called when auto pattern finishes"""
        if success:
            self.actuator_buttons[addr].config(bg='lightgreen')
            self.instruction_text.config(text=f"Pattern completed! Click 'Play Next' or 'Repeat Current'.")
        else:
            self.actuator_buttons[addr].config(bg='lightcoral')
            self.instruction_text.config(text=f"Pattern failed! Click 'Play Next' or 'Repeat Current'.")
        
        # Move to next pattern
        self.current_pattern_index = (self.current_pattern_index + 1) % len(self.pattern_list)
        self.update_progress_display()
        
        # Reset color after 2 seconds
        self.root.after(2000, lambda: self.actuator_buttons[addr].config(bg='SystemButtonFace'))
    
    def _auto_pattern_error(self, addr, error):
        """Called when auto pattern encounters error"""
        self.actuator_buttons[addr].config(bg='red')
        self.instruction_text.config(text=f"Error in auto pattern: {error}")
        messagebox.showerror("Pattern Error", f"Error: {error}")
        
        # Reset color after 3 seconds
        self.root.after(3000, lambda: self.actuator_buttons[addr].config(bg='SystemButtonFace'))
    
    def repeat_current_pattern(self):
        """Repeat the current pattern without advancing"""
        if not self.connected_device:
            messagebox.showwarning("Not Connected", "Please connect to a BLE device first.")
            return
        
        if self.current_actuator is None:
            messagebox.showwarning("No Pattern", "No pattern has been played yet.")
            return
        
        # Go back one pattern and play it
        self.current_pattern_index = (self.current_pattern_index - 1) % len(self.pattern_list)
        self.update_progress_display()
        self.play_next_pattern()
    
    def send_buzz_pattern(self, addr):
        """Send a buzz pattern to specified actuator"""
        try:
            # Start vibration
            success = self.api.send_command(addr, DUTY, FREQ, 1)
            if not success:
                return False
            
            # Wait for duration
            time.sleep(DURATION / 1000.0)
            
            # Stop vibration
            success = self.api.send_command(addr, 0, 0, 0)
            if not success:
                return False
            
            # Verification stop
            time.sleep(0.5)
            return self.api.send_command(addr, 0, 0, 0)
        except Exception as e:
            print(f"Error in buzz pattern: {e}")
            return False
    
    def send_pulse_pattern(self, addr):
        """Send a pulse pattern to specified actuator"""
        try:
            for i in range(NUM_PULSES):
                # Start pulse
                success = self.api.send_command(addr, DUTY, FREQ, 1)
                if not success:
                    return False
                
                # Wait for pulse duration
                time.sleep(PULSE_DURATION / 1000.0)
                
                # Stop pulse
                success = self.api.send_command(addr, 0, 0, 0)
                if not success:
                    return False
                
                # Wait for pause between pulses (except for last pulse)
                if i < NUM_PULSES - 1:
                    time.sleep(PAUSE_DURATION / 1000.0)
            
            # Final verification stop
            time.sleep(0.5)
            return self.api.send_command(addr, 0, 0, 0)
        except Exception as e:
            print(f"Error in pulse pattern: {e}")
            return False
    
    def emergency_stop_all(self):
        """Emergency stop all actuators"""
        if not self.connected_device:
            messagebox.showwarning("Not Connected", "No device connected.")
            return
        
        print("Emergency stop - Stopping all actuators...")
        all_stop_commands = [
            {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
            for addr in range(16)
        ]
        
        try:
            success = self.api.send_command_list(all_stop_commands)
            if success:
                self.instruction_text.config(text="Emergency stop completed - All actuators stopped")
                messagebox.showinfo("Emergency Stop", "All actuators stopped successfully!")
            else:
                self.instruction_text.config(text="Warning: Emergency stop may have failed")
                messagebox.showwarning("Emergency Stop", "Emergency stop may have failed!")
        except Exception as e:
            self.instruction_text.config(text=f"Emergency stop error: {e}")
            messagebox.showerror("Emergency Stop Error", f"Error during emergency stop: {e}")
    
    def __del__(self):
        """Cleanup when closing"""
        if hasattr(self, 'api') and self.api and self.connected_device:
            try:
                self.emergency_stop_all()
                self.api.disconnect_ble_device()
            except:
                pass

def main():
    root = tk.Tk()
    app = SinglePointTesterGUI(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit?"):
            if hasattr(app, 'api') and app.api and app.connected_device:
                try:
                    app.emergency_stop_all()
                    app.api.disconnect_ble_device()
                except:
                    pass
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()