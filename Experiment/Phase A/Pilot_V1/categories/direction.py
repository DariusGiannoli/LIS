import math
from typing import List, Tuple, Dict, Optional
from core.patterns import get_motion_engine
from core.shared import LAYOUT_POSITIONS, DUTY, VELOCITY, FREQ, DURATION, PULSE_DURATION, PAUSE_DURATION, NUM_PULSES
from core.patterns import generate_static_pattern, generate_pulse_pattern, generate_coordinate_pattern    
from core.motion_actuators import *

# Define directional pattern configurations
# Each angle maps to: (phantom_actuators, direct_actuators, phantom_ratio)
DIRECTION_CONFIGS = {
    0: {
        'phantom_pair': [],           
        'direct_actuators': [5, 4, 10, 11],      
        'phantom_ratio': 0.5,
        'description': 'East (0°)'
    },
    30: {
        'phantom_pair': [5, 10],          
        'direct_actuators': [4],          
        'phantom_ratio': 0.3,
        'description': 'Northeast 30°'
    },
    45: {
        'phantom_pair': [],         
        'direct_actuators': [5, 3],          
        'phantom_ratio': 0.4,
        'description': 'Northeast 45°'
    },
    60: {
        'phantom_pair': [5, 6],           
        'direct_actuators': [2],      
        'phantom_ratio': 0.3,
        'description': 'Northeast 60°'
    },
    90: {
        'phantom_pair': [],           
        'direct_actuators': [1, 2, 5, 6],          
        'phantom_ratio': 0.5,
        'description': 'North (90°)'
    },
    120: {
        'phantom_pair': [5, 6],           
        'direct_actuators': [1],       
        'phantom_ratio': 0.7,
        'description': 'Northwest 120°'
    },
    135: {
        'phantom_pair': [],           
        'direct_actuators': [0, 6],          
        'phantom_ratio': 0.6,
        'description': 'Northwest 135°'
    },
    150: {
        'phantom_pair': [6, 9],           
        'direct_actuators': [7],          
        'phantom_ratio': 0.3,
        'description': 'Northwest 150°'
    },
    180: {
        'phantom_pair': [],          
        'direct_actuators': [6, 7, 8, 9],      
        'phantom_ratio': 0.5,
        'description': 'West (180°)'
    },
    210: {
        'phantom_pair': [6, 9],
        'direct_actuators': [8],
        'phantom_ratio': 0.3,
        'description': 'Southwest 210°'
    },
    225: {
        'phantom_pair': [],          
        'direct_actuators': [9, 15],        
        'phantom_ratio': 0.5,
        'description': 'Southwest 225°'
    },
    240: {
        'phantom_pair': [9, 10],          
        'direct_actuators': [14],      
        'phantom_ratio': 0.3,
        'description': 'Southwest 240°'
    },
    270: {
        'phantom_pair': [],         
        'direct_actuators': [9, 10, 13, 14],         
        'phantom_ratio': 0.5,
        'description': 'South (270°)'
    },
    300: {
        'phantom_pair': [9, 10],        
        'direct_actuators': [13],     
        'phantom_ratio': 0.7,
        'description': 'Southeast 300°'
    },
    315: {
        'phantom_pair': [],         
        'direct_actuators': [10, 12],         
        'phantom_ratio': 0.5,
        'description': 'Southeast 315°'
    },
    330: {
        'phantom_pair': [5, 10],        
        'direct_actuators': [11],         
        'phantom_ratio': 0.7,
        'description': 'Southeast 330°'
    }
}

