#!/usr/bin/env python3
"""
flexible_actuator_selector.py

Widget de sélection d'actuateurs avec création dynamique par drag & drop 
et dialogue de création de chaînes, inspiré d'actuators_layout.py
Version avec Canvas élargi pour plus d'espace de travail
"""
import sys
import math
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGroupBox,
    QSpinBox, QFormLayout, QDialog, QMessageBox, QCheckBox, QMenu,
    QLineEdit
)
from PyQt6.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QAction,
    QDrag, QPixmap, QMouseEvent
)
from PyQt6.QtCore import Qt, QRectF, QPointF, QLineF, pyqtSignal, QMimeData

class SelectableActuator(QGraphicsItem):
    """Actuateur sélectionnable et supprimable"""
    
    def __init__(self, x, y, size, actuator_type, actuator_id):
        super().__init__()
        self.setPos(x, y)
        self.size = size
        self.actuator_type = actuator_type
        self.actuator_id = actuator_id
        self.selected_state = False
        self.connections = []  # Pour les connexions visuelles
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.setAcceptHoverEvents(True)
        
    def boundingRect(self):
        return QRectF(0, 0, self.size, self.size)
    
    def paint(self, painter, option, widget=None):
        # Couleur selon l'état de sélection
        if self.selected_state:
            painter.setBrush(QBrush(QColor(100, 200, 100)))  # Vert pour sélectionné
            painter.setPen(QPen(QColor(0, 150, 0), 3))
        else:
            painter.setBrush(QBrush(QColor(200, 200, 200)))  # Gris pour non sélectionné
            painter.setPen(QPen(Qt.GlobalColor.black, 2))
        
        # Dessiner selon le type
        if self.actuator_type == "LRA":
            painter.drawEllipse(0, 0, self.size, self.size)
        elif self.actuator_type == "VCA":
            painter.drawRect(0, 0, self.size, int(self.size * 0.7))
        else:  # "M" ou autre
            painter.drawRoundedRect(0, 0, self.size, self.size, 8, 8)
        
        # Texte de l'ID
        painter.setPen(Qt.GlobalColor.black)
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 0, self.size, self.size),
            Qt.AlignmentFlag.AlignCenter,
            str(self.actuator_id)
        )
    
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.toggle_selection()
        elif event.button() == Qt.MouseButton.RightButton:
            self.show_context_menu(event)
        super().mousePressEvent(event)
    
    def show_context_menu(self, event):
        """Afficher le menu contextuel pour supprimer"""
        menu = QMenu()
        delete_action = QAction("Delete", menu)
        menu.addAction(delete_action)
        
        choice = menu.exec(event.screenPos().toPoint())
        if choice == delete_action:
            self.remove_self()
    
    def remove_self(self):
        """Supprimer cet actuateur de la scène"""
        # Supprimer les connexions
        for line, other in list(self.connections):
            self.scene().removeItem(line)
            other.connections = [c for c in other.connections if c[0] != line]
        
        # Notifier la vue du changement
        if self.scene() and hasattr(self.scene().views()[0], 'on_actuator_removed'):
            self.scene().views()[0].on_actuator_removed(self)
        
        # Supprimer de la scène
        self.scene().removeItem(self)
    
    def toggle_selection(self):
        self.selected_state = not self.selected_state
        self.update()
        # Notifier la vue parent du changement
        if self.scene() and hasattr(self.scene().views()[0], 'on_actuator_selection_changed'):
            self.scene().views()[0].on_actuator_selection_changed()
    
    def set_selected_state(self, selected):
        self.selected_state = selected
        self.update()
    
    def connection_point(self, other):
        """Calculer le point de connexion vers un autre actuateur"""
        center1 = self.pos() + QPointF(self.size/2, self.size/2)
        center2 = other.pos() + QPointF(other.size/2, other.size/2)
        dx = center2.x() - center1.x()
        dy = center2.y() - center1.y()
        length = math.hypot(dx, dy)
        if length == 0:
            return center1
        ux, uy = dx/length, dy/length
        
        if self.actuator_type == "LRA":
            radius = self.size/2
            return center1 + QPointF(ux * radius, uy * radius)
        else:
            # Pour les autres formes, calculer l'intersection avec les bords
            halfsize = self.size/2
            tx = abs(halfsize/ux) if ux != 0 else float('inf')
            ty = abs(halfsize/uy) if uy != 0 else float('inf')
            t = min(tx, ty)
            return center1 + QPointF(ux * t, uy * t)
    
    def itemChange(self, change, value):
        """Mettre à jour les connexions lors du déplacement"""
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            for line, other in self.connections:
                start = self.connection_point(other)
                end = other.connection_point(self)
                line.setLine(QLineF(start, end))
        return super().itemChange(change, value)
    
    def hoverEnterEvent(self, event):
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        super().hoverEnterEvent(event)
    
    def hoverLeaveEvent(self, event):
        self.unsetCursor()
        super().hoverLeaveEvent(event)

