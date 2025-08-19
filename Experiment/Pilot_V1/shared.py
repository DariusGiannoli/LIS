def get_4x4_grid_mapping():
    return [
        [0,  1,  2,  3],   # Row 0
        [4,  5,  6,  7],   # Row 1  
        [8,  9, 10, 11],   # Row 2
        [12, 13, 14, 15]   # Row 3
    ]

#Common parameters
DUTY = 8
FREQ = 3
DURATION = 2000
PULSE_DURATION = 500
PAUSE_DURATION = 500
NUM_PULSES = 3

# Actuator mappings
cross_actuators = [0, 5, 10, 15, 3, 6, 9, 12]
h_line_actuators = [4, 5, 6, 7]
v_line_actuators = [1, 5, 9, 13]
square_actuators = [0, 1, 2, 3, 4, 7, 11, 15, 14, 13, 12, 8, 4]
circle_actuators = [1, 2, 7, 11, 13, 14, 4, 8]
l_actuators = [0, 4, 8, 12, 13, 14, 15]