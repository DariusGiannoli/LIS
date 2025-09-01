from core.patterns import generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern    
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY,
                cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)
from core.motion_actuators import square, circle, h_line, v_line, l

# size: (actuators for static & pulse, actuators for motion)
SIZE_CONFIGS = {
    'l_shape': {
        'big': (l_actuators, l.get_big_l),
        'medium': ([4, 8, 12, 13, 14], l.get_medium_l),
        'small': ([8, 12, 13], l.get_small_l)
    },
    'h_line': {
        'big': (h_line_actuators, h_line.get_big_h_line),
        'medium': ([4, 5, 6], h_line.get_medium_h_line),
        'small': ([4, 5], h_line.get_small_h_line),
        'one': ([4], h_line.get_point)
    },
    'v_line': {
        'big': (v_line_actuators, v_line.get_big_v_line),
        'medium': ([1, 5, 9], v_line.get_medium_v_line),
        'small': ([1, 5], v_line.get_small_v_line),
        'one': ([1], v_line.get_point)
    },
    'square': {
        'big': (square_actuators, square.get_big_square),
        'small': ([5, 6, 9, 10], square.get_small_square)
    },
    'circle': {
        'big': (circle_actuators, circle.get_big_circle),
        'medium': ([1, 2, 7, 11, 13, 14], circle.get_medium_circle),
        'small': ([5, 6, 9, 10], circle.get_small_circle)
    }
}

def _create_size_patterns(actuators, motion_method):
    """Create static, pulse, and motion patterns for a specific size"""
    return {
        'static': generate_static_pattern(actuators, DUTY, FREQ, DURATION),
        'pulse': generate_pulse_pattern(actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES),
        'motion': generate_coordinate_pattern(
            coordinates=motion_method(),
            velocity=VELOCITY,
            intensity=DUTY,
            freq=FREQ
        )
    }

def _create_shape_size_patterns(shape_config):
    """Create all size patterns for a shape"""
    result = {'static': {}, 'pulse': {}, 'motion': {}}
    
    for size_name, (actuators, motion_method) in shape_config.items():
        patterns = _create_size_patterns(actuators, motion_method)
        result['static'][size_name] = patterns['static']
        result['pulse'][size_name] = patterns['pulse']
        result['motion'][size_name] = patterns['motion']
    
    return result

# Generate all size pattern functions dynamically
SIZE_PATTERN_FUNCTIONS = {
    shape_name: lambda config=shape_config: _create_shape_size_patterns(config)
    for shape_name, shape_config in SIZE_CONFIGS.items()
}

# Export individual pattern functions for backward compatibility
l_size_pattern = SIZE_PATTERN_FUNCTIONS['l_shape']
h_line_size_pattern = SIZE_PATTERN_FUNCTIONS['h_line']
v_line_size_pattern = SIZE_PATTERN_FUNCTIONS['v_line']
square_size_pattern = SIZE_PATTERN_FUNCTIONS['square']
circle_size_pattern = SIZE_PATTERN_FUNCTIONS['circle']

def get_all_size_patterns():
    """Get all size patterns organized by shape and pattern type"""
    return {shape_name: pattern_func() for shape_name, pattern_func in SIZE_PATTERN_FUNCTIONS.items()}
