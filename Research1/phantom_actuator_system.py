import math
from dataclasses import dataclass
from typing import List, Tuple, Optional, Dict, Union


@dataclass
class Enhanced3ActuatorPhantom:
    """Enhanced phantom using 3-actuator system (following Park et al. paper)"""
    phantom_id: int
    virtual_position: Tuple[float, float]
    physical_actuator_1: int
    physical_actuator_2: int
    physical_actuator_3: int
    desired_intensity: int
    required_intensity_1: int
    required_intensity_2: int
    required_intensity_3: int
    triangle_area: float
    energy_efficiency: float
    phantom_type: str = "3-actuator"
    timestamp: float = 0.0
    trajectory_id: Optional[int] = None


def point_in_triangle(p: Tuple[float, float], a: Tuple[float, float], 
                    b: Tuple[float, float], c: Tuple[float, float]) -> bool:
    """Check if point p is inside triangle abc using barycentric coordinates"""
    def sign(p1, p2, p3):
        return (p1[0] - p3[0]) * (p2[1] - p3[1]) - (p2[0] - p3[0]) * (p1[1] - p3[1])
    
    d1 = sign(p, a, b)
    d2 = sign(p, b, c)
    d3 = sign(p, c, a)
    
    has_neg = (d1 < 0) or (d2 < 0) or (d3 < 0)
    has_pos = (d1 > 0) or (d2 > 0) or (d3 > 0)
    
    return not (has_neg and has_pos)


