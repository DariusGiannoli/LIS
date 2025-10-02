#Common parameters
DUTY = 14
FREQ = 7
DURATION = 1000
PULSE_DURATION = 100
PAUSE_DURATION = 100
NUM_PULSES = 5

# Park et al. (2016) parameters
MOTION_PARAMS = {
    'SOA_SLOPE': 0.32,
    'SOA_BASE': 0.0473,
    'MAX_DURATION': 0.07,
    'MIN_TRIANGLE_AREA': 25,
}

MOTION_DURATION = 0.04  # Reduced from 0.06 for faster motion
MOVEMENT_SPEED = 2000    # Reduced from 2000 for smoother motion (more samples)