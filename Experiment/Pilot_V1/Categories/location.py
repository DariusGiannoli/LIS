from shared import get_4x4_grid_mapping
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY)

from core.patterns import generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern

def generate_horizontal_bar_patterns():
    """
    Patterns: [0,1], [1,2], [2,3],
                [4,5], [5,6], [6,7],
                    [8,9], [9,10], [10,11],
                    [12,13], [13,14], [14,15]
    """
    grid = get_4x4_grid_mapping()
    horizontal_patterns = []
    
    for row in range(4):
        for col in range(3):  # 3 adjacent pairs per row
            device_pair = [grid[row][col], grid[row][col + 1]]
            horizontal_patterns.append(device_pair)
    
    return horizontal_patterns

def generate_vertical_bar_patterns():
    """
    Patterns: [0,4],  [1,5],  [2,6],  [3,7],
            [4,8],  [5,9],  [6,10], [7,11],
            [8,12], [9,13], [10,14],[11,15]
    """
    grid = get_4x4_grid_mapping()
    vertical_patterns = []
    
    for col in range(4):
        for row in range(3):  # 3 adjacent pairs per column
            device_pair = [grid[row][col], grid[row + 1][col]]
            vertical_patterns.append(device_pair)
    
    return vertical_patterns

def generate_horizontal_motion_coordinates():
    """
    Generate 3-point coordinate patterns for horizontal motion
    Each pattern uses 3 coordinates that create horizontal movement
    """
    horizontal_motion_coords = [
        # Row 1 horizontal motions (12 patterns total)
        [0,1,2,3],        # Pattern 0: Left to center-left
        [7,6,5,4],      # Pattern 1: Center-left to center-right  
        [8,9,10,11],     # Pattern 2: Center-right to right
# Pattern 11: Row 4 center-right to right
    ]
    
    return horizontal_motion_coords

def generate_vertical_motion_coordinates():
    
    vertical_motion_coords = [
        [0,1,2,3],        # Pattern 0: Left to center-left
        [7,6,5,4],      # Pattern 1: Center-left to center-right  
        [8,9,10,11],
    ]
    return vertical_motion_coords

def create_all_commands(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES):
    """
    Create all commands organized in 4 lists
    
    Returns:
        dict with 4 lists:
        - static_horizontal: List of static commands for horizontal patterns
        - static_vertical: List of static commands for vertical patterns  
        - pulse_horizontal: List of pulse commands for horizontal patterns
        - pulse_vertical: List of pulse commands for vertical patterns
    """
    
    horizontal_pairs = generate_horizontal_bar_patterns()
    vertical_pairs = generate_vertical_bar_patterns()
    
    static_horizontal = []
    static_vertical = []
    pulse_horizontal = []
    pulse_vertical = []
    
    # Generate horizontal static commands
    for devices in horizontal_pairs:
        commands = generate_static_pattern(devices, DUTY, FREQ, DURATION)
        static_horizontal.append(commands)
    
    # Generate vertical static commands  
    for devices in vertical_pairs:
        commands = generate_static_pattern(devices, DUTY, FREQ, DURATION)
        static_vertical.append(commands)
    
    # Generate horizontal pulse commands
    for devices in horizontal_pairs:
        commands = generate_pulse_pattern(devices, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
        pulse_horizontal.append(commands)
    
    # Generate vertical pulse commands
    for devices in vertical_pairs:
        commands = generate_pulse_pattern(devices, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
        pulse_vertical.append(commands)
    
    return {
        'static_horizontal': static_horizontal,
        'static_vertical': static_vertical,
        'pulse_horizontal': pulse_horizontal,
        'pulse_vertical': pulse_vertical
    }

def create_motion_commands(DUTY, FREQ, VELOCITY):
    """
    Create motion commands using 3-coordinate patterns
    
    Returns:
        dict with 2 lists:
        - motion_horizontal: List of motion commands for horizontal patterns (12 patterns)
        - motion_vertical: List of motion commands for vertical patterns (12 patterns)
    """
    
    horizontal_coords = generate_horizontal_motion_coordinates()
    vertical_coords = generate_vertical_motion_coordinates()
    
    motion_horizontal = []
    motion_vertical = []
    
    # Generate horizontal motion commands
    for coords in horizontal_coords:
        commands = generate_coordinate_pattern(
            coordinates=coords,
            velocity=VELOCITY,
            intensity=DUTY,
            freq=FREQ
        )
        motion_horizontal.append(commands)
    
    # Generate vertical motion commands
    for coords in vertical_coords:
        commands = generate_coordinate_pattern(
            coordinates=coords,
            velocity=VELOCITY,
            intensity=DUTY,
            freq=FREQ
        )
        motion_vertical.append(commands)
    
    return {
        'motion_horizontal': motion_horizontal,
        'motion_vertical': motion_vertical
    }

def create_all_commands_with_motion(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY):
    """
    Create ALL commands including motion patterns
    
    Returns:
        dict with 6 lists:
        - static_horizontal: List of static commands for horizontal patterns
        - static_vertical: List of static commands for vertical patterns  
        - pulse_horizontal: List of pulse commands for horizontal patterns
        - pulse_vertical: List of pulse commands for vertical patterns
        - motion_horizontal: List of motion commands for horizontal patterns
        - motion_vertical: List of motion commands for vertical patterns
    """
    
    # Get static and pulse commands
    basic_commands = create_all_commands(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    
    # Get motion commands
    motion_commands = create_motion_commands(DUTY, FREQ, VELOCITY)
    
    # Combine all commands
    all_commands = {
        'static_horizontal': basic_commands['static_horizontal'],
        'static_vertical': basic_commands['static_vertical'],
        'pulse_horizontal': basic_commands['pulse_horizontal'], 
        'pulse_vertical': basic_commands['pulse_vertical'],
        'motion_horizontal': motion_commands['motion_horizontal'],
        'motion_vertical': motion_commands['motion_vertical']
    }
    
    return all_commands

def create_static_commands(DUTY, FREQ, DURATION):
    """Create only static commands"""
    
    horizontal_pairs = generate_horizontal_bar_patterns()
    vertical_pairs = generate_vertical_bar_patterns()
    
    static_horizontal = []
    static_vertical = []
    
    for devices in horizontal_pairs:
        commands = generate_static_pattern(devices, DUTY, FREQ, DURATION)
        static_horizontal.append(commands)
    
    for devices in vertical_pairs:
        commands = generate_static_pattern(devices, DUTY, FREQ, DURATION)
        static_vertical.append(commands)
    
    return {
        'static_horizontal': static_horizontal,
        'static_vertical': static_vertical
    }

def create_pulse_commands(DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES):
    """Create only pulse commands"""
    
    horizontal_pairs = generate_horizontal_bar_patterns()
    vertical_pairs = generate_vertical_bar_patterns()
    
    pulse_horizontal = []
    pulse_vertical = []
    
    for devices in horizontal_pairs:
        commands = generate_pulse_pattern(devices, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
        pulse_horizontal.append(commands)
    
    for devices in vertical_pairs:
        commands = generate_pulse_pattern(devices, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
        pulse_vertical.append(commands)
    
    return {
        'pulse_horizontal': pulse_horizontal,
        'pulse_vertical': pulse_vertical
    }