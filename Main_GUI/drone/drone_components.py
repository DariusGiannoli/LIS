import math
import random
from PyQt6.QtWidgets import QWidget, QMenu
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont
import pyqtgraph.opengl as gl

# Event patterns for drone events
EVENT_PATTERNS = {
    "Crash": lambda drone_id: [(0, 1.0, 0.5), (0.7, 0.8, 0.3)],
    "Isolation": lambda drone_id: [(0, 0.6, 0.2), (0.3, 0.6, 0.2), (0.6, 0.6, 0.2)],
    "Custom…": lambda drone_id: [(0, 0.5, 1.0)], 
    "Selection": lambda drone_id: [(0.5, 0.5, 0.5), (0.8, 0.8, 0.8)], 
    "Obstacle": lambda drone_id: [(1.0, 0.647, 0.0),(0.8, 0.518, 0.0)],
}

class Interactive2DMap(QWidget):
    """Interactive 2D map showing drone positions with click/hover functionality"""
    drone_clicked = pyqtSignal(int)
    drone_event_requested = pyqtSignal(int, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(400, 400)
        
        # Drone data
        self.drone_positions = []
        self.drone_colors = []
        self.drone_radius = 15
        self.selected_drone = None
        self.hovered_drone = None
        
        # View parameters
        self.view_center = [0, 0]
        self.scale = 50
        self.margin = 30
        self.zoom_factor = 1.0
        
        self.setMouseTracking(True)
        
        self.font = QFont()
        self.font.setPointSize(10)
        self.font.setBold(True)
        
    def update_positions(self, positions_3d, colors=None, maintain_scale=True):
        """Update 2D view with new 3D positions"""
        if not positions_3d:
            return
            
        self.drone_positions = [(pos[0], pos[2]) for pos in positions_3d]
        
        if colors is None:
            colors = [QColor(100, 150, 200) for _ in positions_3d]
        else:
            colors = [QColor(*color[:3]) if len(color) >= 3 else QColor(100, 150, 200) 
                     for color in colors]
        
        self.drone_colors = colors
        
        if not maintain_scale or not hasattr(self, '_scale_initialized'):
            if self.drone_positions:
                x_coords = [pos[0] for pos in self.drone_positions]
                z_coords = [pos[1] for pos in self.drone_positions]
                
                x_min, x_max = min(x_coords), max(x_coords)
                z_min, z_max = min(z_coords), max(z_coords)
                
                self.view_center = [(x_min + x_max) / 2, (z_min + z_max) / 2]
                self.scale = 50
                self._scale_initialized = True
        
        self.update()
    
    def world_to_screen(self, world_x, world_z):
        """Convert world coordinates to screen coordinates"""
        screen_x = self.width() / 2 + (world_x - self.view_center[0]) * self.scale * self.zoom_factor
        screen_y = self.height() / 2 - (world_z - self.view_center[1]) * self.scale * self.zoom_factor
        return int(screen_x), int(screen_y)
    
    def get_drone_at_position(self, screen_x, screen_y):
        """Return drone index at screen position, or None"""
        for i, (world_x, world_z) in enumerate(self.drone_positions):
            drone_screen_x, drone_screen_y = self.world_to_screen(world_x, world_z)
            distance = math.sqrt((screen_x - drone_screen_x)**2 + (screen_y - drone_screen_y)**2)
            if distance <= self.drone_radius:
                return i
        return None
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        painter.fillRect(self.rect(), QColor(240, 240, 240))
        self.draw_grid(painter)
        self.draw_axes(painter)
        
        for i, (world_x, world_z) in enumerate(self.drone_positions):
            screen_x, screen_y = self.world_to_screen(world_x, world_z)
            
            color = self.drone_colors[i] if i < len(self.drone_colors) else QColor(100, 150, 200)
            
            if i == self.selected_drone:
                painter.setPen(QPen(QColor(255, 255, 0), 3))
            elif i == self.hovered_drone:
                painter.setPen(QPen(QColor(255, 255, 255), 2))
            else:
                painter.setPen(QPen(QColor(0, 0, 0), 1))
            
            painter.setBrush(QBrush(color))
            painter.drawEllipse(screen_x - self.drone_radius, screen_y - self.drone_radius,
                              2 * self.drone_radius, 2 * self.drone_radius)
            
            painter.setPen(QPen(QColor(0, 0, 0)))
            painter.setFont(self.font)
            painter.drawText(screen_x - 10, screen_y + 5, str(i))
    
    def draw_grid(self, painter):
        """Draw grid lines"""
        painter.setPen(QPen(QColor(200, 200, 200), 1))
        
        world_width = self.width() / self.scale
        world_height = self.height() / self.scale
        grid_spacing = max(0.5, round(max(world_width, world_height) / 10))
        
        start_x = math.floor(self.view_center[0] - world_width/2 / grid_spacing) * grid_spacing
        for i in range(int(world_width / grid_spacing) + 3):
            world_x = start_x + i * grid_spacing
            screen_x, _ = self.world_to_screen(world_x, 0)
            if 0 <= screen_x <= self.width():
                painter.drawLine(screen_x, 0, screen_x, self.height())
        
        start_z = math.floor(self.view_center[1] - world_height/2 / grid_spacing) * grid_spacing
        for i in range(int(world_height / grid_spacing) + 3):
            world_z = start_z + i * grid_spacing
            _, screen_y = self.world_to_screen(0, world_z)
            if 0 <= screen_y <= self.height():
                painter.drawLine(0, screen_y, self.width(), screen_y)
    
    def draw_axes(self, painter):
        """Draw coordinate axes and labels"""
        painter.setPen(QPen(QColor(100, 100, 100), 2))
        
        center_x, center_y = self.world_to_screen(0, 0)
        if 0 <= center_y <= self.height():
            painter.drawLine(0, center_y, self.width(), center_y)
        
        if 0 <= center_x <= self.width():
            painter.drawLine(center_x, 0, center_x, self.height())
        
        painter.setPen(QPen(QColor(0, 0, 0)))
        painter.setFont(self.font)
        painter.drawText(10, 20, "2D Back View (X-Z)")
        painter.drawText(self.width() - 50, center_y - 10, "X")
        painter.drawText(center_x + 10, 20, "Z")
    
    def mousePressEvent(self, event):
        drone_idx = self.get_drone_at_position(event.pos().x(), event.pos().y())
        
        if drone_idx is not None:
            self.selected_drone = drone_idx
            
            if event.button() == Qt.MouseButton.LeftButton:
                self.drone_clicked.emit(drone_idx)
            elif event.button() == Qt.MouseButton.RightButton:
                self.show_context_menu(drone_idx, event.globalPosition().toPoint())
            
            self.update()
    
    def mouseMoveEvent(self, event):
        drone_idx = self.get_drone_at_position(event.pos().x(), event.pos().y())
        
        if drone_idx != self.hovered_drone:
            self.hovered_drone = drone_idx
            self.update()
    
    def wheelEvent(self, event):
        """Handle mouse wheel for zooming"""
        zoom_in = event.angleDelta().y() > 0
        zoom_factor = 1.2 if zoom_in else 1/1.2
        
        self.zoom_factor *= zoom_factor
        self.zoom_factor = max(0.1, min(10.0, self.zoom_factor))
        
        self.update()
    
    def show_context_menu(self, drone_id, global_pos):
        """Show context menu for drone events"""
        menu = QMenu(self)
        
        for event_name in ["Crash", "Isolation", "Selection", "Obstacle"]:
            action = menu.addAction(event_name)
            action.triggered.connect(lambda checked, e=event_name: 
                                   self.drone_event_requested.emit(drone_id, e))
        
        menu.exec(global_pos)

class Drone3DView(QWidget):
    """3D visualization of drone positions"""
    drone_event_selected = pyqtSignal(int, str)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 3D view setup
        self.view = gl.GLViewWidget()
        self.view.opts['distance'] = 20
        self.view.setMinimumHeight(300)
        
        # Add grid and axes
        grid = gl.GLGridItem()
        grid.scale(1, 1, 1)
        axes = gl.GLAxisItem()
        axes.setSize(x=5, y=5, z=5)
        self.view.addItem(grid)
        self.view.addItem(axes)
        
        # Generate 12 positions on sphere surface
        N = 12
        sphere_radius = 2.0
        golden_angle = math.pi * (3.0 - math.sqrt(5.0))
        self.base_positions = []
        for i in range(N):
            z = 1 - 2 * i / float(N - 1)
            radius_xy = math.sqrt(1 - z * z)
            theta = golden_angle * i
            x = math.cos(theta) * radius_xy
            y = math.sin(theta) * radius_xy
            self.base_positions.append((x * sphere_radius,
                                        y * sphere_radius,
                                        z * sphere_radius))
        
        # Create sphere mesh and drone items
        mesh_radius = 0.2
        md = gl.MeshData.sphere(rows=10, cols=20, radius=mesh_radius)
        self.spheres = []
        self.sphere_colors = [(100, 150, 200, 255)] * N
        
        for pos in self.base_positions:
            sph = gl.GLMeshItem(
                meshdata=md, smooth=True, shader='shaded',
                color=(0.4, 0.6, 0.9, 1.0)
            )
            sph.translate(*pos)
            self.view.addItem(sph)
            self.spheres.append(sph)
            
        self.selected_drone = None
    
    def get_widget(self):
        """Return the 3D view widget"""
        return self.view
    
    def trigger_drone_event(self, drone_id, event_name):
        """Trigger a drone event with visual feedback"""
        color_map = {
            "Crash": (255, 0, 0, 255),
            "Isolation": (255, 255, 0, 255),
            "Selection": (0, 255, 0, 255),
            "Obstacle": (255, 165, 0, 255)
        }
        
        if 0 <= drone_id < len(self.spheres):
            color_3d = tuple(c/255.0 for c in color_map.get(event_name, (100, 150, 200, 255)))
            self.spheres[drone_id].setColor(color_3d)
            
            self.sphere_colors[drone_id] = color_map.get(event_name, (100, 150, 200, 255))
            
        self.drone_event_selected.emit(drone_id, event_name)
    
    def update_drone_positions(self, scale=1.0, x_offset=0, y_offset=0, z_offset=0):
        """Update drone positions with transformations - all drones move together"""
        current_positions = []
        
        for idx, sph in enumerate(self.spheres):
            x0, y0, z0 = self.base_positions[idx]
            # Apply scale and offset to all drones (swarm moves together)
            x, y, z = x0*scale + x_offset, y0*scale + y_offset, z0*scale + z_offset
            sph.resetTransform()
            sph.translate(x, y, z)
            current_positions.append((x, y, z))
            
        return current_positions
    
    def reset_drones(self):
        """Reset all drones to default state"""
        for idx, sph in enumerate(self.spheres):
            sph.setColor((0.4, 0.6, 0.9, 1))
            self.sphere_colors[idx] = (100, 150, 200, 255)
        
        self.selected_drone = None
    
    def select_drone(self, drone_id):
        """Select a specific drone"""
        self.selected_drone = drone_id
    
    def get_current_positions(self):
        """Get current drone positions"""
        positions = []
        for idx in range(len(self.spheres)):
            x0, y0, z0 = self.base_positions[idx]
            positions.append((x0, y0, z0))
        return positions
    
    def get_sphere_colors(self):
        """Get current sphere colors"""
        return self.sphere_colors.copy()