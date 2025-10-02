class square: 
    
    def get_big_square():
        return [(0,0), (30,0), (60,0), (90,0), (120,0), (150,0), (180,0), (210,0), (240,0), (270,0), 
                (270,30), (270,60), (270,90), (270,120), (270,150), (270,180), (270,210), (270,240), (270,270),
                (240,270), (210,270), (180,270), (150,270), (120,270), (90,270), (60,270), (30,270), (0,270),
                (0,240), (0,210), (0,180), (0,150), (0,120), (0,90), (0,60), (0,30), (0,0)]
        
    def get_medium_square(): 
        return []
        
    def get_small_square(): 
        return [(90,90), (120,90), (150,90), (180,90), 
                (180,120), (180,150), (180,180), (150,180), 
                (120,180), (90,180), (90,150), (90,120)]

class triangle:
    
    def get_big_triangle():
        return []
    
    def get_medium_triangle():
        return []

    def get_small_triangle():
        return []

class l: 
    
    def get_big_l():
        return [(0,0), (0,30),(0,60),(0,90),(0,120),(0,150),(0,180),(0,210),(0,240),(0,270), (30,270), (60,270), (90,270), (120,270), (150,270), (180,270), (210,270), (240,270), (270,270)]
    
    def get_medium_l():
        return [(0,90),(0,120),(0,150),(0,180),(0,210),(0,240),(0,270), (30,270), (60,270), (90,270), (120,270), (150,270), (180,270)]

    def get_small_l():
        return [(0,180),(0,210),(0,240),(0,270), (30,270), (60,270), (90,270)]

class cross: 
    def get_big_cross():
        return [(0,0),(30,30),(60,60),(90,90),(120,120),(150,150),(180,180),(210,210),(240,240),(270,270)
                ,(270,0),(240,30),(210,60),(180,90),(150,120),(120,150),(90,180),(60,210),(30,240),(0,270)]
        
    def get_medium_cross(): 
        return [(60,60), (90,90), (120,120), (150,150), (180,180),  # Diagonal top-left to bottom-right
                (180,90), (150,90), (120,90), (90,90), (60,90), (30,90),  # Horizontal line right to left
                (90,60), (90,90), (90,120), (90,150), (90,180),  # Vertical line up to down
                (120,60), (90,90), (60,120)]  # Second diagonal

    def get_small_cross():
        # Create cross pattern in center area
        return [(120,90), 5, (120,120), (120,150), 10,  # Vertical line down
                (90,150), 9, (90,120), (90,90), 6,      # Horizontal line left
                (120,90), 5]  # Back to center

class circle:
    
    def get_big_circle():
        return [1, (90, 0), 2, (150, 30), 4, (180, 90), 11, (150, 150), 13, (90, 180), 14, (30, 150), 8, (0, 90), 4, (30,30), 1]

    def get_medium_circle():
        return [2, (150, 0), (180, 30), 4, (180, 90), (180, 120), 11, (150, 150), (120, 180), 13, (90, 180), (60, 180), 14, (30, 150), (0, 120), 8, (0, 90), (0, 60), 7, (30, 30), (60, 0), 1, (90, 0), 2]

    def get_small_circle():
        return [5, (120, 90), (135, 105), 10, (135, 135), (120, 150), 9, (105, 135), (90, 120), 6, (105, 105), (120, 90), 5]
    
class h_line: 
    
    def get_big_h_line():
        return [(0,90), (30,90), (60,90), (90,90), (120,90), (150,90), (180,90), (210,90), (240,90), (270,90)]

    def get_medium_h_line():
        return [(0,90), (30,90), (60,90), (90,90), (120,90), (150,90), (180,90)]

    def get_small_h_line(): 
        return [(0,90), (30,90), (60,90), (90,90)]
    
    def get_point(): 
        return [(0,90)]

class v_line:
    
    def get_big_v_line():  
        return [(90,0), (90,30), (90,60), (90,90), (90,120), (90,150), (90,180), (90,210), (90,240), (90,270)]     

    def get_medium_v_line():  
        return [(90,0), (90,30), (90,60), (90,90), (90,120), (90,150), (90,180)]     

    def get_small_v_line():  
        return [(90,0), (90,30), (90,60), (90,90)]  
    
    def get_point(): 
        return [(90,0)]
    
