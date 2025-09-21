from core.patterns.generators import generate_coordinate_pattern, generate_static_pattern, generate_pulse_pattern    
from core.study_params import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
from core.patterns.fix_actuators import (cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)
from core.patterns.motion_actuators import square, circle, h_line, v_line, l, cross

# Shape configuration: (actuators for static and pulse, actuators for motion
SHAPE_CONFIGS = {
    'cross': (cross_actuators, cross.get_big_cross),
    'h_line': (h_line_actuators, h_line.get_big_h_line),
    'v_line': (v_line_actuators, v_line.get_big_v_line),
    'square': (square_actuators, square.get_big_square),
    'circle': (circle_actuators, circle.get_big_circle),
    'l_shape': (l_actuators, l.get_big_l)
}

def _create_shape_pattern(actuators, motion_method):
    """Generic pattern creator for all shapes"""
    static = generate_static_pattern(actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    motion = generate_coordinate_pattern(
        coordinates=motion_method(),
        intensity=DUTY,
        freq=FREQ
    )
    return static, pulse, motion

# Generate all pattern functions dynamically
def _create_pattern_functions():
    """Create pattern functions for all shapes"""
    functions = {}
    for shape_name, (actuators, motion_method) in SHAPE_CONFIGS.items():
        functions[f"{shape_name}_pattern"] = lambda a=actuators, m=motion_method: _create_shape_pattern(a, m)
    return functions

# Create pattern functions
_pattern_functions = _create_pattern_functions()

# Export pattern functions
cross_pattern = _pattern_functions['cross_pattern']
h_line_pattern = _pattern_functions['h_line_pattern'] 
v_line_pattern = _pattern_functions['v_line_pattern']
square_pattern = _pattern_functions['square_pattern']
circle_pattern = _pattern_functions['circle_pattern']
l_shape_pattern = _pattern_functions['l_shape_pattern']