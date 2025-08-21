import numpy as np
import matplotlib.pyplot as plt

def create_grid_layout():
    """
    Create an 8x8 grid with 30mm spacing where:
    - Physical actuators form a 4x4 grid with 60mm spacing
    - Phantom points fill the remaining positions
    """
    
    # Grid parameters
    grid_size = 8
    spacing = 30  # mm between grid points
    
    # Create coordinate arrays
    x_coords = np.arange(0, grid_size) * spacing
    y_coords = np.arange(0, grid_size) * spacing
    
    # Create meshgrid for all positions
    X, Y = np.meshgrid(x_coords, y_coords)
    
    # Initialize arrays to store grid information
    grid_data = []
    
    # Actuator positions (every other point in both directions, forming 4x4)
    actuator_positions = []
    phantom_positions = []
    
    # Counters for separate indexing
    actuator_count = 0
    phantom_count = 0
    
    for i in range(grid_size):
        for j in range(grid_size):
            x_pos = j * spacing
            y_pos = i * spacing
            global_index = i * grid_size + j
            
            # Check if this is an actuator position (every other point)
            if i % 2 == 0 and j % 2 == 0:
                point_type = "Actuator"
                typed_index = f"A{actuator_count:02d}"  # A00, A01, A02, etc.
                actuator_positions.append((i, j, x_pos, y_pos, typed_index, global_index, actuator_count))
                actuator_count += 1
            else:
                point_type = "Phantom"
                typed_index = f"P{phantom_count:02d}"  # P00, P01, P02, etc.
                phantom_positions.append((i, j, x_pos, y_pos, typed_index, global_index, phantom_count))
                phantom_count += 1
            
            grid_data.append({
                'global_index': global_index,
                'typed_index': typed_index,
                'grid_i': i,
                'grid_j': j,
                'x_mm': x_pos,
                'y_mm': y_pos,
                'type': point_type
            })
    
    return grid_data, actuator_positions, phantom_positions, X, Y

def print_grid_summary(grid_data, actuator_positions, phantom_positions):
    """Print summary of the grid layout"""
    
    print("=== GRID LAYOUT SUMMARY ===")
    print(f"Total grid points: {len(grid_data)}")
    print(f"Physical actuators: {len(actuator_positions)}")
    print(f"Phantom points: {len(phantom_positions)}")
    print(f"Grid spacing: 30mm")
    print(f"Actuator spacing: 60mm")
    print()
    
    print("=== ACTUATOR POSITIONS ===")
    print("Type ID | Global | Grid(i,j) | Position(x,y) mm")
    print("-" * 50)
    for i, j, x, y, typed_idx, global_idx, local_idx in actuator_positions:
        print(f"{typed_idx:6s} | {global_idx:6d} | ({i},{j})     | ({x:3.0f},{y:3.0f})")
    
    print("\n=== PHANTOM POSITIONS (First 10) ===")
    print("Type ID | Global | Grid(i,j) | Position(x,y) mm")
    print("-" * 50)
    for i, j, x, y, typed_idx, global_idx, local_idx in phantom_positions[:10]:
        print(f"{typed_idx:6s} | {global_idx:6d} | ({i},{j})     | ({x:3.0f},{y:3.0f})")
    if len(phantom_positions) > 10:
        print(f"... and {len(phantom_positions) - 10} more phantom points")