class PaletteItem(QGraphicsItem):
    """Item de palette pour le drag & drop"""
    
    def __init__(self, x, y, size, actuator_type):
        super().__init__()
        self.setPos(x, y)
        self.size = size
        self.actuator_type = actuator_type
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, False)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, False)
        
    def boundingRect(self):
        return QRectF(0, 0, self.size, self.size)
    
    def paint(self, painter, option, widget=None):
        painter.setBrush(QBrush(QColor(150, 150, 255)))  # Bleu pour la palette
        painter.setPen(QPen(Qt.GlobalColor.black, 2))
        
        if self.actuator_type == "LRA":
            painter.drawEllipse(0, 0, self.size, self.size)
        elif self.actuator_type == "VCA":
            painter.drawRect(0, 0, self.size, int(self.size * 0.7))
        else:
            painter.drawRoundedRect(0, 0, self.size, self.size, 6, 6)
        
        painter.setPen(Qt.GlobalColor.black)
        font = QFont()
        font.setPointSize(8)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(
            QRectF(0, 0, self.size, self.size),
            Qt.AlignmentFlag.AlignCenter,
            self.actuator_type
        )

class PaletteView(QGraphicsView):
    """Vue de la palette pour le drag & drop"""
    
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setFixedWidth(70)  # Maintenir la largeur compacte
        self.setMaximumHeight(150)  # Maintenir la hauteur compacte
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        
        # Créer les items de la palette
        types = ["LRA", "VCA", "M"]
        for i, actuator_type in enumerate(types):
            item = PaletteItem(5, i * 45 + 5, 35, actuator_type)
            self.scene.addItem(item)
        
        self.scene.setSceneRect(0, 0, 50, len(types) * 45)
    
    def mousePressEvent(self, event):
        item = self.itemAt(event.pos())
        if isinstance(item, PaletteItem):
            drag = QDrag(self)
            mime = QMimeData()
            mime.setText(item.actuator_type)
            drag.setMimeData(mime)
            
            # Créer un pixmap pour le drag
            pixmap = QPixmap(item.size, item.size)
            pixmap.fill(Qt.GlobalColor.transparent)
            painter = QPainter(pixmap)
            item.paint(painter, None)
            painter.end()
            
            drag.setPixmap(pixmap)
            drag.exec(Qt.DropAction.CopyAction)
        super().mousePressEvent(event)

