"""
Universal Waveform Designer - Main Application Window avec Interface Encadrée
Barre de connexion en haut et barre d'information en bas encadrant toute l'interface
"""

import sys
import os
import time
import subprocess

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QSplitter, QGroupBox, QLabel, QLineEdit, QTextEdit, QComboBox,
    QPushButton, QFileDialog, QMessageBox, QTabWidget,
    QListWidget, QListWidgetItem, QStatusBar, QToolBar,
    QTreeWidget, QTreeWidgetItem, QGridLayout, QDoubleSpinBox
)
from PyQt6.QtGui import QIcon                
from PyQt6.QtCore import Qt, pyqtSignal, QFileSystemWatcher, QTimer
from PyQt6.QtGui import QAction, QTextCursor

from event_data_model import HapticEvent, EventCategory, WaveformData
from waveform_editor_widget import WaveformEditorWidget
from python_serial_api import python_serial_api
from flexible_actuator_selector import FlexibleActuatorSelector
import numpy as np


class EventLibraryManager:
    """Manager for the root-level haptic waveforms library"""
    
    def __init__(self):
        # Find the actual project root by looking for common project files
        current_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Walk up the directory tree to find project root
        project_root = current_dir
        max_levels = 5  # Prevent infinite loop
        level = 0
        
        while level < max_levels:
            # Check for common project root indicators
            indicators = [
                'requirements.txt', 'setup.py', 'pyproject.toml', 
                '.git', '.gitignore', 'README.md', 'README.txt',
                'main.py', 'app.py'
            ]
            
            found_indicator = any(
                os.path.exists(os.path.join(project_root, indicator)) 
                for indicator in indicators
            )
            
            # If we find indicators or we're already at a reasonable level, stop
            if found_indicator or level >= 2:
                break
                
            # Go up one level
            parent = os.path.dirname(project_root)
            if parent == project_root:  # Reached filesystem root
                break
            project_root = parent
            level += 1
        
        # Force the waveform_library to be in the project root
        self.events_path = os.path.join(project_root, "waveform_library")
        
        # Create the directory if it doesn't exist
        os.makedirs(self.events_path, exist_ok=True)
        print(f"Project root detected: {project_root}")
        print(f"Waveform library path: {self.events_path}")
        
        # Create __init__.py file
        init_file = os.path.join(self.events_path, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write("# Waveform Library\n")
    
    def get_events_directory(self):
        return self.events_path
    
    def save_event(self, waveform_name, waveform_data):
        filename = f"{waveform_name}.json"
        filepath = os.path.join(self.events_path, filename)
        
        try:
            if hasattr(waveform_data, 'save_to_file'):
                result = waveform_data.save_to_file(filepath)
                if result:
                    print(f"Saved waveform to: {filepath}")  # Debug info
                return result
            else:
                import json
                with open(filepath, 'w') as f:
                    json.dump(waveform_data, f, indent=2)
                print(f"Saved waveform to: {filepath}")  # Debug info
                return True
        except Exception as e:
            print(f"Error saving waveform {waveform_name}: {e}")
            return False
    
    def load_event(self, waveform_name):
        filename = f"{waveform_name}.json"
        filepath = os.path.join(self.events_path, filename)
        
        try:
            return HapticEvent.load_from_file(filepath)
        except Exception as e:
            print(f"Error loading waveform {waveform_name}: {e}")
            return None
    
    def get_all_events(self):
        waveforms = []
        
        try:
            if os.path.exists(self.events_path):
                for filename in os.listdir(self.events_path):
                    if filename.endswith('.json'):
                        waveform_name = filename[:-5]
                        waveforms.append(waveform_name)
        except Exception as e:
            print(f"Error scanning waveform library: {e}")
        
        return sorted(waveforms)
    
    def delete_event(self, waveform_name):
        filename = f"{waveform_name}.json"
        filepath = os.path.join(self.events_path, filename)
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                print(f"Deleted waveform: {filepath}")  # Debug info
                return True
        except Exception as e:
            print(f"Error deleting waveform {waveform_name}: {e}")
        
        return False


class EventMetadataWidget(QWidget):
    """Widget for editing waveform metadata"""

    metadata_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_event: HapticEvent | None = None
        self.is_loading = False
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # Waveform name
        row = QHBoxLayout()
        row.addWidget(QLabel("Waveform Name:"))
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.on_name_changed)
        row.addWidget(self.name_edit)
        layout.addLayout(row)

        # Category
        row = QHBoxLayout()
        row.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItems([cat.value for cat in EventCategory])
        self.category_combo.currentTextChanged.connect(self.on_category_changed)
        row.addWidget(self.category_combo)
        layout.addLayout(row)

        # Description
        layout.addWidget(QLabel("Description:"))
        self.description_edit = QTextEdit()
        self.description_edit.setMaximumHeight(80)
        self.description_edit.textChanged.connect(self.on_description_changed)
        layout.addWidget(self.description_edit)

    def set_event(self, event: HapticEvent):
        self.current_event = event
        if event:
            self.load_metadata_from_event()

    def load_metadata_from_event(self):
        if not self.current_event:
            return
        self.is_loading = True

        self.name_edit.setText(self.current_event.metadata.name)
        self.category_combo.setCurrentText(self.current_event.metadata.category.value)

        self.description_edit.blockSignals(True)
        self.description_edit.setPlainText(self.current_event.metadata.description)
        self.description_edit.blockSignals(False)

        cursor = self.description_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        self.description_edit.setTextCursor(cursor)

        self.is_loading = False

    def on_name_changed(self, text):
        if self.current_event and not self.is_loading:
            self.current_event.metadata.name = text
            self.metadata_changed.emit()

    def on_category_changed(self, text):
        if self.current_event and not self.is_loading:
            self.current_event.metadata.category = EventCategory(text)
            self.metadata_changed.emit()

    def on_description_changed(self):
        if self.current_event and not self.is_loading:
            self.current_event.metadata.description = self.description_edit.toPlainText()
            self.metadata_changed.emit()