class GridLookup:
    """Class to handle coordinate and index lookups"""
    
    def __init__(self, grid_data, actuator_positions, phantom_positions):
        self.grid_data = grid_data
        self.actuator_positions = actuator_positions
        self.phantom_positions = phantom_positions
        
        # Create lookup dictionaries
        self._create_lookup_tables()
    
    def _create_lookup_tables(self):
        """Create internal lookup tables for fast access"""
        
        # Typed index to coordinates
        self.typed_to_coords = {}
        # Global index to coordinates  
        self.global_to_coords = {}
        # Coordinates to typed index
        self.coords_to_typed = {}
        
        for item in self.grid_data:
            typed_idx = item['typed_index']
            global_idx = item['global_index']
            coords = (item['x_mm'], item['y_mm'])
            grid_coords = (item['grid_i'], item['grid_j'])
            
            self.typed_to_coords[typed_idx] = {
                'physical_coords': coords,
                'grid_coords': grid_coords,
                'global_index': global_idx,
                'type': item['type']
            }
            
            self.global_to_coords[global_idx] = {
                'physical_coords': coords,
                'grid_coords': grid_coords,
                'typed_index': typed_idx,
                'type': item['type']
            }
            
            self.coords_to_typed[coords] = typed_idx
    
    def get_coords_from_typed_index(self, typed_index):
        """Get coordinates from typed index (e.g., 'A05' or 'P23')"""
        if typed_index in self.typed_to_coords:
            return self.typed_to_coords[typed_index]
        else:
            return None
    
    def get_coords_from_global_index(self, global_index):
        """Get coordinates from global index (0-63)"""
        if global_index in self.global_to_coords:
            return self.global_to_coords[global_index]
        else:
            return None
    
    def get_typed_index_from_coords(self, x, y):
        """Get typed index from coordinates"""
        coords = (x, y)
        return self.coords_to_typed.get(coords, None)
    
    def get_all_actuators(self):
        """Get all actuator information"""
        return [info for idx, info in self.typed_to_coords.items() 
                if idx.startswith('A')]
    
    def get_all_phantoms(self):
        """Get all phantom information"""
        return [info for idx, info in self.typed_to_coords.items() 
                if idx.startswith('P')]
    
    def print_lookup_examples(self):
        """Print examples of how to use the lookup functions"""
        print("\n=== LOOKUP EXAMPLES ===")
        
        # Example with actuator
        print("Getting coordinates from actuator A05:")
        result = self.get_coords_from_typed_index('A05')
        if result:
            print(f"  A05 -> Physical: {result['physical_coords']}, Grid: {result['grid_coords']}")
        
        # Example with phantom
        print("Getting coordinates from phantom P10:")
        result = self.get_coords_from_typed_index('P10')
        if result:
            print(f"  P10 -> Physical: {result['physical_coords']}, Grid: {result['grid_coords']}")
        
        # Example with global index
        print("Getting info from global index 35:")
        result = self.get_coords_from_global_index(35)
        if result:
            print(f"  Global 35 -> {result['typed_index']}, Physical: {result['physical_coords']}")
        
        # Example reverse lookup
        print("Getting typed index from coordinates (90, 60):")
        typed_idx = self.get_typed_index_from_coords(90, 60)
        print(f"  (90, 60) -> {typed_idx}")
        
        print("\nActuator count:", len(self.get_all_actuators()))
        print("Phantom count:", len(self.get_all_phantoms()))

def visualize_grid(X, Y, actuator_positions, phantom_positions):
    """Create a visualization of the grid layout"""
    
    plt.figure(figsize=(12, 10))
    
    # Plot all grid points
    plt.scatter(X, Y, c='lightgray', s=30, alpha=0.5, label='All grid points')
    
    # Plot actuator positions
    act_x = [pos[2] for pos in actuator_positions]
    act_y = [pos[3] for pos in actuator_positions]
    plt.scatter(act_x, act_y, c='red', s=120, marker='s', label='Actuators', edgecolors='black', linewidth=2)
    
    # Plot phantom positions
    phan_x = [pos[2] for pos in phantom_positions]
    phan_y = [pos[3] for pos in phantom_positions]
    plt.scatter(phan_x, phan_y, c='blue', s=60, marker='o', label='Phantoms', alpha=0.7, edgecolors='darkblue')
    
    # Add typed index labels for actuators
    for i, j, x, y, typed_idx, global_idx, local_idx in actuator_positions:
        plt.annotate(f'{typed_idx}', (x, y), xytext=(0, 0), textcoords='offset points', 
                    fontsize=10, fontweight='bold', ha='center', va='center', color='white')
    
    # Add typed index labels for phantoms (every 4th for clarity)
    for i, j, x, y, typed_idx, global_idx, local_idx in phantom_positions[::3]:
        plt.annotate(f'{typed_idx}', (x, y), xytext=(0, 0), textcoords='offset points', 
                    fontsize=8, ha='center', va='center', color='white', fontweight='bold')
    
    plt.xlabel('X Position (mm)', fontsize=12)
    plt.ylabel('Y Position (mm)', fontsize=12)
    plt.title('8x8 Grid Layout: Actuators (A##) and Phantoms (P##)', fontsize=14)
    plt.legend(fontsize=12)
    plt.grid(True, alpha=0.3)
    plt.axis('equal')
    
    # Add coordinate labels on axes
    plt.xticks(np.arange(0, 240, 30))
    plt.yticks(np.arange(0, 240, 30))
    
    plt.tight_layout()
    plt.show()

