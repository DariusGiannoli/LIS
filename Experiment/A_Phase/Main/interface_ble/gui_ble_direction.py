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
from categories.direction import get_all_direction_patterns, DIRECTION_CONFIGS
from core.hardware.ble.python_ble_api import python_ble_api  # Import BLE API instead of serial
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

class DirectionStudyInterface:
    """
    GUI Interface for Direction Study - Tactile Directional Perception (Bluetooth Version)
    
    This interface follows the exact same randomization logic as direction_study_v2.py
    to ensure consistent pattern presentation order between studies.
    
    The interface displays 8 clickable direction images/buttons (north, northeast, east, southeast, 
    south, southwest, west, northwest) and records reaction times and accuracy for each pattern response.
    
    Enhanced with:
    - Previous pattern navigation
    - Study restart functionality
    - Visual direction indicators
    - Bluetooth Low Energy communication
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Direction Study Interface - Bluetooth Version")
        self.root.geometry("1000x800")
        self.root.configure(bg='white')
        
        # Study data - get all direction patterns
        self.api = python_ble_api()  # Use BLE API instead of SERIAL_API
        self.all_patterns = get_all_direction_patterns()
        self.static_directions = self.all_patterns['static']
        self.pulse_directions = self.all_patterns['pulse'] 
        self.motion_directions = self.all_patterns['motion']
        
        # Direction names for reference (8 directions)
        self.direction_names = ['north', 'northeast', 'east', 'southeast', 
                               'south', 'southwest', 'west', 'northwest']
        
        # Current state
        self.current_direction = None
        self.current_pattern_type = None
        self.current_section = None
        self.pattern_start_time = None
        self.pattern_end_time = None
        self.current_pattern_name = None
        self.current_pattern_data = None
        
        # Results storage
        self.results = []
        self.participant_id = None
        
        # Images
        self.direction_images = {}
        self.image_buttons = []
        
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
            text="Direction Study - Tactile Directional Perception (Bluetooth)",
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
        
        # Create grid for answer buttons
        self.answer_grid = ttk.Frame(self.answer_frame)
        self.answer_grid.pack(expand=True)
        
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
        
        # Load direction images
        self.load_direction_images()
        
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
        
    def load_direction_images(self):
        """Load or create direction images"""
        # Direction symbols and descriptions
        direction_info = {
            'north': ('↑', 'N', 'North'),
            'northeast': ('↗', 'NE', 'Northeast'),
            'east': ('→', 'E', 'East'), 
            'southeast': ('↘', 'SE', 'Southeast'),
            'south': ('↓', 'S', 'South'),
            'southwest': ('↙', 'SW', 'Southwest'),
            'west': ('←', 'W', 'West'),
            'northwest': ('↖', 'NW', 'Northwest')
        }
        
        try:
            # Try to load direction images from images/directions/ directory first
            for direction in self.direction_names:
                try:
                    img_path = f"images/directions/{direction}.png"
                    if os.path.exists(img_path):
                        img = Image.open(img_path)
                        img = img.resize((100, 100), Image.Resampling.LANCZOS)
                        self.direction_images[direction] = ImageTk.PhotoImage(img)
                    else:
                        # Create directional arrow image if file doesn't exist
                        arrow, abbrev, name = direction_info[direction]
                        self.direction_images[direction] = self.create_direction_image(arrow, abbrev, name, (100, 100))
                except Exception as e:
                    arrow, abbrev, name = direction_info[direction]
                    self.direction_images[direction] = self.create_direction_image(arrow, abbrev, name, (100, 100))
                    
        except Exception as e:
            # Create all direction images if directory doesn't exist
            for direction in self.direction_names:
                arrow, abbrev, name = direction_info[direction]
                self.direction_images[direction] = self.create_direction_image(arrow, abbrev, name, (100, 100))
    
    def create_direction_image(self, arrow, abbrev, name, size):
        """Create a direction image with arrow and text"""
        img = Image.new('RGB', size, color='white')
        draw = ImageDraw.Draw(img)
        
        # Draw border
        draw.rectangle([0, 0, size[0]-1, size[1]-1], outline='black', width=2)
        
        # Try to use fonts, fallback to default if not available
        try:
            arrow_font = ImageFont.truetype("arial.ttf", 36)
            text_font = ImageFont.truetype("arial.ttf", 12)
        except:
            try:
                arrow_font = ImageFont.load_default()
                text_font = ImageFont.load_default()
            except:
                arrow_font = None
                text_font = None
        
        # Draw arrow symbol (larger)
        if arrow_font:
            arrow_bbox = draw.textbbox((0, 0), arrow, font=arrow_font)
        else:
            arrow_bbox = draw.textbbox((0, 0), arrow)
        arrow_width = arrow_bbox[2] - arrow_bbox[0]
        arrow_height = arrow_bbox[3] - arrow_bbox[1]
        
        arrow_x = (size[0] - arrow_width) // 2
        arrow_y = (size[1] - arrow_height) // 2 - 10
        
        if arrow_font:
            draw.text((arrow_x, arrow_y), arrow, fill='blue', font=arrow_font)
        else:
            draw.text((arrow_x, arrow_y), arrow, fill='blue')
        
        # Draw abbreviation (smaller, below arrow)
        if text_font:
            abbrev_bbox = draw.textbbox((0, 0), abbrev, font=text_font)
        else:
            abbrev_bbox = draw.textbbox((0, 0), abbrev)
        abbrev_width = abbrev_bbox[2] - abbrev_bbox[0]
        
        abbrev_x = (size[0] - abbrev_width) // 2
        abbrev_y = arrow_y + arrow_height + 5
        
        if text_font:
            draw.text((abbrev_x, abbrev_y), abbrev, fill='black', font=text_font)
        else:
            draw.text((abbrev_x, abbrev_y), abbrev, fill='black')
        
        return ImageTk.PhotoImage(img)
    
    def create_study_sequence(self):
        """Create randomized study sequence following direction_study_v2.py logic"""
        
        def create_combined_random_order():
            """Generate a random permutation of all direction-pattern combinations"""
            #pattern_types = ['static', 'pulse', 'motion']  # All types
            pattern_types = ['pulse']  # Only motion for testing
            all_combinations = []
            
            # Create all combinations of direction + pattern type
            for direction in self.direction_names:
                for pattern_type in pattern_types:
                    all_combinations.append((direction, pattern_type))
            
            # Shuffle the complete list
            random.shuffle(all_combinations)
            return all_combinations

        # Create single randomized order for all combinations
        combined_random_order = create_combined_random_order()
        print(f"All types random order: {[f'{direction}_{pattern}' for direction, pattern in combined_random_order]}")
        
        # Store the random order for reference
        self.combined_random_order = combined_random_order
        
        # Clear existing sequence
        self.study_sequence = []
        
        # Create combined pattern list with metadata
        for direction, pattern_type in combined_random_order:
            if pattern_type == 'static':
                pattern_data = self.static_directions[direction]
            elif pattern_type == 'pulse':
                pattern_data = self.pulse_directions[direction]
            else:  # motion
                pattern_data = self.motion_directions[direction]
            
            # Get description from DIRECTION_CONFIGS
            description = DIRECTION_CONFIGS[direction]['description']
            
            self.study_sequence.append({
                'pattern_data': pattern_data,
                'direction': direction,
                'pattern_type': pattern_type,
                'name': f"{direction}_{pattern_type}",
                'section_name': f"Direction: {description} ({pattern_type})"
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
        info_message = f"""Study started with {total_patterns} patterns.

