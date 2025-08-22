from core.patterns import generate_static_pattern, generate_pulse_pattern    
from shared import (DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES, cross_actuators, h_line_actuators, v_line_actuators, square_actuators, circle_actuators, l_actuators)

def error(): #Cross
    return generate_static_pattern(cross_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(cross_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def stop(): #Horizontal
    return generate_static_pattern(h_line_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(h_line_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def start(): #Vertical
    return generate_static_pattern(v_line_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(v_line_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def complete(): #Square
    return generate_static_pattern(square_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(square_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)

def turn(): #L Shape
    return generate_static_pattern(l_actuators, DUTY, FREQ, DURATION), generate_pulse_pattern(l_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES)