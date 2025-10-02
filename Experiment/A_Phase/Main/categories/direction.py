# from core.patterns.motion_actuators import direction_patterns
# from core.patterns.generators import get_motion_engine, generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern
# from core.study_params import DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES
# from core.hardware.actuator_layout import GRID_POSITION, LAYOUT_POSITIONS

# # tuples: (phantom_pair, direct_actuators, phantom_ratio, description)
# DIRECTION_CONFIGS = {
#     0: ([], [5, 4, 10, 11], 0.5, 'East (0°)'),
#     30: ([5, 10], [4], 0.3, 'Northeast 30°'),
#     45: ([], [5, 3], 0.4, 'Northeast 45°'),
#     60: ([5, 6], [2], 0.3, 'Northeast 60°'),
#     90: ([], [1, 2, 5, 6], 0.5, 'North (90°)'),
#     120: ([5, 6], [1], 0.7, 'Northwest 120°'),
#     135: ([], [0, 6], 0.6, 'Northwest 135°'),
#     150: ([6, 9], [7], 0.3, 'Northwest 150°'),
#     180: ([], [6, 7, 8, 9], 0.5, 'West (180°)'),
#     210: ([6, 9], [8], 0.3, 'Southwest 210°'),
#     225: ([], [9, 15], 0.5, 'Southwest 225°'),
#     240: ([9, 10], [14], 0.3, 'Southwest 240°'),
#     270: ([], [9, 10, 13, 14], 0.5, 'South (270°)'),
#     300: ([9, 10], [13], 0.7, 'Southeast 300°'),
#     315: ([], [10, 12], 0.5, 'Southeast 315°'),
#     330: ([5, 10], [11], 0.7, 'Southeast 330°')
# }

# def create_generalized_direction_pattern(angle_degrees, pattern_type, base_intensity=DUTY):
#     if angle_degrees not in DIRECTION_CONFIGS:
#         raise ValueError(f"Angle {angle_degrees}° not configured. Available angles: {list(DIRECTION_CONFIGS.keys())}")
    
#     # Unpack configuration tuple
#     phantom_pair, direct_actuators, phantom_ratio, description = DIRECTION_CONFIGS[angle_degrees]
    
#     print(f"\nCreating {description} pattern:")
#     print(f"  Phantom between actuators: {phantom_pair or 'None (direct only)'}")
#     print(f"  Direct activation: {direct_actuators}")
    
#     # Initialize actuators and duties
#     all_actuators, all_duties = list(direct_actuators), [base_intensity] * len(direct_actuators)
    
#     # Add phantom if configured
#     if len(phantom_pair) >= 2:
#         engine = get_motion_engine()
#         pos_a, pos_b = LAYOUT_POSITIONS[phantom_pair[0]], LAYOUT_POSITIONS[phantom_pair[1]]
#         phantom_pos = (pos_a[0] + phantom_ratio * (pos_b[0] - pos_a[0]), 
#                       pos_a[1] + phantom_ratio * (pos_b[1] - pos_a[1]))
        
#         print(f"  Phantom ratio: {phantom_ratio}, position: {phantom_pos}")
        
#         if phantom := engine.create_phantom(phantom_pos, 0.8):
#             phantom_duties = [max(1, min(15, int(intensity * 15))) for intensity in phantom['intensities']]
            
#             # Merge phantom with direct actuators
#             for actuator, duty in zip(phantom['actuators'], phantom_duties):
#                 if actuator in all_actuators:
#                     all_duties[all_actuators.index(actuator)] = max(all_duties[all_actuators.index(actuator)], duty)
#                 else:
#                     all_actuators.append(actuator)
#                     all_duties.append(duty)
            
#             print(f"  Phantom actuators: {phantom['actuators']}, duties: {phantom_duties}")
#         else:
#             print("  Warning: Could not create phantom sensation, using direct only")
    
#     print(f"  Final actuators: {all_actuators}, duties: {all_duties}")
    
#     # Generate pattern based on type
#     pattern_generators = {
#         'static': lambda: generate_static_pattern(all_actuators, duty=all_duties, freq=FREQ, duration=DURATION),
#         'pulse': lambda: generate_pulse_pattern(all_actuators, duty=all_duties, freq=FREQ, 
#                                             pulse_duration=PULSE_DURATION, pause_duration=PAUSE_DURATION, num_pulses=NUM_PULSES)
#     }
    
#     if pattern_type not in pattern_generators:
#         raise ValueError(f"Pattern type {pattern_type} not supported")
    