class FlexibleActuatorView(QGraphicsView):
    """Vue principale pour les actuateurs avec drag & drop - Canvas élargi"""
    
    selection_changed = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)
        self.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.setAcceptDrops(True)
        
        # Agrandir significativement le canvas pour utiliser tout l'espace disponible
        self.setMinimumHeight(300)  # Augmenté pour utiliser l'espace en haut
        self.setMaximumHeight(450)  # Augmenté pour profiter de l'espace libéré
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        self.actuators = []
        self.last_actuator = None
        self.next_id = 0
        
        # Scène de départ plus grande pour utiliser tout l'espace disponible
        self.scene.setSceneRect(0, 0, 700, 400)  # Encore plus grand pour utiliser l'espace récupéré
    
    def dragEnterEvent(self, event):
        event.acceptProposedAction()
    
    def dragMoveEvent(self, event):
        event.acceptProposedAction()
    
    def dropEvent(self, event):
        """Gérer le drop d'un nouvel actuateur"""
        actuator_type = event.mimeData().text()
        pos = self.mapToScene(event.position().toPoint())
        
        # Créer le nouvel actuateur
        new_actuator = SelectableActuator(pos.x(), pos.y(), 40, actuator_type, self.next_id)
        self.scene.addItem(new_actuator)
        self.actuators.append(new_actuator)
        self.next_id += 1
        
        # Connecter au dernier actuateur s'il existe
        if self.last_actuator:
            start = self.last_actuator.connection_point(new_actuator)
            end = new_actuator.connection_point(self.last_actuator)
            line = self.scene.addLine(QLineF(start, end), QPen(Qt.GlobalColor.blue, 2))
            
            self.last_actuator.connections.append((line, new_actuator))
            new_actuator.connections.append((line, self.last_actuator))
        
        self.last_actuator = new_actuator
        event.acceptProposedAction()
        
        # Notifier du changement
        self.on_actuator_selection_changed()
    
    def create_chain(self, num_actuators, lra_count, vca_count, m_count, grid_pattern):
        """Créer une chaîne d'actuateurs avec plus d'espace"""
        self.clear_canvas()
        
        # Vérification
        if lra_count + vca_count + m_count != num_actuators:
            return False
        
        # Créer la liste des types
        types_list = (["LRA"] * lra_count + ["VCA"] * vca_count + ["M"] * m_count)
        
        # Calculer le layout - profiter de l'espace agrandi
        rows = cols = None
        if 'x' in grid_pattern.lower():
            try:
                r, c = grid_pattern.lower().split('x')
                rows, cols = int(r), int(c)
            except:
                rows = cols = None
        
        spacing = 70  # Légèrement augmenté pour profiter de l'espace
        size = 40     
        start_x = 15  
        start_y = 15  
        
        for idx, actuator_type in enumerate(types_list):
            if rows and cols:
                row = idx // cols
                col = idx % cols
                x = start_x + col * spacing
                y = start_y + row * spacing
            else:
                x = start_x + idx * spacing
                y = start_y
            
            actuator = SelectableActuator(x, y, size, actuator_type, idx)
            self.scene.addItem(actuator)
            self.actuators.append(actuator)
            
            # Connecter au précédent
            if self.last_actuator:
                start = self.last_actuator.connection_point(actuator)
                end = actuator.connection_point(self.last_actuator)
                line = self.scene.addLine(QLineF(start, end), QPen(Qt.GlobalColor.blue, 2))
                
                self.last_actuator.connections.append((line, actuator))
                actuator.connections.append((line, self.last_actuator))
            
            self.last_actuator = actuator
        
        self.next_id = num_actuators
        
        # Ajuster la scène - profiter de l'espace agrandi
        if rows and cols:
            scene_width = start_x + cols * spacing + 50
            scene_height = start_y + rows * spacing + 50
        else:
            scene_width = start_x + num_actuators * spacing + 50
            scene_height = start_y + 100
        
        # S'assurer que la scène utilise tout l'espace disponible
        scene_width = max(scene_width, 700)  # Augmenté pour utiliser l'espace
        scene_height = max(scene_height, 400)  # Augmenté pour utiliser l'espace
        
        self.scene.setSceneRect(0, 0, scene_width, scene_height)
        return True
    
    def clear_canvas(self):
        """Vider le canvas"""
        self.scene.clear()
        self.actuators = []
        self.last_actuator = None
        self.next_id = 0
        self.scene.setSceneRect(0, 0, 700, 400)  # Espace encore plus grand
    
    def on_actuator_selection_changed(self):
        """Appelé quand la sélection change"""
        selected_ids = [act.actuator_id for act in self.actuators if act.selected_state]
        self.selection_changed.emit(selected_ids)
    
    def on_actuator_removed(self, removed_actuator):
        """Appelé quand un actuateur est supprimé"""
        if removed_actuator in self.actuators:
            self.actuators.remove(removed_actuator)
        if self.last_actuator == removed_actuator:
            self.last_actuator = self.actuators[-1] if self.actuators else None
        self.on_actuator_selection_changed()
    
    def get_selected_actuators(self):
        return [act.actuator_id for act in self.actuators if act.selected_state]
    
    def select_all(self):
        for actuator in self.actuators:
            actuator.set_selected_state(True)
        self.on_actuator_selection_changed()
    
    def select_none(self):
        for actuator in self.actuators:
            actuator.set_selected_state(False)
        self.on_actuator_selection_changed()
    
    def select_range(self, start_id, end_id):
        for actuator in self.actuators:
            if start_id <= actuator.actuator_id <= end_id:
                actuator.set_selected_state(True)
            else:
                actuator.set_selected_state(False)
        self.on_actuator_selection_changed()

