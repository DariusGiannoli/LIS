import tkinter as tk
from tkinter import ttk, messagebox, filedialog
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
root_dir = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, root_dir)
from categories.shape import cross_pattern, h_line_pattern, v_line_pattern, square_pattern, circle_pattern, l_shape_pattern
from core.serial_api import SerialAPI
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

class ShapeStudyInterface:
    """
    GUI Interface for Shape Study - Tactile Pattern Recognition
    
    This interface follows the exact same randomization logic as shape_study.py
    to ensure consistent pattern presentation order between studies.
    
    The interface displays 6 clickable shape images (cross, h_line, v_line, square, circle, l_shape)
    and records reaction times and accuracy for each pattern response.
    """
    def __init__(self, root):
        self.root = root
        self.root.title("Shape Study Interface")
        self.root.geometry("1000x800")
        self.root.configure(bg='white')
        
        # Study data - get all shape patterns
        self.api = SerialAPI()
        self.static_shapes, self.pulse_shapes, self.motion_shapes = self.get_all_shape_patterns()
        
        # Shape names for reference
        self.shape_names = ['cross', 'h_line', 'v_line', 'square', 'circle', 'l_shape']
        
        # Current state
        self.current_shape = None
        self.current_pattern_type = None
        self.current_section = None
        self.pattern_start_time = None
        self.pattern_end_time = None
        self.current_pattern_name = None
        
        # Results storage
        self.results = []
        self.participant_id = None
        
        # Images
        self.shape_images = {}
        self.image_buttons = []
        
        # Study sequence
        self.study_sequence = []
        self.current_sequence_index = 0
        
        # GUI setup
        self.setup_gui()
        self.create_study_sequence()
        
    def get_all_shape_patterns(self):
        """Generate all shape patterns organized by type (same as shape_study.py)"""
        
        # Define all shape functions
        shape_functions = {
            'cross': cross_pattern,
            'h_line': h_line_pattern,
            'v_line': v_line_pattern,
            'square': square_pattern,
            'circle': circle_pattern,
            'l_shape': l_shape_pattern
        }
        
        # Generate patterns for each shape
        static_patterns = {}
        pulse_patterns = {}
        motion_patterns = {}
        
        for shape_name, shape_func in shape_functions.items():
            static, pulse, motion = shape_func()
            static_patterns[shape_name] = static
            pulse_patterns[shape_name] = pulse
            motion_patterns[shape_name] = motion
        
        return static_patterns, pulse_patterns, motion_patterns
        
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
            text="Shape Study - Tactile Pattern Recognition",
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
        
        self.connect_button = ttk.Button(
            conn_frame, text="Connect Device", command=self.connect_device
        )
        self.connect_button.pack(side=tk.LEFT, padx=10)
        
        self.start_study_button = ttk.Button(
            conn_frame, text="Start Study", command=self.start_study, state=tk.DISABLED
        )
        self.start_study_button.pack(side=tk.LEFT, padx=5)
        
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
            text="Click 'Connect Device' to begin. Enter participant ID first.\nKeyboard shortcuts: R = Repeat, N = Skip",
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
        
        self.skip_button = ttk.Button(
            pattern_control_frame, text="Skip (N)", command=self.skip_pattern, state=tk.DISABLED
        )
        self.skip_button.pack(side=tk.LEFT, padx=5)
        
        # Right side - Study control buttons
        study_control_frame = ttk.Frame(control_frame)
        study_control_frame.pack(side=tk.RIGHT)
        
        self.save_button = ttk.Button(
            study_control_frame, text="Save Results", command=self.save_results, state=tk.DISABLED
        )
        self.save_button.pack(side=tk.RIGHT, padx=5)
        
        # Load images
        self.load_shape_images()
        
        # Bind keyboard shortcuts
        self.root.bind('<KeyPress-r>', lambda e: self._handle_repeat_key())
        self.root.bind('<KeyPress-R>', lambda e: self._handle_repeat_key())
        self.root.bind('<KeyPress-n>', lambda e: self._handle_skip_key())
        self.root.bind('<KeyPress-N>', lambda e: self._handle_skip_key())
        self.root.focus_set()  # Ensure window can receive key events
        
    def load_shape_images(self):
        """Load the shape images or create placeholders"""
        try:
            # Try to load shape images from images/shapes/ directory
            for shape in self.shape_names:
                try:
                    img_path = f"images/shapes/{shape}.png"
                    if os.path.exists(img_path):
                        img = Image.open(img_path)
                        img = img.resize((100, 100), Image.Resampling.LANCZOS)
                        self.shape_images[shape] = ImageTk.PhotoImage(img)
                    else:
                        # Create placeholder image if file doesn't exist
                        self.shape_images[shape] = self.create_placeholder_image(shape.upper(), (100, 100))
                except Exception as e:
                    self.shape_images[shape] = self.create_placeholder_image(shape.upper(), (100, 100))
                    
        except Exception as e:
            # Create all placeholders if directory doesn't exist
            for shape in self.shape_names:
                self.shape_images[shape] = self.create_placeholder_image(shape.upper(), (100, 100))
    
    def create_placeholder_image(self, text, size):
        """Create a placeholder image with text"""
        from PIL import Image, ImageDraw, ImageFont
        
        img = Image.new('RGB', size, color='lightgray')
        draw = ImageDraw.Draw(img)
        
        # Try to use a font, fallback to default if not available
        try:
            font = ImageFont.truetype("arial.ttf", 14)
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
        """Create randomized study sequence following shape_study.py logic"""
        
        def create_combined_random_order():
            """Generate a random permutation of all shape-pattern combinations"""
            pattern_types = ['static', 'pulse', 'motion']
            all_combinations = []
            
            # Create all combinations of shape + pattern type
            for shape in self.shape_names:
                for pattern_type in pattern_types:
                    all_combinations.append((shape, pattern_type))
            
            # Shuffle the complete list
            random.shuffle(all_combinations)
            return all_combinations

        # Create single randomized order for all combinations
        combined_random_order = create_combined_random_order()
        print(f"Combined random order: {[f'{shape}_{pattern}' for shape, pattern in combined_random_order]}")
        
        # Store the random order for reference
        self.combined_random_order = combined_random_order
        
        # Create combined pattern list with metadata
        for shape, pattern_type in combined_random_order:
            if pattern_type == 'static':
                pattern_data = self.static_shapes[shape]
            elif pattern_type == 'pulse':
                pattern_data = self.pulse_shapes[shape]
            else:  # motion
                pattern_data = self.motion_shapes[shape]
            
            self.study_sequence.append({
                'pattern_data': pattern_data,
                'shape': shape,
                'pattern_type': pattern_type,
                'name': f"{shape}_{pattern_type}",
                'section_name': f"Shape: {shape.title()} ({pattern_type})"
            })
    
    def connect_device(self):
        """Connect to the tactile device"""
        if not self.participant_entry.get().strip():
            messagebox.showwarning("Participant ID", "Please enter a participant ID first.")
            return
            
        ports = self.api.get_serial_ports()
        if not ports:
            messagebox.showerror("Connection", "No serial ports found.")
            return
        
        if len(ports) < 3:
            messagebox.showerror("Connection", f"Need at least 3 ports, only found {len(ports)}.")
            return
        
        # Connect explicitly to port index 2 (third port)
        connected = self.api.connect(ports[2])
        
        if connected:
            self.participant_id = self.participant_entry.get().strip()
            self.status_label.config(text=f"Status: Connected - Participant: {self.participant_id}")
            self.connect_button.config(state=tk.DISABLED)
            self.start_study_button.config(state=tk.NORMAL)
            self.participant_entry.config(state=tk.DISABLED)
            messagebox.showinfo("Connection", "Successfully connected to tactile device!")
        else:
            messagebox.showerror("Connection", "Failed to connect to tactile device.")
    
    def start_study(self):
        """Start the study"""
        self.current_sequence_index = 0
        self.results = []
        
        # Update progress
        total_patterns = len(self.study_sequence)
        self.progress_bar.config(maximum=total_patterns)
        self.progress_bar.config(value=0)
        self.progress_label.config(text=f"Progress: 0/{total_patterns}")
        
        # Enable controls
        self.start_study_button.config(state=tk.DISABLED)
        self.play_button.config(state=tk.NORMAL)
        self.save_button.config(state=tk.NORMAL)
        
        # Load first pattern
        self.load_current_pattern()
        
        # Show study information
        info_message = f"""Study started with {total_patterns} patterns.

Randomized Shape Order (same as shape_study.py):
- All shapes (cross, h_line, v_line, square, circle, l_shape)
- All pattern types (static, pulse, motion) mixed together
- Total combinations: {len(self.study_sequence)}

Controls:
- Play Pattern: Play the current tactile pattern
- Repeat (R): Replay the same pattern again
- Skip (N): Skip to next pattern without answering
- Click shape images: Select your answer

Click 'Play Pattern' to begin."""
        
        messagebox.showinfo("Study Started", info_message)
    
    def load_current_pattern(self):
        """Load the current pattern from the sequence"""
        if self.current_sequence_index >= len(self.study_sequence):
            self.study_complete()
            return
            
        current = self.study_sequence[self.current_sequence_index]
        self.current_section = current['section_name']
        self.current_shape = current['shape']
        self.current_pattern_type = current['pattern_type']
        self.current_pattern_name = current['name']
        
        # Update UI
        progress = self.current_sequence_index + 1
        total = len(self.study_sequence)
        self.progress_label.config(text=f"Progress: {progress}/{total}")
        self.progress_bar.config(value=progress)
        
        self.instruction_text.config(
            text=f"Ready: {self.current_pattern_name}\nClick 'Play Pattern', then use Repeat/Skip buttons or select your answer."
        )
        
        # Setup answer grid
        self.setup_answer_grid()
        
        # Enable play button, disable repeat/skip buttons initially
        self.play_button.config(state=tk.NORMAL)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
    
    def setup_answer_grid(self):
        """Setup the answer grid with shape images"""
        # Clear existing buttons
        for widget in self.answer_grid.winfo_children():
            widget.destroy()
        self.image_buttons = []
        
        # Create title
        title_text = "Select the shape you felt:"
        title_label = ttk.Label(self.answer_grid, text=title_text, font=('Arial', 14, 'bold'))
        title_label.grid(row=0, column=0, columnspan=3, pady=(0, 20))
        
        # Create 2x3 grid of answer buttons (6 shapes)
        for i, shape in enumerate(self.shape_names):
            row = (i // 3) + 1  # Start from row 1 (row 0 is title)
            col = i % 3
            
            button = tk.Button(
                self.answer_grid,
                image=self.shape_images[shape],
                text=shape.replace('_', ' ').title(),
                compound=tk.TOP,
                command=lambda idx=i: self.answer_selected(idx),
                state=tk.DISABLED,
                bg='lightgray',
                font=('Arial', 10, 'bold'),
                width=120,
                height=140
            )
            button.grid(row=row, column=col, padx=15, pady=15, sticky='nsew')
            self.image_buttons.append(button)
        
        # Configure grid weights
        for i in range(3):
            self.answer_grid.columnconfigure(i, weight=1)
        for i in range(3):  # 2 rows + title
            self.answer_grid.rowconfigure(i, weight=1)
    
    def play_current_pattern(self):
        """Play the current tactile pattern"""
        if self.current_sequence_index >= len(self.study_sequence):
            return
            
        current = self.study_sequence[self.current_sequence_index]
        pattern_data = current['pattern_data']
        
        # Record pattern start time
        self.pattern_start_time = time.time()
        
        # Update UI
        self.instruction_text.config(text=f"Playing: {self.current_pattern_name}...")
        self.play_button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        
        # Disable answer buttons
        for button in self.image_buttons:
            button.config(state=tk.DISABLED, bg='lightgray')
        
        # Play pattern in separate thread
        def play_pattern():
            try:
                success = self.api.send_timed_batch(pattern_data)
                if success:
                    # Calculate pattern duration
                    max_delay = max(cmd.get('delay_ms', 0) for cmd in pattern_data)
                    # Add a small buffer to ensure pattern completes
                    time.sleep((max_delay + 500) / 1000.0)  # Convert to seconds
                    
                    # Pattern finished - record end time and enable answers
                    self.pattern_end_time = time.time()
                    self.root.after(0, self.pattern_finished)
                else:
                    self.root.after(0, lambda: messagebox.showerror("Error", "Failed to send pattern"))
                    self.root.after(0, self._reset_buttons_after_error)
            except Exception as e:
                self.root.after(0, lambda: messagebox.showerror("Error", f"Pattern playback error: {e}"))
                self.root.after(0, self._reset_buttons_after_error)
        
        Thread(target=play_pattern, daemon=True).start()
    
    def _reset_buttons_after_error(self):
        """Reset button states after an error during pattern playback"""
        self.play_button.config(state=tk.NORMAL)
        # Don't enable repeat/skip buttons until pattern has been played successfully
    
    def _handle_repeat_key(self):
        """Handle R key press"""
        if self.repeat_button['state'] == tk.NORMAL:
            self.repeat_pattern()
    
    def _handle_skip_key(self):
        """Handle N key press"""
        if self.skip_button['state'] == tk.NORMAL:
            self.skip_pattern()
    
    def pattern_finished(self):
        """Called when pattern playback is complete"""
        self.instruction_text.config(
            text=f"Pattern complete! Click on the shape you felt, or use Repeat/Skip buttons."
        )
        
        # Enable answer buttons
        for button in self.image_buttons:
            button.config(state=tk.NORMAL, bg='white')
            
        # Enable repeat and skip buttons
        self.repeat_button.config(state=tk.NORMAL)
        self.skip_button.config(state=tk.NORMAL)
    
    def answer_selected(self, selected_index):
        """Handle answer selection"""
        answer_time = time.time()
        reaction_time = answer_time - self.pattern_end_time
        
        # Record result
        current = self.study_sequence[self.current_sequence_index]
        
        # The correct answer is the current shape
        correct_shape_index = self.shape_names.index(current['shape'])
        selected_shape = self.shape_names[selected_index]
        
        result = {
            'participant_id': self.participant_id,
            'timestamp': datetime.now().isoformat(),
            'sequence_position': self.current_sequence_index + 1,
            'section_name': current['section_name'],
            'pattern_type': current['pattern_type'],
            'correct_answer': current['shape'],
            'selected_answer': selected_shape,
            'is_correct': selected_index == correct_shape_index,
            'reaction_time_ms': round(reaction_time * 1000, 2),
            'pattern_duration_ms': round((self.pattern_end_time - self.pattern_start_time) * 1000, 2),
            'combined_random_order': [f'{shape}_{pattern}' for shape, pattern in self.combined_random_order]  # For reference
        }
        
        self.results.append(result)
        
        # Visual feedback
        correct_button = self.image_buttons[correct_shape_index]
        selected_button = self.image_buttons[selected_index]
        
        if result['is_correct']:
            selected_button.config(bg='lightgreen')
            feedback_text = f"Correct! Reaction time: {result['reaction_time_ms']:.0f}ms"
        else:
            selected_button.config(bg='lightcoral')
            correct_button.config(bg='lightgreen')
            feedback_text = f"Incorrect. Correct answer: {result['correct_answer']}. Reaction time: {result['reaction_time_ms']:.0f}ms"
        
        self.instruction_text.config(text=feedback_text)
        
        # Disable all answer buttons and repeat/skip buttons
        for button in self.image_buttons:
            button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        
        # Auto-advance after showing feedback for 3 seconds
        self.root.after(3000, self.next_pattern)
    
    def next_pattern(self):
        """Move to the next pattern"""
        self.current_sequence_index += 1
        
        if self.current_sequence_index >= len(self.study_sequence):
            self.study_complete()
        else:
            self.load_current_pattern()
    
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
                'correct_answer': current['shape'],
                'selected_answer': 'SKIPPED',
                'is_correct': False,
                'reaction_time_ms': 0,
                'pattern_duration_ms': 0,
                'combined_random_order': getattr(self, 'combined_random_order', [])
            }
            self.results.append(skip_result)
        
        # Move to next pattern after brief delay
        self.root.after(500, self.next_pattern)
    
    def study_complete(self):
        """Handle study completion"""
        self.instruction_text.config(text="Study Complete! Click 'Save Results' to save your data.")
        self.play_button.config(state=tk.DISABLED)
        self.repeat_button.config(state=tk.DISABLED)
        self.skip_button.config(state=tk.DISABLED)
        
        # Show completion message with summary
        total_patterns = len(self.results)
        correct_answers = sum(1 for r in self.results if r['is_correct'])
        accuracy = (correct_answers / total_patterns) * 100 if total_patterns > 0 else 0
        avg_reaction_time = sum(r['reaction_time_ms'] for r in self.results if r['reaction_time_ms'] > 0) / max(1, len([r for r in self.results if r['reaction_time_ms'] > 0]))
        
        summary = f"""Study Complete!

Results Summary:
- Total Patterns: {total_patterns}
- Correct Answers: {correct_answers}
- Accuracy: {accuracy:.1f}%
- Average Reaction Time: {avg_reaction_time:.0f}ms

Click 'Save Results' to save your data."""
        
        messagebox.showinfo("Study Complete", summary)
    
    def save_results(self):
        """Save results to file"""
        if not self.results:
            messagebox.showwarning("No Data", "No results to save.")
            return
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"shape_study_results_{self.participant_id}_{timestamp}"
        
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
            self.api.disconnect()

def main():
    root = tk.Tk()
    app = ShapeStudyInterface(root)
    
    def on_closing():
        if messagebox.askokcancel("Quit", "Do you want to quit? Any unsaved data will be lost."):
            if hasattr(app, 'api') and app.api:
                app.api.disconnect()
            root.destroy()
    
    root.protocol("WM_DELETE_WINDOW", on_closing)
    root.mainloop()

if __name__ == "__main__":
    main()
