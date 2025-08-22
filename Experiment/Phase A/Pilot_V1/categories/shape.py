from core.patterns import generate_static_pattern, generate_pulse_pattern    
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)


def cross():
    return generate_static_pattern(cross_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(cross_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def h_line(): 
    return generate_static_pattern(h_line_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(h_line_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def v_line():
    return generate_static_pattern(v_line_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(v_line_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def square(): 
    return generate_static_pattern(square_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(square_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def circle(): 
    return generate_static_pattern(circle_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(circle_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def l_shape(): 
    return generate_static_pattern(l_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(l_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)












