def get_4x4_grid_mapping():
    return [
        [0,  1,  2,  3],   # Row 0
        [4,  5,  6,  7],   # Row 1  
        [8,  9, 10, 11],   # Row 2
        [12, 13, 14, 15]   # Row 3
    ]

LAYOUT_POSITIONS = {
    0: (0, 0), 1: (60, 0), 2: (120, 0), 3: (180, 0),
    4: (0, 60), 5: (60, 60), 6: (120, 60), 7: (180, 60),
    8: (0, 120), 9: (60, 120), 10: (120, 120), 11: (180, 120),
    12: (0, 180), 13: (60, 180), 14: (120, 180), 15: (180, 180)
}

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

# Park et al. (2016) parameters
MOTION_PARAMS = {
    'SOA_SLOPE': 0.32,
    'SOA_BASE': 0.0473,
    'MAX_DURATION': 0.07,
    'MIN_TRIANGLE_AREA': 25,
}
