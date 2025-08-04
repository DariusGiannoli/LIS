#!/usr/bin/env python3
import sys
import os
import time
import json
import random
from datetime import datetime
from PyQt6 import QtWidgets, uic
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *

from python_serial_api import python_serial_api
from vibration_patterns import *

# Import du sélecteur d'actuateurs compact
from flexible_actuator_selector import FlexibleActuatorSelector

# Import event library components
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from data.event_data_model import HapticEvent
except ImportError:
    # Fallback if import fails
    HapticEvent = None

# Configuration des paramètres spécifiques aux motifs
PATTERN_PARAMETERS = {
    "Single Pulse": {
        "parameters": []
    },
    "Wave": {
        "parameters": [
            {
                "name": "wave_speed",
                "label": "Wave Speed:",
                "type": "float",
                "default": 0.5,
                "range": (0.1, 10.0),
                "step": 0.1,
                "suffix": " s",
                "description": "Time duration for wave to move across all actuators"
            }
        ]
    },
    "Pulse Train": {
        "parameters": [
            {
                "name": "pulse_on",
                "label": "Pulse On:",
                "type": "float",
                "default": 0.2,
                "range": (0.01, 5.0),
                "step": 0.01,
                "suffix": " s",
                "description": "Duration of each pulse (ON time)"
            },
            {
                "name": "pulse_off",
                "label": "Pulse Off:",
                "type": "float",
                "default": 0.3,
                "range": (0.01, 5.0),
                "step": 0.01,
                "suffix": " s",
                "description": "Duration between pulses (OFF time)"
            }
        ]
    },
    "Fade": {
        "parameters": [
            {
                "name": "fade_steps",
                "label": "Fade Steps:",
                "type": "int",
                "default": 10,
                "range": (1, 50),
                "step": 1,
                "suffix": "",
                "description": "Number of intensity steps for fade in/out transition"
            }
        ]
    },
    "Circular": {
        "parameters": [
            {
                "name": "rotation_speed",
                "label": "Rotation Speed:",
                "type": "float",
                "default": 1.0,
                "range": (0.1, 10.0),
                "step": 0.1,
                "suffix": " s",
                "description": "Time for one complete rotation through all actuators"
            }
        ]
    },
    "Random": {
        "parameters": [
            {
                "name": "change_interval",
                "label": "Change Interval:",
                "type": "float",
                "default": 0.3,
                "range": (0.1, 5.0),
                "step": 0.1,
                "suffix": " s",
                "description": "Time interval between random actuator changes"
            }
        ]
    },
    "Sine Wave": {
        "parameters": [
            {
                "name": "sine_frequency",
                "label": "Sine Frequency:",
                "type": "float",
                "default": 2.0,
                "range": (0.1, 20.0),
                "step": 0.1,
                "suffix": " Hz",
                "description": "Frequency of sine wave intensity modulation"
            }
        ]
    }
}