def get_grid_arrays():
    """Return structured arrays for easy data manipulation"""
    
    grid_data, actuator_positions, phantom_positions, X, Y = create_grid_layout()
    
    # Create numpy arrays for actuators
    actuator_array = np.array([(pos[4], pos[5], pos[6], pos[0], pos[1], pos[2], pos[3]) 
                              for pos in actuator_positions],
                             dtype=[('typed_index', 'U4'), ('global_index', int), ('local_index', int),
                                   ('grid_i', int), ('grid_j', int), ('x_mm', float), ('y_mm', float)])
    
    # Create numpy arrays for phantoms
    phantom_array = np.array([(pos[4], pos[5], pos[6], pos[0], pos[1], pos[2], pos[3]) 
                             for pos in phantom_positions],
                            dtype=[('typed_index', 'U4'), ('global_index', int), ('local_index', int),
                                  ('grid_i', int), ('grid_j', int), ('x_mm', float), ('y_mm', float)])
    
    return actuator_array, phantom_array, grid_data

# Main execution
if __name__ == "__main__":
    # Generate the grid layout
    grid_data, actuator_positions, phantom_positions, X, Y = create_grid_layout()
    
    # Print summary
    print_grid_summary(grid_data, actuator_positions, phantom_positions)
    
    # Create lookup system
    lookup = GridLookup(grid_data, actuator_positions, phantom_positions)
    
    # Show lookup examples
    lookup.print_lookup_examples()
    
    # Get structured arrays
    actuator_array, phantom_array, full_grid = get_grid_arrays()
    
    print(f"\n=== ARRAYS CREATED ===")
    print(f"actuator_array.shape: {actuator_array.shape}")
    print(f"phantom_array.shape: {phantom_array.shape}")
    
    # Example of accessing data with new structure
    print(f"\nActuator typed indices: {actuator_array['typed_index']}")
    print(f"First 5 phantom typed indices: {phantom_array['typed_index'][:5]}")
    
    # Visualize the grid
    visualize_grid(X, Y, actuator_positions, phantom_positions)
    
    # Additional examples
    print("\n=== PRACTICAL USAGE EXAMPLES ===")
    print("# Get coordinates from actuator A07:")
    result = lookup.get_coords_from_typed_index('A07')
    if result:
        print(f"A07 is at physical position {result['physical_coords']} mm")
    
    print("\n# Get info from phantom P15:")
    result = lookup.get_coords_from_typed_index('P15')
    if result:
        print(f"P15 is at physical position {result['physical_coords']} mm")
        print(f"P15 global index: {result['global_index']}")
    
    print("\n# Find what's at coordinate (120, 90):")
    typed_idx = lookup.get_typed_index_from_coords(120, 90)
    print(f"At (120, 90) mm: {typed_idx}")
    
    print("\n# All actuator positions:")
    actuators = lookup.get_all_actuators()
    for i, act in enumerate(actuators):
        act_id = [k for k, v in lookup.typed_to_coords.items() if v == act and k.startswith('A')][0]
        print(f"{act_id}: {act['physical_coords']} mm")