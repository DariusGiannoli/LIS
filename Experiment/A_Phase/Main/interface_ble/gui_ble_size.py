import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk, ImageDraw, ImageFont
import time
import sys
import os
import random
import json
import csv
from datetime import datetime
from threading import Thread

######
# Add root directory to path (from interface/ directory, go up one level to reach root)
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)
from categories.size import get_all_size_patterns
from core.hardware.ble.python_ble_api import python_ble_api
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

class SizeStudyInterface:
    """
    GUI Interface for Size Study - Tactile Size Discrimination (Bluetooth Version)
    
    This interface follows the same randomization logic as size_study_v2.py
    to ensure consistent pattern presentation order between studies.
    
    The interface displays clickable size options for each shape and records 
    reaction times and accuracy for each pattern response.
    
    Enhanced with:
    - Previous pattern navigation
    - Study restart functionality
    - Size-specific answer options based on available sizes
    - Bluetooth Low Energy communication
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Size Study Interface - Bluetooth Version")
        self.root.geometry("1000x800")
        self.root.configure(bg='white')
        
        # Study data - get all size patterns
        self.api = python_ble_api()  # Use BLE API instead of SERIAL_API
        self.all_size_patterns = get_all_size_patterns()
        
        # Available shapes and their sizes
        self.shape_sizes = {
            'cross': ['big', 'small'],
            'square': ['big', 'small'], 
            'circle': ['big', 'medium', 'small'],
            'l_shape': ['big', 'medium', 'small'],
            'h_line': ['big', 'medium', 'small', 'one'],
            'v_line': ['big', 'medium', 'small', 'one']
        }
        
        # Current state
        self.current_shape = None
        self.current_size = None
        self.current_pattern_type = None
        self.pattern_start_time = None
        self.pattern_end_time = None
        self.current_pattern_name = None
        self.current_pattern_data = None
        
        # Results storage
        self.results = []
        self.participant_id = None
        
        # Study sequence
        self.study_sequence = []
        self.current_sequence_index = 0
        self.study_completed = False
        
        # BLE connection state
        self.connected_device = None
        
        # GUI setup
        self.setup_gui()
        self.create_study_sequence()
        
    def emergency_stop_all(self):
        """Send stop commands to ALL 16 actuators - optimized version"""
        all_stop_commands = [
            {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
            for addr in range(16)
        ]
        
        print("Emergency stop - Stopping all actuators...")
        try:
            self.api.send_command_list(all_stop_commands)
            time.sleep(0.1)
            print("Emergency stop completed")
        except Exception as e:
            print(f"Error during emergency stop: {e}")
    
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
            text="Size Study - Tactile Size Discrimination (Bluetooth)",
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
        
        ttk.Label(conn_frame, text="Participant ID:").pack(side=tk.LEFT, padx=5)
        self.participant_entry = ttk.Entry(conn_frame, width=10)
        self.participant_entry.pack(side=tk.LEFT, padx=5)
        
        # BLE device selection
        ttk.Label(conn_frame, text="BLE Device:").pack(side=tk.LEFT, padx=(20, 5))
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(conn_frame, textvariable=self.device_var, 
                                        width=20, state="readonly")
        self.device_combo.pack(side=tk.LEFT, padx=5)
        
        self.scan_button = ttk.Button(
            conn_frame, text="Scan BLE", command=self.scan_ble_devices
        )
        self.scan_button.pack(side=tk.LEFT, padx=5)
        
        self.connect_button = ttk.Button(
            conn_frame, text="Connect Device", command=self.connect_device, state=tk.DISABLED
        )
        self.connect_button.pack(side=tk.LEFT, padx=10)
        
        self.start_study_button = ttk.Button(
            conn_frame, text="Start Study", command=self.start_study, state=tk.DISABLED
        )
        self.start_study_button.pack(side=tk.LEFT, padx=5)
        
        self.emergency_button = ttk.Button(
            conn_frame, text="Emergency Stop", command=self.emergency_stop_all, state=tk.DISABLED
        )
        self.emergency_button.pack(side=tk.LEFT, padx=5)
        
        # Progress frame
        progress_frame = ttk.Frame(header_frame)
        progress_frame.pack(fill=tk.X, pady=10)
        
        self.progress_label = ttk.Label(progress_frame, text="Progress: 0/0")
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(pady=5)
        
        # Instructions frame
        self.instructions_frame = ttk.Frame(main_frame)
        self.instructions_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.instruction_text = ttk.Label(
            self.instructions_frame,
            text="Click 'Scan BLE' to find devices, then select and connect.\nKeyboard shortcuts: R = Repeat, N = Skip, P = Previous, E = Emergency Stop",
            font=('Arial', 11),
            foreground='blue'
        )
        self.instruction_text.pack()
        
        # Answer selection frame
        self.answer_frame = ttk.Frame(main_frame)
        self.answer_frame.pack(fill=tk.BOTH, expand=True)
        
        # Create container for answer buttons
        self.answer_container = ttk.Frame(self.answer_frame)
        self.answer_container.pack(expand=True)
        
        # Control buttons frame
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(20, 0))
        
        # Left side - Pattern control buttons
        pattern_control_frame = ttk.Frame(control_frame)
        pattern_control_frame.pack(side=tk.LEFT)
        
        self.play_button = ttk.Button(
            pattern_control_frame, text="Play Pattern", command=self.play_current_pattern, state=tk.DISABLED
        )
        self.play_button.pack(side=tk.LEFT, padx=5)
        
        self.repeat_button = ttk.Button(
            pattern_control_frame, text="Repeat (R)", command=self.repeat_pattern, state=tk.DISABLED
        )
        self.repeat_button.pack(side=tk.LEFT, padx=5)
        
        self.previous_button = ttk.Button(
            pattern_control_frame, text="Previous (P)", command=self.previous_pattern, state=tk.DISABLED
        )
        self.previous_button.pack(side=tk.LEFT, padx=5)
        
        self.skip_button = ttk.Button(
            pattern_control_frame, text="Skip (N)", command=self.skip_pattern, state=tk.DISABLED
        )
        self.skip_button.pack(side=tk.LEFT, padx=5)
        
        # Right side - Study control buttons
        study_control_frame = ttk.Frame(control_frame)
        study_control_frame.pack(side=tk.RIGHT)
        
        self.restart_study_button = ttk.Button(
            study_control_frame, text="New Study", command=self.restart_study, state=tk.DISABLED
        )
        self.restart_study_button.pack(side=tk.RIGHT, padx=5)
        
        self.save_button = ttk.Button(
            study_control_frame, text="Save Results", command=self.save_results, state=tk.DISABLED
        )
        self.save_button.pack(side=tk.RIGHT, padx=5)
        
        # Bind keyboard shortcuts
        self.root.bind('<KeyPress-r>', lambda e: self._handle_repeat_key())
        self.root.bind('<KeyPress-R>', lambda e: self._handle_repeat_key())
        self.root.bind('<KeyPress-n>', lambda e: self._handle_skip_key())
        self.root.bind('<KeyPress-N>', lambda e: self._handle_skip_key())
        self.root.bind('<KeyPress-p>', lambda e: self._handle_previous_key())
        self.root.bind('<KeyPress-P>', lambda e: self._handle_previous_key())
        self.root.bind('<KeyPress-e>', lambda e: self._handle_emergency_key())
        self.root.bind('<KeyPress-E>', lambda e: self._handle_emergency_key())
        self.root.focus_set()  # Ensure window can receive key events
    
    def scan_ble_devices(self):
        """Scan for available BLE devices"""
        self.instruction_text.config(text="Scanning for BLE devices...")
        self.scan_button.config(state=tk.DISABLED)
        
        def scan_thread():
            try:
                devices = self.api.get_ble_devices()
                # Filter for relevant devices (optional - you can modify this filter)
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
            self.device_combo.current(0)  # Select first device by default
            self.connect_button.config(state=tk.NORMAL)
        
        self.instruction_text.config(
            text=f"Found {len(devices)} BLE device(s). Select device and click 'Connect Device'."
        )
        
        print(f"Found BLE devices: {devices}")
    
    def create_study_sequence(self):
        """Create randomized study sequence following size_study_v2.py logic"""
        
        def create_randomized_pattern_list():
            """Create a completely randomized list of all size-shape-pattern combinations"""
            pattern_list = []
            
            # Create all possible combinations
            for shape_name, shape_patterns in self.all_size_patterns.items():
                for pattern_type in ['static', 'pulse', 'motion']:  # All types
                # for pattern_type in ['motion']:  # Only motion for testing
                    for size_name, pattern_commands in shape_patterns[pattern_type].items():
                        
                        # Create a descriptive name for this combination
                        combination_name = f"{size_name}_{shape_name}_{pattern_type}"
                        
                        # Store the combination
                        pattern_entry = {
                            'name': combination_name,
                            'shape': shape_name,
                            'size': size_name,
                            'pattern_type': pattern_type,
                            'commands': pattern_commands
                        }
                        
                        pattern_list.append(pattern_entry)
            
            # Completely randomize the order
            random.shuffle(pattern_list)
            return pattern_list

        # Generate the randomized pattern list
        pattern_list = create_randomized_pattern_list()
        print(f"All types random order: {[p['name'] for p in pattern_list]}")
        
        # Store the random order for reference
        self.randomized_order = [p['name'] for p in pattern_list]
        
        # Clear existing sequence
        self.study_sequence = []
        
        # Create study sequence with metadata
        for pattern in pattern_list:
            self.study_sequence.append({
                'pattern_data': pattern['commands'],
                'shape': pattern['shape'],
                'size': pattern['size'],
                'pattern_type': pattern['pattern_type'],
                'name': pattern['name'],
                'section_name': f"Shape: {pattern['shape'].title()} | Size: {pattern['size'].title()} ({pattern['pattern_type']})"
            })
    
    def connect_device(self):
        """Connect to the selected BLE device"""
        if not self.participant_entry.get().strip():
            messagebox.showwarning("Participant ID", "Please enter a participant ID first.")
            return
        
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
            self.participant_id = self.participant_entry.get().strip()
            self.status_label.config(text=f"Status: Connected to {device_name} - Participant: {self.participant_id}")
            self.connect_button.config(state=tk.DISABLED)
            self.start_study_button.config(state=tk.NORMAL)
            self.emergency_button.config(state=tk.NORMAL)
            self.participant_entry.config(state=tk.DISABLED)
            self.device_combo.config(state=tk.DISABLED)
            self.scan_button.config(state=tk.DISABLED)
            
            # Initial emergency stop to ensure clean state
            self.emergency_stop_all()
            
            self.instruction_text.config(text=f"Successfully connected to {device_name}! Click 'Start Study' to begin.")
            messagebox.showinfo("Connection", f"Successfully connected to {device_name}!")
        else:
            self.connect_button.config(state=tk.NORMAL)
            self.instruction_text.config(text="Failed to connect. Try selecting a different device.")
            messagebox.showerror("Connection", f"Failed to connect to {device_name}.")
    
    def _handle_connection_error(self, error):
        """Handle connection error"""
        self.connect_button.config(state=tk.NORMAL)
        self.instruction_text.config(text="Connection error occurred.")
        messagebox.showerror("Connection Error", f"Error during connection: {error}")
    
    def start_study(self):
        """Start the study"""
        self.current_sequence_index = 0
        self.results = []
        self.study_completed = False
        
        # Update progress
        total_patterns = len(self.study_sequence)
        self.progress_bar.config(maximum=total_patterns)
        self.progress_bar.config(value=0)
        self.progress_label.config(text=f"Progress: 0/{total_patterns}")
        
        # Enable controls
        self.start_study_button.config(state=tk.DISABLED)
        self.play_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.NORMAL)
        self.restart_study_button.config(state=tk.DISABLED)  # Disable during study
        
        # Load first pattern
        self.load_current_pattern()
        
        # Show study information
        info_message = f"""Size Study started with {total_patterns} patterns.