class CreateChainDialog(QDialog):
    """Dialog pour créer une chaîne d'actuateurs"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Create Actuator Chain")
        self.setModal(True)
        self.resize(350, 250)
        
        layout = QVBoxLayout(self)
        
        # Formulaire
        form = QFormLayout()
        
        self.num_spin = QSpinBox()
        self.num_spin.setRange(1, 100)
        self.num_spin.setValue(9)
        form.addRow("Number of Actuators:", self.num_spin)
        
        self.lra_spin = QSpinBox()
        self.lra_spin.setRange(0, 100)
        self.lra_spin.setValue(9)
        form.addRow("LRA Count:", self.lra_spin)
        
        self.vca_spin = QSpinBox()
        self.vca_spin.setRange(0, 100)
        self.vca_spin.setValue(0)
        form.addRow("VCA Count:", self.vca_spin)
        
        self.m_spin = QSpinBox()
        self.m_spin.setRange(0, 100)
        self.m_spin.setValue(0)
        form.addRow("M Count:", self.m_spin)
        
        self.grid_edit = QLineEdit("3x3")
        self.grid_edit.setPlaceholderText("e.g., 3x3, 2x5, or leave empty for linear")
        form.addRow("Grid Pattern:", self.grid_edit)
        
        layout.addLayout(form)
        
        # Validation label
        self.validation_label = QLabel("")
        self.validation_label.setStyleSheet("color: red;")
        layout.addWidget(self.validation_label)
        
        # Boutons
        button_layout = QHBoxLayout()
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.clicked.connect(self.reject)
        self.ok_button = QPushButton("Create")
        self.ok_button.clicked.connect(self.accept)
        
        button_layout.addWidget(self.cancel_button)
        button_layout.addWidget(self.ok_button)
        layout.addLayout(button_layout)
        
        # Connecter la validation
        self.num_spin.valueChanged.connect(self.validate)
        self.lra_spin.valueChanged.connect(self.validate)
        self.vca_spin.valueChanged.connect(self.validate)
        self.m_spin.valueChanged.connect(self.validate)
        
        self.validate()
    
    def validate(self):
        """Valider que la somme des types égale le total"""
        total = self.num_spin.value()
        sum_types = self.lra_spin.value() + self.vca_spin.value() + self.m_spin.value()
        
        if sum_types == total:
            self.validation_label.setText("✓ Valid configuration")
            self.validation_label.setStyleSheet("color: green;")
            self.ok_button.setEnabled(True)
        else:
            self.validation_label.setText(f"✗ Sum of types ({sum_types}) must equal total ({total})")
            self.validation_label.setStyleSheet("color: red;")
            self.ok_button.setEnabled(False)
    
    def get_values(self):
        return (
            self.num_spin.value(),
            self.lra_spin.value(),
            self.vca_spin.value(),
            self.m_spin.value(),
            self.grid_edit.text()
        )

class FlexibleActuatorSelector(QWidget):
    """Widget principal avec palette et contrôles - Canvas élargi"""
    
    selection_changed = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        
        # Titre et instructions - maintenir compact
        title_label = QLabel("Actuator Designer")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        layout.addWidget(title_label)
        
        # Boutons de contrôle - maintenir compacts
        controls_layout = QHBoxLayout()
        controls_layout.setSpacing(5)
        
        self.clear_btn = QPushButton("Clear")
        self.clear_btn.setMaximumWidth(60)
        self.clear_btn.clicked.connect(self.clear_canvas)
        controls_layout.addWidget(self.clear_btn)
        
        self.create_chain_btn = QPushButton("Create Chain")
        self.create_chain_btn.setMaximumWidth(90)
        self.create_chain_btn.clicked.connect(self.create_chain)
        controls_layout.addWidget(self.create_chain_btn)
        
        self.select_all_btn = QPushButton("All")
        self.select_all_btn.setMaximumWidth(40)
        self.select_all_btn.clicked.connect(self.select_all)
        controls_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("None")
        self.select_none_btn.setMaximumWidth(50)
        self.select_none_btn.clicked.connect(self.select_none)
        controls_layout.addWidget(self.select_none_btn)
        
        controls_layout.addStretch()
        layout.addLayout(controls_layout)
        
        # Zone principale avec palette et canvas élargi
        main_layout = QHBoxLayout()
        main_layout.setSpacing(5)
        
        # Palette - maintenir compacte
        palette_group = QGroupBox("Palette")
        palette_group.setMaximumWidth(80)
        palette_layout = QVBoxLayout(palette_group)
        palette_layout.setContentsMargins(5, 5, 5, 5)
        
        self.palette = PaletteView()
        palette_layout.addWidget(self.palette)
        
        main_layout.addWidget(palette_group)
        
        # Canvas - agrandi pour plus d'espace
        canvas_group = QGroupBox("Canvas")
        canvas_layout = QVBoxLayout(canvas_group)
        canvas_layout.setContentsMargins(5, 5, 5, 5)
        
        self.canvas = FlexibleActuatorView()
        # Le canvas utilise maintenant tout l'espace disponible
        self.canvas.setMaximumHeight(450)  # Augmenté significativement
        self.canvas.setMinimumHeight(300)  # Augmenté pour garantir l'espace
        self.canvas.selection_changed.connect(self.on_selection_changed)
        canvas_layout.addWidget(self.canvas)
        
        main_layout.addWidget(canvas_group)
        layout.addLayout(main_layout)
        
        # Status - maintenir compact
        self.status_label = QLabel("Drag from palette or create chain")
        self.status_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        self.status_label.setMaximumHeight(25)
        layout.addWidget(self.status_label)
    
    def clear_canvas(self):
        self.canvas.clear_canvas()
    
    def create_chain(self):
        dialog = CreateChainDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            num, lra, vca, m, grid = dialog.get_values()
            if self.canvas.create_chain(num, lra, vca, m, grid):
                self.status_label.setText(f"Created chain with {num} actuators")
            else:
                QMessageBox.warning(self, "Error", "Failed to create chain. Check parameters.")
    
    def select_all(self):
        self.canvas.select_all()
    
    def select_none(self):
        self.canvas.select_none()
    
    def on_selection_changed(self, selected_ids):
        if selected_ids:
            ids_str = ", ".join(map(str, sorted(selected_ids)))
            self.status_label.setText(f"Selected: {ids_str}")
        else:
            total = len(self.canvas.actuators)
            if total > 0:
                self.status_label.setText(f"{total} actuators - none selected")
            else:
                self.status_label.setText("No actuators - Drag from palette or create a chain")
        
        self.selection_changed.emit(selected_ids)
    
    def get_selected_actuators(self):
        return self.canvas.get_selected_actuators()

# Test standalone
if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication, QMainWindow
    
    app = QApplication(sys.argv)
    
    window = QMainWindow()
    window.setWindowTitle("Flexible Actuator Selector Test - Expanded Canvas")
    
    selector = FlexibleActuatorSelector()
    selector.selection_changed.connect(lambda ids: print(f"Selected actuators: {ids}"))
    
    window.setCentralWidget(selector)
    window.resize(800, 600)
    window.show()
    
    sys.exit(app.exec())