class PhantomActuatorSystem:
    """
    Phantom Actuator System implementing ONLY 3-actuator phantom creation
    Following Park et al. paper: "Rendering Moving Tactile Stroke on the Palm Using a Sparse 2D Array"
    
    Uses 3-actuator phantom sensations for arbitrary positions inside triangular areas
    with energy model: A²v = Σ(A²i) and Ai = sqrt((1/di) / Σ(1/dj)) * Av
    """
    
    def __init__(self, actuator_positions: Dict[int, Tuple[float, float]]):
        """Initialize phantom actuator system"""
        self.actuator_positions = actuator_positions
        self.enhanced_phantoms: List[Enhanced3ActuatorPhantom] = []
        self.actuator_triangles: List[Dict] = []
        self.phantoms_enabled = True
        
        self.compute_actuator_triangles()
    
    def update_actuator_positions(self, actuator_positions: Dict[int, Tuple[float, float]]):
        """Update actuator positions and recompute triangles"""
        self.actuator_positions = actuator_positions
        self.compute_actuator_triangles()

    def compute_actuator_triangles(self):
        """Compute triangles for 3-actuator phantom placement following Park et al."""
        self.actuator_triangles = []
        positions = self.actuator_positions
        
        if len(positions) < 3:
            return
        
        actuator_ids = list(positions.keys())
        
        for i in range(len(actuator_ids)):
            for j in range(i + 1, len(actuator_ids)):
                for k in range(j + 1, len(actuator_ids)):
                    act1, act2, act3 = actuator_ids[i], actuator_ids[j], actuator_ids[k]
                    pos1, pos2, pos3 = positions[act1], positions[act2], positions[act3]
                    
                    # Calculate triangle area
                    area = abs((pos1[0]*(pos2[1]-pos3[1]) + 
                            pos2[0]*(pos3[1]-pos1[1]) + 
                            pos3[0]*(pos1[1]-pos2[1]))/2)
                    
                    # Only include triangles with reasonable area
                    if area > 50 and area < 5000:
                        triangle = {
                            'actuators': [act1, act2, act3],
                            'positions': [pos1, pos2, pos3],
                            'area': area,
                            'center': ((pos1[0]+pos2[0]+pos3[0])/3, 
                                    (pos1[1]+pos2[1]+pos3[1])/3),
                            'type': f'triangle_{act1}_{act2}_{act3}',
                            'smoothness_score': self.calculate_triangle_smoothness([pos1, pos2, pos3])
                        }
                        self.actuator_triangles.append(triangle)
        
        # Sort by quality (smoothness first, then area)
        self.actuator_triangles.sort(key=lambda t: (t['smoothness_score'], t['area']))
        
        # Keep reasonable number of triangles
        max_triangles = min(100, len(self.actuator_triangles))
        self.actuator_triangles = self.actuator_triangles[:max_triangles]
        
        print(f"🔺 Generated {len(self.actuator_triangles)} triangles for 3-actuator phantoms (Park et al. method)")

    def calculate_triangle_smoothness(self, triangle_pos: List[Tuple[float, float]]) -> float:
        """Calculate smoothness score for triangle (lower = better)"""
        perimeter = 0
        for i in range(3):
            j = (i + 1) % 3
            dist = math.sqrt((triangle_pos[i][0] - triangle_pos[j][0])**2 + 
                        (triangle_pos[i][1] - triangle_pos[j][1])**2)
            perimeter += dist
        
        area = abs((triangle_pos[0][0]*(triangle_pos[1][1]-triangle_pos[2][1]) + 
                triangle_pos[1][0]*(triangle_pos[2][1]-triangle_pos[0][1]) + 
                triangle_pos[2][0]*(triangle_pos[0][1]-triangle_pos[1][1]))/2)
        
        if area > 0:
            aspect_penalty = (perimeter ** 2) / (12 * math.sqrt(3) * area)
        else:
            aspect_penalty = 1000
        
        return perimeter * 0.1 + aspect_penalty

    def find_best_triangle_for_position(self, pos: Tuple[float, float]) -> Optional[Dict]:
        """
        Find optimal triangle for 3-actuator phantom placement
        Following Park et al.: phantom tactor located at arbitrary position inside triangle
        
        Args:
            pos: (x, y) position for phantom
            
        Returns:
            Triangle containing the point, or None if position is outside all triangular areas
        """
        # Find triangles that contain the point
        containing_triangles = []
        for triangle in self.actuator_triangles:
            if point_in_triangle(pos, *triangle['positions']):
                containing_triangles.append(triangle)
        
        if containing_triangles:
            # Return the triangle with best smoothness score
            return min(containing_triangles, key=lambda t: t['smoothness_score'])
        
        return None
    
    def calculate_3actuator_intensities(self, phantom_pos: Tuple[float, float], 
                                      triangle: Dict, desired_intensity: int) -> Tuple[int, int, int]:
        """
        Calculate intensities for 3-actuator phantom using Park et al. energy model
        
        Following paper equations (8), (9), (10):
        - A²v = A²1 + A²2 + A²3 (energy summation)
        - d1·A²1 = d2·A²2 = d3·A²3 = const. (energy moment)
        - Ai = sqrt((1/di) / Σ(1/dj)) * Av (intensity calculation)
        """
        if desired_intensity < 1 or desired_intensity > 15:
            raise ValueError(f"Intensity must be 1-15, got {desired_intensity}")
        
        positions = triangle['positions']
        
        # Calculate distances from phantom to each actuator
        distances = []
        for pos in positions:
            dist = math.sqrt((phantom_pos[0] - pos[0])**2 + (phantom_pos[1] - pos[1])**2)
            distances.append(max(dist, 1.0))  # Prevent division by zero
        
        # Park et al. energy model: Ai = sqrt((1/di) / Σ(1/dj)) * Av
        sum_inv_distances = sum(1/d for d in distances)
        
        intensities_norm = []
        for dist in distances:
            intensity_norm = math.sqrt((1/dist) / sum_inv_distances) * (desired_intensity / 15.0)
            intensities_norm.append(intensity_norm)
        
        # Convert to device range (1-15)
        device_intensities = []
        for intensity_norm in intensities_norm:
            device_intensity = max(1, min(15, round(intensity_norm * 15)))
            device_intensities.append(device_intensity)
        
        return tuple(device_intensities)
    
    def create_phantom(self, phantom_pos: Tuple[float, float], 
                      desired_intensity: int) -> Optional[Enhanced3ActuatorPhantom]:
        """
        Create 3-actuator phantom at specified position following Park et al. method
        
        CRITICAL: Following the paper, phantoms can ONLY be created inside triangular areas.
        The paper states: "phantom tactor Pphantom located at an arbitrary position 
        inside of the triangle" - phantoms cannot exist outside actuator triangles.
        
        Args:
            phantom_pos: (x, y) position for phantom
            desired_intensity: Desired intensity (1-15)
            
        Returns:
            Created 3-actuator phantom or None if position is outside coverage areas
        """
        if not self.phantoms_enabled:
            return None
            
        if desired_intensity < 1 or desired_intensity > 15:
            return None
        
        phantom_id = len(self.enhanced_phantoms)
        
        # Find triangle containing the position (ONLY valid phantom locations)
        triangle = self.find_best_triangle_for_position(phantom_pos)
        if not triangle:
            print(f"❌ Position {phantom_pos} is OUTSIDE all triangular coverage areas")
            print("📍 Following Park et al.: phantoms can only exist inside triangular areas formed by 3 actuators")
            return None
        
        try:
            intensities = self.calculate_3actuator_intensities(phantom_pos, triangle, desired_intensity)
            
            # Calculate energy efficiency (A²v = A²1 + A²2 + A²3)
            total_energy = sum(i**2 for i in intensities)
            theoretical_energy = desired_intensity**2
            efficiency = theoretical_energy / total_energy if total_energy > 0 else 0
            
            phantom = Enhanced3ActuatorPhantom(
                phantom_id=phantom_id,
                virtual_position=phantom_pos,
                physical_actuator_1=triangle['actuators'][0],
                physical_actuator_2=triangle['actuators'][1],
                physical_actuator_3=triangle['actuators'][2],
                desired_intensity=desired_intensity,
                required_intensity_1=intensities[0],
                required_intensity_2=intensities[1],
                required_intensity_3=intensities[2],
                triangle_area=triangle['area'],
                energy_efficiency=efficiency
            )
            
            self.enhanced_phantoms.append(phantom)
            print(f"✅ 3-Actuator Phantom {phantom_id} created at {phantom_pos} (Park et al. method)")
            return phantom
            
        except ValueError as e:
            print(f"❌ Failed to create 3-actuator phantom: {e}")
            return None
    
    def clear_phantoms(self):
        """Clear all phantoms"""
        self.enhanced_phantoms = []
        print("🗑️ All phantoms cleared")
    
    def toggle_phantoms(self, enabled: bool):
        """Toggle phantom system on/off"""
        self.phantoms_enabled = enabled
        print(f"👻 3-Actuator Phantoms {'enabled' if enabled else 'disabled'}")
    
    def get_phantom_info(self, phantom_id: int) -> Optional[Dict]:
        """Get detailed information about a phantom"""
        if phantom_id >= len(self.enhanced_phantoms):
            return None
        
        phantom = self.enhanced_phantoms[phantom_id]
        
        return {
            'id': phantom.phantom_id,
            'type': phantom.phantom_type,
            'position': phantom.virtual_position,
            'actuators': [phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3],
            'intensities': [phantom.required_intensity_1, phantom.required_intensity_2, phantom.required_intensity_3],
            'desired_intensity': phantom.desired_intensity,
            'triangle_area': phantom.triangle_area,
            'energy_efficiency': phantom.energy_efficiency,
            'timestamp': phantom.timestamp,
            'trajectory_id': phantom.trajectory_id
        }
    
    def get_all_phantoms(self) -> List[Enhanced3ActuatorPhantom]:
        """Get all current phantoms"""
        return self.enhanced_phantoms.copy()
    
    def get_phantom_display_info(self, phantom: Enhanced3ActuatorPhantom) -> Dict:
        """Get safe display information for 3-actuator phantom"""
        return {
            'id': phantom.phantom_id,
            'type': phantom.phantom_type,
            'position': phantom.virtual_position,
            'actuators': [phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3],
            'actuators_str': f"{phantom.physical_actuator_1}, {phantom.physical_actuator_2}, {phantom.physical_actuator_3}",
            'intensities': [phantom.required_intensity_1, phantom.required_intensity_2, phantom.required_intensity_3],
            'intensities_str': f"{phantom.required_intensity_1}, {phantom.required_intensity_2}, {phantom.required_intensity_3}",
            'desired_intensity': phantom.desired_intensity,
            'energy_efficiency': phantom.energy_efficiency,
            'timestamp': phantom.timestamp,
            'trajectory_id': phantom.trajectory_id,
            'specific_info': f"Triangle area: {phantom.triangle_area:.1f}",
            'actuator_count': 3
        }
    
    def format_phantom_summary(self, phantom: Enhanced3ActuatorPhantom) -> str:
        """Get a formatted summary string for 3-actuator phantom"""
        info = self.get_phantom_display_info(phantom)
        return (f"Phantom {info['id']} ({info['type']}): "
                f"Position {info['position']}, "
                f"Using actuators: {info['actuators_str']}, "
                f"Intensities: {info['intensities_str']}, "
                f"{info['specific_info']}")
    
    def get_phantom_actuators_safe(self, phantom: Enhanced3ActuatorPhantom) -> List[int]:
        """Safely get actuator list for 3-actuator phantom"""
        return [phantom.physical_actuator_1, phantom.physical_actuator_2, phantom.physical_actuator_3]
    
    def get_phantom_intensities_safe(self, phantom: Enhanced3ActuatorPhantom) -> List[int]:
        """Safely get intensity list for 3-actuator phantom"""
        return [phantom.required_intensity_1, phantom.required_intensity_2, phantom.required_intensity_3]
    
    def get_phantom_statistics(self) -> Dict:
        """Get statistics about phantom system (always 3-actuator following Park et al.)"""
        total_phantoms = len(self.enhanced_phantoms)
        
        return {
            'total_phantoms': total_phantoms,
            'two_actuator_phantoms': 0,  # Always 0 - only 3-actuator phantoms
            'three_actuator_phantoms': total_phantoms,
            'two_actuator_percentage': 0.0,
            'three_actuator_percentage': 100.0 if total_phantoms > 0 else 0.0,
            'line_segments_available': 0,  # Not used - only triangular areas
            'triangles_available': len(self.actuator_triangles),
            'line_tolerance': 0,  # Not applicable
            'coverage_constraint': 'Park et al. method: Phantoms ONLY inside triangular areas formed by 3 actuators',
            'phantom_limitations': {
                '3_actuator': 'Only inside triangular areas formed by three actuators (Park et al.)',
                'outside_boundaries': 'CANNOT create phantoms outside triangular coverage areas',
                'method': 'Following Park et al. energy model: A²v = A²1 + A²2 + A²3'
            }
        }
    
    def remove_phantom(self, phantom_id: int) -> bool:
        """Remove a specific phantom"""
        if phantom_id < len(self.enhanced_phantoms):
            phantom_type = self.enhanced_phantoms[phantom_id].phantom_type
            del self.enhanced_phantoms[phantom_id]
            # Re-index remaining phantoms
            for i, phantom in enumerate(self.enhanced_phantoms):
                phantom.phantom_id = i
            print(f"🗑️ {phantom_type} Phantom {phantom_id} removed")
            return True
        return False


