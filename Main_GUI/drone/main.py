# main.py - Simplified Drone Control GUI
import sys
import os
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QSizePolicy
from PyQt6.QtCore import Qt
from PyQt6 import uic

# Import the refactored drone grid widget
from drone_3d_grid import Drone3DGrid

# Import the event library widget from the data folder
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'data'))
try:
    from universal_event_designer import EventLibraryWidget
    EVENT_LIBRARY_AVAILABLE = True
except ImportError:
    print("Warning: Event library not available. EventLibraryWidget not found.")
    EVENT_LIBRARY_AVAILABLE = False

class DroneControlWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Get parent directory path
        parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        
        # Load UI from .ui file (look in parent directory)
        ui_path = os.path.join(parent_dir, 'main_window.ui')
        if not os.path.exists(ui_path):
            # Fallback: look in current directory
            ui_path = 'main_window.ui'
        uic.loadUi(ui_path, self)
        
        # ─── Initialize Components ────────────────────────────────────────
        self.setup_drone_components()
        self.setup_event_library()
        self.setup_connections()
        self.setup_splitter()
        
    def setup_drone_components(self):
        """Setup the drone 3D grid components"""
        # Create the drone 3D grid widget (contains 3D view, 2D map, actuator canvas)
        self.grid_widget = Drone3DGrid(haptic_manager=None, parent=self)
        
        # ─── Setup 3D View ──────────────────────────────────────────────
        # Get the 3D view widget and add it to the container
        drone_3d_widget = self.grid_widget.drone_3d_view.get_widget()
        self.drone3dLayout.addWidget(drone_3d_widget)
        
        # ─── Setup 2D Map ────────────────────────────────────────────────
        # Add the 2D map to its container
        self.drone2dLayout.addWidget(self.grid_widget.map_2d)
        
        # ─── Setup Actuator Canvas ───────────────────────────────────────
        # Add the actuator canvas to its container
        self.actuatorCanvasLayout.addWidget(self.grid_widget.actuator_selector.canvas)
        self.actuatorCanvasLayout.setContentsMargins(0, 0, 0, 0)
        self.actuatorCanvasLayout.setSpacing(0)
        self.grid_widget.actuator_selector.canvas.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        # Donner plus d'espace vertical au canvas
        self.grid_widget.actuator_selector.canvas.setMinimumHeight(350)
        self.grid_widget.actuator_selector.canvas.setMaximumHeight(16777215)
        
        # ─── Setup Selection Bar ─────────────────────────────────────────
        # Add the selection bar view to its container
        self.selectionBarLayout.addWidget(self.grid_widget.actuator_selector.palette)
        
        # ─── Remove unwanted buttons ─────────────────────────────────────
        self.rightPanelLayout.removeWidget(self.openEventDesignerButton)
        self.openEventDesignerButton.setParent(None)
        self.rightPanelLayout.removeWidget(self.openHapticPatternButton)
        self.openHapticPatternButton.setParent(None)
        
        # ─── Remove createBranchButton temporarily ───────────────────────
        self.rightPanelLayout.removeWidget(self.createBranchButton)
        self.createBranchButton.setParent(None)
        
        # ─── Take the selectionBarLayout ─────────────────────────────────
        selection_item = self.rightPanelLayout.takeAt(self.rightPanelLayout.indexOf(self.selectionBarLayout))
        
        # ─── Create buttons widget ───────────────────────────────────────
        buttons_widget = QWidget()
        buttons_hbox = QHBoxLayout(buttons_widget)
        buttons_hbox.setContentsMargins(0, 0, 0, 0)
        buttons_hbox.setSpacing(8)  # Espacement légèrement augmenté entre boutons
        
        # Style moderne pour tous les boutons
        button_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 8px 16px;
                font-size: 11px;
                font-weight: 500;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #6c757d;
            }
            QPushButton:disabled {
                background-color: #f8f9fa;
                border-color: #dee2e6;
                color: #adb5bd;
            }
        """
        
        self.createBranchButton.setMaximumHeight(32)
        self.createBranchButton.setFixedWidth(110)
        self.createBranchButton.setStyleSheet(button_style)
        buttons_hbox.addWidget(self.createBranchButton)
        
        self.grid_widget.clear_button.setMaximumHeight(32)
        self.grid_widget.clear_button.setFixedWidth(70)
        self.grid_widget.clear_button.setStyleSheet(button_style)
        buttons_hbox.addWidget(self.grid_widget.clear_button)
        
        self.grid_widget.select_all_button.setMaximumHeight(32)
        self.grid_widget.select_all_button.setFixedWidth(85)
        self.grid_widget.select_all_button.setStyleSheet(button_style)
        buttons_hbox.addWidget(self.grid_widget.select_all_button)
        
        self.grid_widget.deselect_button.setMaximumHeight(32)
        self.grid_widget.deselect_button.setFixedWidth(70)
        self.grid_widget.deselect_button.setStyleSheet(button_style)
        buttons_hbox.addWidget(self.grid_widget.deselect_button)
        
        # ─── Create combined widget for palette and buttons ─────────────
        combined_widget = QWidget()
        combined_hbox = QHBoxLayout(combined_widget)
        combined_hbox.setContentsMargins(0, 0, 0, 0)  # Pas de marges
        combined_hbox.setSpacing(2)  # Espacement réduit entre palette et boutons
        combined_hbox.addLayout(selection_item.layout())  # Add the selectionBarLayout
        combined_hbox.addWidget(buttons_widget)
        combined_hbox.addStretch()
        
        # Réduire la hauteur maximale du widget combiné
        combined_widget.setMaximumHeight(90)  # Hauteur légèrement augmentée pour les nouveaux boutons
        
        # ─── Insert combined widget after actuatorCanvasLayout ──────────
        actuator_index = self.rightPanelLayout.indexOf(self.actuatorCanvasLayout)
        self.rightPanelLayout.insertWidget(actuator_index + 1, combined_widget)
        
        # Réduire drastiquement l'espacement dans le panneau droit
        self.rightPanelLayout.setSpacing(2)  # Espacement très réduit entre éléments
        self.rightPanelLayout.setContentsMargins(5, 0, 5, 2)  # Marges réduites
        
        # Réduire l'espacement dans l'actuatorCanvasLayout
        self.actuatorCanvasLayout.setSpacing(0)
        self.actuatorCanvasLayout.setContentsMargins(0, 0, 0, 0)
        
        # Donner plus de stretch au canvas pour qu'il occupe l'espace disponible
        self.rightPanelLayout.setStretchFactor(self.actuatorCanvasLayout, 3)  # Canvas prend 3 parts
        
        # ─── Connect Slider Events ───────────────────────────────────────
        self.connect_sliders()
        
        # ─── Connect Button Events ───────────────────────────────────────
        self.resetButton.clicked.connect(self.reset_all)
        self.createBranchButton.clicked.connect(self.grid_widget.create_actuator_branch)
        
        # Appliquer le style moderne au bouton reset aussi
        reset_button_style = """
            QPushButton {
                background-color: #f8f9fa;
                border: 1px solid #dee2e6;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 11px;
                font-weight: 500;
                color: #495057;
            }
            QPushButton:hover {
                background-color: #e9ecef;
                border-color: #adb5bd;
            }
            QPushButton:pressed {
                background-color: #dee2e6;
                border-color: #6c757d;
            }
        """
        self.resetButton.setStyleSheet(reset_button_style)
        
    def setup_event_library(self):
        """Setup the event library widget in the bottom right corner"""
        if EVENT_LIBRARY_AVAILABLE:
            try:
                self.event_library_widget = EventLibraryWidget(self)
                # Réduire les marges du layout de la bibliothèque d'événements
                self.eventLibraryLayout.setContentsMargins(0, 0, 0, 0)
                self.eventLibraryLayout.setSpacing(0)
                self.eventLibraryLayout.addWidget(self.event_library_widget)
                
                # Donner du stretch à la bibliothèque d'événements pour occuper l'espace restant
                self.rightPanelLayout.setStretchFactor(self.eventLibraryLayout, 2)  # Event library prend 2 parts
                
                print("Event library widget initialized successfully")
            except Exception as e:
                print(f"Error initializing event library widget: {e}")
                self.event_library_widget = None
        else:
            # Create a placeholder label if the event library is not available
            placeholder = QLabel("Event Library Not Available")
            placeholder.setStyleSheet("color: gray; text-align: center; padding: 10px; border: 1px solid #ccc;")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(100)  # Hauteur minimum pour occuper l'espace
            self.eventLibraryLayout.addWidget(placeholder)
            
            # Donner du stretch au placeholder aussi
            self.rightPanelLayout.setStretchFactor(self.eventLibraryLayout, 2)
            
            self.event_library_widget = None
        
    def connect_sliders(self):
        """Connect slider signals to update methods"""
        self.scaleSlider.valueChanged.connect(self.update_positions)
        self.xoffSlider.valueChanged.connect(self.update_positions)
        self.yoffSlider.valueChanged.connect(self.update_positions)
        self.zoffSlider.valueChanged.connect(self.update_positions)
        
        # Initialize the display
        self.update_positions()
        
    def setup_connections(self):
        """Set up signal connections between widgets"""
        # Connect grid widget signals
        self.grid_widget.drone_event_selected.connect(self.on_drone_event_selected)
        
        # Connect event library signals if available
        if hasattr(self, 'event_library_widget') and self.event_library_widget:
            self.event_library_widget.event_selected.connect(self.on_event_library_selection)
        
    def setup_splitter(self):
        """Setup splitter proportions"""
        # Set initial stretch/fractions (left 50%, right 50%)
        # Utiliser la largeur totale de la fenêtre pour calculer 50/50
        total_width = self.width()
        self.mainSplitter.setSizes([total_width // 2, total_width // 2])
        
        # S'assurer que les proportions restent 50/50 lors du redimensionnement
        self.mainSplitter.setStretchFactor(0, 1)  # Panneau gauche
        self.mainSplitter.setStretchFactor(1, 1)  # Panneau droit
        
    def update_positions(self):
        """Update drone positions based on slider values"""
        scale = self.scaleSlider.value() / 10.0
        self.scaleLabel.setText(f"Scale: {scale:.1f}")
        
        xoff = self.xoffSlider.value() / 10.0
        yoff = self.yoffSlider.value() / 10.0
        zoff = self.zoffSlider.value() / 10.0
        self.xoffLabel.setText(f"X offset: {xoff:.1f}")
        self.yoffLabel.setText(f"Y offset: {yoff:.1f}")
        self.zoffLabel.setText(f"Z offset: {zoff:.1f}")
        
        # Update 3D positions
        current_positions = self.grid_widget.drone_3d_view.update_drone_positions(scale, xoff, yoff, zoff)
        
        # Update 2D view
        colors = self.grid_widget.drone_3d_view.get_sphere_colors()
        self.grid_widget.map_2d.update_positions(current_positions, colors)

    def reset_all(self):
        """Reset all drone states and positions"""
        self.scaleSlider.setValue(10)
        self.xoffSlider.setValue(0)
        self.yoffSlider.setValue(0)
        self.zoffSlider.setValue(0)
        
        # Reset drone states
        self.grid_widget.drone_3d_view.reset_drones()
        
        # Reset 2D map selection
        self.grid_widget.map_2d.selected_drone = None
        self.grid_widget._update_2d_view()
    
    def on_drone_event_selected(self, drone_id, event_name):
        """Handle drone event selection"""
        print(f"Drone {drone_id} event: {event_name}")
        # Add any additional handling here
    
    def on_event_library_selection(self, event_path_or_token):
        """Handle event library selection"""
        print(f"Event selected from library: {event_path_or_token}")
        
        # Check if it's a built-in oscillator or a saved event
        if event_path_or_token.startswith("oscillator::"):
            oscillator_type = event_path_or_token.split("::", 1)[1]
            print(f"Built-in oscillator selected: {oscillator_type}")
            # Handle oscillator selection - you can apply this to selected drones
            self.apply_oscillator_to_selected_drones(oscillator_type)
        else:
            print(f"Saved event selected: {os.path.basename(event_path_or_token)}")
            # Handle saved event selection
            self.apply_saved_event_to_selected_drones(event_path_or_token)
    
    def apply_oscillator_to_selected_drones(self, oscillator_type):
        """Apply a built-in oscillator to selected drones"""
        # This is where you would integrate with your drone system
        # For now, just print the action
        print(f"Applying {oscillator_type} oscillator to selected drones")
        
        # Example: You might want to create a haptic event and send it to drones
        # This would depend on your drone haptic system implementation
        
    def apply_saved_event_to_selected_drones(self, event_path):
        """Apply a saved haptic event to selected drones"""
        # This is where you would load and apply the saved event
        print(f"Applying saved event from {event_path} to selected drones")
        
        # Example: Load the event and send it to the haptic system
        # This would depend on your drone haptic system implementation
    
    def refresh_event_library(self):
        """Refresh the event library widget"""
        if hasattr(self, 'event_library_widget') and self.event_library_widget:
            self.event_library_widget.refresh_event_tree()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = DroneControlWindow()
    w.resize(1400, 700)  # Fenêtre plus large pour mieux voir la répartition 50/50
    w.show()
    sys.exit(app.exec())