Connected Device: {self.connected_device}

Randomized Direction Order (same as direction_study_v2.py):
- All 8 directions (North, Northeast, East, Southeast, South, Southwest, West, Northwest)
- All pattern types (static, pulse, motion) mixed together
- Total combinations: {len(self.study_sequence)}

Pattern characteristics:
- All patterns start from center and radiate outward
- Motion patterns create smooth directional movement
- Randomized order eliminates order effects

Controls:
- Play Pattern: Play the current tactile pattern
- Repeat (R): Replay the same pattern again
- Previous (P): Go back to previous pattern
- Skip (N): Skip to next pattern without answering
- Emergency Stop (E): Stop all actuators immediately
- Click direction arrows: Select your answer

Click 'Play Pattern' to begin."""
        
        messagebox.showinfo("Study Started", info_message)
    
    def load_current_pattern(self):
        """Load the current pattern from the sequence"""
        if self.current_sequence_index >= len(self.study_sequence):
            self.study_complete()
            return
            
        current = self.study_sequence[self.current_sequence_index]
        self.current_section = current['section_name']
        self.current_direction = current['direction']
        self.current_pattern_type = current['pattern_type']
        self.current_pattern_name = current['name']
        self.current_pattern_data = current['pattern_data']
        
        # Update UI
        progress = self.current_sequence_index + 1
        total = len(self.study_sequence)
        self.progress_label.config(text=f"Progress: {progress}/{total}")
        self.progress_bar.config(value=progress)
        
        self.instruction_text.config(
            text=f"Ready - Pattern {progress}/{total}\nClick 'Play Pattern', then use control buttons or select your answer."
        )
        
        # Setup answer grid
        self.setup_answer_grid()
        
        # Enable/disable buttons based on position
        self.play_button.config(state=tk.NORMAL)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        
        # Enable Previous button only if not at the first pattern
        if self.current_sequence_index > 0:
            self.previous_button.config(state=tk.NORMAL)
        else:
            self.previous_button.config(state=tk.DISABLED)
    
    def setup_answer_grid(self):
        """Setup the answer grid with direction images"""
        # Clear existing buttons
        for widget in self.answer_grid.winfo_children():
            widget.destroy()
        self.image_buttons = []
        
        # Create title
        title_text = "Select the direction you felt:"
        title_label = ttk.Label(self.answer_grid, text=title_text, font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 20))
        
        # Create compass-like layout (3x3 grid with center empty)
        # Layout:
        #   NW  N  NE
        #   W   C   E
        #   SW  S  SE
        
        direction_positions = {
            'northwest': (1, 0),
            'north': (1, 1),
            'northeast': (1, 2),
            'west': (2, 0),
            'east': (2, 2),
            'southwest': (3, 0),
            'south': (3, 1),
            'southeast': (3, 2)
        }
        
        for i, direction in enumerate(self.direction_names):
            row, col = direction_positions[direction]
            
            button = tk.Button(
                self.answer_grid,
                image=self.direction_images[direction],
                text=DIRECTION_CONFIGS[direction]['description'],
                compound=tk.TOP,
                command=lambda idx=i: self.answer_selected(idx),
                state=tk.DISABLED,
                bg='lightgray',
                font=('Arial', 9, 'bold'),
                width=120,
                height=140
            )
            button.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            self.image_buttons.append(button)
        
        # Add center indicator (optional)
        center_label = ttk.Label(self.answer_grid, text="CENTER\n(Starting Point)", 
                                font=('Arial', 8), foreground='gray')
        center_label.grid(row=2, column=1, pady=5)
        
        # Configure grid weights
        for i in range(4):
            self.answer_grid.columnconfigure(i, weight=1)
        for i in range(4):
            self.answer_grid.rowconfigure(i, weight=1)
    
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
        for button in self.image_buttons:
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
    
    def pattern_finished(self):
        """Called when pattern playback is complete"""
        self.instruction_text.config(
            text=f"Pattern complete! Click on the direction you felt, or use control buttons."
        )
        
        # Enable answer buttons
        for button in self.image_buttons:
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
        
        # Record result
        current = self.study_sequence[self.current_sequence_index]
        
        # The correct answer is the current direction
        correct_direction_index = self.direction_names.index(current['direction'])
        selected_direction = self.direction_names[selected_index]
        
        result = {
            'participant_id': self.participant_id,
            'timestamp': datetime.now().isoformat(),
            'sequence_position': self.current_sequence_index + 1,
            'section_name': current['section_name'],
            'pattern_type': current['pattern_type'],
            'correct_answer': current['direction'],
            'correct_answer_description': DIRECTION_CONFIGS[current['direction']]['description'],
            'selected_answer': selected_direction,
            'selected_answer_description': DIRECTION_CONFIGS[selected_direction]['description'],
            'is_correct': selected_index == correct_direction_index,
            'reaction_time_ms': round(reaction_time * 1000, 2),
            'pattern_duration_ms': round((self.pattern_end_time - self.pattern_start_time) * 1000, 2),
            'connected_device': self.connected_device,
            'combined_random_order': [f'{direction}_{pattern}' for direction, pattern in self.combined_random_order]  # For reference
        }
        
        self.results.append(result)
        
        # Visual feedback
        correct_button = self.image_buttons[correct_direction_index]
        selected_button = self.image_buttons[selected_index]
        
        if result['is_correct']:
            selected_button.config(bg='lightgreen')
            feedback_text = f"Correct! {result['correct_answer_description']} - Reaction time: {result['reaction_time_ms']:.0f}ms"
        else:
            selected_button.config(bg='lightcoral')
            correct_button.config(bg='lightgreen')
            feedback_text = f"Incorrect. Correct: {result['correct_answer_description']} - Reaction time: {result['reaction_time_ms']:.0f}ms"
        
        self.instruction_text.config(text=feedback_text)
        
        # Disable all answer buttons and control buttons
        for button in self.image_buttons:
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
        """Repeat the current pattern (same as 'r' key in console version)"""
        if hasattr(self, 'pattern_end_time') and self.pattern_end_time:
            # Pattern has been played, replay it
            self.instruction_text.config(text="Repeating pattern...")
            self.root.after(500, self.play_current_pattern)  # Small delay for visual feedback
        else:
            # Pattern hasn't been played yet, just play it
            self.play_current_pattern()
    
    def skip_pattern(self):
        """Skip to next pattern without recording answer (same as 'n' key in console version)"""
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
                'pattern_type': current['pattern_type'],
                'correct_answer': current['direction'],
                'correct_answer_description': DIRECTION_CONFIGS[current['direction']]['description'],
                'selected_answer': 'SKIPPED',
                'selected_answer_description': 'SKIPPED',
                'is_correct': False,
                'reaction_time_ms': 0,
                'pattern_duration_ms': 0,
                'connected_device': self.connected_device,
                'combined_random_order': getattr(self, 'combined_random_order', [])
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
        
        summary = f"""Study Complete!

Device: {self.connected_device}

Direction Discrimination Results:
- Total Patterns: {total_patterns}
- Correct Answers: {correct_answers}
- Accuracy: {accuracy:.1f}%
- Average Reaction Time: {avg_reaction_time:.0f}ms

Pattern Details:
- All patterns started from center and radiated outward
- Randomized order eliminated order effects
- All pattern types (static, pulse, motion) tested

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
            
            new_id = tk.simpledialog.askstring(
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
        
        # Clear answer grid
        for widget in self.answer_grid.winfo_children():
            widget.destroy()
        
        messagebox.showinfo("New Study", "New study ready! Click 'Start Study' when you're ready to begin.")
    
    def save_results(self):
        """Save results to file"""
        if not self.results:
            messagebox.showwarning("No Data", "No results to save.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"direction_study_ble_results_{self.participant_id}_{timestamp}"
        
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
    app = DirectionStudyInterface(root)
    
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