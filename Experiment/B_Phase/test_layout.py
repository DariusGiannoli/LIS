#!/usr/bin/env python3
"""
Test script to verify the custom actuator grid layout.
"""

import sys
from PyQt6.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QLabel
from widgets.actuator_grid import ActuatorGrid

class TestWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Actuator Grid Layout Test")
        self.setGeometry(100, 100, 600, 500)
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        
        # Add info label
        info_label = QLabel("""
        Custom Grid Layout Test:
        Row 0: 0, 1, 2, 3
        Row 1: 7, 6, 5, 4  
        Row 2: 8, 9, 10, 11
        Row 3: 15, 14, 13, 12
        
        Click buttons to see the layout in action!
        """)
        layout.addWidget(info_label)
        
        # Create the actuator grid
        self.grid = ActuatorGrid()
        layout.addWidget(self.grid)
        
        # Add selection info
        self.selection_label = QLabel("Selected: None")
        layout.addWidget(self.selection_label)
        
        # Connect selection changes
        self.grid.selectionChanged.connect(self.on_selection_changed)
        
        # Test the layout by printing button positions
        print("Testing custom layout:")
        print("Expected layout:")
        for i, row in enumerate(self.grid.GRID_POSITION):
            print(f"Row {i}: {row}")
            
    def on_selection_changed(self, mode, selection):
        selected_list = sorted(selection)
        self.selection_label.setText(f"Selected ({mode}): {selected_list}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = TestWindow()
    window.show()
    sys.exit(app.exec())