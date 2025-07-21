# drone_widget.py
from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QPainter, QBrush, QColor

class DroneCircle(QWidget):
    clicked = pyqtSignal(int)

    def __init__(self, drone_id: int, diameter: int = 50, parent=None):
        super().__init__(parent)
        self.drone_id = drone_id
        self.diameter = diameter
        self.current_color = QColor(100, 150, 200)
        self.setFixedSize(self.diameter, self.diameter)

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(self.current_color))
        p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(0, 0, self.diameter, self.diameter)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.drone_id)

    def update_color_for_event(self, event_name: str):
        colors = {
            "Crash":     QColor(200, 50, 50),
            "Isolation": QColor(200, 200, 50),
            "Selection": QColor(50, 200, 50),
            
        }
        self.current_color = colors.get(event_name, QColor(100, 150, 200))
        self.update()