class TrajectoryPhantomManager:
    """Manages phantom creation along trajectories using 3-actuator method"""
    
    def __init__(self, phantom_system: PhantomActuatorSystem):
        self.phantom_system = phantom_system
        self.trajectory_collection: List[Dict] = []
        self.current_trajectory: List[Tuple[float, float]] = []
        self.current_trajectory_id = 0
        self.phantom_spacing_ms = 100
    
    def create_trajectory_phantoms_with_spacing(self, trajectory_points: List[Tuple[float, float]], 
                                              spacing_ms: int, trajectory_id: int, 
                                              intensity: int) -> List[Enhanced3ActuatorPhantom]:
        """Create 3-actuator phantoms along trajectory following Park et al. method"""
        if len(trajectory_points) < 2:
            return []
        
        trajectory_length = self.calculate_trajectory_length_points(trajectory_points)
        
        # Calculate number of phantoms based on spacing
        min_phantoms = 2
        max_phantoms = min(20, int(trajectory_length / 30))
        time_based_phantoms = max(2, int(trajectory_length / (spacing_ms * 0.1)))
        num_phantoms = max(min_phantoms, min(max_phantoms, time_based_phantoms))
        
        phantoms = []
        for i in range(num_phantoms):
            t = i / (num_phantoms - 1)
            point = self.interpolate_trajectory_points(trajectory_points, t)
            timestamp = i * spacing_ms
            
            phantom = self.phantom_system.create_phantom(point, intensity)
            if phantom:
                phantom.timestamp = timestamp
                phantom.trajectory_id = trajectory_id
                phantoms.append(phantom)
        
        return phantoms
    
    def calculate_trajectory_length_points(self, points: List[Tuple[float, float]]) -> float:
        """Calculate total length of trajectory from points"""
        if len(points) < 2:
            return 0
        
        length = 0
        for i in range(1, len(points)):
            dx = points[i][0] - points[i-1][0]
            dy = points[i][1] - points[i-1][1]
            length += math.sqrt(dx * dx + dy * dy)
        
        return length
    
    def interpolate_trajectory_points(self, points: List[Tuple[float, float]], t: float) -> Tuple[float, float]:
        """Interpolate point along trajectory using parameter t (0 to 1)"""
        if len(points) < 2:
            return points[0] if points else (0, 0)
        if t <= 0:
            return points[0]
        if t >= 1:
            return points[-1]
        
        total_length = self.calculate_trajectory_length_points(points)
        target_length = t * total_length
        
        current_length = 0
        for i in range(1, len(points)):
            segment_length = math.sqrt(
                (points[i][0] - points[i-1][0])**2 + 
                (points[i][1] - points[i-1][1])**2
            )
            
            if current_length + segment_length >= target_length:
                if segment_length > 0:
                    segment_t = (target_length - current_length) / segment_length
                    x = points[i-1][0] + segment_t * (points[i][0] - points[i-1][0])
                    y = points[i-1][1] + segment_t * (points[i][1] - points[i-1][1])
                    return (x, y)
                else:
                    return points[i-1]
            
            current_length += segment_length
        
        return points[-1]
    
    def set_phantom_spacing(self, spacing_ms: int):
        """Set spacing between phantoms in trajectory"""
        self.phantom_spacing_ms = max(50, min(500, spacing_ms))
        print(f"⏱️ Phantom spacing set to {self.phantom_spacing_ms}ms")
    
    def add_new_trajectory(self):
        """Start a new trajectory"""
        if len(self.current_trajectory) >= 2:
            # Save current trajectory
            trajectory_data = {
                'id': self.current_trajectory_id,
                'points': self.current_trajectory.copy(),
                'color': self.get_trajectory_color(self.current_trajectory_id),
                'phantoms': []
            }
            self.trajectory_collection.append(trajectory_data)
            print(f"📝 Trajectory {self.current_trajectory_id} saved with {len(self.current_trajectory)} points")
        
        # Start new trajectory
        self.current_trajectory_id += 1
        self.current_trajectory = []
        print(f"🆕 Started new trajectory {self.current_trajectory_id}")
    
    def get_trajectory_color(self, trajectory_id: int) -> Tuple[int, int, int]:
        """Get unique color for each trajectory"""
        colors = [
            (255, 0, 0),    # Red
            (0, 255, 0),    # Green
            (0, 0, 255),    # Blue
            (255, 255, 0),  # Yellow
            (255, 0, 255),  # Magenta
            (0, 255, 255),  # Cyan
            (255, 128, 0),  # Orange
            (128, 0, 255),  # Purple
        ]
        return colors[trajectory_id % len(colors)]
    
    def add_trajectory_point(self, point: Tuple[float, float]):
        """Add point to current trajectory"""
        self.current_trajectory.append(point)
    
    def clear_all_trajectories(self):
        """Clear all trajectories and phantoms"""
        self.trajectory_collection = []
        self.current_trajectory = []
        self.current_trajectory_id = 0
        self.phantom_system.clear_phantoms()
        print("🗑️ All trajectories and phantoms cleared")
    
    def create_all_trajectory_phantoms(self, intensity: int):
        """Create phantoms for all trajectories"""
        all_phantoms = []
        
        # Process saved trajectories
        for trajectory_data in self.trajectory_collection:
            phantoms = self.create_trajectory_phantoms_with_spacing(
                trajectory_data['points'], self.phantom_spacing_ms, 
                trajectory_data['id'], intensity
            )
            trajectory_data['phantoms'] = phantoms
            all_phantoms.extend(phantoms)
        
        return all_phantoms