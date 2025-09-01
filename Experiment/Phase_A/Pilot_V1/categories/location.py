import itertools
from core.shared import get_4x4_grid_mapping
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

    for row, col in itertools.product(range(4), range(3)):
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

    for col, row in itertools.product(range(4), range(3)):
        device_pair = [grid[row][col], grid[row + 1][col]]
        vertical_patterns.append(device_pair)

    return vertical_patterns

def generate_horizontal_motion_coordinates():

    return [
        # Row 0
        [0, (30, 0), 1],
        [1, (90, 0), 2],
        [2, (150, 0), 3],
        # Row 1
        [7, (30, 60), 6],
        [6, (90, 60), 5],
        [5, (150, 60), 4],
        # Row 2
        [8, (30, 120), 9],
        [9, (90, 120), 10],
        [10, (150, 120), 11],
        # Row 3
        [15, (30, 180), 14],
        [14, (90, 180), 13],
        [13, (150, 180), 12],
    ]

def generate_vertical_motion_coordinates():
    
    return [
        # Column 0
        [0, (0, 30), 7],
        [7, (0, 90), 8],
        [8, (0, 150), 15],
        # Column 1
        [1, (60, 30), 6],
        [6, (60, 90), 9],
        [9, (60, 150), 14], 
        # Column 2
        [2, (120, 30), 5],
        [5, (120, 90), 10],
        [10, (120, 150), 13],
        # Column 3
        [3, (180, 30), 4],
        [4, (180, 90), 11],
        [11, (180, 150), 12],
    ]

def create_all_commands(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES):
        
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