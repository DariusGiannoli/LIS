import sys
from PyQt6.QtWidgets import QWidget, QDialog, QApplication, QPushButton, QHBoxLayout
from PyQt6.QtCore import pyqtSignal, QTimer

# Import the separated components
from drone_components import Interactive2DMap, Drone3DView, EVENT_PATTERNS
from flexible_actuator_selector import FlexibleActuatorSelector, CreateChainDialog

class Drone3DGrid(QWidget):
    """Simplified 3D drone grid - components only, no layout creation"""
    drone_event_selected = pyqtSignal(int, str)

    def __init__(self, haptic_manager, parent=None):
        super().__init__(parent)
        self.haptic_manager = haptic_manager

        # ─── Initialize Components (no layout creation) ───────────────────
        self.init_components()
        self.connect_signals()

    def init_components(self):
        """Initialize all components without creating layouts"""
        # ─── 3D View Setup ──────────────────────────────────────────────
        self.drone_3d_view = Drone3DView()
        
        # ─── 2D Map ─────────────────────────────────────────────────────
        self.map_2d = Interactive2DMap()
        
        # ─── Actuator Selector (new flexible system) ────────────────────
        self.actuator_selector = FlexibleActuatorSelector()
        
        # ─── Additional Buttons ─────────────────────────────────────────
        self.buttons_layout = QHBoxLayout()  # Layout to group the new buttons
        
        self.clear_button = QPushButton("Clear")
        self.clear_button.clicked.connect(self.actuator_selector.clear_canvas)
        self.buttons_layout.addWidget(self.clear_button)
        
        self.select_all_button = QPushButton("Select All")
        self.select_all_button.clicked.connect(self.actuator_selector.select_all)
        self.buttons_layout.addWidget(self.select_all_button)
        
        self.deselect_button = QPushButton("None")
        self.deselect_button.clicked.connect(self.actuator_selector.select_none)
        self.buttons_layout.addWidget(self.deselect_button)

    def connect_signals(self):
        """Connect all component signals"""
        # 2D Map signals
        self.map_2d.drone_clicked.connect(self._on_2d_drone_clicked)
        self.map_2d.drone_event_requested.connect(self._emit_event)
        
        # Actuator selector signals
        self.actuator_selector.selection_changed.connect(self.on_actuators_selected)
        
        # 3D view signals
        self.drone_3d_view.drone_event_selected.connect(self.drone_event_selected.emit)

    def create_actuator_branch(self):
        """Create actuator branch dialog using new system"""
        dialog = CreateChainDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            num_actuators, lra_count, vca_count, m_count, grid_pattern = dialog.get_values()
            self.actuator_selector.canvas.create_chain(
                num_actuators, lra_count, vca_count, m_count, grid_pattern)

    def on_actuators_selected(self, selected_ids):
        """Handle actuator selection event"""
        print(f"Selected actuators: {selected_ids}")
        # Add any additional handling here, e.g., activate haptic feedback

    def _on_2d_drone_clicked(self, drone_id):
        """Handle drone selection from 2D map"""
        self.drone_3d_view.select_drone(drone_id)

    def _emit_event(self, drone_id, event_name):
        """Handle drone events from 2D map"""
        if self.haptic_manager:
            self.haptic_manager.start_playback()
            
        # Trigger the event in the 3D view
        self.drone_3d_view.trigger_drone_event(drone_id, event_name)
        
        # Update the 2D view
        self._update_2d_view()
            
        # Handle haptic feedback
        if self.haptic_manager:
            pattern_fn = EVENT_PATTERNS.get(event_name)
            if pattern_fn:
                pattern = pattern_fn(drone_id)
                act_id = f"A.{drone_id+1}"
                for delay, amp, dur in pattern:
                    start = self.haptic_manager.prepare_command(act_id, amp, 200, 1)
                    stop = self.haptic_manager.prepare_command(act_id, 0, 200, 0)
                    QTimer.singleShot(int(delay*1000), lambda c=start: self.haptic_manager.process_commands([c]))
                    QTimer.singleShot(int((delay+dur)*1000), lambda c=stop: self.haptic_manager.process_commands([c]))
                    
        self.drone_event_selected.emit(drone_id, event_name)

    def _update_2d_view(self):
        """Update 2D view with current positions and colors"""
        # Get current positions from 3D view
        current_positions = self.drone_3d_view.get_current_positions()
        colors = self.drone_3d_view.get_sphere_colors()
        
        self.map_2d.update_positions(current_positions, colors)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = Drone3DGrid(haptic_manager=None)
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec())