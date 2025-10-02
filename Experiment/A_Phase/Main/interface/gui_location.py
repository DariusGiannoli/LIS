import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
from PIL import Image, ImageTk
import time
import sys
import os
import random
import json
import csv
from datetime import datetime
from threading import Thread

######
# Add root directory to path
root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, root_dir)
from categories.location import create_all_commands_with_motion
from core.hardware.serial.serial_api import SERIAL_API
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

class LocationStudyInterface:
    """
    GUI Interface for Location Study - Tactile Pattern Recognition
    
    Based on the existing interface but adapted for full_loc_study.py logic.
    Enhanced with Previous/New Study functionality.
    
    The interface displays 12 clickable images (horizontal or vertical patterns)
    and records reaction times and accuracy for each pattern response.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Location Study Interface - Enhanced")
        self.root.geometry("1200x800")
        self.root.configure(bg='white')
        
        # Setup custom styles
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure("Big.TButton", font=("Segoe UI", 16, "bold"), padding=10, foreground="#222", background="#e0e0e0")
        style.configure("TLabel", font=("Segoe UI", 12), foreground="#222")
        style.configure("TEntry", font=("Segoe UI", 12))
        
        # Study data
        self.api = SERIAL_API()
        self.all_commands = create_all_commands_with_motion(
            DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES
        )
        
        # Pattern arrays
        # self.static_horizontal = self.all_commands['static_horizontal']
        # self.static_vertical = self.all_commands['static_vertical']
        # self.pulse_horizontal = self.all_commands['pulse_horizontal']
        # self.pulse_vertical = self.all_commands['pulse_vertical']
        self.motion_horizontal = self.all_commands['motion_horizontal']
        # self.motion_vertical = self.all_commands['motion_vertical']
        
        # Current state
        self.current_pattern_type = None  # 'horizontal' or 'vertical'
        self.current_pattern_index = None
        self.current_section = None
        self.pattern_start_time = None
        self.pattern_end_time = None
        self.current_patterns = None
        self.current_pattern_name = None
        self.repeat_used = False
        self.play_used = False
        
        # Results storage
        self.results = []
        self.participant_id = None
        
        # Timer
        self.study_start_time = None
        self.timer_running = False
        
        # Images
        self.horizontal_images = []
        self.vertical_images = []
        self.image_buttons = []
        
        # Study sequence
        self.study_sequence = []
        self.current_sequence_index = 0
        self.study_completed = False
        
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
        
        # Title and timer frame
        title_timer_frame = ttk.Frame(header_frame)
        title_timer_frame.pack(fill=tk.X)
        
        self.title_label = ttk.Label(
            title_timer_frame, 
            text="Location Study - Tactile Pattern Recognition (Enhanced)",
            font=('Arial', 16, 'bold')
        )
        self.title_label.pack(side=tk.LEFT)
        
        # Timer label in top right
        self.timer_label = ttk.Label(
            title_timer_frame,
            text="Time: 00:00:00",
            font=('Arial', 14, 'bold'),
            foreground='blue'
        )
        self.timer_label.pack(side=tk.RIGHT)
        
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
        
        self.connect_button = ttk.Button(
            conn_frame, text="Connect Device", command=self.connect_device
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
        
        self.progress_label = ttk.Label(progress_frame, text="Progress: 0/0", font=('Arial', 16, 'bold'))
        self.progress_label.pack()
        
        self.progress_bar = ttk.Progressbar(progress_frame, length=400, mode='determinate')
        self.progress_bar.pack(pady=5)
        
        # Pattern type display
        self.pattern_type_label = ttk.Label(
            progress_frame, 
            text="Pattern Type: Not Started", 
            font=('Arial', 14, 'bold'), 
            foreground='darkgreen'
        )
        self.pattern_type_label.pack(pady=5)
        
        # Instructions frame
        self.instructions_frame = ttk.Frame(main_frame)
        self.instructions_frame.pack(fill=tk.X, pady=(0, 20))
        
        self.instruction_text = ttk.Label(
            self.instructions_frame,
            text="Click 'Connect Device' to begin. Enter participant ID first.\nKeyboard shortcuts: R = Repeat, N = Skip, P = Previous, E = Emergency Stop",
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

        # CORRECTED: Control frame with tkinter buttons for guaranteed visibility
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(20, 0))

        # Define button style properties
        button_config = {
            'font': ("Segoe UI", 12, "bold"),
            'width': 14,
            'height': 2,
            'bg': '#e0e0e0',
            'fg': '#222222',
            'activebackground': '#d0d0d0',
            'activeforeground': '#000000',
            'disabledforeground': '#888888',
            'relief': 'raised',
            'borderwidth': 2
        }
        
        button_config_disabled = button_config.copy()
        button_config_disabled['bg'] = '#f5f5f5'
        button_config_disabled['state'] = tk.DISABLED

        # Left side - Pattern control buttons
        pattern_control_frame = ttk.Frame(control_frame)
        pattern_control_frame.pack(side=tk.LEFT)

        self.play_button = tk.Button(
            pattern_control_frame, text="Play Pattern", command=self.play_current_pattern,
            **button_config_disabled
        )
        self.play_button.pack(side=tk.LEFT, padx=5)

        self.repeat_button = tk.Button(
            pattern_control_frame, text="Repeat (R)", command=self.repeat_pattern,
            **button_config_disabled
        )
        self.repeat_button.pack(side=tk.LEFT, padx=5)

        self.previous_button = tk.Button(
            pattern_control_frame, text="Previous (P)", command=self.previous_pattern,
            **button_config_disabled
        )
        self.previous_button.pack(side=tk.LEFT, padx=5)

        self.skip_button = tk.Button(
            pattern_control_frame, text="Skip (N)", command=self.skip_pattern,
            **button_config_disabled
        )
        self.skip_button.pack(side=tk.LEFT, padx=5)

        # Right side - Study control buttons
        study_control_frame = ttk.Frame(control_frame)
        study_control_frame.pack(side=tk.RIGHT)

        self.restart_study_button = tk.Button(
            study_control_frame, text="New Study", command=self.restart_study,
            **button_config_disabled
        )
        self.restart_study_button.pack(side=tk.RIGHT, padx=5)

        self.save_button = tk.Button(
            study_control_frame, text="Save Results", command=self.save_results,
            **button_config_disabled
        )
        self.save_button.pack(side=tk.RIGHT, padx=5)

        # Load images
        self.load_pattern_images()
        
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
        
    def load_pattern_images(self):
        """Load the pattern images"""
        try:
            # Load horizontal pattern images (../images/location/horizontal/H01.png to H12.png)
            for i in range(12):
                try:
                    img_path = f"../images/location/horizontal/H{i+1:02d}.png"  # Format as H01, H02, etc.
                    if os.path.exists(img_path):
                        img = Image.open(img_path)
                        img = img.resize((140, 140), Image.Resampling.LANCZOS)
                        self.horizontal_images.append(ImageTk.PhotoImage(img))
                    else:
                        # Create placeholder image if file doesn't exist
                        self.horizontal_images.append(self.create_placeholder_image(f"H{i+1:02d}", (140, 140)))
                except Exception as e:
                    self.horizontal_images.append(self.create_placeholder_image(f"H{i+1:02d}", (140, 140)))
            
            # Load vertical pattern images (../images/location/vertical/V01.png to V12.png)
            for i in range(12):
                try:
                    img_path = f"../images/location/vertical/V{i+1:02d}.png"  # Format as V01, V02, etc.
                    if os.path.exists(img_path):
                        img = Image.open(img_path)
                        img = img.resize((140, 140), Image.Resampling.LANCZOS)
                        self.vertical_images.append(ImageTk.PhotoImage(img))
                    else:
                        # Create placeholder image if file doesn't exist
                        self.vertical_images.append(self.create_placeholder_image(f"V{i+1:02d}", (140, 140)))
                except Exception as e:
                    self.vertical_images.append(self.create_placeholder_image(f"V{i+1:02d}", (140, 140)))
                    
        except Exception as e:
            messagebox.showwarning("Image Loading", f"Could not load some images: {e}\nUsing placeholders.")
    
    def create_placeholder_image(self, text, size):
        """Create a placeholder image with text"""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', size, color='lightblue')
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fallback to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 12)
        except:
            font = ImageFont.load_default()
        
        # Get text bounding box for centering
        bbox = draw.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        
        x = (size[0] - text_width) // 2
        y = (size[1] - text_height) // 2
        
        draw.text((x, y), text, fill='black', font=font)
        
        return ImageTk.PhotoImage(img)
    
    def create_study_sequence(self):
        """Create randomized study sequence following full_loc_study.py logic"""
        
        # Create random indices exactly like full_loc_study.py
        def create_random_indices(length=12):
            """Generate a random permutation of indices from 0 to length-1"""
            indices = list(range(length))
            random.shuffle(indices)
            return indices
        
        def create_combined_random_patterns(pattern_type_name, random_order):
            """Create a combined list mixing all pattern types for a given orientation"""
            # pattern_types = ['static', 'pulse', 'motion']  # All types
            pattern_types = ['motion']  # Only motion for testing
            all_combinations = []
            
            # Create all combinations of pattern index + pattern type
            for i, pattern_index in enumerate(random_order):
                for pattern_type in pattern_types:
                    if pattern_type_name == 'horizontal':
                        # if pattern_type == 'static':
                        #     pattern_data = self.static_horizontal[pattern_index]
                        # elif pattern_type == 'pulse':
                        #     pattern_data = self.pulse_horizontal[pattern_index]
                        # else:  # motion
                        if pattern_type == 'motion':
                            pattern_data = self.motion_horizontal[pattern_index]
                    # else:  # vertical
                    #     if pattern_type == 'static':
                    #         pattern_data = self.static_vertical[pattern_index]
                    #     elif pattern_type == 'pulse':
                    #         pattern_data = self.pulse_vertical[pattern_index]
                    #     else:  # motion
                    #         pattern_data = self.motion_vertical[pattern_index]
                    
                    all_combinations.append({
                        'pattern': pattern_data,
                        'type': pattern_type,
                        'original_index': pattern_index,
                        'randomized_position': i,
                        'name': f"{pattern_type}_{pattern_type_name}_{pattern_index+1}",
                        'pattern_type': pattern_type_name,
                        'section_name': f"Combined {pattern_type_name.title()} ({pattern_type})"
                    })
            
            # Shuffle the complete list to mix pattern types
            random.shuffle(all_combinations)
            return all_combinations
        
        # Create the same random orders as full_loc_study.py
        horizontal_random_order = create_random_indices(12)
        # vertical_random_order = create_random_indices(12)
        
        print(f"Horizontal random order: {horizontal_random_order}")
        # print(f"Vertical random order: {vertical_random_order}")
        
        # Store the random orders for answer validation
        self.horizontal_random_order = horizontal_random_order
        # self.vertical_random_order = vertical_random_order
        self.combined_random_order = [(f"horizontal_{i}", "motion") for i in horizontal_random_order]
        
        # Create combined randomized patterns
        horizontal_combined = create_combined_random_patterns('horizontal', horizontal_random_order)
        # vertical_combined = create_combined_random_patterns('vertical', vertical_random_order)
        
        print(f"Horizontal combined order: {[p['name'] for p in horizontal_combined]}")
        # print(f"Vertical combined order: {[p['name'] for p in vertical_combined[:6]]}...")  # Show first 6
        
        # Clear existing sequence
        self.study_sequence = []
        
        # Create study sequence with combined patterns (only horizontal for now)
        for pattern_info in horizontal_combined:
            self.study_sequence.append({
                'patterns': None,  # Not used in new format
                'section_name': pattern_info['section_name'],
                'pattern_type': pattern_info['pattern_type'],
                'pattern_index': pattern_info['randomized_position'],
                'original_index': pattern_info['original_index'],
                'pattern_data': pattern_info['pattern'],
                'randomized_position': pattern_info['randomized_position'],
                'full_name': pattern_info['name']
            })
        
        # Uncomment to add vertical patterns
        # for pattern_info in vertical_combined:
        #     self.study_sequence.append({
        #         'patterns': None,  # Not used in new format
        #         'section_name': pattern_info['section_name'],
        #         'pattern_type': pattern_info['pattern_type'],
        #         'pattern_index': pattern_info['randomized_position'],
        #         'original_index': pattern_info['original_index'],
        #         'pattern_data': pattern_info['pattern'],
        #         'randomized_position': pattern_info['randomized_position'],
        #         'full_name': pattern_info['name']
        #     })
    
    def connect_device(self):
        """Connect to the tactile device"""
        if not self.participant_entry.get().strip():
            messagebox.showwarning("Participant ID", "Please enter a participant ID first.")
            return
            
        ports = self.api.get_serial_devices()
        if not ports:
            messagebox.showerror("Connection", "No serial ports found.")
            return
        
        if len(ports) < 3:
            messagebox.showerror("Connection", f"Need at least 3 ports, only found {len(ports)}.")
            return
        
        # Connect explicitly to port index 2 (third port)
        connected = self.api.connect_serial_device(ports[2])
        
        if connected:
            self.participant_id = self.participant_entry.get().strip()
            self.status_label.config(text=f"Status: Connected - Participant: {self.participant_id}")
            self.connect_button.config(state=tk.DISABLED)
            self.start_study_button.config(state=tk.NORMAL)
            self.emergency_button.config(state=tk.NORMAL)
            self.participant_entry.config(state=tk.DISABLED)
            
            # Initial emergency stop to ensure clean state
            self.emergency_stop_all()
            
            messagebox.showinfo("Connection", "Successfully connected to tactile device!")
        else:
            messagebox.showerror("Connection", "Failed to connect to tactile device.")
    
    def start_study(self):
        """Start the study"""
        self.current_sequence_index = 0
        self.results = []
        self.study_completed = False
        
        # Start timer
        self.study_start_time = time.time()
        self.timer_running = True
        self.update_timer()
        
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
        
        # Show study information including randomization orders
        info_message = f"""Study started with {total_patterns} patterns.

Motion-only Combined Randomization (same as full_loc_study.py):
- All horizontal motion patterns mixed together
- Following the exact same randomization logic

Base Random Order:
Horizontal: {self.horizontal_random_order}

Controls:
- Play Pattern: Play the current tactile pattern
- Repeat (R): Replay the same pattern again
- Previous (P): Go back to previous pattern
- Skip (N): Skip to next pattern without answering
- Emergency Stop (E): Stop all actuators immediately
- Click images: Select your answer

Click 'Play Pattern' to begin."""
        
        messagebox.showinfo("Study Started", info_message)
    
    def load_current_pattern(self):
        """Load the current pattern from the sequence"""
        # Ensure play button is disabled at start of pattern load
        self.play_button.config(state=tk.DISABLED)
        
        if self.current_sequence_index >= len(self.study_sequence):
            self.study_complete()
            return
            
        current = self.study_sequence[self.current_sequence_index]
        self.current_section = current['section_name']
        self.current_pattern_type = current['pattern_type']
        
        # Use the full descriptive name from the combined randomization
        self.current_pattern_name = current['full_name']
        
        # Update UI
        progress = self.current_sequence_index + 1
        total = len(self.study_sequence)
        self.progress_label.config(text=f"Progress: {progress}/{total}")
        self.progress_bar.config(value=progress)
        
        # Update pattern type display
        pattern_parts = self.current_pattern_name.split('_')
        pattern_type = pattern_parts[0].upper() if pattern_parts else "UNKNOWN"
        orientation = pattern_parts[1].upper() if len(pattern_parts) > 1 else ""
        self.pattern_type_label.config(text=f"Pattern Type: {pattern_type} {orientation}")
        
        self.instruction_text.config(
            text=f"Ready - Pattern {progress}/{total}\nClick 'Play Pattern', then use control buttons or select your answer."
        )
        
        # Setup answer grid for current pattern type
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
            
        self.repeat_used = False
        self.play_used = False
    
    def setup_answer_grid(self):
        """Setup the answer grid based on current pattern type"""
        # Clear existing buttons
        for widget in self.answer_grid.winfo_children():
            widget.destroy()
        self.image_buttons = []
        
        # Choose images based on pattern type
        images = self.horizontal_images if self.current_pattern_type == 'horizontal' else self.vertical_images
        
        # Create title
        title_text = f"Select the {self.current_pattern_type} pattern you felt:"
        title_label = ttk.Label(self.answer_grid, text=title_text, font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=4, pady=(0, 20))
        
        # Create 3x4 grid of answer buttons
        for i in range(12):
            row = (i // 4) + 1  # Start from row 1 (row 0 is title)
            col = i % 4
            
            button = tk.Button(
                self.answer_grid,
                image=images[i],
                text=f"{i+1}",
                compound=tk.TOP,
                command=lambda idx=i: self.answer_selected(idx),
                state=tk.DISABLED,
                bg='lightgray',
                font=('Arial', 10, 'bold')
            )
            button.grid(row=row, column=col, padx=10, pady=10, sticky='nsew')
            self.image_buttons.append(button)
        
        # Configure grid weights
        for i in range(4):
            self.answer_grid.columnconfigure(i, weight=1)
        for i in range(4):  # 3 rows + title
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

        # Check if play button has already been used for this pattern
        if self.play_used:
            return

        # Mark play as used and disable Play button immediately
        self.play_used = True
        self.play_button.config(state=tk.DISABLED)

        current = self.study_sequence[self.current_sequence_index]
        pattern_data = current['pattern_data']

        # Record pattern start time
        self.pattern_start_time = time.time()

        # Update UI
        self.instruction_text.config(text=f"Playing: {self.current_pattern_name}...")
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.previous_button.config(state=tk.DISABLED)

        # Disable answer buttons
        for button in self.image_buttons:
            button.config(state=tk.DISABLED, bg='lightgray')

        # Play pattern in separate thread
        def play_pattern():
            try:
                print(f"Starting pattern: {self.current_pattern_name}")
                
                # Pre-execution clean stop
                self.emergency_stop_all()
                time.sleep(0.1)
                
                # Execute the pattern with optimized timing
                self.execute_pattern_optimized(pattern_data)
                
                # Pattern finished - record end time and enable answers
                self.pattern_end_time = time.time()
                print("Pattern playback completed")
                self.root.after(0, self.pattern_finished)
                
            except Exception as e:
                print(f"Pattern playback error: {e}")
                self.root.after(0, lambda: messagebox.showerror("Error", f"Pattern playback error: {e}"))
                self.root.after(0, self._reset_buttons_after_error)

        Thread(target=play_pattern, daemon=True).start()
    
    def _reset_buttons_after_error(self):
        """Reset button states after an error during pattern playback"""
        # Don't re-enable play button since it can only be used once per pattern
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
            text=f"Pattern complete! Click on the {self.current_pattern_type} pattern you felt, or use control buttons."
        )

        # Enable answer buttons
        for button in self.image_buttons:
            button.config(state=tk.NORMAL, bg='white')

        # Enable control buttons
        if not self.repeat_used:
            self.repeat_button.config(state=tk.NORMAL)
        else:
            self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.NORMAL)
        if self.current_sequence_index > 0:
            self.previous_button.config(state=tk.NORMAL)

        # Don't re-enable Play button since it can only be used once per pattern
    
    def answer_selected(self, selected_index):
        """Handle answer selection"""
        answer_time = time.time()
        reaction_time = answer_time - self.pattern_end_time
        
        # Record result
        current = self.study_sequence[self.current_sequence_index]
        
        # The correct answer is the original pattern index (0-11) + 1 for 1-indexing
        # The user clicks on images 0-11, so selected_index is 0-11
        # We need to check if selected_index matches the original_index
        correct_pattern_index = current['original_index']  # This is the actual pattern that was played
        
        result = {
            'participant_id': self.participant_id,
            'timestamp': datetime.now().isoformat(),
            'sequence_position': self.current_sequence_index + 1,
            'section_name': current['section_name'],
            'pattern_type': current['pattern_type'],
            'correct_answer': correct_pattern_index + 1,  # 1-indexed for display
            'selected_answer': selected_index + 1,  # 1-indexed for display
            'is_correct': selected_index == correct_pattern_index,
            'reaction_time_ms': round(reaction_time * 1000, 2),
            'pattern_duration_ms': round((self.pattern_end_time - self.pattern_start_time) * 1000, 2),
            'randomized_position': current['randomized_position'] + 1,  # Position in randomized sequence
            'horizontal_random_order': self.horizontal_random_order,  # For reference
            # 'vertical_random_order': getattr(self, 'vertical_random_order', []),  # For reference
            'combined_random_order': getattr(self, 'combined_random_order', []),
            'repeat_used': self.repeat_used
        }
        
        self.results.append(result)
        
        # Visual feedback
        correct_button = self.image_buttons[correct_pattern_index]
        selected_button = self.image_buttons[selected_index]
        
        if result['is_correct']:
            selected_button.config(bg='lightgreen')
            feedback_text = f"Correct! Reaction time: {result['reaction_time_ms']:.0f}ms"
        else:
            selected_button.config(bg='lightcoral')
            correct_button.config(bg='lightgreen')
            feedback_text = f"Incorrect. Correct answer: {result['correct_answer']}. Reaction time: {result['reaction_time_ms']:.0f}ms"
        
        self.instruction_text.config(text=feedback_text)
        
        # Disable all answer buttons and control buttons
        for button in self.image_buttons:
            button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        self.previous_button.config(state=tk.DISABLED)
        self.play_button.config(state=tk.DISABLED)
        
        # Auto-advance after showing feedback for 3 seconds
        self.root.after(3000, self.next_pattern)
    
    def next_pattern(self):
        """Move to the next pattern"""
        print(f"Transitioning to next pattern (current: {self.current_sequence_index})")
        
        # Stop all actuators and clear buffers before transitioning
        print("Stopping all actuators before transition...")
        self.emergency_stop_all()
        
        self.play_button.config(state=tk.DISABLED)
        self.current_sequence_index += 1
        
        if self.current_sequence_index >= len(self.study_sequence):
            print("Study completed!")
            self.study_complete()
        else:
            print(f"Loading pattern {self.current_sequence_index + 1}/{len(self.study_sequence)}")
            # Longer delay to ensure clean transition
            self.root.after(300, self.load_current_pattern)
    
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
        
        # Stop all actuators before going back
        self.emergency_stop_all()
        
        # Go back one pattern
        self.current_sequence_index -= 1
        self.load_current_pattern()
        
        # Show message
        self.instruction_text.config(
            text=f"Returned to previous pattern. Click 'Play Pattern' to start."
        )
    
    def repeat_pattern(self):
        """Repeat the current pattern only once, log repeat usage"""
        if self.repeat_used:
            print("Repeat already used for this pattern")
            return
            
        print(f"Repeating pattern: {self.current_pattern_name}")
        self.repeat_used = True
        self.repeat_button.config(state=tk.DISABLED)
        
        # Reset play_used so the pattern can be played again
        self.play_used = False
        
        if hasattr(self, 'pattern_end_time') and self.pattern_end_time:
            self.instruction_text.config(text="Repeating pattern...")
            self.root.after(500, self.play_current_pattern)  # Small delay for visual feedback
        else:
            print("No previous pattern to repeat, playing fresh")
            self.play_current_pattern()
    
    def skip_pattern(self):
        """Skip to next pattern without recording answer (same as 'n' key in console version)"""
        # Show visual feedback
        self.instruction_text.config(text="Skipping pattern...")
        self.play_button.config(state=tk.DISABLED)
        
        # Record that the pattern was skipped
        if self.current_sequence_index < len(self.study_sequence):
            current = self.study_sequence[self.current_sequence_index]
            skip_result = {
                'participant_id': self.participant_id,
                'timestamp': datetime.now().isoformat(),
                'sequence_position': self.current_sequence_index + 1,
                'section_name': current['section_name'],
                'pattern_type': current['pattern_type'],
                'correct_answer': current['original_index'] + 1,
                'selected_answer': 'SKIPPED',
                'is_correct': False,
                'reaction_time_ms': 0,
                'pattern_duration_ms': 0,
                'randomized_position': current['randomized_position'] + 1,
                'horizontal_random_order': getattr(self, 'horizontal_random_order', []),
                # 'vertical_random_order': getattr(self, 'vertical_random_order', []),
                'combined_random_order': getattr(self, 'combined_random_order', [])
            }
            self.results.append(skip_result)
            
        # Move to next pattern after brief delay
        self.root.after(500, self.next_pattern)
    
    def study_complete(self):
        """Handle study completion"""
        self.study_completed = True
        
        # Stop timer
        self.timer_running = False
        
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

Results Summary:
- Total Patterns: {total_patterns}
- Correct Answers: {correct_answers}
- Accuracy: {accuracy:.1f}%
- Average Reaction Time: {avg_reaction_time:.0f}ms

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
                self.status_label.config(text=f"Status: Connected - Participant: {self.participant_id}")
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
        self.timer_running = False
        
        # Create new randomized sequence
        self.create_study_sequence()
        
        # Reset UI elements
        self.progress_bar.config(value=0)
        self.progress_label.config(text="Progress: 0/0")
        self.pattern_type_label.config(text="Pattern Type: Not Started")
        self.timer_label.config(text="Time: 00:00:00")
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
    
    def update_timer(self):
        """Update the timer display"""
        if self.timer_running and self.study_start_time:
            elapsed = time.time() - self.study_start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            time_str = f"Time: {hours:02d}:{minutes:02d}:{seconds:02d}"
            self.timer_label.config(text=time_str)
            # Update every second
            self.root.after(1000, self.update_timer)
    
    def save_results(self):
        """Save results to file"""
        if not self.results:
            messagebox.showwarning("No Data", "No results to save.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"location_study_results_{self.participant_id}_{timestamp}"
        
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
                self.api.disconnect_serial_device()
            except:
                pass

def main():
    root = tk.Tk()
    app = LocationStudyInterface(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit? Any unsaved data will be lost."):
            if hasattr(app, 'api') and app.api:
                try:
                    app.emergency_stop_all()
                    app.api.disconnect_serial_device()
                except:
                    pass
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()