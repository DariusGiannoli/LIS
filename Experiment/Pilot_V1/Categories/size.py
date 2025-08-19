from Categories.core.patterns import generate_static_pattern, generate_pulse_pattern    
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)

def l_size(): 
    big = l_actuators
    medium = [4, 8, 12, 13, 14]
    small = [8, 12, 13,]
    
    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)
    
    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    return big_static, medium_static, small_static, big_pulse, medium_pulse, small_pulse

def h_size():
    big = h_line_actuators
    medium = [4, 5, 6]
    small = [4, 5]
    one = [4]

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)
    one_static = generate_static_pattern(one, DUTY, FREQ, DURATION)

    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    one_pulse = generate_pulse_pattern(one, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    return big_static, medium_static, small_static, one_static, big_pulse, medium_pulse, small_pulse, one_pulse

def v_size():
    big = v_line_actuators
    medium = [1, 5, 9]
    small = [1, 5]
    one = [1]

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)
    one_static = generate_static_pattern(one, DUTY, FREQ, DURATION)

    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    one_pulse = generate_pulse_pattern(one, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    return big_static, medium_static, small_static, one_static, big_pulse, medium_pulse, small_pulse, one_pulse

def square_size():
    big = square_actuators
    medium = None
    small = [5, 6, 9, 10]

    big_static = generate_static_pattern(big, DUTY, FREQ, DURATION)
    medium_static = generate_static_pattern(medium, DUTY, FREQ, DURATION)
    small_static = generate_static_pattern(small, DUTY, FREQ, DURATION)

    big_pulse = generate_pulse_pattern(big, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    medium_pulse = generate_pulse_pattern(medium, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)
    small_pulse = generate_pulse_pattern(small, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

    return big_static, medium_static, small_static, big_pulse, medium_pulse, small_pulse