Connected Device: {self.connected_device}

Randomized Pattern Order (same as size_study_v2.py):
- All shapes with their available sizes
- All pattern types (static, pulse, motion) mixed together
- Total combinations: {len(self.study_sequence)}

Shape Sizes Available:
- Cross/Square: Big, Small
- Circle/L-Shape: Big, Medium, Small  
- H-Line/V-Line: Big, Medium, Small, One

Controls:
- Play Pattern: Play the current tactile pattern
- Repeat (R): Replay the same pattern again
- Previous (P): Go back to previous pattern
- Skip (N): Skip to next pattern without answering
- Emergency Stop (E): Stop all actuators immediately
- Click size buttons: Select your answer

Click 'Play Pattern' to begin."""
        
        messagebox.showinfo("Study Started", info_message)
    
    def load_current_pattern(self):
        """Load the current pattern from the sequence"""
        if self.current_sequence_index >= len(self.study_sequence):
            self.study_complete()
            return
            
        current = self.study_sequence[self.current_sequence_index]
        self.current_shape = current['shape']
        self.current_size = current['size']
        self.current_pattern_type = current['pattern_type']
        self.current_pattern_name = current['name']
        self.current_pattern_data = current['pattern_data']
        
        # Update UI
        progress = self.current_sequence_index + 1
        total = len(self.study_sequence)
        self.progress_label.config(text=f"Progress: {progress}/{total}")
        self.progress_bar.config(value=progress)
        
        self.instruction_text.config(
            text=f"Ready - Pattern {progress}/{total}\nShape: {self.current_shape.title()} | Actual Size: {self.current_size.title()}\nClick 'Play Pattern', then select the size you felt."
        )
        
        # Setup answer options for the current shape
        self.setup_answer_options()
        
        # Enable/disable buttons based on position
        self.play_button.config(state=tk.NORMAL)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        
        # Enable Previous button only if not at the first pattern
        if self.current_sequence_index > 0:
            self.previous_button.config(state=tk.NORMAL)
        else:
            self.previous_button.config(state=tk.DISABLED)
    
    def create_size_image(self, size_name, shape_name):
        """Create a visual representation of size"""
        img = Image.new('RGB', (120, 120), color='white')
        draw = ImageDraw.Draw(img)
        
        # Define size mappings for visual representation
        size_mappings = {
            'big': 80,
            'medium': 60,
            'small': 40,
            'one': 20
        }
        
        size_pixels = size_mappings.get(size_name, 40)
        
        # Center the shape
        center_x, center_y = 60, 60
        
        # Draw different shapes based on shape_name
        if shape_name in ['square', 'cross']:
            # Draw a square or cross-like shape
            left = center_x - size_pixels // 2
            top = center_y - size_pixels // 2
            right = center_x + size_pixels // 2
            bottom = center_y + size_pixels // 2
            draw.rectangle([left, top, right, bottom], outline='black', width=2, fill='lightblue')
            
        elif shape_name == 'circle':
            # Draw a circle
            radius = size_pixels // 2
            draw.ellipse([center_x - radius, center_y - radius, 
                         center_x + radius, center_y + radius], 
                        outline='black', width=2, fill='lightgreen')
            
        elif shape_name == 'h_line':
            # Draw horizontal line
            thickness = max(4, size_pixels // 10)
            draw.rectangle([center_x - size_pixels // 2, center_y - thickness // 2,
                           center_x + size_pixels // 2, center_y + thickness // 2],
                          outline='black', width=1, fill='orange')
            
        elif shape_name == 'v_line':
            # Draw vertical line
            thickness = max(4, size_pixels // 10)
            draw.rectangle([center_x - thickness // 2, center_y - size_pixels // 2,
                           center_x + thickness // 2, center_y + size_pixels // 2],
                          outline='black', width=1, fill='orange')
            
        elif shape_name == 'l_shape':
            # Draw L shape
            thickness = max(6, size_pixels // 8)
            # Vertical part
            draw.rectangle([center_x - size_pixels // 2, center_y - size_pixels // 2,
                           center_x - size_pixels // 2 + thickness, center_y + size_pixels // 2],
                          outline='black', width=1, fill='pink')
            # Horizontal part
            draw.rectangle([center_x - size_pixels // 2, center_y + size_pixels // 2 - thickness,
                           center_x + size_pixels // 2, center_y + size_pixels // 2],
                          outline='black', width=1, fill='pink')
        
        # Add size label
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        # Get text bounding box for centering
        text = size_name.upper()
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_x = center_x - text_width // 2
        text_y = 95
        
        draw.text((text_x, text_y), text, fill='black', font=font)
        
        return ImageTk.PhotoImage(img)
    
    def setup_answer_options(self):
        """Setup answer options based on current shape's available sizes"""
        # Clear existing buttons
        for widget in self.answer_container.winfo_children():
            widget.destroy()
        
        # Get available sizes for current shape
        available_sizes = self.shape_sizes.get(self.current_shape, ['small', 'medium', 'big'])
        
        # Create title
        title_text = f"Select the size you felt for {self.current_shape.replace('_', ' ').title()}:"
        title_label = ttk.Label(self.answer_container, text=title_text, font=('Arial', 14, 'bold'))
        title_label.pack(pady=(0, 20))
        
        # Create frame for size buttons
        buttons_frame = ttk.Frame(self.answer_container)
        buttons_frame.pack()
        
        # Create size buttons
        self.size_buttons = []
        for i, size in enumerate(available_sizes):
            # Create image for this size
            size_image = self.create_size_image(size, self.current_shape)
            
            button = tk.Button(
                buttons_frame,
                image=size_image,
                text=size.replace('_', ' ').title(),
                compound=tk.TOP,
                command=lambda idx=i: self.answer_selected(idx),
                state=tk.DISABLED,
                bg='lightgray',
                font=('Arial', 12, 'bold'),
                width=140,
                height=160
            )
            button.image = size_image  # Keep reference to prevent garbage collection
            button.pack(side=tk.LEFT, padx=15, pady=15)
            self.size_buttons.append(button)
    
    def execute_pattern_optimized(self, pattern):
        """Execute pattern with optimized timing based on pattern type"""
        activated_actuators = set()
        
        try:
            for step_num, step in enumerate(pattern['steps']):
                # Send commands for this step
                success = self.api.send_command_list(step['commands'])
                if not success:
                    print(f"Warning: Step {step_num + 1} may have failed")
                
                # Track actuators that were started
                for cmd in step['commands']:
                    if cmd.get('start_or_stop') == 1:
                        activated_actuators.add(cmd['addr'])
                
                # Wait if there's a delay after this step
                if step['delay_after_ms'] > 0:
                    time.sleep(step['delay_after_ms'] / 1000.0)
            
            # Single optimized final stop for activated actuators only
            if activated_actuators:
                final_stop_commands = [
                    {"addr": addr, "duty": 0, "freq": 0, "start_or_stop": 0}
                    for addr in activated_actuators
                ]
                self.api.send_command_list(final_stop_commands)
                time.sleep(0.05)  # Brief pause to ensure clean stop
                
        except Exception as e:
            print(f"Error during pattern execution: {e}")
            self.emergency_stop_all()
            raise
    
    def play_current_pattern(self):
        """Play the current tactile pattern"""
        if self.current_sequence_index >= len(self.study_sequence):
            return
            
        pattern_data = self.current_pattern_data
        
        # Record pattern start time
        self.pattern_start_time = time.time()
        
        # Update UI
        self.instruction_text.config(text=f"Playing...")
        self.play_button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.previous_button.config(state=tk.DISABLED)
        
        # Disable answer buttons
        for button in self.size_buttons:
            button.config(state=tk.DISABLED, bg='lightgray')
        
        # Play pattern in separate thread
        def play_pattern():
            try:
                # Pre-execution clean stop
                self.emergency_stop_all()
                time.sleep(0.1)
                
                # Execute the pattern with optimized timing
                self.execute_pattern_optimized(pattern_data)
                
                # Pattern finished - record end time and enable answers
                self.pattern_end_time = time.time()
                self.root.after(0, self.pattern_finished)
                
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Pattern playback error: {e}"))
                self.root.after(0, self._reset_buttons_after_error)
        
        Thread(target=play_pattern, daemon=True).start()
    
    def _reset_buttons_after_error(self):
        """Reset button states after an error during pattern playback"""
        self.play_button.config(state=tk.NORMAL)
        if self.current_sequence_index > 0:
            self.previous_button.config(state=tk.NORMAL)
        # Don't enable repeat/skip buttons until pattern has been played successfully
    
    def pattern_finished(self):
        """Called when pattern playback is complete"""
        self.instruction_text.config(
            text=f"Pattern complete! Select the size you felt for {self.current_shape.replace('_', ' ').title()}, or use control buttons."
        )
        
        # Enable answer buttons
        for button in self.size_buttons:
            button.config(state=tk.NORMAL, bg='white')
            
        # Enable control buttons
        self.repeat_button.config(state=tk.NORMAL)
        self.skip_button.config(state=tk.NORMAL)
        if self.current_sequence_index > 0:
            self.previous_button.config(state=tk.NORMAL)
    
    def answer_selected(self, selected_index):
        """Handle answer selection"""
        answer_time = time.time()
        reaction_time = answer_time - self.pattern_end_time
        
        # Get available sizes for current shape
        available_sizes = self.shape_sizes.get(self.current_shape, ['small', 'medium', 'big'])
        
        # Record result
        current = self.study_sequence[self.current_sequence_index]
        
        # The correct answer is the current size
        correct_size_index = available_sizes.index(current['size']) if current['size'] in available_sizes else -1
        selected_size = available_sizes[selected_index] if selected_index < len(available_sizes) else 'unknown'
        
        result = {
            'participant_id': self.participant_id,
            'timestamp': datetime.now().isoformat(),
            'sequence_position': self.current_sequence_index + 1,
            'section_name': current['section_name'],
            'shape': current['shape'],
            'correct_size': current['size'],
            'pattern_type': current['pattern_type'],
            'selected_answer': selected_size,
            'is_correct': selected_index == correct_size_index,
            'reaction_time_ms': round(reaction_time * 1000, 2),
            'pattern_duration_ms': round((self.pattern_end_time - self.pattern_start_time) * 1000, 2),
            'available_sizes': available_sizes,
            'connected_device': self.connected_device,
            'randomized_order': self.randomized_order  # For reference
        }
        
        self.results.append(result)
        
        # Visual feedback
        if correct_size_index >= 0 and correct_size_index < len(self.size_buttons):
            correct_button = self.size_buttons[correct_size_index]
            selected_button = self.size_buttons[selected_index]
            
            if result['is_correct']:
                selected_button.config(bg='lightgreen')
                feedback_text = f"Correct! Reaction time: {result['reaction_time_ms']:.0f}ms"
            else:
                selected_button.config(bg='lightcoral')
                correct_button.config(bg='lightgreen')
                feedback_text = f"Incorrect. Correct size: {result['correct_size']}. Reaction time: {result['reaction_time_ms']:.0f}ms"
        else:
            feedback_text = f"Answer recorded. Reaction time: {result['reaction_time_ms']:.0f}ms"
        
        self.instruction_text.config(text=feedback_text)
        
        # Disable all answer buttons and control buttons
        for button in self.size_buttons:
            button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.previous_button.config(state=tk.DISABLED)
        
        # Auto-advance after showing feedback for 3 seconds
        self.root.after(3000, self.next_pattern)
    
    def next_pattern(self):
        """Move to the next pattern"""
        self.current_sequence_index += 1
        
        if self.current_sequence_index >= len(self.study_sequence):
            self.study_complete()
        else:
            self.load_current_pattern()
    
    def previous_pattern(self):
        """Go back to the previous pattern"""
        if self.current_sequence_index <= 0:
            messagebox.showwarning("Navigation", "Already at the first pattern.")
            return
        
        # Remove the last result if it corresponds to the current pattern
        if (self.results and 
            len(self.results) > 0 and 
            self.results[-1]['sequence_position'] == self.current_sequence_index + 1):
            
            confirm = messagebox.askyesno(
                "Go Back", 
                "Going back will remove the result for the current pattern. Continue?"
            )
            if confirm:
                self.results.pop()  # Remove the last result
            else:
                return
        
        # Go back one pattern
        self.current_sequence_index -= 1
        self.load_current_pattern()
        
        # Show message
        self.instruction_text.config(
            text=f"Returned to previous pattern. Click 'Play Pattern' to start."
        )
    
    def repeat_pattern(self):
        """Repeat the current pattern"""
        if hasattr(self, 'pattern_end_time') and self.pattern_end_time:
            # Pattern has been played, replay it
            self.instruction_text.config(text="Repeating pattern...")
            self.root.after(500, self.play_current_pattern)  # Small delay for visual feedback
        else:
            # Pattern hasn't been played yet, just play it
            self.play_current_pattern()
    
    def skip_pattern(self):
        """Skip to next pattern without recording answer"""
        # Show visual feedback
        self.instruction_text.config(text="Skipping pattern...")
        
        # Record that the pattern was skipped
        if self.current_sequence_index < len(self.study_sequence):
            current = self.study_sequence[self.current_sequence_index]
            skip_result = {
                'participant_id': self.participant_id,
                'timestamp': datetime.now().isoformat(),
                'sequence_position': self.current_sequence_index + 1,
                'section_name': current['section_name'],
                'shape': current['shape'],
                'correct_size': current['size'],
                'pattern_type': current['pattern_type'],
                'selected_answer': 'SKIPPED',
                'is_correct': False,
                'reaction_time_ms': 0,
                'pattern_duration_ms': 0,
                'available_sizes': self.shape_sizes.get(current['shape'], []),
                'connected_device': self.connected_device,
                'randomized_order': getattr(self, 'randomized_order', [])
            }
            self.results.append(skip_result)
        
        # Move to next pattern after brief delay
        self.root.after(500, self.next_pattern)
    
    def study_complete(self):
        """Handle study completion"""
        self.study_completed = True
        self.instruction_text.config(text="Study Complete! Click 'Save Results' to save your data, or 'New Study' to start again.")
        self.play_button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.previous_button.config(state=tk.DISABLED)
        self.restart_study_button.config(state=tk.NORMAL)  # Enable restart button
        
        # Final emergency stop
        self.emergency_stop_all()
        
        # Show completion message with summary
        total_patterns = len(self.results)
        correct_answers = sum(1 for r in self.results if r['is_correct'])
        accuracy = (correct_answers / total_patterns) * 100 if total_patterns > 0 else 0
        valid_reactions = [r for r in self.results if r['reaction_time_ms'] > 0]
        avg_reaction_time = sum(r['reaction_time_ms'] for r in valid_reactions) / max(1, len(valid_reactions))
        
        summary = f"""Size Study Complete!

Device: {self.connected_device}

Results Summary:
- Total Patterns: {total_patterns}
- Correct Answers: {correct_answers}
- Accuracy: {accuracy:.1f}%
- Average Reaction Time: {avg_reaction_time:.0f}ms

Pattern Details:
- All pattern types (static, pulse, motion) tested
- Size discrimination across all available shapes
- Adaptive answer options per shape

Options:
- 'Save Results' to save your data
- 'New Study' to start a fresh study with new randomization"""
        
        messagebox.showinfo("Study Complete", summary)
    
    def restart_study(self):
        """Start a new study with fresh randomization"""
        if not self.study_completed and self.results:
            confirm = messagebox.askyesno(
                "New Study", 
                "This will start a completely new study and discard current progress. Continue?"
            )
            if not confirm:
                return
        
        # Ask if user wants to change participant ID
        change_id = messagebox.askyesno(
            "New Study", 
            "Would you like to change the participant ID for the new study?"
        )
        
        if change_id:
            # Enable participant entry temporarily
            self.participant_entry.config(state=tk.NORMAL)
            self.participant_entry.delete(0, tk.END)
            
            new_id = simpledialog.askstring(
                "Participant ID", 
                "Enter new participant ID:",
                initialvalue=""
            )
            
            if new_id and new_id.strip():
                self.participant_id = new_id.strip()
                self.participant_entry.insert(0, self.participant_id)
                self.status_label.config(text=f"Status: Connected to {self.connected_device} - Participant: {self.participant_id}")
            else:
                # User cancelled or entered empty ID, keep current ID
                self.participant_entry.insert(0, self.participant_id)
            
            self.participant_entry.config(state=tk.DISABLED)
        
        # Reset study state
        self.current_sequence_index = 0
        self.results = []
        self.study_completed = False
        self.pattern_start_time = None
        self.pattern_end_time = None
        
        # Create new randomized sequence
        self.create_study_sequence()
        
        # Reset UI elements
        self.progress_bar.config(value=0)
        self.progress_label.config(text="Progress: 0/0")
        self.instruction_text.config(
            text="New study created with fresh randomization!\nClick 'Start Study' to begin."
        )
        
        # Reset button states
        self.start_study_button.config(state=tk.NORMAL)
        self.play_button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.previous_button.config(state=tk.DISABLED)
        self.restart_study_button.config(state=tk.DISABLED)
        self.save_button.config(state=tk.DISABLED)
        
        # Clear answer container
        for widget in self.answer_container.winfo_children():
            widget.destroy()
        
        messagebox.showinfo("New Study", "New study ready! Click 'Start Study' when you're ready to begin.")
    
    def save_results(self):
        """Save results to file"""
        if not self.results:
            messagebox.showwarning("No Data", "No results to save.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"size_study_ble_results_{self.participant_id}_{timestamp}"
        
        # Ask user for save location
        json_file = filedialog.asksaveasfilename(
            defaultextension=".json",
            initialfile=filename,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )
        
        if json_file:
            try:
                # Save as JSON
                with open(json_file, 'w') as f:
                    json.dump(self.results, f, indent=2)
                
                # Also save as CSV
                csv_file = json_file.replace('.json', '.csv')
                with open(csv_file, 'w', newline='') as f:
                    if self.results:
                        writer = csv.DictWriter(f, fieldnames=self.results[0].keys())
                        writer.writeheader()
                        writer.writerows(self.results)
                
                messagebox.showinfo("Results Saved", f"Results saved to:\n{json_file}\n{csv_file}")
                
            except Exception as e:
                messagebox.showerror("Save Error", f"Failed to save results: {e}")
    
    def _handle_repeat_key(self):
        """Handle R key press"""
        if self.repeat_button['state'] == tk.NORMAL:
            self.repeat_pattern()
    
    def _handle_skip_key(self):
        """Handle N key press"""
        if self.skip_button['state'] == tk.NORMAL:
            self.skip_pattern()
    
    def _handle_previous_key(self):
        """Handle P key press"""
        if self.previous_button['state'] == tk.NORMAL:
            self.previous_pattern()
    
    def _handle_emergency_key(self):
        """Handle E key press"""
        if self.emergency_button['state'] == tk.NORMAL:
            self.emergency_stop_all()
            messagebox.showinfo("Emergency Stop", "All actuators stopped!")
    
    def __del__(self):
        """Cleanup when closing"""
        if hasattr(self, 'api') and self.api:
            try:
                self.emergency_stop_all()
                self.api.disconnect_ble_device()
            except:
                pass

def main():
    root = tk.Tk()
    app = SizeStudyInterface(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit? Any unsaved data will be lost."):
            if hasattr(app, 'api') and app.api:
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