def create_generalized_direction_pattern(angle_degrees, pattern_type, base_intensity=DUTY):
    
    if angle_degrees not in DIRECTION_CONFIGS:
        raise ValueError(f"Angle {angle_degrees}° not configured. Available angles: {list(DIRECTION_CONFIGS.keys())}")
    
    config = DIRECTION_CONFIGS[angle_degrees]
    
    # Get configuration
    phantom_pair = config['phantom_pair']
    direct_actuators = config['direct_actuators']
    phantom_ratio = config['phantom_ratio']
    description = config['description']
    
    print(f"\nCreating {description} pattern:")
    print(f"  Phantom between actuators: {phantom_pair if phantom_pair else 'None (direct only)'}")
    print(f"  Direct activation: {direct_actuators}")
    
    # Check if phantom is requested
    if phantom_pair and len(phantom_pair) >= 2:
        # PHANTOM + DIRECT MODE
        engine = get_motion_engine()
        print(f"  Phantom ratio: {phantom_ratio}")
        
        # Calculate phantom position
        pos_a = LAYOUT_POSITIONS[phantom_pair[0]]
        pos_b = LAYOUT_POSITIONS[phantom_pair[1]]
        
        phantom_x = pos_a[0] + phantom_ratio * (pos_b[0] - pos_a[0])
        phantom_y = pos_a[1] + phantom_ratio * (pos_b[1] - pos_a[1])
        phantom_pos = (phantom_x, phantom_y)
        
        print(f"  Phantom position: {phantom_pos}")
        
        # Create phantom sensation
        phantom = engine.create_phantom(phantom_pos, 0.8)  # 80% intensity for phantom
        
        if not phantom:
            print("  Warning: Could not create phantom sensation, falling back to direct only")
            phantom_actuators = []
            phantom_duties = []
        else:
            # Get phantom results
            phantom_actuators = phantom['actuators']
            phantom_intensities = phantom['intensities']
            phantom_duties = [max(1, min(15, int(intensity * 15))) for intensity in phantom_intensities]
            
            print(f"  Phantom actuators: {phantom_actuators}")
            print(f"  Phantom duties: {phantom_duties}")
        
        # Combine phantom with direct activation
        all_actuators = list(phantom_actuators)
        all_duties = list(phantom_duties)
        
        # Add direct activation actuators
        for actuator in direct_actuators:
            if actuator not in phantom_actuators:
                all_actuators.append(actuator)
                all_duties.append(base_intensity)
            else:
                # If direct actuator is already in phantom, boost its intensity
                idx = phantom_actuators.index(actuator)
                all_duties[idx] = max(all_duties[idx], base_intensity)
    
    else:
        # DIRECT ONLY MODE - no phantom
        print("  Using direct activation only (no phantom)")
        all_actuators = list(direct_actuators)
        all_duties = [base_intensity] * len(direct_actuators)
    
    print(f"  Final actuators: {all_actuators}")
    print(f"  Final duties: {all_duties}")
    
    # Generate pattern
    if pattern_type == 'static':
        return generate_static_pattern(all_actuators, duty=all_duties, freq=FREQ, duration=DURATION)
    elif pattern_type == 'pulse':
        return generate_pulse_pattern(all_actuators, duty=all_duties, freq=FREQ, pulse_duration=PULSE_DURATION, pause_duration=PAUSE_DURATION, num_pulses=NUM_PULSES)
    else:
        raise ValueError(f"Pattern type {pattern_type} not supported")


# Generate pattern functions for all configured angles
def create_direction_pattern_functions():
    """Dynamically create pattern functions for all configured angles"""
    pattern_functions = {}
    
    for angle in DIRECTION_CONFIGS.keys():
        def make_pattern_function(angle_deg):
            def pattern_function():
                static = create_generalized_direction_pattern(angle_deg, 'static')
                pulse = create_generalized_direction_pattern(angle_deg, 'pulse')
                motion = static  # For now, motion is same as static
                return static, pulse, motion
            return pattern_function
        
        # Create function name
        func_name = f"direction_{angle}_pattern"
        pattern_functions[func_name] = make_pattern_function(angle)
        pattern_functions[angle] = make_pattern_function(angle)  # Also store by angle number
    
    return pattern_functions

# Create all pattern functions
DIRECTION_PATTERN_FUNCTIONS = create_direction_pattern_functions()

def get_all_direction_patterns():
    """Get all direction patterns organized by type"""
    patterns = {
        'static': {},
        'pulse': {},
        'motion': {}
    }
    
    for angle in DIRECTION_CONFIGS.keys():
        pattern_func = DIRECTION_PATTERN_FUNCTIONS[angle]
        static, pulse, motion = pattern_func()
        patterns['static'][f'{angle}_deg'] = static
        patterns['pulse'][f'{angle}_deg'] = pulse
        patterns['motion'][f'{angle}_deg'] = motion
    
    return patterns


# Generate motion patterns
ANGLES = [0, 30, 45, 60, 90, 120, 135, 150, 180]
direction_motions = {}
for angle in ANGLES:
    method = getattr(direction_patterns, f"get_{angle}", None)
    if method:
        coords = method()
        # Filter only tuple coordinates (ignore ints)
        coords = [c for c in coords if isinstance(c, tuple)]
        direction_motions[angle] = generate_coordinate_pattern(
            coordinates=coords,
            velocity=VELOCITY,
            intensity=DUTY,
            freq=FREQ
        )
    

if __name__ == "__main__":
    None