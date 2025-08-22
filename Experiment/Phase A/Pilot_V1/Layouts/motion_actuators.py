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
        """Big circle using full grid space"""
        center_x, center_y = 90, 90
        radius = 80
        points = []
        for i in range(16):
            angle = 2 * math.pi * i / 16
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0])
        return points
    
    def get_medium_circle():
        """Medium circle using reduced grid space"""
        center_x, center_y = 90, 90
        radius = 50
        points = []
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0])
        return points

    def get_small_circle():
        """Small circle in center of grid"""
        center_x, center_y = 90, 90
        radius = 30
        points = []
        for i in range(12):
            angle = 2 * math.pi * i / 12
            x = center_x + radius * math.cos(angle)
            y = center_y + radius * math.sin(angle)
            points.append((x, y))
        points.append(points[0])
        return points
    
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