from core.patterns import generate_coordinate_pattern, generate_static_pattern, generate_pulse_pattern    
from core.shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, VELOCITY, cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)
from core.motion_actuators import square, circle, h_line, v_line, l, cross


def cross_pattern():
    static = generate_static_pattern(cross_actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(cross_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    motion_coords = cross.get_big_cross()
    motion = generate_coordinate_pattern(
        coordinates=motion_coords,
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    
    return static, pulse, motion

def h_line_pattern(): 
    static = generate_static_pattern(h_line_actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(h_line_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    motion_coords = h_line.get_big_h_line()
    motion = generate_coordinate_pattern(
        coordinates=motion_coords,
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    return static, pulse, motion

def v_line_pattern():
    static = generate_static_pattern(v_line_actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(v_line_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    motion_coords = v_line.get_big_v_line()
    motion = generate_coordinate_pattern(
        coordinates=motion_coords,
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    return static, pulse, motion

def square_pattern(): 
    static = generate_static_pattern(square_actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(square_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    motion_coords = square.get_big_square()
    motion = generate_coordinate_pattern(
        coordinates=motion_coords,
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    return static, pulse, motion

def circle_pattern(): 
    static = generate_static_pattern(circle_actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(circle_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    motion_coords = circle.get_big_circle()
    motion = generate_coordinate_pattern(
        coordinates=motion_coords,
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    return static, pulse, motion

def l_shape_pattern(): 
    static = generate_static_pattern(l_actuators, DUTY, FREQ, DURATION)
    pulse = generate_pulse_pattern(l_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    motion_coords = l.get_big_l()
    motion = generate_coordinate_pattern(
        coordinates=motion_coords,
        velocity=VELOCITY,
        intensity=DUTY,
        freq=FREQ
    )
    return static, pulse, motion