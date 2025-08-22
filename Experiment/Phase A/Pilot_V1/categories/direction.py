import math
from typing import List, Tuple

def generate_radial_circle_points(center: Tuple[float, float], radius: float, 
                                num_circumference_points: int = 8, 
                                points_per_line: int = 5) -> List[Tuple[float, float]]:
    """
    Generate points along radial lines from center to circumference points
    
    Args:
        center: (x, y) center of the circle
        radius: Circle radius
        num_circumference_points: Number of points on circumference (constant you can modify)
        points_per_line: Number of points to sample along each radial line
        
    Returns:
        List of (x, y) coordinates along all radial lines
    """
    
    center_x, center_y = center
    all_points = []
    
    # Generate evenly spaced points on circumference
    for i in range(num_circumference_points):
        # Calculate angle for this circumference point
        angle = 2 * math.pi * i / num_circumference_points
        
        # Calculate circumference point
        circumference_x = center_x + radius * math.cos(angle)
        circumference_y = center_y + radius * math.sin(angle)
        
        # Generate points along the line from center to circumference
        for j in range(points_per_line):
            # Parameter t goes from 0 (center) to 1 (circumference)
            t = j / (points_per_line - 1) if points_per_line > 1 else 0
            
            # Interpolate along the line
            point_x = center_x + t * (circumference_x - center_x)
            point_y = center_y + t * (circumference_y - center_y)
            
            all_points.append((point_x, point_y))
    
    return all_points

def generate_radial_circle_lines(center: Tuple[float, float], radius: float,
                                num_lines: int = 8,
                                points_per_line: int = 5) -> List[List[Tuple[float, float]]]:
    """
    Generate radial lines as separate lists (alternative organization)
    
    Returns:
        List of lines, where each line is a list of (x, y) coordinates
    """
    
    center_x, center_y = center
    lines = []
    
    for i in range(num_lines):
        # Calculate angle for this line
        angle = 2 * math.pi * i / num_lines
        
        # Calculate endpoint on circumference
        end_x = center_x + radius * math.cos(angle)
        end_y = center_y + radius * math.sin(angle)
        
        # Generate points along this radial line
        line_points = []
        for j in range(points_per_line):
            t = j / (points_per_line - 1) if points_per_line > 1 else 0
            
            point_x = center_x + t * (end_x - center_x)
            point_y = center_y + t * (end_y - center_y)
            
            line_points.append((point_x, point_y))
        
        lines.append(line_points)
    
    return lines

def generate_expanding_circle(center: Tuple[float, float], max_radius: float,
                            num_circumference_points: int = 12,
                            num_radius_steps: int = 5) -> List[Tuple[float, float]]:
    """
    Generate expanding circle pattern - points at different radii
    
    Args:
        center: (x, y) center of the circle
        max_radius: Maximum radius
        num_circumference_points: Points around circumference
        num_radius_steps: Number of concentric circles
        
    Returns:
        List of (x, y) coordinates forming expanding circles
    """
    
    center_x, center_y = center
    all_points = []
    
    # Start from center
    all_points.append((center_x, center_y))
    
    # Generate concentric circles
    for radius_step in range(1, num_radius_steps + 1):
        current_radius = (radius_step / num_radius_steps) * max_radius
        
        # Generate points on this circle
        for i in range(num_circumference_points):
            angle = 2 * math.pi * i / num_circumference_points
            
            point_x = center_x + current_radius * math.cos(angle)
            point_y = center_y + current_radius * math.sin(angle)
            
            all_points.append((point_x, point_y))
    
    return all_points

def generate_spiral_outward(center: Tuple[float, float], max_radius: float,
                        total_points: int = 50) -> List[Tuple[float, float]]:
    """
    Generate spiral pattern from center outward
    
    Args:
        center: (x, y) center point
        max_radius: Maximum radius to reach
        total_points: Total number of points in spiral
        
    Returns:
        List of (x, y) coordinates forming spiral
    """
    
    center_x, center_y = center
    points = []
    
    for i in range(total_points):
        # Parameter t goes from 0 to 1
        t = i / (total_points - 1)
        
        # Radius grows linearly
        radius = t * max_radius
        
        # Angle creates spiral (multiple rotations)
        angle = 4 * math.pi * t  # 2 full rotations
        
        point_x = center_x + radius * math.cos(angle)
        point_y = center_y + radius * math.sin(angle)
        
        points.append((point_x, point_y))
    
    return points

# Configuration constants (modify these as needed)
NUM_CIRCUMFERENCE_POINTS = 8  # Number of radial lines
POINTS_PER_LINE = 5           # Points along each line
DEFAULT_RADIUS = 60           # Default radius
DEFAULT_CENTER = (90, 90)     # Default center for 4x4 grid

# Example usage functions
def create_radial_pattern_for_tactile():
    """Create radial pattern suitable for your tactile system"""
    return generate_radial_circle_points(
        center=DEFAULT_CENTER,
        radius=DEFAULT_RADIUS, 
        num_circumference_points=NUM_CIRCUMFERENCE_POINTS,
        points_per_line=POINTS_PER_LINE
    )

def create_expanding_pattern_for_tactile():
    """Create expanding circle pattern"""
    return generate_expanding_circle(
        center=DEFAULT_CENTER,
        max_radius=DEFAULT_RADIUS,
        num_circumference_points=12,
        num_radius_steps=4
    )

def create_spiral_pattern_for_tactile():
    """Create spiral pattern"""
    return generate_spiral_outward(
        center=DEFAULT_CENTER,
        max_radius=DEFAULT_RADIUS,
        total_points=30
    )
