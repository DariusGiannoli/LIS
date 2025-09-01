from core.patterns import generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern    
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY,
                   cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)
from Layouts.motion_actuators import square, circle, h_line, v_line, l

def l_size_pattern(): 
    """L-shape in 3 sizes: big, medium, small"""
    # Static patterns
    big = l_actuators
    medium = [4, 8, 12, 13, 14]
    small = [8, 12, 13]
    
    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)
    
    # Pulse patterns
    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    # Motion patterns
    big_motion = generate_coordinate_pattern(
        coordinates=l.get_big_l(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    medium_motion = generate_coordinate_pattern(
        coordinates=l.get_medium_l(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    small_motion = generate_coordinate_pattern(
        coordinates=l.get_small_l(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )

    return {
        'static': {'big': big_static, 'medium': medium_static, 'small': small_static},
        'pulse': {'big': big_pulse, 'medium': medium_pulse, 'small': small_pulse},
        'motion': {'big': big_motion, 'medium': medium_motion, 'small': small_motion}
    }

def h_line_size_pattern():
    """Horizontal line in 4 sizes: big, medium, small, one"""
    # Static patterns
    big = h_line_actuators
    medium = [4, 5, 6]
    small = [4, 5]
    one = [4]

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)
    one_static = generate_static_pattern(one, DUTY, FREQ, DURATION)

    # Pulse patterns
    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    one_pulse = generate_pulse_pattern(one, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    # Motion patterns
    big_motion = generate_coordinate_pattern(
        coordinates=h_line.get_big_h_line(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    medium_motion = generate_coordinate_pattern(
        coordinates=h_line.get_medium_h_line(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    small_motion = generate_coordinate_pattern(
        coordinates=h_line.get_small_h_line(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    one_motion = generate_coordinate_pattern(
        coordinates=h_line.get_point(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )

    return {
        'static': {'big': big_static, 'medium': medium_static, 'small': small_static, 'one': one_static},
        'pulse': {'big': big_pulse, 'medium': medium_pulse, 'small': small_pulse, 'one': one_pulse},
        'motion': {'big': big_motion, 'medium': medium_motion, 'small': small_motion, 'one': one_motion}
    }

def v_line_size_pattern():
    """Vertical line in 4 sizes: big, medium, small, one"""
    # Static patterns
    big = v_line_actuators
    medium = [1, 5, 9]
    small = [1, 5]
    one = [1]

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)
    one_static = generate_static_pattern(one, DUTY, FREQ, DURATION)

    # Pulse patterns
    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    one_pulse = generate_pulse_pattern(one, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    # Motion patterns
    big_motion = generate_coordinate_pattern(
        coordinates=v_line.get_big_v_line(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    medium_motion = generate_coordinate_pattern(
        coordinates=v_line.get_medium_v_line(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    small_motion = generate_coordinate_pattern(
        coordinates=v_line.get_small_v_line(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    one_motion = generate_coordinate_pattern(
        coordinates=v_line.get_point(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )

    return {
        'static': {'big': big_static, 'medium': medium_static, 'small': small_static, 'one': one_static},
        'pulse': {'big': big_pulse, 'medium': medium_pulse, 'small': small_pulse, 'one': one_pulse},
        'motion': {'big': big_motion, 'medium': medium_motion, 'small': small_motion, 'one': one_motion}
    }

def square_size_pattern():
    """Square in 2 sizes: big, small (no medium in motion_actuators.py)"""
    # Static patterns
    big = square_actuators
    small = [5, 6, 9, 10]

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)

    # Pulse patterns
    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    # Motion patterns
    big_motion = generate_coordinate_pattern(
        coordinates=square.get_big_square(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    small_motion = generate_coordinate_pattern(
        coordinates=square.get_small_square(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )

    return {
        'static': {'big': big_static, 'small': small_static},
        'pulse': {'big': big_pulse, 'small': small_pulse},
        'motion': {'big': big_motion, 'small': small_motion}
    }

def circle_size_pattern():
    """Circle in 3 sizes: big, medium, small"""
    # Static patterns  
    big = circle_actuators
    small = [5, 6, 9, 10]  # Same as square small for static
    # For medium, we'll use a subset of the big circle
    medium = [1, 2, 7, 11, 13, 14]  # Partial circle

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)

    # Pulse patterns
    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    # Motion patterns
    big_motion = generate_coordinate_pattern(
        coordinates=circle.get_big_circle(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    medium_motion = generate_coordinate_pattern(
        coordinates=circle.get_medium_circle(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    small_motion = generate_coordinate_pattern(
        coordinates=circle.get_small_circle(),
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )

    return {
        'static': {'big': big_static, 'medium': medium_static, 'small': small_static},
        'pulse': {'big': big_pulse, 'medium': medium_pulse, 'small': small_pulse},
        'motion': {'big': big_motion, 'medium': medium_motion, 'small': small_motion}
    }

# Dictionary of all size pattern functions
SIZE_PATTERN_FUNCTIONS = {
    'l_shape': l_size_pattern,
    'h_line': h_line_size_pattern,
    'v_line': v_line_size_pattern,
    'square': square_size_pattern,
    'circle': circle_size_pattern
}

def get_all_size_patterns():
    """Get all size patterns organized by shape and pattern type"""
    all_patterns = {}
    
    for shape_name, pattern_func in SIZE_PATTERN_FUNCTIONS.items():
        all_patterns[shape_name] = pattern_func()
    
    return all_patterns