#     return pattern_generators[pattern_type]()


# # Create pattern functions for all configured angles using dictionary comprehension
# DIRECTION_PATTERN_FUNCTIONS = {
#     **{f"direction_{angle}_pattern": lambda a=angle: (
#         create_generalized_direction_pattern(a, 'static'),
#         create_generalized_direction_pattern(a, 'pulse'), 
#         create_generalized_direction_pattern(a, 'static')  # motion same as static for now
#     ) for angle in DIRECTION_CONFIGS.keys()},
#     **{angle: lambda a=angle: (
#         create_generalized_direction_pattern(a, 'static'),
#         create_generalized_direction_pattern(a, 'pulse'),
#         create_generalized_direction_pattern(a, 'static')
#     ) for angle in DIRECTION_CONFIGS.keys()}
# }

# def get_all_direction_patterns():
#     """Get all direction patterns organized by type"""
#     return {
#         pattern_type: {f'{angle}_deg': DIRECTION_PATTERN_FUNCTIONS[angle]()[i] 
#                     for angle in DIRECTION_CONFIGS.keys()}
#         for i, pattern_type in enumerate(['static', 'pulse', 'motion'])
#     }

# # Generate motion patterns for specific angles (keeping original functionality)
# ANGLES = [0, 30, 45, 60, 90, 120, 135, 150, 180]
# direction_motions = {
#     angle: generate_coordinate_pattern(
#         coordinates=[c for c in getattr(direction_patterns, f"get_{angle}", lambda: [])() 
#                     if isinstance(c, tuple)],
#         intensity=DUTY, freq=FREQ
#     ) for angle in ANGLES 
#     if hasattr(direction_patterns, f"get_{angle}")
# }

from core.patterns.motion_actuators import direction_patterns
from core.patterns.serial.generators import generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern
from core.study_params import DUTY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES

# 8 cardinal and intercardinal directions starting from center (between actuators 5 and 6)
DIRECTION_CONFIGS = {
    'north': {
        'description': 'North (0°)',
        'trajectory_method': direction_patterns.get_north,
        'static_actuators': [1, 2]
    },
    'northeast': {
        'description': 'Northeast (45°)',
        'trajectory_method': direction_patterns.get_northeast,
        'static_actuators': [0] 
    },
    'east': {
        'description': 'East (90°)',
        'trajectory_method': direction_patterns.get_east,
        'static_actuators': [7]
    },
    'southeast': {
        'description': 'Southeast (135°)',
        'trajectory_method': direction_patterns.get_southeast,
        'static_actuators': [15]
    },
    'south': {
        'description': 'South (180°)',
        'trajectory_method': direction_patterns.get_south,
        'static_actuators': [13, 14]
    },
    'southwest': {
        'description': 'Southwest (225°)',
        'trajectory_method': direction_patterns.get_southwest,
        'static_actuators': [12]
    },
    'west': {
        'description': 'West (270°)',
        'trajectory_method': direction_patterns.get_west,
        'static_actuators': [4]
    },
    'northwest': {
        'description': 'Northwest (315°)',
        'trajectory_method': direction_patterns.get_northwest,
        'static_actuators': [3]
    }
}

def _create_direction_patterns(direction_config):
    """Create static, pulse, and motion patterns for a specific direction"""
    static_actuators = direction_config['static_actuators']
    trajectory_method = direction_config['trajectory_method']
    
    return {
        'static': generate_static_pattern(static_actuators, DUTY, FREQ, DURATION),
        'pulse': generate_pulse_pattern(static_actuators, DUTY, FREQ, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES),
        'motion': generate_coordinate_pattern(
            coordinates=trajectory_method(),
            intensity=DUTY,
            freq=FREQ
        )
    }

def get_all_direction_patterns():
    """Get all direction patterns organized by pattern type"""
    result = {'static': {}, 'pulse': {}, 'motion': {}}
    
    for direction_name, direction_config in DIRECTION_CONFIGS.items():
        patterns = _create_direction_patterns(direction_config)
        result['static'][direction_name] = patterns['static']
        result['pulse'][direction_name] = patterns['pulse']
        result['motion'][direction_name] = patterns['motion']
    
    return result

# Individual pattern functions for backward compatibility
def north_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['north'])

def northeast_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['northeast'])

def east_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['east'])

def southeast_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['southeast'])

def south_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['south'])

def southwest_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['southwest'])

def west_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['west'])

def northwest_pattern():
    return _create_direction_patterns(DIRECTION_CONFIGS['northwest'])