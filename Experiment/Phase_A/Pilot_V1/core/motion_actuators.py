import math

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
        return []

    def get_small_cross():
        return []

class circle:
    
    def get_big_circle():
        return None

    def get_medium_circle():
        return None

    def get_small_circle():
        return None
    
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
    
    def get_0(): 
        return [(90, 90), (120, 90), (150, 90), (180, 90)]

    def get_30():
        return [(90, 90), (120, 80), (150, 70), 4]
    
    def get_45(): 
        return [(90, 90), 5, (150, 30), 3]

    def get_60():
        return [(90, 90), (100, 60), (110, 30), 2]
    
    def get_90(): 
        return [(90, 90), (90, 60), (90, 30), (90, 0)]
    
    def get_120(): 
        return [(90, 90), (80, 60), (70, 30), 1]
    
    def get_135(): 
        return [(90, 90), (60, 60), (30, 30), 0]
    
    def get_150():
        return [(90, 90), (60, 80), (30, 70), 7]
    
    def get_180(): 
        return [(90, 90), (60, 90), (30, 90), (0, 90)]
    