# Motion pattern registry
MOTION_PATTERNS = {
    "squares": [square.get_big_square, square.get_medium_square, square.get_small_square],
    "triangle": [triangle.get_big_triangle, triangle.get_medium_triangle, triangle.get_small_triangle],
    "l": [l.get_big_l, l.get_medium_l, l.get_small_l],
    "cross": [cross.get_big_cross, cross.get_medium_cross, cross.get_small_cross],
    "circle": [circle.get_big_circle, circle.get_medium_circle, circle.get_small_circle],
    "h_line": [h_line.get_big_h_line, h_line.get_medium_h_line, h_line.get_small_h_line],
    "v_line": [v_line.get_big_v_line, v_line.get_medium_v_line, v_line.get_small_v_line]
}

def get_pattern_coordinates(pattern_name):
    """Get coordinates for a named pattern"""
    if pattern_name in MOTION_PATTERNS:
        return MOTION_PATTERNS[pattern_name]()
    else:
        return circle.get_small_circle()

def list_available_patterns():
    """Get list of all available pattern names"""
    return list(MOTION_PATTERNS.keys())

class direction_patterns:
    
    # Center point between actuators 5 and 6
    CENTER = (105, 120)  # Midpoint between actuators 5 and 6
    
    def get_north():  # Center to between actuators 1 and 2
        return [
            direction_patterns.CENTER, 
            (105, 110), (105, 100), (105, 90),  # Phantom steps (Y decreases = north)
            (105, 80), (105, 70), (105, 60),    # More phantoms
            (105, 50), (105, 40), (105, 30)     # Smooth approach to 1-2 area
        ]
    
    def get_northeast():  # Center to actuator 0
        return [
            direction_patterns.CENTER,
            (95, 110), (85, 100), (75, 90),     # Phantom steps (X-, Y- = northeast)
            (65, 80), (55, 70), (45, 60),       # More phantoms  
            (35, 50), (25, 40), 0               # Smooth approach to actuator 0
        ]
    
    def get_east():  # Center to actuator 7
        return [
            direction_patterns.CENTER,
            (95, 120), (85, 120), (75, 120),    # Phantom steps (X decreases = east)
            (65, 120), (55, 120), (45, 120),    # More phantoms
            (35, 120), (25, 120), 7             # Smooth approach to actuator 7
        ]
    
    def get_southeast():  # Center to actuator 15
        return [
            direction_patterns.CENTER,
            (95, 130), (85, 140), (75, 150),    # Phantom steps (X-, Y+ = southeast)
            (65, 160), (55, 170), (45, 180),    # More phantoms
            (35, 190), (25, 200), 15            # Smooth approach to actuator 15
        ]
    
    def get_south():  # Center to between actuators 13 and 14
        return [
            direction_patterns.CENTER,
            (105, 130), (105, 140), (105, 150), # Phantom steps (Y increases = south)
            (105, 160), (105, 170), (105, 180), # More phantoms
            (105, 190), (105, 200), (105, 210)  # Smooth approach to 13-14 area
        ]
    
    def get_southwest():  # Center to actuator 12
        return [
            direction_patterns.CENTER,
            (115, 130), (125, 140), (135, 150), # Phantom steps (X+, Y+ = southwest)
            (145, 160), (155, 170), (165, 180), # More phantoms
            (175, 190), (185, 200), 12          # Smooth approach to actuator 12
        ]
    
    def get_west():  # Center to actuator 4
        return [
            direction_patterns.CENTER,
            (115, 120), (125, 120), (135, 120), # Phantom steps (X increases = west)
            (145, 120), (155, 120), (165, 120), # More phantoms
            (175, 120), (185, 120), 4           # Smooth approach to actuator 4
        ]
    
    def get_northwest():  # Center to actuator 3
        return [
            direction_patterns.CENTER,
            (115, 110), (125, 100), (135, 90),  # Phantom steps (X+, Y- = northwest)
            (145, 80), (155, 70), (165, 60),    # More phantoms
            (175, 50), (185, 40), 3             # Smooth approach to actuator 3
        ]
    
    # Keep old numbered methods for backward compatibility
    def get_0():
        return direction_patterns.get_east()
    
    def get_30():
        return [direction_patterns.CENTER, (120, 105), (135, 90), 4]
    
    def get_45():
        return direction_patterns.get_northeast()
    
    def get_60():
        return [direction_patterns.CENTER, (120, 100), (135, 80), 2]
    
    def get_90():
        return direction_patterns.get_north()
    
    def get_120():
        return [direction_patterns.CENTER, (90, 100), (75, 80), 1]
    
    def get_135():
        return direction_patterns.get_northwest()
    
    def get_150():
        return [direction_patterns.CENTER, (90, 105), (75, 90), 7]
    
    def get_180():
        return direction_patterns.get_west()