import itertools
from core.shared import get_4x4_grid_mapping
from core.patterns import generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern

# Location configuration: orientation -> (pattern_generator, motion_coordinates)
LOCATION_CONFIGS = {
    'horizontal': {
        'patterns': lambda: _generate_horizontal_bar_patterns(),
        'motion_coords': lambda: [
            [0, (30, 0), 1], [1, (90, 0), 2], [2, (150, 0), 3],
            [7, (30, 60), 6], [6, (90, 60), 5], [5, (150, 60), 4],
            [8, (30, 120), 9], [9, (90, 120), 10], [10, (150, 120), 11],
            [15, (30, 180), 14], [14, (90, 180), 13], [13, (150, 180), 12]
        ]
    },
    'vertical': {
        'patterns': lambda: _generate_vertical_bar_patterns(), 
        'motion_coords': lambda: [
            [0, (0, 30), 7], [7, (0, 90), 8], [8, (0, 150), 15],
            [1, (60, 30), 6], [6, (60, 90), 9], [9, (60, 150), 14],
            [2, (120, 30), 5], [5, (120, 90), 10], [10, (120, 150), 13],
            [3, (180, 30), 4], [4, (180, 90), 11], [11, (180, 150), 12]
        ]
    }
}

def _generate_horizontal_bar_patterns():
    """Generate horizontal bar patterns: [0,1], [1,2], [2,3], [4,5], etc."""
    grid = get_4x4_grid_mapping()
    return [[grid[row][col], grid[row][col + 1]] 
            for row, col in itertools.product(range(4), range(3))]

def _generate_vertical_bar_patterns():
    """Generate vertical bar patterns: [0,4], [1,5], [2,6], [4,8], etc."""
    grid = get_4x4_grid_mapping()
    return [[grid[row][col], grid[row + 1][col]] 
            for col, row in itertools.product(range(4), range(3))]

def _create_orientation_patterns(orientation, pattern_type, **params):
    """Create patterns for a specific orientation and type"""
    config = LOCATION_CONFIGS[orientation]
    
    if pattern_type == 'motion':
        return [generate_coordinate_pattern(
            coordinates=coords,
            intensity=params['DUTY'],
            freq=params['FREQ']
        ) for coords in config['motion_coords']()]
    
    # Static or pulse patterns
    pattern_func = (generate_static_pattern if pattern_type == 'static' 
                else generate_pulse_pattern)
    
    if pattern_type == 'static':
        return [pattern_func(devices, params['DUTY'], params['FREQ'], params['DURATION'])
                for devices in config['patterns']()]
    else:  # pulse
        return [pattern_func(devices, params['DUTY'], params['FREQ'], 
                        params['PULSE_DURATION'], params['PAUSE_DURATION'], params['NUM_PULSES'])
                for devices in config['patterns']()]

def create_all_commands_with_motion(DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES):
    """Create ALL commands including motion patterns"""
    # Create static commands
    static_params = {'DUTY': DUTY, 'FREQ': FREQ, 'DURATION': DURATION}
    static_commands = {
        'static_horizontal': _create_orientation_patterns('horizontal', 'static', **static_params),
        'static_vertical': _create_orientation_patterns('vertical', 'static', **static_params)
    }

    # Create pulse commands
    pulse_params = {'DUTY': DUTY, 'FREQ': FREQ, 'PULSE_DURATION': PULSE_DURATION, 
                'PAUSE_DURATION': PAUSE_DURATION, 'NUM_PULSES': NUM_PULSES}
    pulse_commands = {
        'pulse_horizontal': _create_orientation_patterns('horizontal', 'pulse', **pulse_params),
        'pulse_vertical': _create_orientation_patterns('vertical', 'pulse', **pulse_params)
    }

    # Create motion commands
    motion_params = {'DUTY': DUTY, 'FREQ': FREQ}
    motion_commands = {
        'motion_horizontal': _create_orientation_patterns('horizontal', 'motion', **motion_params),
        'motion_vertical': _create_orientation_patterns('vertical', 'motion', **motion_params)
    }

    return static_commands | pulse_commands | motion_commands