class EventLibraryManager:
    """Manager for the root-level event library"""
    
    def __init__(self):
        # Determine the event_library path relative to the project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.event_library_path = os.path.join(project_root, "event_library")
        
        # Create event_library directory if it doesn't exist
        os.makedirs(self.event_library_path, exist_ok=True)
        
        # Create __init__.py if it doesn't exist
        init_file = os.path.join(self.event_library_path, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write("# Event Library\n")
    
    def get_all_events(self):
        """Get all available events"""
        events = {}
        
        try:
            if os.path.exists(self.event_library_path):
                for filename in os.listdir(self.event_library_path):
                    if filename.endswith('.json'):
                        event_name = filename[:-5]  # Remove .json extension
                        events[event_name] = filename
        except Exception as e:
            print(f"Error scanning event library: {e}")
        
        return events
    
    def load_event(self, event_name):
        """Load an event from the library"""
        try:
            if HapticEvent:
                filepath = os.path.join(self.event_library_path, f"{event_name}.json")
                return HapticEvent.load_from_file(filepath)
        except Exception as e:
            print(f"Error loading event {event_name}: {e}")
        return None

class PatternLibraryManager:
    """Gestionnaire pour la bibliothèque de patterns"""
    
    def __init__(self):
        # Determine the pattern_library path relative to the project root
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        self.pattern_library_path = os.path.join(project_root, "pattern_library")
        
        # Create pattern_library directory if it doesn't exist
        os.makedirs(self.pattern_library_path, exist_ok=True)
        
        # Create __init__.py if it doesn't exist
        init_file = os.path.join(self.pattern_library_path, "__init__.py")
        if not os.path.exists(init_file):
            with open(init_file, 'w') as f:
                f.write("# Pattern Library\n")
    
    def save_pattern(self, pattern_name, pattern_data):
        """Sauvegarder un pattern dans la bibliothèque"""
        filename = f"{pattern_name}.json"
        filepath = os.path.join(self.pattern_library_path, filename)
        
        try:
            with open(filepath, 'w') as f:
                json.dump(pattern_data, f, indent=2)
            return True
        except Exception as e:
            print(f"Error saving pattern {pattern_name}: {e}")
            return False
    
    def load_pattern(self, pattern_name):
        """Charger un pattern depuis la bibliothèque"""
        filename = f"{pattern_name}.json"
        filepath = os.path.join(self.pattern_library_path, filename)
        
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading pattern {pattern_name}: {e}")
            return None
    
    def get_all_patterns(self):
        """Obtenir tous les patterns disponibles"""
        patterns = {}
        
        try:
            if os.path.exists(self.pattern_library_path):
                for filename in os.listdir(self.pattern_library_path):
                    if filename.endswith('.json'):
                        pattern_name = filename[:-5]  # Remove .json extension
                        pattern_data = self.load_pattern(pattern_name)
                        if pattern_data:
                            patterns[pattern_name] = pattern_data
        except Exception as e:
            print(f"Error scanning pattern library: {e}")
        
        return patterns
    
    def delete_pattern(self, pattern_name):
        """Supprimer un pattern de la bibliothèque"""
        filename = f"{pattern_name}.json"
        filepath = os.path.join(self.pattern_library_path, filename)
        
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                return True
        except Exception as e:
            print(f"Error deleting pattern {pattern_name}: {e}")
        
        return False
    
    def get_pattern_info(self, pattern_name):
        """Obtenir les informations d'un pattern"""
        pattern_data = self.load_pattern(pattern_name)
        if pattern_data:
            return {
                'name': pattern_data.get('name', pattern_name),
                'description': pattern_data.get('description', ''),
                'timestamp': pattern_data.get('timestamp', ''),
                'config': pattern_data.get('config', {})
            }
        return None

class PatternVisualizationWidget(QWidget):
    """Widget pour visualiser les patterns disponibles"""
    
    pattern_selected = pyqtSignal(dict)
    pattern_deleted = pyqtSignal(str)
    
    def __init__(self, pattern_manager):
        super().__init__()
        self.pattern_manager = pattern_manager
        self.setup_ui()
        self.refresh_patterns()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        
        # Header
        header_layout = QHBoxLayout()
        title_label = QLabel("Pattern Library")
        title_label.setStyleSheet("font-weight: bold; font-size: 12px;")
        header_layout.addWidget(title_label)
        
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setMaximumWidth(80)
        self.refresh_button.clicked.connect(self.refresh_patterns)
        header_layout.addWidget(self.refresh_button)
        
        layout.addLayout(header_layout)
        
        # Pattern list
        self.pattern_list = QListWidget()
        self.pattern_list.setMaximumHeight(150)
        self.pattern_list.itemClicked.connect(self.on_pattern_clicked)
        self.pattern_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.pattern_list.customContextMenuRequested.connect(self.show_context_menu)
        layout.addWidget(self.pattern_list)
        
        # Pattern info display
        self.info_label = QLabel("Select a pattern to view details")
        self.info_label.setWordWrap(True)
        self.info_label.setStyleSheet("background-color: #f0f0f0; padding: 8px; border-radius: 4px;")
        self.info_label.setMinimumHeight(60)
        layout.addWidget(self.info_label)
        
        # Load button
        self.load_button = QPushButton("Load Selected Pattern")
        self.load_button.setEnabled(False)
        self.load_button.clicked.connect(self.load_selected_pattern)
        layout.addWidget(self.load_button)
    
    def refresh_patterns(self):
        """Rafraîchir la liste des patterns"""
        self.pattern_list.clear()
        self.patterns = self.pattern_manager.get_all_patterns()
        
        for pattern_name in sorted(self.patterns.keys()):
            item = QListWidgetItem(pattern_name)
            # Add some metadata as tooltip
            pattern_info = self.patterns[pattern_name]
            config = pattern_info.get('config', {})
            tooltip = f"Pattern: {config.get('pattern_type', 'Unknown')}\n"
            tooltip += f"Actuators: {len(config.get('actuators', []))}\n"
            tooltip += f"Created: {pattern_info.get('timestamp', 'Unknown')}"
            item.setToolTip(tooltip)
            self.pattern_list.addItem(item)
        
        # Update info
        count = len(self.patterns)
        if count == 0:
            self.info_label.setText("No patterns found in library")
        else:
            self.info_label.setText(f"Found {count} pattern(s) in library")
    
    def on_pattern_clicked(self, item):
        """Gérer le clic sur un pattern"""
        pattern_name = item.text()
        pattern_info = self.pattern_manager.get_pattern_info(pattern_name)
        
        if pattern_info:
            # Display pattern information
            config = pattern_info['config']
            info_text = f"<b>{pattern_info['name']}</b><br>"
            info_text += f"<i>{pattern_info['description']}</i><br><br>" if pattern_info['description'] else "<br>"
            info_text += f"<b>Type:</b> {config.get('pattern_type', 'Unknown')}<br>"
            info_text += f"<b>Actuators:</b> {config.get('actuators', [])}<br>"
            info_text += f"<b>Intensity:</b> {config.get('intensity', 0)}<br>"
            info_text += f"<b>Frequency:</b> {config.get('frequency', 0)}<br>"
            info_text += f"<b>Duration:</b> {config.get('duration', 0)}s<br>"
            
            # Show waveform info if available
            waveform_info = config.get('waveform', {})
            if waveform_info:
                info_text += f"<b>Waveform:</b> {waveform_info.get('name', 'Unknown')} ({waveform_info.get('source', 'Unknown')})<br>"
            
            specific_params = config.get('specific_parameters', {})
            if specific_params:
                info_text += f"<b>Specific Parameters:</b><br>"
                for key, value in specific_params.items():
                    info_text += f"&nbsp;&nbsp;{key}: {value}<br>"
            
            info_text += f"<br><small>Created: {pattern_info['timestamp']}</small>"
            
            self.info_label.setText(info_text)
            self.load_button.setEnabled(True)
        else:
            self.info_label.setText("Error loading pattern information")
            self.load_button.setEnabled(False)
    
    def load_selected_pattern(self):
        """Charger le pattern sélectionné"""
        current_item = self.pattern_list.currentItem()
        if current_item:
            pattern_name = current_item.text()
            pattern_info = self.pattern_manager.get_pattern_info(pattern_name)
            if pattern_info:
                self.pattern_selected.emit(pattern_info)
    
    def show_context_menu(self, position):
        """Afficher le menu contextuel"""
        item = self.pattern_list.itemAt(position)
        if item:
            menu = QMenu(self)
            
            load_action = menu.addAction("Load Pattern")
            load_action.triggered.connect(self.load_selected_pattern)
            
            menu.addSeparator()
            
            delete_action = menu.addAction("Delete Pattern")
            delete_action.triggered.connect(lambda: self.delete_pattern(item.text()))
            
            menu.exec(self.pattern_list.mapToGlobal(position))
    
    def delete_pattern(self, pattern_name):
        """Supprimer un pattern"""
        reply = QMessageBox.question(
            self,
            "Delete Pattern",
            f"Are you sure you want to delete pattern '{pattern_name}'?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            if self.pattern_manager.delete_pattern(pattern_name):
                self.pattern_deleted.emit(pattern_name)
                self.refresh_patterns()
                self.info_label.setText("Pattern deleted successfully")
                self.load_button.setEnabled(False)
            else:
                QMessageBox.critical(self, "Error", f"Failed to delete pattern '{pattern_name}'")

class PatternWorker(QThread):
    """Worker thread for running patterns"""
    finished = pyqtSignal(bool, str)
    log_message = pyqtSignal(str)
    
    def __init__(self, pattern, params):
        super().__init__()
        self.pattern = pattern
        self.params = params
    
    def run(self):
        try:
            result = self.pattern.execute(**self.params)
            message = "Pattern completed successfully" if result else "Pattern execution failed"
            self.log_message.emit(message)
            self.finished.emit(result, message)
        except Exception as e:
            error_msg = f"Pattern execution error: {e}"
            self.log_message.emit(error_msg)
            self.finished.emit(False, error_msg)

class SavePatternDialog(QDialog):
    """Dialog pour sauvegarder un pattern"""
    
    def __init__(self, current_config, parent=None):
        super().__init__(parent)
        self.current_config = current_config
        self.setWindowTitle("Save Pattern Configuration")
        self.setModal(True)
        self.resize(400, 300)
        
        layout = QVBoxLayout(self)
        
        # Nom du pattern
        form_layout = QFormLayout()
        self.nameEdit = QLineEdit()
        self.nameEdit.setPlaceholderText("Enter pattern name...")
        form_layout.addRow("Pattern Name:", self.nameEdit)
        
        self.descriptionEdit = QTextEdit()
        self.descriptionEdit.setPlaceholderText("Optional description...")
        self.descriptionEdit.setMaximumHeight(80)
        form_layout.addRow("Description:", self.descriptionEdit)
        
        layout.addLayout(form_layout)
        
        # Aperçu de la configuration
        preview_group = QGroupBox("Configuration Preview")
        preview_layout = QVBoxLayout(preview_group)
        
        self.previewText = QTextEdit()
        self.previewText.setReadOnly(True)
        self.previewText.setMaximumHeight(120)
        self._update_preview()
        preview_layout.addWidget(self.previewText)
        
        layout.addWidget(preview_group)
        
        # Boutons
        button_layout = QHBoxLayout()
        self.cancelButton = QPushButton("Cancel")
        self.cancelButton.clicked.connect(self.reject)
        self.saveButton = QPushButton("Save")
        self.saveButton.clicked.connect(self.accept)
        
        button_layout.addWidget(self.cancelButton)
        button_layout.addWidget(self.saveButton)
        layout.addLayout(button_layout)
        
        # Validation
        self.nameEdit.textChanged.connect(self._validate_input)
        self._validate_input()
    
    def _update_preview(self):
        """Mettre à jour l'aperçu de la configuration"""
        config_text = f"Pattern Type: {self.current_config.get('pattern_type', 'N/A')}\n"
        config_text += f"Actuators: {self.current_config.get('actuators', [])}\n"
        config_text += f"Intensity: {self.current_config.get('intensity', 0)}\n"
        config_text += f"Frequency: {self.current_config.get('frequency', 0)}\n"
        config_text += f"Duration: {self.current_config.get('duration', 0.0)}s\n"
        
        # Waveform info
        waveform_info = self.current_config.get('waveform', {})
        if waveform_info:
            config_text += f"Waveform: {waveform_info.get('name', 'N/A')} ({waveform_info.get('source', 'N/A')})\n"
        
        # Paramètres spécifiques
        specific_params = self.current_config.get('specific_parameters', {})
        if specific_params:
            config_text += "Specific Parameters:\n"
            for key, value in specific_params.items():
                config_text += f"  {key}: {value}\n"
        
        self.previewText.setPlainText(config_text)
    
    def _validate_input(self):
        """Valider l'entrée utilisateur"""
        name = self.nameEdit.text().strip()
        self.saveButton.setEnabled(len(name) > 0)
    
    def get_save_data(self):
        """Récupérer les données de sauvegarde"""
        return {
            'name': self.nameEdit.text().strip(),
            'description': self.descriptionEdit.toPlainText().strip(),
            'timestamp': datetime.now().isoformat(),
            'config': self.current_config
        }

class CompactActuatorSelector(QWidget):
    """Version compacte du sélecteur d'actuateurs pour l'intégration"""
    
    selection_changed = pyqtSignal(list)
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Titre simple
        title_label = QLabel("Select actuators (click to select, right-click to delete)")
        title_label.setStyleSheet("color: #666; font-size: 11px;")
        layout.addWidget(title_label)
        
        # Créer le sélecteur flexible
        self.selector = FlexibleActuatorSelector()
        self.selector.selection_changed.connect(self.selection_changed.emit)
        self.selector.setMinimumHeight(350)
        layout.addWidget(self.selector)
    
    def get_selected_actuators(self):
        return self.selector.get_selected_actuators()
    
    def load_actuator_configuration(self, actuators):
        """Charger une configuration d'actuateurs"""
        self.selector.select_none()
        for actuator in self.selector.canvas.actuators:
            if actuator.actuator_id in actuators:
                actuator.set_selected_state(True)
        self.selector.canvas.on_actuator_selection_changed()

class HapticPatternGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        
        # Initialize API and patterns
        self.api = python_serial_api()
        self.current_pattern = None
        self.pattern_worker = None
        self.is_running = False
        
        # Initialize library managers
        self.pattern_manager = PatternLibraryManager()
        self.event_manager = EventLibraryManager()
        
        # Current waveform tracking
        self.current_waveform_source = "Built-in Oscillators"
        self.current_waveform_name = "Sine"
        self.current_event = None
        
        # Available patterns
        self.patterns = {
            "Single Pulse": SinglePulsePattern(),
            "Wave": WavePattern(),
            "Pulse Train": PulseTrainPattern(),
            "Fade": FadePattern(),
            "Circular": CircularPattern(),
            "Random": RandomPattern(),
            "Sine Wave": SineWavePattern()
        }
        
        # Set API for all patterns
        for pattern in self.patterns.values():
            pattern.set_api(self.api)
        
        self._create_ui()
        self._connect_signals()
        self.scan_ports()
    
    def _create_ui(self):
        """Create the complete UI programmatically"""
        self.setWindowTitle("Haptic Vibration Pattern Controller")
        
        # Rendre la fenêtre redimensionnable et commencer plus petit
        self.setGeometry(100, 100, 1200, 900)
        self.setMinimumSize(1000, 700)  # Taille minimum
        
        # Create central widget and main layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)
        layout.setSpacing(10)  # Plus d'espace entre sections
        
        # Connection group
        self._create_connection_group(layout)
        
        # Main layout with two columns
        main_layout = QHBoxLayout()
        
        # Left column - Tabbed interface
        self._create_left_column(main_layout)
        
        # Right column - Actuator selection  
        self._create_right_column(main_layout)
        
        layout.addLayout(main_layout)
        
        # Info section - TOUJOURS visible
        self._create_info_section(layout)
        
        # Maximiser la fenêtre au démarrage pour garantir que tout soit visible
        self.showMaximized()
    
    def _create_connection_group(self, layout):
        """Create connection controls"""
        connectionGroup = QGroupBox("Connection")
        connectionLayout = QHBoxLayout(connectionGroup)
        
        self.scanPortsButton = QPushButton("Scan Ports")
        self.portComboBox = QComboBox()
        self.connectButton = QPushButton("Connect")
        self.disconnectButton = QPushButton("Disconnect")
        self.statusLabel = QLabel("Status: Disconnected")
        
        connectionLayout.addWidget(self.scanPortsButton)
        connectionLayout.addWidget(self.portComboBox)
        connectionLayout.addWidget(self.connectButton)
        connectionLayout.addWidget(self.disconnectButton)
        connectionLayout.addStretch()
        connectionLayout.addWidget(self.statusLabel)
        
        layout.addWidget(connectionGroup)
    
    def _create_left_column(self, main_layout):
        """Create left column with tabbed interface"""
        leftColumn = QWidget()
        leftColumn.setMaximumWidth(450)
        leftColumnLayout = QVBoxLayout(leftColumn)
        
        # Create tab widget for Waveform Lab and Pattern Library
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #ccc;
            }
            QTabBar::tab {
                padding: 8px 16px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                border: 1px solid #ccc;
                background-color: #f5f5f5;
            }
            QTabBar::tab:selected {
                background-color: white;
                border-bottom: 1px solid white;
                font-weight: bold;
            }
            QTabBar::tab:hover {
                background-color: #eeeeee;
            }
        """)
        
        # Create Waveform Lab tab
        waveform_tab = QWidget()
        waveform_tab_layout = QVBoxLayout(waveform_tab)
        self._create_waveform_lab_content(waveform_tab_layout)
        
        # Create Pattern Library tab
        pattern_library_tab = QWidget()
        pattern_library_tab_layout = QVBoxLayout(pattern_library_tab)
        self._create_pattern_library_content(pattern_library_tab_layout)
        
        # Add tabs
        self.tab_widget.addTab(waveform_tab, "Waveform Lab")
        self.tab_widget.addTab(pattern_library_tab, "Pattern Library")
        
        leftColumnLayout.addWidget(self.tab_widget)
        leftColumnLayout.addStretch()
        main_layout.addWidget(leftColumn)
    
    def _create_waveform_lab_content(self, layout):
        """Create Waveform Lab tab content - COMPACT"""
        # Waveform Selection section - plus compact
        self._create_waveform_selection_section(layout)
        
        # Pattern selection - plus compact
        self._create_pattern_selection_section(layout)
        
        # Basic parameters - plus compact
        self._create_basic_parameters_section(layout)
        
        # Specific parameters - plus compact
        self._create_specific_parameters_section(layout)
        
        # Save pattern - plus compact
        self._create_save_pattern_section(layout)
        
        # Control section - plus compact
        self._create_control_section(layout)
        
        # Pas de stretch pour maximiser l'espace visible
        layout.addStretch()
    
    def _create_pattern_library_content(self, layout):
        """Create Pattern Library tab content"""
        # Pattern library section
        self._create_pattern_library_section(layout)
        layout.addStretch()
    
    def _create_waveform_selection_section(self, layout):
        """Create Waveform Selection section - COMPACT"""
        waveformGroup = QGroupBox("Waveform Selection")
        waveformGroup.setMaximumHeight(140)  # Limite la hauteur
        waveformLayout = QVBoxLayout(waveformGroup)
        waveformLayout.setSpacing(5)  # Espacement réduit
        waveformLayout.setContentsMargins(8, 5, 8, 5)  # Marges réduites
        
        # Waveform source selection - une ligne compacte
        source_layout = QHBoxLayout()
        source_layout.setSpacing(5)
        source_layout.addWidget(QLabel("Source:"))
        
        self.waveformSourceComboBox = QComboBox()
        self.waveformSourceComboBox.addItems(["Built-in Oscillators", "Event Library"])
        source_layout.addWidget(self.waveformSourceComboBox)
        
        self.refreshWaveformsButton = QPushButton("Refresh")
        self.refreshWaveformsButton.setMaximumWidth(60)  # Plus petit
        source_layout.addWidget(self.refreshWaveformsButton)
        
        waveformLayout.addLayout(source_layout)
        
        # Waveform selection - une ligne compacte
        waveform_layout = QHBoxLayout()
        waveform_layout.setSpacing(5)
        waveform_layout.addWidget(QLabel("Waveform:"))
        
        self.waveformComboBox = QComboBox()
        waveform_layout.addWidget(self.waveformComboBox)
        
        waveformLayout.addLayout(waveform_layout)
        
        # Waveform info - plus compact
        self.waveformInfoLabel = QLabel("Standard sine wave oscillator")
        self.waveformInfoLabel.setWordWrap(True)
        self.waveformInfoLabel.setStyleSheet(
            "padding: 4px; border: 1px solid #ddd; border-radius: 3px; "
            "background-color: #f9f9f9; font-style: italic; font-size: 10px;"
        )
        self.waveformInfoLabel.setMaximumHeight(40)  # Plus petit
        waveformLayout.addWidget(self.waveformInfoLabel)
        
        layout.addWidget(waveformGroup)
    
    def _create_pattern_selection_section(self, layout):
        """Create pattern selection - COMPACT"""
        patternGroup = QGroupBox("Pattern Selection")
        patternGroup.setMaximumHeight(80)  # Plus compact
        patternLayout = QVBoxLayout(patternGroup)
        patternLayout.setSpacing(3)
        patternLayout.setContentsMargins(8, 5, 8, 5)
        
        self.patternComboBox = QComboBox()
        self.patternComboBox.addItems([
            "Single Pulse", "Wave", "Pulse Train", "Fade", 
            "Circular", "Random", "Sine Wave"
        ])
        patternLayout.addWidget(self.patternComboBox)
        
        self.patternDescLabel = QLabel("Single vibration pulse on selected actuators")
        self.patternDescLabel.setWordWrap(True)
        self.patternDescLabel.setStyleSheet("font-style: italic; padding: 2px; color: #666; font-size: 10px;")
        self.patternDescLabel.setMaximumHeight(25)  # Plus petit
        patternLayout.addWidget(self.patternDescLabel)
        
        layout.addWidget(patternGroup)
    
    def _create_basic_parameters_section(self, layout):
        """Create basic parameters - COMPACT"""
        basicParamsGroup = QGroupBox("Basic Parameters")
        basicParamsGroup.setMaximumHeight(100)  # Plus compact
        basicParamsLayout = QGridLayout(basicParamsGroup)
        basicParamsLayout.setSpacing(3)
        basicParamsLayout.setContentsMargins(8, 5, 8, 5)
        
        # Intensity - ligne compacte
        basicParamsLayout.addWidget(QLabel("Intensity:"), 0, 0)
        self.intensitySlider = QSlider(Qt.Orientation.Horizontal)
        self.intensitySlider.setRange(0, 15)
        self.intensitySlider.setValue(7)
        basicParamsLayout.addWidget(self.intensitySlider, 0, 1)
        self.intensityValueLabel = QLabel("7")
        self.intensityValueLabel.setMinimumWidth(20)
        basicParamsLayout.addWidget(self.intensityValueLabel, 0, 2)
        
        # Frequency - ligne compacte
        basicParamsLayout.addWidget(QLabel("Frequency:"), 1, 0)
        self.frequencySlider = QSlider(Qt.Orientation.Horizontal)
        self.frequencySlider.setRange(0, 7)
        self.frequencySlider.setValue(2)
        basicParamsLayout.addWidget(self.frequencySlider, 1, 1)
        self.frequencyValueLabel = QLabel("2")
        self.frequencyValueLabel.setMinimumWidth(20)
        basicParamsLayout.addWidget(self.frequencyValueLabel, 1, 2)
        
        # Duration - ligne compacte
        basicParamsLayout.addWidget(QLabel("Duration:"), 2, 0)
        self.durationSpinBox = QDoubleSpinBox()
        self.durationSpinBox.setRange(0.1, 60.0)
        self.durationSpinBox.setValue(2.0)
        self.durationSpinBox.setDecimals(1)
        self.durationSpinBox.setSuffix(" s")
        basicParamsLayout.addWidget(self.durationSpinBox, 2, 1, 1, 2)
        
        layout.addWidget(basicParamsGroup)
    
    def _create_specific_parameters_section(self, layout):
        """Create pattern-specific parameters section - COMPACT"""
        self.specificParamsGroup = QGroupBox("Pattern-Specific Parameters")
        self.specificParamsGroup.setMaximumHeight(60)  # Plus compact
        self.specificParamsGroup.setMinimumHeight(50)
        
        # Initialize with empty layout
        self.pattern_specific_widgets = {}
        self._create_pattern_specific_params()
        
        layout.addWidget(self.specificParamsGroup)
    
    def _create_save_pattern_section(self, layout):
        """Create save pattern section - COMPACT"""
        saveGroup = QGroupBox("Save Pattern")
        saveGroup.setMaximumHeight(60)  # Plus compact
        saveLayout = QVBoxLayout(saveGroup)
        saveLayout.setContentsMargins(8, 5, 8, 5)
        
        self.saveButton = QPushButton("Save Current Pattern")
        saveLayout.addWidget(self.saveButton)
        
        layout.addWidget(saveGroup)
    
    def _create_control_section(self, layout):
        """Create control section - COMPACT"""
        controlGroup = QGroupBox("Control")
        controlGroup.setMaximumHeight(90)  # Plus compact
        controlLayout = QVBoxLayout(controlGroup)
        controlLayout.setSpacing(5)
        controlLayout.setContentsMargins(8, 5, 8, 5)
        
        # Start/Stop buttons - ligne compacte
        buttonLayout = QHBoxLayout()
        buttonLayout.setSpacing(5)
        
        self.startButton = QPushButton("Start")
        self.stopButton = QPushButton("Stop")
        
        buttonLayout.addWidget(self.startButton)
        buttonLayout.addWidget(self.stopButton)
        controlLayout.addLayout(buttonLayout)
        
        # Emergency stop - compact
        self.emergencyStopButton = QPushButton("Emergency Stop")
        self.emergencyStopButton.setStyleSheet("QPushButton { font-weight: bold; }")
        controlLayout.addWidget(self.emergencyStopButton)
        
        layout.addWidget(controlGroup)
    
    def _create_pattern_library_section(self, layout):
        """Create pattern library section"""
        # No group box here since it's already in a tab
        self.pattern_visualization = PatternVisualizationWidget(self.pattern_manager)
        self.pattern_visualization.pattern_selected.connect(self.load_pattern_from_library)
        self.pattern_visualization.pattern_deleted.connect(self.on_pattern_deleted)
        layout.addWidget(self.pattern_visualization)
    
    def _create_right_column(self, main_layout):
        """Create right column with actuator selection"""
        rightColumn = QWidget()
        rightColumnLayout = QVBoxLayout(rightColumn)
        
        actuatorGroup = QGroupBox("Actuator Selection & Design")
        actuatorLayout = QVBoxLayout(actuatorGroup)
        
        self.actuator_selector = CompactActuatorSelector()
        self.actuator_selector.selection_changed.connect(self.on_actuator_selection_changed)
        actuatorLayout.addWidget(self.actuator_selector)
        
        rightColumnLayout.addWidget(actuatorGroup)
        main_layout.addWidget(rightColumn)
    
    def _create_info_section(self, layout):
        """Create info section - ALWAYS VISIBLE but compact"""
        infoGroup = QGroupBox("Information")
        # Taille beaucoup plus petite mais toujours visible
        infoGroup.setFixedHeight(80)  # Réduit de 200px à 80px
        infoLayout = QVBoxLayout(infoGroup)
        infoLayout.setContentsMargins(5, 5, 5, 5)  # Marges réduites
        
        self.infoTextEdit = QTextEdit()
        self.infoTextEdit.setReadOnly(True)
        self.infoTextEdit.setStyleSheet(
            "QTextEdit { "
            "font-family: 'Consolas', 'Monaco', monospace; "
            "font-size: 10px; "  # Police plus petite
            "padding: 5px; "     # Padding réduit
            "border: 1px solid #999; "  # Bordure plus fine
            "background-color: #f8f8f8; "
            "line-height: 1.2; "  # Espacement réduit
            "}"
        )
        infoLayout.addWidget(self.infoTextEdit)
        
        layout.addWidget(infoGroup)
    
    def _connect_signals(self):
        """Connect signals to slots"""
        # Connection buttons
        self.scanPortsButton.clicked.connect(self.scan_ports)
        self.connectButton.clicked.connect(self.connect)
        self.disconnectButton.clicked.connect(self.disconnect)
        
        # Waveform controls
        self.waveformSourceComboBox.currentTextChanged.connect(self.on_waveform_source_changed)
        self.waveformComboBox.currentTextChanged.connect(self.on_waveform_changed)
        self.refreshWaveformsButton.clicked.connect(self.refresh_waveforms)
        
        # Pattern controls
        self.patternComboBox.currentTextChanged.connect(self._on_pattern_change)
        
        # Basic parameter sliders
        self.intensitySlider.valueChanged.connect(
            lambda v: self.intensityValueLabel.setText(str(v))
        )
        self.frequencySlider.valueChanged.connect(
            lambda v: self.frequencyValueLabel.setText(str(v))
        )
        
        # Control buttons
        self.startButton.clicked.connect(self.start_pattern)
        self.stopButton.clicked.connect(self.stop_pattern)
        self.emergencyStopButton.clicked.connect(self.emergency_stop)
        self.saveButton.clicked.connect(self.save_pattern)
        
        # Initialize waveform controls
        self.refresh_waveforms()
        self.update_waveform_info()
    
    def refresh_waveforms(self):
        """Refresh available waveforms based on selected source"""
        self.waveformComboBox.clear()
        source = self.waveformSourceComboBox.currentText()
        
        if source == "Built-in Oscillators":
            oscillators = ["Sine", "Square", "Saw", "Triangle", "Chirp", "FM", "PWM", "Noise"]
            self.waveformComboBox.addItems(oscillators)
        
        elif source == "Event Library":
            events = self.event_manager.get_all_events()
            if events:
                self.waveformComboBox.addItems(sorted(events.keys()))
            else:
                self.waveformComboBox.addItem("No events found")
        
        # Update waveform info for first item
        if self.waveformComboBox.count() > 0:
            self.update_waveform_info()
    
    def on_waveform_source_changed(self):
        """Handle waveform source change"""
        self.current_waveform_source = self.waveformSourceComboBox.currentText()
        self.refresh_waveforms()
        self._log_info(f"Waveform source changed to: {self.current_waveform_source}")
    
    def on_waveform_changed(self):
        """Handle waveform selection change"""
        self.current_waveform_name = self.waveformComboBox.currentText()
        self.update_waveform_info()
        self._log_info(f"Waveform changed to: {self.current_waveform_name}")
    
    def update_waveform_info(self):
        """Update waveform information display"""
        source = self.current_waveform_source
        name = self.current_waveform_name
        
        if source == "Built-in Oscillators":
            descriptions = {
                "Sine": "Standard sine wave oscillator - Smooth, continuous vibration",
                "Square": "Square wave with sharp edges - Sharp on/off vibration",
                "Saw": "Sawtooth wave with linear ramp - Gradual build-up vibration",
                "Triangle": "Triangle wave with smooth transitions - Gentle rise/fall vibration",
                "Chirp": "Frequency sweep from low to high - Dynamic frequency change",
                "FM": "Frequency modulated sine wave - Complex modulated vibration",
                "PWM": "Pulse width modulated square wave - Variable duty cycle pulses",
                "Noise": "Random noise signal - Unpredictable vibration pattern"
            }
            self.waveformInfoLabel.setText(descriptions.get(name, "Built-in oscillator"))
            self.current_event = None
        
        elif source == "Event Library":
            if name and name != "No events found":
                # Load event details
                event = self.event_manager.load_event(name)
                if event:
                    self.current_event = event
                    info_text = f"<b>{event.metadata.name}</b><br>"
                    info_text += f"Category: {event.metadata.category.value}<br>"
                    if event.metadata.description:
                        info_text += f"Description: {event.metadata.description}<br>"
                    if event.waveform_data:
                        info_text += f"Duration: {event.waveform_data.duration:.2f}s<br>"
                        info_text += f"Sample Rate: {event.waveform_data.sample_rate}Hz"
                    self.waveformInfoLabel.setText(info_text)
                else:
                    self.waveformInfoLabel.setText("Error loading waveform details")
                    self.current_event = None
            else:
                self.waveformInfoLabel.setText("No waveforms available in event library")
                self.current_event = None
    
    def get_current_waveform_info(self):
        """Get current waveform selection info"""
        return {
            'source': self.current_waveform_source,
            'name': self.current_waveform_name,
            'event': self.current_event
        }
    
    def _create_pattern_specific_params(self):
        """Create pattern-specific parameter widgets"""
        # Clear existing layout
        if self.specificParamsGroup.layout():
            self._clear_layout(self.specificParamsGroup.layout())
        
        layout = QHBoxLayout()
        self.specificParamsGroup.setLayout(layout)
        
        pattern_name = self.patternComboBox.currentText()
        self.pattern_specific_widgets = {}
        
        # Get pattern parameters from configuration
        pattern_config = PATTERN_PARAMETERS.get(pattern_name, {})
        parameters = pattern_config.get("parameters", [])
        
        if len(parameters) == 0:
            no_params_label = QLabel("No additional parameters")
            no_params_label.setStyleSheet("font-style: italic; padding: 20px; color: #666;")
            layout.addWidget(no_params_label)
            layout.addStretch()
        else:
            # Create vertical layout for multiple parameters
            params_widget = QWidget()
            params_layout = QFormLayout(params_widget)
            
            for param in parameters:
                label = QLabel(param["label"])
                label.setToolTip(param["description"])
                
                if param["type"] == "float":
                    widget = QDoubleSpinBox()
                    widget.setRange(*param["range"])
                    widget.setValue(param["default"])
                    widget.setSingleStep(param["step"])
                    if param["suffix"]:
                        widget.setSuffix(param["suffix"])
                elif param["type"] == "int":
                    widget = QSpinBox()
                    widget.setRange(*param["range"])
                    widget.setValue(param["default"])
                    widget.setSingleStep(param["step"])
                    if param["suffix"]:
                        widget.setSuffix(param["suffix"])
                
                widget.setToolTip(param["description"])
                params_layout.addRow(label, widget)
                self.pattern_specific_widgets[param["name"]] = widget
            
            layout.addWidget(params_widget)
            layout.addStretch()
        
        self.specificParamsGroup.update()
        self.update()
    
    def _clear_layout(self, layout):
        """Clear all widgets from layout"""
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                widget = item.widget()
                widget.setParent(None)
                widget.deleteLater()
            elif item.layout():
                self._clear_layout(item.layout())
    
    def _on_pattern_change(self):
        """Handle pattern selection change"""
        pattern_name = self.patternComboBox.currentText()
        if pattern_name in self.patterns:
            self.patternDescLabel.setText(self.patterns[pattern_name].description)
        self._create_pattern_specific_params()
    
    def scan_ports(self):
        """Scan for available serial ports"""
        try:
            ports = self.api.get_serial_devices()
            self.portComboBox.clear()
            self.portComboBox.addItems(ports)
            self._log_info(f"Found {len(ports)} ports" if ports else "No ports found")
        except Exception as e:
            self._log_info(f"Error scanning ports: {e}")
    
    def connect(self):
        """Connect to selected serial port"""
        port = self.portComboBox.currentText()
        if not port:
            QMessageBox.warning(self, "Error", "Please select a port")
            return
        
        try:
            success = self.api.connect_serial_device(port)
            status = "Connected" if success else "Connection Failed"
            self.statusLabel.setText(f"Status: {status}")
            self._log_info(f"{'Connected to' if success else 'Failed to connect to'} {port}")
        except Exception as e:
            self.statusLabel.setText("Status: Connection Error")
            self._log_info(f"Connection error: {e}")
    
    def disconnect(self):
        """Disconnect from serial port"""
        try:
            if self.api.disconnect_serial_device():
                self.statusLabel.setText("Status: Disconnected")
                self._log_info("Disconnected")
        except Exception as e:
            self._log_info(f"Disconnect error: {e}")
    
    def save_pattern(self):
        """Sauvegarder la configuration actuelle dans la pattern library"""
        actuators = self._get_selected_actuators()
        if not actuators:
            QMessageBox.warning(self, "Warning", "Please select at least one actuator before saving.")
            return
        
        # Get current waveform selection
        waveform_info = self.get_current_waveform_info()
        
        # Préparer la configuration actuelle
        current_config = {
            'pattern_type': self.patternComboBox.currentText(),
            'actuators': actuators,
            'intensity': self.intensitySlider.value(),
            'frequency': self.frequencySlider.value(),
            'duration': self.durationSpinBox.value(),
            'waveform': {
                'source': waveform_info['source'],
                'name': waveform_info['name']
            },
            'specific_parameters': {}
        }
        
        # Ajouter les paramètres spécifiques
        for param_name, widget in self.pattern_specific_widgets.items():
            current_config['specific_parameters'][param_name] = widget.value()
        
        # Ouvrir le dialogue de sauvegarde
        dialog = SavePatternDialog(current_config, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            save_data = dialog.get_save_data()
            pattern_name = save_data['name']
            
            # Vérifier si le pattern existe déjà dans la bibliothèque
            existing_patterns = self.pattern_manager.get_all_patterns()
            if pattern_name in existing_patterns:
                reply = QMessageBox.question(
                    self, 
                    "Overwrite Pattern", 
                    f"Pattern '{pattern_name}' already exists in the library. Overwrite?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
                )
                if reply != QMessageBox.StandardButton.Yes:
                    return
            
            # Sauvegarder dans la pattern library
            if self.pattern_manager.save_pattern(pattern_name, save_data):
                self.pattern_visualization.refresh_patterns()
                self._log_info(f"Pattern '{pattern_name}' saved to pattern library")
                QMessageBox.information(self, "Success", f"Pattern '{pattern_name}' saved to pattern library!")
            else:
                QMessageBox.critical(self, "Error", "Failed to save pattern to library.")
    
    def load_pattern_from_library(self, pattern_info):
        """Charger un pattern depuis la bibliothèque"""
        try:
            config = pattern_info['config']
            
            # Switch to Waveform Lab tab to show loaded configuration
            self.tab_widget.setCurrentIndex(0)
            
            # Charger la configuration de base
            self.patternComboBox.setCurrentText(config['pattern_type'])
            self.intensitySlider.setValue(config['intensity'])
            self.frequencySlider.setValue(config['frequency'])
            self.durationSpinBox.setValue(config['duration'])
            
            # Charger la configuration de waveform
            waveform_info = config.get('waveform', {})
            if waveform_info:
                source = waveform_info.get('source', 'Built-in Oscillators')
                name = waveform_info.get('name', 'Sine')
                
                # Set waveform selection
                self.waveformSourceComboBox.setCurrentText(source)
                self.refresh_waveforms()
                self.waveformComboBox.setCurrentText(name)
            
            # Charger les paramètres spécifiques
            specific_params = config.get('specific_parameters', {})
            for param_name, value in specific_params.items():
                if param_name in self.pattern_specific_widgets:
                    self.pattern_specific_widgets[param_name].setValue(value)
            
            # Charger les actuateurs sélectionnés
            self.actuator_selector.load_actuator_configuration(config['actuators'])
            
            self._log_info(f"Pattern '{pattern_info['name']}' loaded from library")
            QMessageBox.information(self, "Success", f"Pattern '{pattern_info['name']}' loaded successfully!")
            
        except Exception as e:
            self._log_info(f"Error loading pattern: {e}")
            QMessageBox.critical(self, "Error", f"Failed to load pattern: {e}")
    
    def on_pattern_deleted(self, pattern_name):
        """Appelé quand un pattern est supprimé de la bibliothèque"""
        self._log_info(f"Pattern '{pattern_name}' deleted from library")
    
    def on_actuator_selection_changed(self, selected_ids):
        """Appelé quand la sélection d'actuateurs change"""
        if selected_ids:
            self._log_info(f"Selected actuators: {selected_ids}")
        else:
            self._log_info("No actuators selected")
    
    def _get_selected_actuators(self):
        """Obtenir la liste des actuateurs sélectionnés"""
        return self.actuator_selector.get_selected_actuators()
    
    def start_pattern(self):
        """Start the selected pattern"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Pattern is already running")
            return
        
        if not self.api.connected:
            QMessageBox.warning(self, "Error", "Please connect to a device first")
            return
        
        actuators = self._get_selected_actuators()
        if not actuators:
            QMessageBox.warning(self, "Error", "Please select at least one actuator")
            return
        
        pattern_name = self.patternComboBox.currentText()
        if pattern_name not in self.patterns:
            QMessageBox.warning(self, "Error", "Invalid pattern selected")
            return
        
        # Get waveform information
        waveform_info = self.get_current_waveform_info()
        
        # Apply waveform-specific modifications to basic parameters
        base_intensity = self.intensitySlider.value()
        base_frequency = self.frequencySlider.value()
        
        # Modify parameters based on waveform type
        if waveform_info['source'] == 'Built-in Oscillators':
            intensity, frequency = self._apply_builtin_waveform_modulation(
                waveform_info['name'], base_intensity, base_frequency
            )
        else:
            intensity, frequency = base_intensity, base_frequency
        
        # Prepare basic parameters
        params = {
            'actuators': actuators,
            'intensity': intensity,
            'frequency': frequency,
            'duration': self.durationSpinBox.value()
        }
        
        # Add pattern-specific parameters
        for param_name, widget in self.pattern_specific_widgets.items():
            params[param_name] = widget.value()
        
        # Start pattern
        self.current_pattern = self.patterns[pattern_name]
        
        # Set waveform data if using event library
        if waveform_info['source'] == 'Event Library' and waveform_info['event']:
            if hasattr(self.current_pattern, 'set_waveform_data'):
                self.current_pattern.set_waveform_data(waveform_info['event'])
            self.current_pattern.waveform_info = waveform_info
        else:
            self.current_pattern.waveform_info = waveform_info
        
        self.current_pattern.stop_flag = False
        self.is_running = True
        
        self.pattern_worker = PatternWorker(self.current_pattern, params)
        self.pattern_worker.finished.connect(self._on_pattern_finished)
        self.pattern_worker.log_message.connect(self._log_info)
        self.pattern_worker.start()
        
        waveform_desc = f" with {waveform_info['name']} waveform" if waveform_info['name'] else ""
        self._log_info(f"Started {pattern_name} pattern{waveform_desc} on actuators {actuators} (I:{intensity}, F:{frequency})")
    
    def _apply_builtin_waveform_modulation(self, waveform_name, base_intensity, base_frequency):
        """Apply waveform-specific modifications to basic parameters"""
        
        # Different waveforms can modify intensity and frequency differently
        waveform_modifications = {
            "Sine": (base_intensity, base_frequency),
            "Square": (min(15, base_intensity + 2), base_frequency),
            "Saw": (base_intensity, min(7, base_frequency + 1)),
            "Triangle": (max(1, base_intensity - 1), base_frequency),
            "Chirp": (base_intensity, min(7, base_frequency + 2)),
            "FM": (base_intensity, max(0, base_frequency - 1)),
            "PWM": (min(15, base_intensity + 1), base_frequency),
            "Noise": (max(1, min(15, base_intensity + random.randint(-2, 2))), 
                     max(0, min(7, base_frequency + random.randint(-1, 1))))
        }
        
        intensity, frequency = waveform_modifications.get(waveform_name, (base_intensity, base_frequency))
        
        self._log_info(f"Waveform '{waveform_name}' modified parameters: {base_intensity}->{intensity}, {base_frequency}->{frequency}")
        
        return intensity, frequency
    
    def stop_pattern(self):
        """Stop the current pattern"""
        if self.current_pattern:
            self.current_pattern.stop()
            self._log_info("Pattern stop requested")
        
        if self.pattern_worker and self.pattern_worker.isRunning():
            self.pattern_worker.wait(1000)
        
        self._force_stop_selected_actuators()
        self.is_running = False
        self._log_info("Pattern stopped")
    
    def _force_stop_selected_actuators(self):
        """Force stop all selected actuators"""
        try:
            actuators = self._get_selected_actuators()
            if actuators:
                for addr in actuators:
                    self.api.send_command(addr, 0, 0, 0)
                self._log_info(f"Force stopped actuators: {actuators}")
        except Exception as e:
            self._log_info(f"Error force stopping actuators: {e}")
    
    def emergency_stop(self):
        """Emergency stop - stops pattern and all actuators"""
        self.stop_pattern()
        try:
            for i in range(128):
                self.api.send_command(i, 0, 0, 0)
            self._log_info("Emergency stop executed - all actuators (0-127) stopped")
        except Exception as e:
            self._log_info(f"Emergency stop error: {e}")
    
    def _on_pattern_finished(self, success, message):
        """Handle pattern completion"""
        self._force_stop_selected_actuators()
        self.is_running = False
        self._log_info("Pattern completed")
    
    def closeEvent(self, event):
        """Handle window closing"""
        self.emergency_stop()
        if self.api.connected:
            self.api.disconnect_serial_device()
        event.accept()
    
    def _log_info(self, message):
        """Log information to the text widget"""
        timestamp = time.strftime('%H:%M:%S')
        log_message = f"{timestamp} - {message}"
        
        self.infoTextEdit.append(log_message)
        print(log_message)

def main():
    app = QApplication(sys.argv)
    window = HapticPatternGUI()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()