import random
from PyQt6.QtWidgets import (
    QGraphicsItem, QGraphicsView, QGraphicsScene, QDialog, QFormLayout, 
    QLineEdit, QRadioButton, QButtonGroup, QSpinBox, QDialogButtonBox, 
    QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QMenu
)
from PyQt6.QtCore import Qt, pyqtSignal, QObject, QRectF, QMimeData
from PyQt6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QDrag

# Constants
COLOR_LIST = [
    QColor(255, 0, 0), QColor(0, 255, 0), QColor(0, 0, 255), 
    QColor(255, 255, 0), QColor(255, 0, 255), QColor(0, 255, 255),
    QColor(225, 127, 147)
]

ACTUATOR_CONFIG = {
    "LRA": {
        "text_vertical_offset": 0, "text_horizontal_offset": 0,
        "font_size_factor": 0.8, "min_font_size": 8, "max_font_size": 16
    },
    "VCA": {
        "text_vertical_offset": 0, "text_horizontal_offset": 0,
        "font_size_factor": 0.8, "min_font_size": 8, "max_font_size": 16
    },
    "M": {
        "text_vertical_offset": 0, "text_horizontal_offset": 0,
        "font_size_factor": 0.8, "min_font_size": 8, "max_font_size": 16
    }
}

def to_subscript(text):
    subscript_map = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
    return text.translate(subscript_map)

def generate_contrasting_color(existing_colors):
    while True:
        color = QColor(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255))
        if all(abs(color.red() - ec.red()) + abs(color.green() - ec.green()) + abs(color.blue() - ec.blue()) > 150 for ec in existing_colors):
            return color

class ActuatorSignalHandler(QObject):
    clicked = pyqtSignal(str)
    properties_changed = pyqtSignal(str, str, str)

    def __init__(self, actuator_id, parent=None):
        super().__init__(parent)
        self.actuator_id = actuator_id

class Actuator(QGraphicsItem):
    def __init__(self, x, y, size, color, actuator_type, id, predecessor=None, successor=None):
        super().__init__()
        self.setPos(x, y)
        self.size = size
        self.color = color
        self.actuator_type = actuator_type
        self.id = id
        self.predecessor = predecessor
        self.successor = successor
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setAcceptHoverEvents(True)

        self.signal_handler = ActuatorSignalHandler(self.id)

        config = ACTUATOR_CONFIG.get(self.actuator_type, ACTUATOR_CONFIG["LRA"])
        self.text_vertical_offset = config["text_vertical_offset"]
        self.text_horizontal_offset = config["text_horizontal_offset"]
        self.font_size_factor = config["font_size_factor"]
        self.min_font_size = config["min_font_size"]
        self.max_font_size = config["max_font_size"]

        self.font_size = self.calculate_font_size()   

    def calculate_font_size(self):
        base_size = self.size / 2 * self.font_size_factor
        id_length = len(self.id)
        if id_length > 3:
            base_size *= 3 / id_length
        return max(self.min_font_size, min(base_size, self.max_font_size))

    def boundingRect(self):
        return QRectF(-self.size/2, -self.size/2, self.size, self.size)

    def paint(self, painter, option, widget):
        painter.setBrush(QBrush(self.color))
        painter.setPen(QPen(Qt.GlobalColor.black, 1))

        if self.actuator_type == "LRA":
            painter.drawEllipse(self.boundingRect())
        elif self.actuator_type == "VCA":
            painter.drawRect(self.boundingRect())
        else:  # "M"
            painter.drawRoundedRect(self.boundingRect(), 5, 5)

        if self.isSelected():
            highlight_pen = QPen(QColor(225, 20, 146), 3)
            painter.setPen(highlight_pen)
            
            if self.actuator_type == "LRA":
                painter.drawEllipse(self.boundingRect().adjusted(-2, -2, 2, 2))
            elif self.actuator_type == "VCA":
                painter.drawRect(self.boundingRect().adjusted(-2, -2, 2, 2))
            else:  # "M"
                painter.drawRoundedRect(self.boundingRect().adjusted(-2, -2, 2, 2), 5, 5)

        font = painter.font()
        font.setPointSizeF(self.calculate_font_size())
        painter.setFont(font)

        if '.' in self.id:
            main_id, sub_id = self.id.split('.')
            formatted_id = main_id + to_subscript(sub_id)
        else:
            formatted_id = self.id

        rect = self.boundingRect()
        text_rect = QRectF(rect.left() + self.text_horizontal_offset,
                        rect.top() + self.text_vertical_offset,
                        rect.width(),
                        rect.height())

        painter.drawText(text_rect, Qt.AlignmentFlag.AlignCenter, formatted_id)

    def hoverEnterEvent(self, event):
        self.setCursor(Qt.CursorShape.OpenHandCursor)

    def hoverLeaveEvent(self, event):
        self.setCursor(Qt.CursorShape.ArrowCursor)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            self.signal_handler.clicked.emit(self.id)
        super().mousePressEvent(event)
        
        # Update all related lines when actuator moves
        if hasattr(self, 'dragging') and self.dragging:
            canvas = self.scene().views()[0]
            canvas.redraw_all_lines()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
            # Redraw lines after movement is complete
            if hasattr(self.scene().views()[0], 'redraw_all_lines'):
                self.scene().views()[0].redraw_all_lines()
        super().mouseReleaseEvent(event)

class ActuatorPropertiesDialog(QDialog):
    def __init__(self, actuator, parent=None):
        super().__init__(parent)
        self.actuator = actuator
        self.setWindowTitle("Actuator Properties")
        self.layout = QVBoxLayout(self)

        form_layout = QFormLayout()
        self.id_input = QLineEdit(actuator.id)
        form_layout.addRow("ID:", self.id_input)

        type_layout = QHBoxLayout()
        self.type_group = QButtonGroup(self)
        self.lra_radio = QRadioButton("LRA")
        self.vca_radio = QRadioButton("VCA")
        self.m_radio = QRadioButton("M")
        self.type_group.addButton(self.lra_radio)
        self.type_group.addButton(self.vca_radio)
        self.type_group.addButton(self.m_radio)
        type_layout.addWidget(self.lra_radio)
        type_layout.addWidget(self.vca_radio)
        type_layout.addWidget(self.m_radio)
        form_layout.addRow("Type:", type_layout)

        self.layout.addLayout(form_layout)

        button = QPushButton("OK")
        button.clicked.connect(self.accept)
        self.layout.addWidget(button)

        self.set_initial_type()

    def set_initial_type(self):
        if self.actuator.actuator_type == "LRA":
            self.lra_radio.setChecked(True)
        elif self.actuator.actuator_type == "VCA":
            self.vca_radio.setChecked(True)
        else:
            self.m_radio.setChecked(True)

    def get_type(self):
        if self.lra_radio.isChecked():
            return "LRA"
        elif self.vca_radio.isChecked():
            return "VCA"
        else:
            return "M"

class SelectionBar(QGraphicsItem):
    def __init__(self, scene, parent=None):
        super().__init__()
        self.setPos(-60, 10)  # Position in the margin area
        self.setAcceptHoverEvents(True)
        self.setAcceptedMouseButtons(Qt.MouseButton.LeftButton)
        self.selection_icons = []
        self.scene = scene
        self.create_selection_icons()

    def create_selection_icons(self):
        actuator_types = ["LRA", "VCA", "M"]
        for i, act_type in enumerate(actuator_types):
            icon = Actuator(0, 0, 20, QColor(200, 200, 200), act_type, act_type)
            # Make drag icons non-interactive (can't be moved or selected)
            icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
            icon.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
            icon.setPos(-60, i * 30 + 10)  # Position in margin
            self.selection_icons.append(icon)
            self.scene.addItem(icon)

class ActuatorCanvas(QGraphicsView):
    actuator_added = pyqtSignal(str, str, str, int, int)
    actuator_clicked = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)

        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing)

        self.actuators = []
        self.branch_colors = {}
        self.color_index = 0

        # Set light background without borders
        self.setBackgroundBrush(QBrush(QColor(240, 235, 229)))
        self.setFrameStyle(0)  # Remove frame
        
        # Use full canvas area with margin for drag elements
        margin = 80
        canvas_width = 400
        canvas_height = 300
        self.setSceneRect(-margin, -margin, canvas_width + 2*margin, canvas_height + 2*margin)
        
        # Main working area (no visual border)
        self.canvas_rect = QRectF(0, 0, canvas_width, canvas_height)

        self.setMouseTracking(True)
        self.setAcceptDrops(True)

        self.actuator_size = 20

    def update_canvas_visuals(self):
        # Remove any existing visual boundaries
        pass

    def dragEnterEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event):
        if event.mimeData().hasText():
            actuator_type = event.mimeData().text()
            pos = self.mapToScene(event.position().toPoint())
            
            if self.is_drop_allowed(pos):
                self.add_actuator(pos.x(), pos.y(), actuator_type=actuator_type)
                event.acceptProposedAction()
            else:
                event.ignore()

    def add_actuator(self, x, y, new_id=None, actuator_type="LRA"):
        if new_id is None:
            new_id = self.generate_next_id()
        
        branch = new_id.split('.')[0]
        if branch not in self.branch_colors:
            if self.color_index < len(COLOR_LIST):
                self.branch_colors[branch] = COLOR_LIST[self.color_index]
                self.color_index += 1
            else:
                self.branch_colors[branch] = generate_contrasting_color(list(self.branch_colors.values()))

        color = self.branch_colors[branch]

        actuator = Actuator(x, y, self.actuator_size, color, actuator_type, new_id)
        self.scene.addItem(actuator)
        self.actuators.append(actuator)
        actuator.setZValue(0)

        # Connect click signal
        actuator.signal_handler.clicked.connect(self.actuator_clicked.emit)

        # Redraw lines after adding new actuator
        self.redraw_all_lines()

        self.actuator_added.emit(new_id, actuator_type, color.name(), x, y)

    def redraw_all_lines(self):
        """Redraw all connecting lines between actuators"""
        # Remove existing lines
        for item in list(self.scene.items()):
            if hasattr(item, 'item_type') and item.item_type == 'connection_line':
                self.scene.removeItem(item)
        
        # Draw lines based on actuator sequence
        sorted_actuators = sorted(self.actuators, key=lambda a: (a.id.split('.')[0], int(a.id.split('.')[1])))
        
        for i in range(len(sorted_actuators) - 1):
            current = sorted_actuators[i]
            next_actuator = sorted_actuators[i + 1]
            
            # Only connect if they're in the same branch
            if current.id.split('.')[0] == next_actuator.id.split('.')[0]:
                line = self.scene.addLine(
                    current.pos().x(), current.pos().y(),
                    next_actuator.pos().x(), next_actuator.pos().y(),
                    QPen(QColor(0, 0, 0), 2)
                )
                line.setZValue(-1)
                line.item_type = 'connection_line'

    def get_actuator_by_id(self, actuator_id):
        """Retrieve an actuator by its ID."""
        for actuator in self.actuators:
            if actuator.id == actuator_id:
                return actuator
        return None

    def is_drop_allowed(self, pos):
        return self.canvas_rect.contains(pos)

    def generate_next_id(self):
        if not self.actuators:
            return "A.1"
        
        max_branch = max(act.id.split('.')[0] for act in self.actuators if '.' in act.id)
        max_number = max(int(act.id.split('.')[1]) for act in self.actuators if '.' in act.id and act.id.startswith(max_branch))
        
        return f"{max_branch}.{max_number + 1}"

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())

        if event.button() == Qt.MouseButton.LeftButton:
            # Only allow interaction with actuators in main canvas area, not the drag icons
            if isinstance(item, Actuator) and self.canvas_rect.contains(self.mapToScene(event.pos())):
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                item.signal_handler.clicked.emit(item.id)
                super().mousePressEvent(event)
            else:
                self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
                super().mousePressEvent(event)

        elif event.button() == Qt.MouseButton.RightButton:
            # Only show context menu for actuators in main canvas area
            if isinstance(item, Actuator) and self.canvas_rect.contains(self.mapToScene(event.pos())):
                self.show_context_menu(item, event.pos())
            super().mousePressEvent(event)

    def show_context_menu(self, actuator, pos):
        menu = QMenu()
        edit_action = menu.addAction("Edit Properties")
        delete_action = menu.addAction("Delete")

        action = menu.exec(self.mapToGlobal(pos))
        if action == edit_action:
            self.edit_actuator_properties(actuator)
        elif action == delete_action:
            self.remove_actuator(actuator)

    def edit_actuator_properties(self, actuator):
        dialog = ActuatorPropertiesDialog(actuator, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            actuator.id = dialog.id_input.text()
            actuator.actuator_type = dialog.get_type()
            actuator.update()

    def remove_actuator(self, actuator):
        self.actuators.remove(actuator)
        self.scene.removeItem(actuator)

    def create_actuator_branch(self, num_actuators, lra_count, vca_count, m_count, grid_pattern):
        if not self.actuators:
            next_branch = 'A'
        else:
            max_branch = max(act.id.split('.')[0] for act in self.actuators if '.' in act.id)
            next_branch = chr(ord(max_branch) + 1)

        rows, cols = map(int, grid_pattern.split('x'))

        spacing_x = self.canvas_rect.width() / (cols + 1)
        spacing_y = self.canvas_rect.height() / (rows + 1)

        actuator_types = ['LRA'] * lra_count + ['VCA'] * vca_count + ['M'] * m_count
        random.shuffle(actuator_types)

        for i in range(num_actuators):
            row = i // cols
            col = i % cols
            x = spacing_x * (col + 1)
            y = spacing_y * (row + 1)

            new_id = f"{next_branch}.{i+1}"
            actuator_type = actuator_types[i] if i < len(actuator_types) else 'LRA'

            self.add_actuator(x, y, new_id, actuator_type)
        
        # Redraw all connection lines after creating the branch
        self.redraw_all_lines()

class SelectionBarView(QGraphicsView):
    def __init__(self, scene, parent=None):
        super().__init__(parent)
        self.setScene(scene)
        self.setRenderHints(QPainter.RenderHint.Antialiasing)
        self.setFixedSize(80, 120)  # Adjusted size for margin area
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setStyleSheet("background: transparent; border: none;")
        self.setMouseTracking(True)
        
        # Center view on the drag icons in the margin
        self.centerOn(-60, 40)

    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        # Only allow dragging from the selection icons (in margin area)
        if isinstance(item, Actuator) and not item.isSelected():
            scene_pos = self.mapToScene(event.pos())
            # Check if click is on a drag icon (outside main canvas)
            if scene_pos.x() < 0:  # In the margin area
                drag = QDrag(self)
                mime_data = QMimeData()
                mime_data.setText(item.actuator_type)
                drag.setMimeData(mime_data)
                drag.exec(Qt.DropAction.CopyAction)
        super().mousePressEvent(event)

class CreateBranchDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Actuator Branch")
        layout = QVBoxLayout(self)

        self.num_actuators_input = QSpinBox()
        self.num_actuators_input.setMinimum(1)
        self.num_actuators_input.valueChanged.connect(self.update_max_counts)
        layout.addWidget(QLabel("Number of Actuators:"))
        layout.addWidget(self.num_actuators_input)

        self.lra_input = QSpinBox()
        self.lra_input.valueChanged.connect(self.check_total)
        layout.addWidget(QLabel("LRA Count:"))
        layout.addWidget(self.lra_input)

        self.vca_input = QSpinBox()
        self.vca_input.valueChanged.connect(self.check_total)
        layout.addWidget(QLabel("VCA Count:"))
        layout.addWidget(self.vca_input)

        self.m_input = QSpinBox()
        self.m_input.valueChanged.connect(self.check_total)
        layout.addWidget(QLabel("M Count:"))
        layout.addWidget(self.m_input)

        self.grid_pattern_input = QLineEdit()
        self.grid_pattern_input.textChanged.connect(self.validate_inputs)
        layout.addWidget(QLabel("Grid Pattern (e.g., 2x2, 3x3):"))
        layout.addWidget(self.grid_pattern_input)

        self.button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        layout.addWidget(self.button_box)

        self.num_actuators_input.setValue(1)
        self.update_max_counts()
        self.validate_inputs()

    def update_max_counts(self):
        total = self.num_actuators_input.value()
        self.lra_input.setMaximum(total)
        self.vca_input.setMaximum(total)
        self.m_input.setMaximum(total)
        self.check_total()
        self.validate_inputs()

    def check_total(self):
        total = self.num_actuators_input.value()
        sum_counts = self.lra_input.value() + self.vca_input.value() + self.m_input.value()
        
        if sum_counts > total:
            diff = sum_counts - total
            if self.sender() == self.lra_input:
                self.lra_input.setValue(max(0, self.lra_input.value() - diff))
            elif self.sender() == self.vca_input:
                self.vca_input.setValue(max(0, self.vca_input.value() - diff))
            elif self.sender() == self.m_input:
                self.m_input.setValue(max(0, self.m_input.value() - diff))

        self.validate_inputs()

    def accept(self):
        if (self.lra_input.value() + self.vca_input.value() + self.m_input.value() == self.num_actuators_input.value() and
            self.validate_grid_pattern(self.grid_pattern_input.text())):
            super().accept()

    def validate_grid_pattern(self, pattern):
        if not pattern.strip():
            return True
        try:
            rows, cols = map(int, pattern.split('x'))
            return rows > 0 and cols > 0
        except ValueError:
            return False
        
    def validate_inputs(self):
        total = self.num_actuators_input.value()
        sum_counts = self.lra_input.value() + self.vca_input.value() + self.m_input.value()
        grid_pattern = self.grid_pattern_input.text().strip()
        
        counts_valid = sum_counts == total
        grid_valid = self.validate_grid_pattern(grid_pattern)
        
        is_valid = counts_valid and grid_valid
        
        self.button_box.button(QDialogButtonBox.StandardButton.Ok).setEnabled(is_valid)