import numpy as np
import math
from typing import List, Tuple, Dict, Any
from dataclasses import dataclass

@dataclass
class Tactor:
    """Represents a physical tactile actuator"""
    id: int
    x: float
    y: float
    
class TactilePatternGenerator:
    """Core class for generating tactile patterns using the new algorithm from the paper"""
    
    def __init__(self, tactor_grid: List[Tactor], max_sampling_rate: float = 0.07):
        """
        Initialize the pattern generator
        
        Args:
            tactor_grid: List of Tactor objects representing physical actuators
            max_sampling_rate: Maximum sampling rate (duration constraint) in seconds
        """
        self.tactors = tactor_grid
        self.max_sampling_rate = max_sampling_rate
    
    def calculate_soa_duration(self, duration: float) -> float:
        """
        Calculate Signal Onset Asynchrony based on duration (Equation 1)
        SOA = 0.32 * duration + 0.0473
        """
        return 0.32 * duration + 0.0473
    
    def calculate_duration_from_soa(self, soa: float) -> float:
        """Calculate duration from SOA (inverse of Equation 1)"""
        return (soa - 0.0473) / 0.32
    
    def get_optimal_duration(self, sampling_rate: float) -> float:
        """
        Get optimal duration that satisfies constraint duration ≤ SOA (Equation 11)
        This prevents overlapping tactors
        """
        max_duration = min(sampling_rate, self.max_sampling_rate)
        calculated_duration = self.calculate_duration_from_soa(sampling_rate)
        return min(max_duration, calculated_duration)
    
    def calculate_distance(self, point: Tuple[float, float], tactor: Tactor) -> float:
        """Calculate Euclidean distance between a point and a tactor"""
        return math.sqrt((point[0] - tactor.x)**2 + (point[1] - tactor.y)**2)
    
    def find_nearest_tactors(self, point: Tuple[float, float], n: int = 3) -> List[Tuple[Tactor, float]]:
        """Find the n nearest tactors to a given point"""
        distances = [(tactor, self.calculate_distance(point, tactor)) for tactor in self.tactors]
        distances.sort(key=lambda x: x[1])
        return distances[:n]
    
    def calculate_phantom_intensities_2tactor(self, point: Tuple[float, float], 
                                            tactor1: Tactor, tactor2: Tactor, 
                                            target_intensity: float) -> Dict[int, float]:
        """
        Calculate phantom sensation intensities for 2-tactor configuration (Equation 2)
        Used when phantom point lies on line segment between two tactors
        """
        d1 = self.calculate_distance(point, tactor1)
        d2 = self.calculate_distance(point, tactor2)
        
        if d1 + d2 == 0:
            return {tactor1.id: target_intensity, tactor2.id: 0}
        
        a1 = math.sqrt(d2 / (d1 + d2)) * target_intensity
        a2 = math.sqrt(d1 / (d1 + d2)) * target_intensity
        
        return {tactor1.id: a1, tactor2.id: a2}
    
    def calculate_phantom_intensities_3tactor(self, point: Tuple[float, float], 
                                            tactors: List[Tactor], 
                                            target_intensity: float) -> Dict[int, float]:
        """
        Calculate phantom sensation intensities for 3-tactor configuration (Equation 10)
        Ai = √(1/di / Σ(1/dj)) * Av
        """
        distances = [self.calculate_distance(point, tactor) for tactor in tactors]
        
        # Avoid division by zero
        distances = [max(d, 1e-6) for d in distances]
        
        # Calculate inverse distances
        inv_distances = [1.0 / d for d in distances]
        sum_inv_distances = sum(inv_distances)
        
        intensities = {}
        for i, tactor in enumerate(tactors):
            intensity = math.sqrt(inv_distances[i] / sum_inv_distances) * target_intensity
            intensities[tactor.id] = intensity
            
        return intensities
    
    def is_point_on_line_segment(self, point: Tuple[float, float], 
                                tactor1: Tactor, tactor2: Tactor, 
                                tolerance: float = 1e-6) -> bool:
        """Check if a point lies on the line segment between two tactors"""
        # Vector from tactor1 to tactor2
        v1 = (tactor2.x - tactor1.x, tactor2.y - tactor1.y)
        # Vector from tactor1 to point
        v2 = (point[0] - tactor1.x, point[1] - tactor1.y)
        
        # Cross product to check if collinear
        cross = v1[0] * v2[1] - v1[1] * v2[0]
        if abs(cross) > tolerance:
            return False
        
        # Check if point is within the segment
        dot = v1[0] * v2[0] + v1[1] * v2[1]
        len_sq = v1[0] * v1[0] + v1[1] * v1[1]
        
        return 0 <= dot <= len_sq
    
    def calculate_phantom_intensities(self, point: Tuple[float, float], 
                                    target_intensity: float = 1.0) -> Dict[int, float]:
        """
        Calculate phantom sensation intensities for a point
        Automatically chooses between 2-tactor and 3-tactor method
        """
        nearest = self.find_nearest_tactors(point, 3)
        
        # Check if point is on line segment between first two tactors
        if len(nearest) >= 2:
            tactor1, tactor2 = nearest[0][0], nearest[1][0]
            if self.is_point_on_line_segment(point, tactor1, tactor2):
                return self.calculate_phantom_intensities_2tactor(
                    point, tactor1, tactor2, target_intensity)
        
        # Use 3-tactor configuration
        tactors = [item[0] for item in nearest[:3]]
        return self.calculate_phantom_intensities_3tactor(point, tactors, target_intensity)
    
    def sample_trajectory(self, trajectory_points: List[Tuple[float, float]], 
                         travel_time: float) -> List[Tuple[float, Tuple[float, float]]]:
        """
        Sample points along a trajectory with proper timing
        """
        if len(trajectory_points) < 2:
            return [(0.0, trajectory_points[0])] if trajectory_points else []
        
        # Calculate cumulative distances
        distances = [0.0]
        for i in range(1, len(trajectory_points)):
            dist = math.sqrt(
                (trajectory_points[i][0] - trajectory_points[i-1][0])**2 + 
                (trajectory_points[i][1] - trajectory_points[i-1][1])**2
            )
            distances.append(distances[-1] + dist)
        
        total_distance = distances[-1]
        if total_distance == 0:
            return [(0.0, trajectory_points[0])]
        
        # Sample at regular time intervals
        sampling_rate = min(self.max_sampling_rate, travel_time / 10)  # At least 10 samples
        num_samples = max(2, int(travel_time / sampling_rate))
        
        sampled_points = []
        for i in range(num_samples):
            t = (i / (num_samples - 1)) * travel_time
            target_distance = (i / (num_samples - 1)) * total_distance
            
            # Find segment containing target distance
            for j in range(len(distances) - 1):
                if distances[j] <= target_distance <= distances[j + 1]:
                    if distances[j + 1] == distances[j]:
                        point = trajectory_points[j]
                    else:
                        ratio = (target_distance - distances[j]) / (distances[j + 1] - distances[j])
                        point = (
                            trajectory_points[j][0] + ratio * (trajectory_points[j + 1][0] - trajectory_points[j][0]),
                            trajectory_points[j][1] + ratio * (trajectory_points[j + 1][1] - trajectory_points[j][1])
                        )
                    sampled_points.append((t, point))
                    break
        
        return sampled_points
    
    def generate_pattern(self, trajectory_points: List[Tuple[float, float]], 
                        travel_time: float, 
                        target_intensity: float = 1.0) -> Dict[str, Any]:
        """
        Generate complete tactile pattern using the new algorithm
        
        Args:
            trajectory_points: List of (x, y) points defining the trajectory
            travel_time: Total time to complete the trajectory in seconds
            target_intensity: Desired phantom intensity
            
        Returns:
            Dictionary containing pattern data with timing and intensities
        """
        sampled_points = self.sample_trajectory(trajectory_points, travel_time)
        
        pattern = {
            'total_time': travel_time,
            'num_points': len(sampled_points),
            'tactor_signals': {}
        }
        
        # Initialize tactor signals
        for tactor in self.tactors:
            pattern['tactor_signals'][tactor.id] = []
        
        for i, (time, point) in enumerate(sampled_points):
            intensities = self.calculate_phantom_intensities(point, target_intensity)
            
            # Calculate timing parameters
            if i < len(sampled_points) - 1:
                soa = sampled_points[i + 1][0] - time
            else:
                soa = self.max_sampling_rate
            
            duration = self.get_optimal_duration(soa)
            
            # Add signals for active tactors
            for tactor_id, intensity in intensities.items():
                if intensity > 1e-6:  # Only add significant intensities
                    pattern['tactor_signals'][tactor_id].append({
                        'start_time': time,
                        'duration': duration,
                        'intensity': intensity,
                        'soa': soa
                    })
        
        return pattern

def create_rectangular_grid(rows: int, cols: int, spacing: float) -> List[Tactor]:
    """
    Create a rectangular grid of tactors
    
    Args:
        rows: Number of rows
        cols: Number of columns  
        spacing: Distance between adjacent tactors
        
    Returns:
        List of Tactor objects
    """
    tactors = []
    tactor_id = 0
    
    for row in range(rows):
        for col in range(cols):
            x = col * spacing
            y = row * spacing
            tactors.append(Tactor(tactor_id, x, y))
            tactor_id += 1
    
    return tactors