class EventLibraryWidget(QWidget):
    """A tree-view library that lists user-saved waveforms and built-in oscillators"""

    event_selected = pyqtSignal(str)

    BUILTIN_OSCILLATORS = [
        "Sine", "Square", "Saw", "Triangle",
        "Chirp", "FM", "PWM", "Noise"
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self.event_manager = EventLibraryManager()
        self.events_directory = self.event_manager.get_events_directory()
        self.dir_watcher = QFileSystemWatcher(self)
        self.dir_watcher.directoryChanged.connect(self.refresh_event_tree)
        self._setup_ui()
        self.dir_watcher.addPath(self.events_directory)
        self.refresh_event_tree()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Waveform Library"))
        
        info_label = QLabel(f"Location: {os.path.basename(self.events_directory)}/")
        info_label.setStyleSheet("color: #666; font-size: 10px;")
        header.addWidget(info_label)
        header.addStretch()
        
        layout.addLayout(header)

        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.itemDoubleClicked.connect(self._on_item_double_clicked)
        layout.addWidget(self.tree)

        btn_row = QHBoxLayout()
        btn_load = QPushButton("Load Selected")
        btn_load.clicked.connect(self._load_selected_item)
        btn_row.addWidget(btn_load)

        btn_delete = QPushButton("Delete")
        btn_delete.clicked.connect(self._delete_selected_item)
        btn_row.addWidget(btn_delete)
        
        btn_refresh = QPushButton("Refresh")
        btn_refresh.clicked.connect(self.refresh_event_tree)
        btn_row.addWidget(btn_refresh)
        
        layout.addLayout(btn_row)

    def refresh_event_tree(self) -> None:
        self.tree.clear()

        # Built-in oscillators
        osc_root = QTreeWidgetItem(["Built-in Oscillators"])
        self.tree.addTopLevelItem(osc_root)

        icon_path_root = os.path.join(os.path.dirname(__file__), "icons")
        for osc in self.BUILTIN_OSCILLATORS:
            child = QTreeWidgetItem([osc])
            icon_fp = os.path.join(icon_path_root, f"{osc.lower()}.png")
            if os.path.isfile(icon_fp):
                child.setIcon(0, QIcon(icon_fp))
            child.setData(0, Qt.ItemDataRole.UserRole, f"oscillator::{osc}")
            osc_root.addChild(child)
        osc_root.setExpanded(False)

        # User-saved waveforms
        category_nodes: dict[str, QTreeWidgetItem] = {}
        for filename in os.listdir(self.events_directory):
            if not filename.endswith(".json"):
                continue

            file_path = os.path.join(self.events_directory, filename)

            try:
                event = HapticEvent.load_from_file(file_path)
                category = event.metadata.category.value
                display_name = event.metadata.name
            except Exception:
                category = "Uncategorised"
                display_name = filename

            root = category_nodes.get(category)
            if root is None:
                root = QTreeWidgetItem([category])
                self.tree.addTopLevelItem(root)
                category_nodes[category] = root

            child = QTreeWidgetItem([display_name])
            child.setData(0, Qt.ItemDataRole.UserRole, file_path)
            root.addChild(child)

        self.tree.expandAll()

    def _on_item_double_clicked(self, item: QTreeWidgetItem, _column: int) -> None:
        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if payload:
            self.event_selected.emit(payload)

    def _load_selected_item(self) -> None:
        item = self.tree.currentItem()
        if item:
            payload = item.data(0, Qt.ItemDataRole.UserRole)
            if payload:
                self.event_selected.emit(payload)

    def _delete_selected_item(self) -> None:
        item = self.tree.currentItem()
        if not item:
            return

        payload = item.data(0, Qt.ItemDataRole.UserRole)
        if payload is None or payload.startswith("oscillator::"):
            QMessageBox.information(self, "Delete", "Built-in oscillators can't be deleted.")
            return

        if QMessageBox.question(
            self, "Delete waveform",
            f"Delete \"{os.path.basename(payload)}\" from waveform library?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        ) == QMessageBox.StandardButton.Yes:
            try:
                os.remove(payload)
            except OSError as e:
                QMessageBox.critical(self, "Error", str(e))


class HapticDeviceControlWidget(QWidget):
    """Widget simplifié pour contrôle haptique intégré dans l'interface principale"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.serial_api = python_serial_api()
        self.current_event = None
        self.setup_ui()
        
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Remplacer Playback Configuration par Actuator Selector
        self.actuator_selector = FlexibleActuatorSelector()
        self.actuator_selector.selection_changed.connect(self.on_actuator_selection_changed)
        
        # Connecter l'API aux actuateurs pour la vibration physique
        self.actuator_selector.canvas.set_api(self.serial_api)
        
        layout.addWidget(self.actuator_selector)
        
        # Paramètres de lecture compacts
        params_group = QGroupBox("Playback Parameters")
        params_layout = QGridLayout(params_group)
        
        params_layout.addWidget(QLabel("Duration (s):"), 0, 0)
        self.duration_spin = QDoubleSpinBox()
        self.duration_spin.setRange(0.1, 10.0)
        self.duration_spin.setValue(1.0)
        self.duration_spin.setSingleStep(0.1)
        params_layout.addWidget(self.duration_spin, 0, 1)
        
        params_layout.addWidget(QLabel("Intensity:"), 1, 0)
        self.intensity_spin = QDoubleSpinBox()
        self.intensity_spin.setRange(0.1, 2.0)
        self.intensity_spin.setValue(1.0)
        self.intensity_spin.setSingleStep(0.1)
        params_layout.addWidget(self.intensity_spin, 1, 1)
        
        layout.addWidget(params_group)
        
        # Contrôles
        controls_group = QGroupBox("Playback Controls")
        controls_layout = QHBoxLayout(controls_group)
        
        self.play_button = QPushButton("Play Waveform")
        self.play_button.setEnabled(False)
        controls_layout.addWidget(self.play_button)
        
        self.stop_button = QPushButton("Stop")
        self.stop_button.setEnabled(False)
        controls_layout.addWidget(self.stop_button)
        
        self.test_button = QPushButton("Test Selected")
        self.test_button.setEnabled(False)
        self.test_button.clicked.connect(self.test_selected_actuators)
        controls_layout.addWidget(self.test_button)
        
        layout.addWidget(controls_group)
        
    def on_actuator_selection_changed(self, selected_ids):
        """Appelé quand la sélection d'actuateurs change"""
        self.selected_actuator_ids = selected_ids
        self.test_button.setEnabled(len(selected_ids) > 0 and self.serial_api.connected)
        
    def test_selected_actuators(self):
        """Tester les actuateurs sélectionnés"""
        if not self.serial_api.connected:
            return
            
        selected_ids = getattr(self, 'selected_actuator_ids', [])
        if not selected_ids:
            return
            
        # Envoyer une impulsion de test aux actuateurs sélectionnés
        for actuator_id in selected_ids:
            self.serial_api.send_command(actuator_id, 10, 4, 1)  # Intensité moyenne
            
        # Arrêter après 500ms
        QTimer.singleShot(500, lambda: self.stop_test_actuators(selected_ids))
        
    def stop_test_actuators(self, actuator_ids):
        """Arrêter le test des actuateurs"""
        for actuator_id in actuator_ids:
            self.serial_api.send_command(actuator_id, 0, 4, 0)
        
    def get_selected_actuator_addresses(self):
        """Obtenir les adresses des actuateurs sélectionnés"""
        return getattr(self, 'selected_actuator_ids', [])
        
    def set_event(self, event):
        self.current_event = event
        if event and event.waveform_data:
            # Mettre à jour la durée par défaut depuis l'événement
            self.duration_spin.setValue(event.waveform_data.duration)
            
    def update_connection_status(self, connected):
        self.play_button.setEnabled(connected and self.current_event is not None)
        selected_ids = getattr(self, 'selected_actuator_ids', [])
        self.test_button.setEnabled(connected and len(selected_ids) > 0)


class UniversalEventDesigner(QMainWindow):
    """Fenêtre principale avec interface encadrée"""

    def __init__(self):
        super().__init__()
        self.current_event: HapticEvent | None = None
        self.current_file_path: str | None = None
        
        # Initialize components
        self.event_manager = EventLibraryManager()
        self.serial_api = python_serial_api()
        
        # Meta Haptics Studio auto-import
        self.export_watch_dir: str | None = None
        self.export_start_mtime: float = 0.0
        self.dir_watcher = QFileSystemWatcher(self)
        self.dir_watcher.directoryChanged.connect(self._dir_changed)

        self.setup_ui()
        self.new_event()

    def setup_ui(self):
        self.setWindowTitle("Universal Haptic Waveform Designer")
        self.setGeometry(100, 100, 1600, 900)
        
        # Style global pour l'interface encadrée - Mode sombre standard sans vert
        self.setStyleSheet("""
            QMainWindow {
                background-color: #2a2a2a;
                color: white;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12pt;
            }
            QWidget {
                background-color: #2a2a2a;
                color: white;
                font-family: "Segoe UI", Arial, sans-serif;
                font-size: 12pt;
            }
            QGroupBox {
                background-color: #3a3a3a;
                border: 1px solid #555;
                border-radius: 5px;
                margin-top: 10px;
                padding-top: 10px;
                color: white;
                font-weight: normal;
                font-size: 12pt;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
                color: white;
                font-weight: normal;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #666;
                color: white;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 12pt;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
                border: 1px solid #777;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
                border: 1px solid #555;
            }
            QPushButton:disabled {
                background-color: #333;
                color: #666;
                border: 1px solid #444;
            }
            QLineEdit {
                background-color: #444;
                border: 1px solid #666;
                color: white;
                padding: 4px;
                border-radius: 3px;
                font-size: 12pt;
            }
            QLineEdit:focus {
                border: 1px solid #888;
                background-color: #484848;
            }
            QTextEdit {
                background-color: #444;
                border: 1px solid #666;
                color: white;
                padding: 4px;
                border-radius: 3px;
                font-size: 12pt;
            }
            QTextEdit:focus {
                border: 1px solid #888;
                background-color: #484848;
            }
            QComboBox {
                background-color: #444;
                border: 1px solid #666;
                color: white;
                padding: 4px;
                border-radius: 3px;
                font-size: 12pt;
            }
            QComboBox::drop-down {
                border: none;
                width: 20px;
            }
            QComboBox::down-arrow {
                image: none;
                border-left: 4px solid transparent;
                border-right: 4px solid transparent;
                border-top: 4px solid white;
                width: 0;
                height: 0;
            }
            QComboBox QAbstractItemView {
                background-color: #444;
                color: white;
                selection-background-color: #5a5a5a;
                border: 1px solid #666;
            }
            QDoubleSpinBox, QSpinBox {
                background-color: #444;
                border: 1px solid #666;
                color: white;
                padding: 4px;
                border-radius: 3px;
                font-size: 12pt;
            }
            QDoubleSpinBox:focus, QSpinBox:focus {
                border: 1px solid #888;
                background-color: #484848;
            }
            QDoubleSpinBox::up-button, QSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                width: 16px;
                border-left-width: 1px;
                border-left-color: #666;
                border-left-style: solid;
                border-top-right-radius: 3px;
                background-color: #555;
            }
            QDoubleSpinBox::down-button, QSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                width: 16px;
                border-left-width: 1px;
                border-left-color: #666;
                border-left-style: solid;
                border-bottom-right-radius: 3px;
                background-color: #555;
            }
            QDoubleSpinBox::up-arrow, QSpinBox::up-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-bottom: 3px solid white;
                width: 0;
                height: 0;
            }
            QDoubleSpinBox::down-arrow, QSpinBox::down-arrow {
                image: none;
                border-left: 3px solid transparent;
                border-right: 3px solid transparent;
                border-top: 3px solid white;
                width: 0;
                height: 0;
            }
            QLabel {
                color: white;
                font-size: 12pt;
                font-weight: normal;
            }
            QTabWidget::pane {
                border: 1px solid #555;
                background-color: #3a3a3a;
            }
            QTabBar::tab {
                background-color: #444;
                color: white;
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                font-size: 12pt;
                font-weight: normal;
            }
            QTabBar::tab:selected {
                background-color: #5a5a5a;
                color: white;
            }
            QTabBar::tab:hover {
                background-color: #505050;
            }
            QSplitter::handle {
                background-color: #555;
            }
            QTreeWidget {
                background-color: #3a3a3a;
                color: white;
                border: 1px solid #555;
                selection-background-color: #5a5a5a;
                font-size: 12pt;
            }
            QTreeWidget::item:hover {
                background-color: #484848;
            }
            QTreeWidget::item:selected {
                background-color: #5a5a5a;
            }
            QScrollBar:vertical {
                background-color: #3a3a3a;
                width: 12px;
                border: none;
            }
            QScrollBar::handle:vertical {
                background-color: #555;
                border-radius: 6px;
                min-height: 20px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: #666;
            }
            QScrollBar:horizontal {
                background-color: #3a3a3a;
                height: 12px;
                border: none;
            }
            QScrollBar::handle:horizontal {
                background-color: #555;
                border-radius: 6px;
                min-width: 20px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: #666;
            }
            QScrollBar::add-line, QScrollBar::sub-line {
                border: none;
                background: none;
            }
            QGraphicsView {
                background-color: #2a2a2a;
                border: 1px solid #555;
            }
        """)

        # Widget central principal
        central = QWidget()
        self.setCentralWidget(central)
        
        # Layout principal avec les barres d'encadrement
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 1. BARRE DE CONNEXION EN HAUT (encadrement supérieur)
        self.connection_bar = self.create_connection_bar()
        main_layout.addWidget(self.connection_bar)
        
        # 2. CONTENU PRINCIPAL
        content_widget = QWidget()
        content_layout = QHBoxLayout(content_widget)
        content_layout.setContentsMargins(10, 10, 10, 10)
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        content_layout.addWidget(splitter)

        # Left panel (tabs)
        splitter.addWidget(self.create_left_panel())

        # Center panel (waveform editor)
        self.waveform_editor = WaveformEditorWidget()
        splitter.addWidget(self.waveform_editor)

        # Right panel (haptic device control)
        self.haptic_control = HapticDeviceControlWidget()
        splitter.addWidget(self.haptic_control)

        # Set sizes
        splitter.setSizes([250, 1000, 350])
        
        main_layout.addWidget(content_widget, 1)  # Stretch factor 1
        
        # 3. BARRE D'INFORMATION EN BAS (encadrement inférieur)
        self.info_bar = self.create_info_bar()
        main_layout.addWidget(self.info_bar)

    def create_connection_bar(self):
        """Créer la barre de connexion en haut qui encadre l'interface"""
        connection_widget = QWidget()
        connection_widget.setFixedHeight(50)
        connection_widget.setStyleSheet("""
            QWidget {
                background-color: #3a3a3a;
                border-bottom: 2px solid #666;
            }
            QLabel {
                color: white;
                font-weight: normal;
                font-size: 12pt;
            }
            QPushButton {
                background-color: #4a4a4a;
                border: 1px solid #666;
                color: white;
                padding: 6px 12px;
                border-radius: 3px;
                font-size: 12pt;
                font-weight: normal;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QPushButton:pressed {
                background-color: #3a3a3a;
            }
            QComboBox {
                background-color: #444;
                border: 1px solid #666;
                color: white;
                padding: 5px;
                border-radius: 3px;
                min-width: 180px;
                font-size: 12pt;
            }
        """)
        
        layout = QHBoxLayout(connection_widget)
        layout.setContentsMargins(15, 8, 25, 8)  # Plus de marge à droite
        
        # Device Connection section
        device_label = QLabel("Device Connection")
        device_label.setStyleSheet("font-size: 11pt; font-weight: bold;")
        layout.addWidget(device_label)
        
        layout.addSpacing(15)  # Réduit l'espacement
        
        layout.addWidget(QLabel("Device:"))
        self.device_combo = QComboBox()
        layout.addWidget(self.device_combo)
        
        self.scan_button = QPushButton("Scan")
        self.scan_button.clicked.connect(self.scan_devices)
        layout.addWidget(self.scan_button)
        
        self.connect_button = QPushButton("Connect")
        self.connect_button.clicked.connect(self.toggle_connection)
        layout.addWidget(self.connect_button)
        
        # Espacement flexible plus petit pour laisser plus de place au statut
        layout.addStretch(1)
        
        # Status à droite avec plus d'espace réservé
        self.connection_status_label = QLabel("Status: Disconnected")
        self.connection_status_label.setStyleSheet("color: #ff6b6b; font-weight: normal;")
        self.connection_status_label.setMinimumWidth(140)  # Largeur minimum garantie
        layout.addWidget(self.connection_status_label)
        
        # Scan initial
        QTimer.singleShot(100, self.scan_devices)
        
        return connection_widget

    def create_info_bar(self):
        """Créer la barre d'information en bas qui encadre l'interface"""
        info_widget = QWidget()
        info_widget.setFixedHeight(100)
        info_widget.setStyleSheet("""
            QWidget {
                background-color: #2a2a2a;
                border-top: 2px solid #666;
            }
            QLabel {
                color: white;
                font-weight: normal;
                padding: 5px;
                font-size: 12pt;
            }
            QTextEdit {
                background-color: #1a1a1a;
                border: 1px solid #555;
                color: #cccccc;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 12pt;
                padding: 5px;
            }
        """)
        
        layout = QVBoxLayout(info_widget)
        layout.setContentsMargins(15, 5, 15, 5)
        layout.setSpacing(3)
        
        # Header
        info_label = QLabel("Information")
        info_label.setStyleSheet("font-size: 10pt; font-weight: bold;")
        layout.addWidget(info_label)
        
        # Log text
        self.info_text = QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)
        
        # Message initial
        self.log_info_message("New waveform created")
        
        return info_widget

    def create_left_panel(self):
        tabs = QTabWidget()

        # Waveform design tab
        meta_tab = QWidget()
        meta_layout = QVBoxLayout(meta_tab)

        # Buttons
        buttons_layout = QHBoxLayout()
        btn_new = QPushButton("New")
        btn_new.clicked.connect(self.new_event)
        buttons_layout.addWidget(btn_new)

        btn_save = QPushButton("Save")
        btn_save.clicked.connect(self.save_event)
        buttons_layout.addWidget(btn_save)

        meta_layout.addLayout(buttons_layout)

        # Waveform Information
        group_info = QGroupBox("Waveform Information")
        box = QVBoxLayout(group_info)
        self.metadata_widget = EventMetadataWidget()
        self.metadata_widget.metadata_changed.connect(self.on_metadata_changed)
        box.addWidget(self.metadata_widget)
        meta_layout.addWidget(group_info)

        # Haptic File
        group_file = QGroupBox("Haptic File")
        file_layout = QVBoxLayout(group_file)

        btn_import = QPushButton("Import .haptic File")
        btn_import.clicked.connect(self.import_haptic_file)
        file_layout.addWidget(btn_import)

        btn_create = QPushButton("Create with Meta Haptics Studio")
        btn_create.clicked.connect(self.create_with_meta_studio)
        file_layout.addWidget(btn_create)

        self.file_info_label = QLabel("No file loaded")
        self.file_info_label.setWordWrap(True)
        file_layout.addWidget(self.file_info_label)

        meta_layout.addWidget(group_file)

        # Math section
        group_math = QGroupBox("Math")
        math_layout = QVBoxLayout(group_math)

        equation_layout = QHBoxLayout()
        equation_layout.addWidget(QLabel("Equation:"))
        self.math_equation = QLineEdit("np.sin(2 * np.pi * f * t)")
        equation_layout.addWidget(self.math_equation)
        math_layout.addLayout(equation_layout)

        params_layout = QGridLayout()
        params_layout.addWidget(QLabel("Frequency:"), 0, 0)
        self.math_freq = QDoubleSpinBox(value=100.0, minimum=0.1, maximum=1000.0, singleStep=1.0)
        params_layout.addWidget(self.math_freq, 0, 1)

        params_layout.addWidget(QLabel("Duration (s):"), 1, 0)
        self.math_dur = QDoubleSpinBox(value=1.0, minimum=0.1, maximum=10.0, singleStep=0.1)
        params_layout.addWidget(self.math_dur, 1, 1)

        params_layout.addWidget(QLabel("Sample Rate:"), 2, 0)
        self.math_sr = QDoubleSpinBox(value=1000.0, minimum=100.0, maximum=10000.0, singleStep=100.0)
        params_layout.addWidget(self.math_sr, 2, 1)

        math_layout.addLayout(params_layout)

        btn_gen = QPushButton("Generate")
        btn_gen.clicked.connect(self.generate_from_math)
        math_layout.addWidget(btn_gen)

        meta_layout.addWidget(group_math)

        meta_layout.addStretch()
        tabs.addTab(meta_tab, "Waveform Design")

        # Library tab
        self.library_widget = EventLibraryWidget()
        self.library_widget.event_selected.connect(self.load_event_from_file)
        tabs.addTab(self.library_widget, "Waveform Library")

        return tabs

    def scan_devices(self):
        """Scan for available serial devices"""
        try:
            devices = self.serial_api.get_serial_devices()
            self.device_combo.clear()
            self.device_combo.addItems(devices)
            self.log_info_message(f"Found {len(devices)} devices")
        except Exception as e:
            self.log_info_message(f"Error scanning devices: {e}")

    def toggle_connection(self):
        """Connect or disconnect from the selected device"""
        if self.serial_api.connected:
            if self.serial_api.disconnect_serial_device():
                self.connection_status_label.setText("Status: Disconnected")
                self.connection_status_label.setStyleSheet("color: #ff6b6b; font-weight: normal;")
                self.connect_button.setText("Connect")
                self.haptic_control.update_connection_status(False)
                self.log_info_message("Disconnected from device")
            else:
                self.log_info_message("Failed to disconnect")
        else:
            device_info = self.device_combo.currentText()
            if device_info and self.serial_api.connect_serial_device(device_info):
                self.connection_status_label.setText("Status: Connected")
                self.connection_status_label.setStyleSheet("color: #6bff6b; font-weight: normal;")
                self.connect_button.setText("Disconnect")
                self.haptic_control.update_connection_status(True)
                self.log_info_message(f"Connected to {device_info}")
            else:
                self.log_info_message("Failed to connect to device")

    def log_info_message(self, message):
        """Add a message to the info log"""
        timestamp = time.strftime("%H:%M:%S")
        self.info_text.append(f"[{timestamp}] {message}")
        scrollbar = self.info_text.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    # Meta Haptics Studio workflow
    def create_with_meta_studio(self):
        watch_dir = QFileDialog.getExistingDirectory(
            self, "Choose the folder where you will export your .haptic file"
        )
        if not watch_dir:
            return

        if self.export_watch_dir:
            self.dir_watcher.removePath(self.export_watch_dir)
        self.export_watch_dir = watch_dir
        self.export_start_mtime = time.time()
        self.dir_watcher.addPath(watch_dir)

        if sys.platform.startswith("darwin"):
            subprocess.Popen(["open", "-a", "Meta Haptics Studio"])
        elif sys.platform.startswith("win"):
            os.startfile(r"C:\Program Files\Meta Haptic Studio\MetaHapticStudio.exe")
        else:
            subprocess.Popen(["/opt/meta-haptic-studio/MetaHapticStudio"])

        self.log_info_message(f"Meta Haptics Studio launched – waiting for .haptic in \"{watch_dir}\"…")

    def _dir_changed(self, path):
        if path != self.export_watch_dir:
            return

        candidates = [
            os.path.join(path, f) for f in os.listdir(path)
            if f.lower().endswith(".haptic")
        ]
        if not candidates:
            return

        latest = max(candidates, key=os.path.getmtime)
        if os.path.getmtime(latest) < self.export_start_mtime:
            return

        self.dir_watcher.removePath(path)
        self.export_watch_dir = None

        if self.current_event.load_from_haptic_file(latest):
            self.update_ui()
            self.file_info_label.setText(f"Loaded: {os.path.basename(latest)}")
            self.log_info_message(f"File imported: {os.path.basename(latest)}")
        else:
            QMessageBox.critical(
                self, "Error", f"Could not import \"{os.path.basename(latest)}\"."
            )

    # File operations
    def new_event(self):
        self.current_event = HapticEvent()
        self.current_file_path = None
        self.update_ui()
        self.log_info_message("New waveform created")

    def open_event(self):
        """Open waveform from the waveform library"""
        path, _ = QFileDialog.getOpenFileName(
            self, "Open Waveform", self.event_manager.get_events_directory(), 
            "Waveform Files (*.json);;All Files (*)"
        )
        if path:
            self.load_event_from_file(path)

    def load_event_from_file(self, path: str) -> None:
        """Load waveform from file or create oscillator"""
        if path.startswith("oscillator::"):
            osc_type = path.split("::", 1)[1]
            try:
                self.current_event = HapticEvent.new_basic_oscillator(osc_type)
            except Exception as e:
                QMessageBox.critical(
                    self, "Error",
                    f"Could not create {osc_type} oscillator: {str(e)}"
                )
                return
            self.current_file_path = None
            self.update_ui()
            self.log_info_message(f"New {osc_type} oscillator created")
            return

        # Ordinary JSON files
        try:
            event = HapticEvent.load_from_file(path)
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))
            return

        self.current_event = event
        self.current_file_path = path
        self.update_ui()
        self.log_info_message(f"Loaded: {os.path.basename(path)}")

    def save_event(self):
        """Save waveform to the waveform library"""
        if self.current_event is None:
            return
        if self.current_file_path:
            if self.current_event.save_to_file(self.current_file_path):
                self.log_info_message(f"Saved: {os.path.basename(self.current_file_path)}")
            else:
                QMessageBox.critical(self, "Error", "Save failed")
        else:
            self.save_event_as()

    def save_event_as(self):
        """Save waveform as new file in the waveform library"""
        if self.current_event is None:
            return
        
        suggested = (self.current_event.metadata.name or "untitled").replace(" ", "_")
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Waveform As", 
            os.path.join(self.event_manager.get_events_directory(), f"{suggested}.json"),
            "Waveform Files (*.json);;All Files (*)"
        )
        if path and self.current_event.save_to_file(path):
            self.current_file_path = path
            self.log_info_message(f"Saved: {os.path.basename(path)}")

    def import_haptic_file(self):
        if self.current_event is None:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Import .haptic File", "", "Haptic Files (*.haptic);;All Files (*)"
        )
        if path and self.current_event.load_from_haptic_file(path):
            self.update_ui()
            self.file_info_label.setText(f"Loaded: {os.path.basename(path)}")
            self.log_info_message(f"Imported: {os.path.basename(path)}")

    def generate_from_math(self):
        if not self.current_event:
            return
        try:
            f = self.math_freq.value()
            dur = self.math_dur.value()
            sr = self.math_sr.value()
            t = np.linspace(0, dur, int(sr * dur), endpoint=False)
            eq = self.math_equation.text()
            locals_dict = {"t": t, "f": f, "pi": np.pi, "np": np, "sin": np.sin, "cos": np.cos, "exp": np.exp}
            y = eval(eq, {"__builtins__": {}}, locals_dict)
            amp = [{"time": float(tt), "amplitude": float(yy)} for tt, yy in zip(t, y)]
            freq = [{"time": 0.0, "frequency": f}, {"time": dur, "frequency": f}]
            self.current_event.waveform_data = WaveformData(amp, freq, dur, sr)
            self.update_ui()
            self.log_info_message("Waveform generated from equation")
        except Exception as e:
            QMessageBox.critical(self, "Generation Error", f"Error generating waveform: {str(e)}")

    def update_ui(self):
        if self.current_event:
            self.metadata_widget.set_event(self.current_event)
            self.waveform_editor.set_event(self.current_event)
            self.haptic_control.set_event(self.current_event)

            if self.current_event.original_haptic_file:
                self.file_info_label.setText(
                    f"Loaded: {os.path.basename(self.current_event.original_haptic_file)}"
                )
            else:
                self.file_info_label.setText("No file loaded")

            title = self.current_event.metadata.name or "Untitled"
            self.setWindowTitle(f"Universal Haptic Waveform Designer – {title}")
        else:
            self.setWindowTitle("Universal Haptic Waveform Designer")

    def on_metadata_changed(self):
        self.update_ui()

    def closeEvent(self, event):
        """Clean up when closing the application"""
        if self.export_watch_dir:
            self.dir_watcher.removePath(self.export_watch_dir)
            
        if self.serial_api.connected:
            self.serial_api.disconnect_serial_device()
            
        event.accept()


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Universal Haptic Waveform Designer")
    app.setApplicationVersion("2.1")
    app.setOrganizationName("Haptic Systems")

    window = UniversalEventDesigner()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()