#!/usr/bin/env python3
"""
Interface Tactile Simplifiée - Dessin et Sauvegarde
L'utilisateur dessine ce qu'il ressent sur le layout physique et peut sauvegarder ses dessins.
"""
import sys
import json
import os
from datetime import datetime
from typing import List, Tuple, Optional
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QApplication, QMainWindow, QFileDialog, QMessageBox,
    QLineEdit, QTextEdit, QGroupBox
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QPainter, QPen, QBrush, QColor, QFont, QMouseEvent

# CONFIGURATION PHYSIQUE EXACTE DU BOSS
CM_TO_PIXELS = 20
HORIZONTAL_SPACING_CM = 5.0  # 5cm entre actuateurs horizontalement
VERTICAL_SPACING_CM = 6.0    # 6cm entre rangées verticalement
HORIZONTAL_SPACING_PX = int(HORIZONTAL_SPACING_CM * CM_TO_PIXELS)  # 100px
VERTICAL_SPACING_PX = int(VERTICAL_SPACING_CM * CM_TO_PIXELS)      # 120px

# Layout physique exact du boss (disposition 2-4-4-4-2)
BOSS_PHYSICAL_LAYOUT = {
    # Rangée 0: 2 actuateurs
    0: (1 * HORIZONTAL_SPACING_PX, 0 * VERTICAL_SPACING_PX),
    1: (2 * HORIZONTAL_SPACING_PX, 0 * VERTICAL_SPACING_PX),
    
    # Rangée 1: 4 actuateurs
    5: (0 * HORIZONTAL_SPACING_PX, 1 * VERTICAL_SPACING_PX),
    4: (1 * HORIZONTAL_SPACING_PX, 1 * VERTICAL_SPACING_PX), 
    3: (2 * HORIZONTAL_SPACING_PX, 1 * VERTICAL_SPACING_PX),
    2: (3 * HORIZONTAL_SPACING_PX, 1 * VERTICAL_SPACING_PX),
    
    # Rangée 2: 4 actuateurs
    6: (0 * HORIZONTAL_SPACING_PX, 2 * VERTICAL_SPACING_PX),
    7: (1 * HORIZONTAL_SPACING_PX, 2 * VERTICAL_SPACING_PX),
    8: (2 * HORIZONTAL_SPACING_PX, 2 * VERTICAL_SPACING_PX), 
    9: (3 * HORIZONTAL_SPACING_PX, 2 * VERTICAL_SPACING_PX),
    
    # Rangée 3: 4 actuateurs
    13: (0 * HORIZONTAL_SPACING_PX, 3 * VERTICAL_SPACING_PX),
    12: (1 * HORIZONTAL_SPACING_PX, 3 * VERTICAL_SPACING_PX),
    11: (2 * HORIZONTAL_SPACING_PX, 3 * VERTICAL_SPACING_PX),
    10: (3 * HORIZONTAL_SPACING_PX, 3 * VERTICAL_SPACING_PX),
    
    # Rangée 4: 2 actuateurs
    14: (1 * HORIZONTAL_SPACING_PX, 4 * VERTICAL_SPACING_PX),
    15: (2 * HORIZONTAL_SPACING_PX, 4 * VERTICAL_SPACING_PX)
}

ACTUATORS = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15]

class Drawing:
    """Classe pour représenter un dessin"""
    def __init__(self, name: str = ""):
        self.name = name or f"Dessin_{datetime.now().strftime('%H%M%S')}"
        self.points = []  # Liste de points (x, y)
        self.description = ""
        self.timestamp = datetime.now().isoformat()
    
    def add_point(self, x: float, y: float):
        """Ajouter un point au dessin"""
        self.points.append((x, y))
    
    def to_dict(self):
        """Convertir en dictionnaire pour sauvegarde JSON"""
        return {
            'name': self.name,
            'points': self.points,
            'description': self.description,
            'timestamp': self.timestamp
        }
    
    @classmethod
    def from_dict(cls, data):
        """Créer un dessin depuis un dictionnaire"""
        drawing = cls(data['name'])
        drawing.points = data['points']
        drawing.description = data.get('description', '')
        drawing.timestamp = data.get('timestamp', datetime.now().isoformat())
        return drawing

class TactileCanvas(QWidget):
    """Canvas pour dessiner sur le layout physique"""
    
    drawing_changed = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self.setMinimumSize(600, 500)
        self.setMouseTracking(True)
        
        self.current_drawing = Drawing()
        self.saved_drawings = []  # Liste des dessins sauvegardés
        self.display_mode = "none"  # "none", "all", "selected"
        self.selected_drawing_index = -1  # Index du dessin sélectionné
        
        # État du dessin
        self.is_drawing = False
        self.drawing_enabled = True
        
        # Calcul de l'échelle et offset
        self.margin = 50
        self.scale = 1.0
        self.offset_x = 0.0
        self.offset_y = 0.0
        
        print("🎨 Canvas tactile initialisé")
    
    def mousePressEvent(self, event: QMouseEvent):
        if not self.drawing_enabled or event.button() != Qt.MouseButton.LeftButton:
            return
        
        physical_pos = self.screen_to_physical(event.position())
        if physical_pos:
            self.is_drawing = True
            self.current_drawing = Drawing()  # Nouveau dessin
            self.current_drawing.add_point(physical_pos[0], physical_pos[1])
            self.update()
    
    def mouseMoveEvent(self, event: QMouseEvent):
        if not self.is_drawing or not self.drawing_enabled:
            return
        
        physical_pos = self.screen_to_physical(event.position())
        if physical_pos:
            # Ajouter le point seulement s'il est assez loin du précédent
            if (not self.current_drawing.points or 
                self.distance_between_points(physical_pos, self.current_drawing.points[-1]) > 5):
                self.current_drawing.add_point(physical_pos[0], physical_pos[1])
                self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        if self.is_drawing and event.button() == Qt.MouseButton.LeftButton:
            self.is_drawing = False
            if len(self.current_drawing.points) >= 2:
                self.drawing_changed.emit()
    
    def screen_to_physical(self, screen_pos) -> Optional[Tuple[float, float]]:
        """Convertir position écran vers coordonnées physiques"""
        x = (screen_pos.x() - self.offset_x) / self.scale
        y = (screen_pos.y() - self.offset_y) / self.scale
        
        layout_width = 3 * HORIZONTAL_SPACING_PX
        layout_height = 4 * VERTICAL_SPACING_PX
        
        if 0 <= x <= layout_width and 0 <= y <= layout_height:
            return (x, y)
        return None
    
    def physical_to_screen(self, physical_pos: Tuple[float, float]) -> Tuple[float, float]:
        """Convertir coordonnées physiques vers position écran"""
        return (physical_pos[0] * self.scale + self.offset_x,
                physical_pos[1] * self.scale + self.offset_y)
    
    def distance_between_points(self, p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
        return ((p1[0] - p2[0])**2 + (p1[1] - p2[1])**2)**0.5
    
    def clear_current_drawing(self):
        """Effacer le dessin actuel"""
        self.current_drawing = Drawing()
        self.update()
    
    def save_current_drawing(self, name: str, description: str = ""):
        """Sauvegarder le dessin actuel"""
        if len(self.current_drawing.points) < 2:
            return False
        
        self.current_drawing.name = name or f"Dessin_{len(self.saved_drawings)+1}"
        self.current_drawing.description = description
        self.saved_drawings.append(self.current_drawing)
        self.current_drawing = Drawing()  # Nouveau dessin vide
        self.update()
        return True
    
    def set_display_mode(self, mode: str, selected_index: int = -1):
        """Définir le mode d'affichage des dessins"""
        self.display_mode = mode  # "none", "all", "selected"
        self.selected_drawing_index = selected_index
        self.update()
    
    def toggle_saved_drawings(self):
        """Basculer l'affichage des dessins sauvegardés (compatibilité)"""
        if self.display_mode == "none":
            self.display_mode = "all"
        else:
            self.display_mode = "none"
        self.update()
    
    def clear_all_saved_drawings(self):
        """Effacer tous les dessins sauvegardés"""
        self.saved_drawings = []
        self.update()
    
    def export_drawings(self, filename: str):
        """Exporter les dessins vers un fichier JSON"""
        try:
            data = {
                'format_version': '1.0',
                'physical_layout': {
                    'horizontal_spacing_cm': HORIZONTAL_SPACING_CM,
                    'vertical_spacing_cm': VERTICAL_SPACING_CM,
                    'layout_type': '2-4-4-4-2'
                },
                'drawings': [drawing.to_dict() for drawing in self.saved_drawings]
            }
            
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Erreur export: {e}")
            return False
    
    def import_drawings(self, filename: str):
        """Importer les dessins depuis un fichier JSON"""
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Vérifier la compatibilité du format
            if 'drawings' in data:
                imported_drawings = []
                for drawing_data in data['drawings']:
                    drawing = Drawing.from_dict(drawing_data)
                    imported_drawings.append(drawing)
                
                self.saved_drawings.extend(imported_drawings)
                self.update()
                return len(imported_drawings)
        except Exception as e:
            print(f"Erreur import: {e}")
            return 0
    
    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fond
        painter.fillRect(self.rect(), QColor(40, 40, 40))
        
        # Calcul de l'échelle et des offsets
        info_width = 200
        available_width = self.width() - 2 * self.margin - info_width - 20
        available_height = self.height() - 2 * self.margin - 80
        
        layout_width = 3 * HORIZONTAL_SPACING_PX
        layout_height = 4 * VERTICAL_SPACING_PX
        
        self.scale = min(available_width / layout_width, available_height / layout_height) * 0.9
        self.offset_x = self.margin + (available_width - layout_width * self.scale) / 2
        self.offset_y = self.margin + 40 + (available_height - layout_height * self.scale) / 2
        
        # Titre
        painter.setPen(QPen(QColor(255, 255, 255)))
        font = QFont()
        font.setBold(True)
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(self.margin, 25, "🎨 Interface Tactile - Dessin sur Layout Physique")
        
        # Grille du layout physique
        painter.setPen(QPen(QColor(80, 80, 80), 1, Qt.PenStyle.DashLine))
        
        # Lignes verticales
        for col in range(5):
            x = self.offset_x + col * HORIZONTAL_SPACING_PX * self.scale
            painter.drawLine(int(x), int(self.offset_y), 
                           int(x), int(self.offset_y + layout_height * self.scale))
        
        # Lignes horizontales
        for row in range(6):
            y = self.offset_y + row * VERTICAL_SPACING_PX * self.scale
            painter.drawLine(int(self.offset_x), int(y), 
                           int(self.offset_x + layout_width * self.scale), int(y))
        
        # Dessiner les actuateurs
        for actuator_id in ACTUATORS:
            pos = BOSS_PHYSICAL_LAYOUT[actuator_id]
            screen_x, screen_y = self.physical_to_screen(pos)
            
            # Actuateur
            painter.setPen(QPen(QColor(150, 150, 150), 2))
            painter.setBrush(QBrush(QColor(100, 100, 100)))
            radius = 15 * self.scale
            painter.drawEllipse(int(screen_x - radius), int(screen_y - radius), 
                              int(radius * 2), int(radius * 2))
            
            # ID de l'actuateur
            painter.setPen(QPen(QColor(255, 255, 255)))
            font.setPointSize(int(9 * self.scale))
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(int(screen_x - 8), int(screen_y + 3), str(actuator_id))
        
        # Dessiner les dessins selon le mode d'affichage
        colors = [
            QColor(100, 150, 255),  # Bleu
            QColor(255, 150, 100),  # Orange
            QColor(100, 255, 150),  # Vert
            QColor(255, 100, 150),  # Rose
            QColor(150, 100, 255),  # Violet
            QColor(255, 255, 100),  # Jaune
            QColor(100, 255, 255),  # Cyan
            QColor(255, 150, 255),  # Magenta
        ]
        
        if self.display_mode == "all":
            # Afficher tous les dessins sauvegardés
            for i, drawing in enumerate(self.saved_drawings):
                if len(drawing.points) > 1:
                    color = colors[i % len(colors)]
                    self._draw_saved_drawing(painter, drawing, color, i)
        
        elif self.display_mode == "selected" and 0 <= self.selected_drawing_index < len(self.saved_drawings):
            # Afficher seulement le dessin sélectionné
            drawing = self.saved_drawings[self.selected_drawing_index]
            if len(drawing.points) > 1:
                color = colors[self.selected_drawing_index % len(colors)]
                self._draw_saved_drawing(painter, drawing, color, self.selected_drawing_index, highlight=True)
        
        # Dessiner le dessin en cours
        if len(self.current_drawing.points) > 1:
            painter.setPen(QPen(QColor(255, 255, 0), 3))  # Jaune vif pour le dessin actuel
            
            screen_points = [self.physical_to_screen(point) for point in self.current_drawing.points]
            for i in range(len(screen_points) - 1):
                painter.drawLine(
                    int(screen_points[i][0]), int(screen_points[i][1]),
                    int(screen_points[i+1][0]), int(screen_points[i+1][1])
                )
            
            # Marqueur de début du dessin actuel
            if screen_points:
                painter.setBrush(QBrush(QColor(0, 255, 0)))
                start_point = screen_points[0]
                painter.drawEllipse(int(start_point[0] - 6), int(start_point[1] - 6), 12, 12)
        
        # Panneau d'information
        info_x = self.width() - info_width - self.margin
        info_y = self.margin + 40
        
        painter.setPen(QPen(QColor(200, 200, 200)))
        painter.setBrush(QBrush(QColor(0, 0, 0, 100)))
        painter.drawRoundedRect(info_x - 10, info_y - 10, info_width + 20, 200, 5, 5)
        
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(info_x, info_y + 10, "📊 Informations")
        
        font.setBold(False)
        font.setPointSize(9)
        painter.setFont(font)
        
        info_lines = [
            f"Layout: 2-4-4-4-2",
            f"Dimensions: {HORIZONTAL_SPACING_CM}×{VERTICAL_SPACING_CM}cm",
            "",
            f"Dessins sauvés: {len(self.saved_drawings)}",
            f"Points actuels: {len(self.current_drawing.points)}",
            "",
            "🎨 Dessinez avec la souris",
            "💾 Sauvegardez vos créations",
            "📁 Exportez en JSON"
        ]
        
        for i, line in enumerate(info_lines):
            painter.drawText(info_x, info_y + 35 + i * 15, line)
        
        # Légende adaptée selon le mode d'affichage
        legend_y = self.height() - 50
        painter.setPen(QPen(QColor(200, 200, 200)))
        font.setPointSize(8)
        painter.setFont(font)
        
        legend_text = "🟡 Dessin actuel  ⚫ Actuateurs"
        if self.display_mode == "all":
            legend_text += "  🔵 Tous les dessins sauvegardés"
        elif self.display_mode == "selected":
            legend_text += "  🎯 Dessin sélectionné"
        
        painter.drawText(self.margin, legend_y, legend_text)
    
    def _draw_saved_drawing(self, painter, drawing, color, index, highlight=False):
        """Dessiner un dessin sauvegardé"""
        line_width = 3 if highlight else 2
        painter.setPen(QPen(color, line_width))
        
        # Dessiner les lignes
        screen_points = [self.physical_to_screen(point) for point in drawing.points]
        for j in range(len(screen_points) - 1):
            painter.drawLine(
                int(screen_points[j][0]), int(screen_points[j][1]),
                int(screen_points[j+1][0]), int(screen_points[j+1][1])
            )
        
        # Marqueur de début
        if screen_points:
            painter.setBrush(QBrush(color))
            start_point = screen_points[0]
            radius = 6 if highlight else 4
            painter.drawEllipse(int(start_point[0] - radius), int(start_point[1] - radius), 
                              radius * 2, radius * 2)
            
            # Nom du dessin si en mode sélectionné
            if highlight:
                painter.setPen(QPen(QColor(255, 255, 255)))
                font = QFont()
                font.setPointSize(10)
                font.setBold(True)
                painter.setFont(font)
                painter.drawText(int(start_point[0] + 10), int(start_point[1] - 10), 
                               f"{drawing.name}")

class SimplifiedTactileInterface(QWidget):
    """Interface principale simplifiée"""
    
    def __init__(self):
        super().__init__()
        self.setup_ui()
    
    def setup_ui(self):
        layout = QHBoxLayout(self)
        
        # Panneau de contrôle gauche
        control_panel = QWidget()
        control_panel.setMaximumWidth(250)
        control_layout = QVBoxLayout(control_panel)
        
        # Titre
        title = QLabel("🎨 Contrôles")
        title.setStyleSheet("font-weight: bold; font-size: 14px; color: white;")
        control_layout.addWidget(title)
        
        # Dessin actuel
        current_group = QGroupBox("Dessin Actuel")
        current_layout = QVBoxLayout(current_group)
        
        self.current_info = QLabel("0 points")
        current_layout.addWidget(self.current_info)
        
        # Boutons pour le dessin actuel
        btn_layout1 = QHBoxLayout()
        
        self.clear_current_btn = QPushButton("🗑️ Effacer")
        self.clear_current_btn.clicked.connect(self.clear_current)
        
        self.save_btn = QPushButton("💾 Sauver")
        self.save_btn.clicked.connect(self.save_current)
        
        btn_layout1.addWidget(self.clear_current_btn)
        btn_layout1.addWidget(self.save_btn)
        current_layout.addLayout(btn_layout1)
        
        # Nom et description pour la sauvegarde
        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Nom du dessin...")
        current_layout.addWidget(self.name_input)
        
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Description (optionnelle)...")
        self.desc_input.setMaximumHeight(60)
        current_layout.addWidget(self.desc_input)
        
        control_layout.addWidget(current_group)
        
        # Gestion des dessins sauvegardés
        saved_group = QGroupBox("Dessins Sauvegardés")
        saved_layout = QVBoxLayout(saved_group)
        
        self.saved_info = QLabel("0 dessins")
        saved_layout.addWidget(self.saved_info)
        
        # Liste des dessins avec sélection
        from PyQt6.QtWidgets import QListWidget, QListWidgetItem
        self.drawings_list = QListWidget()
        self.drawings_list.setMaximumHeight(120)
        self.drawings_list.itemSelectionChanged.connect(self.on_drawing_selection_changed)
        saved_layout.addWidget(self.drawings_list)
        
        # Boutons d'affichage
        display_layout = QHBoxLayout()
        
        self.show_all_btn = QPushButton("👁️ Tous")
        self.show_all_btn.clicked.connect(self.show_all_drawings)
        
        self.show_selected_btn = QPushButton("🎯 Sélectionné")
        self.show_selected_btn.clicked.connect(self.show_selected_drawing)
        
        self.hide_all_btn = QPushButton("❌ Masquer")
        self.hide_all_btn.clicked.connect(self.hide_all_drawings)
        
        display_layout.addWidget(self.show_all_btn)
        display_layout.addWidget(self.show_selected_btn)
        display_layout.addWidget(self.hide_all_btn)
        saved_layout.addLayout(display_layout)
        
        # Bouton pour effacer
        self.clear_all_btn = QPushButton("🗑️ Tout effacer")
        self.clear_all_btn.clicked.connect(self.clear_all_saved)
        saved_layout.addWidget(self.clear_all_btn)
        
        control_layout.addWidget(saved_group)
        
        # Import/Export
        file_group = QGroupBox("Fichiers")
        file_layout = QVBoxLayout(file_group)
        
        self.export_btn = QPushButton("📤 Exporter JSON")
        self.export_btn.clicked.connect(self.export_drawings)
        
        self.import_btn = QPushButton("📥 Importer JSON")
        self.import_btn.clicked.connect(self.import_drawings)
        
        file_layout.addWidget(self.export_btn)
        file_layout.addWidget(self.import_btn)
        
        control_layout.addWidget(file_group)
        
        control_layout.addStretch()
        
        # Canvas principal
        self.canvas = TactileCanvas()
        self.canvas.drawing_changed.connect(self.update_info)
        
        # Assemblage
        layout.addWidget(control_panel)
        layout.addWidget(self.canvas, 1)  # Le canvas prend le reste de l'espace
        
        # Mise à jour initiale
        self.update_info()
        self.update_drawings_list()
    
    def clear_current(self):
        """Effacer le dessin actuel"""
        self.canvas.clear_current_drawing()
        self.update_info()
    
    def save_current(self):
        """Sauvegarder le dessin actuel"""
        name = self.name_input.text().strip()
        description = self.desc_input.toPlainText().strip()
        
        if self.canvas.save_current_drawing(name, description):
            self.name_input.clear()
            self.desc_input.clear()
            self.update_info()
            self.update_drawings_list()  # Mettre à jour la liste
            QMessageBox.information(self, "Succès", f"Dessin '{name or 'Sans nom'}' sauvegardé!")
        else:
            QMessageBox.warning(self, "Erreur", "Le dessin doit contenir au moins 2 points.")
    
    def show_all_drawings(self):
        """Afficher tous les dessins sauvegardés"""
        self.canvas.set_display_mode("all")
        self.drawings_list.clearSelection()
    
    def show_selected_drawing(self):
        """Afficher seulement le dessin sélectionné"""
        current_row = self.drawings_list.currentRow()
        if current_row >= 0:
            self.canvas.set_display_mode("selected", current_row)
        else:
            QMessageBox.information(self, "Info", "Sélectionnez d'abord un dessin dans la liste.")
    
    def hide_all_drawings(self):
        """Masquer tous les dessins sauvegardés"""
        self.canvas.set_display_mode("none")
        self.drawings_list.clearSelection()
    
    def on_drawing_selection_changed(self):
        """Gérer le changement de sélection dans la liste"""
        current_row = self.drawings_list.currentRow()
        if current_row >= 0 and self.canvas.display_mode == "selected":
            # Si on est en mode sélectionné, mettre à jour automatiquement l'affichage
            self.canvas.set_display_mode("selected", current_row)
    
    def toggle_show_saved(self):
        """Basculer l'affichage des dessins sauvegardés (méthode supprimée)"""
        pass
    
    def clear_all_saved(self):
        """Effacer tous les dessins sauvegardés"""
        reply = QMessageBox.question(
            self, "Confirmation", 
            "Effacer tous les dessins sauvegardés ?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        
        if reply == QMessageBox.StandardButton.Yes:
            self.canvas.clear_all_saved_drawings()
            self.update_info()
            self.update_drawings_list()  # Mettre à jour la liste
    
    def update_drawings_list(self):
        """Mettre à jour la liste des dessins"""
        self.drawings_list.clear()
        
        for i, drawing in enumerate(self.canvas.saved_drawings):
            item_text = f"{i+1}. {drawing.name}"
            if drawing.description:
                item_text += f" - {drawing.description[:30]}{'...' if len(drawing.description) > 30 else ''}"
            
            from PyQt6.QtWidgets import QListWidgetItem
            from PyQt6.QtCore import Qt
            from PyQt6.QtGui import QColor
            
            item = QListWidgetItem(item_text)
            
            # Couleur de l'item selon la couleur du dessin
            colors = [
                QColor(100, 150, 255),  # Bleu
                QColor(255, 150, 100),  # Orange
                QColor(100, 255, 150),  # Vert
                QColor(255, 100, 150),  # Rose
                QColor(150, 100, 255),  # Violet
                QColor(255, 255, 100),  # Jaune
                QColor(100, 255, 255),  # Cyan
                QColor(255, 150, 255),  # Magenta
            ]
            color = colors[i % len(colors)]
            item.setForeground(color)
            
            self.drawings_list.addItem(item)
    
    def export_drawings(self):
        """Exporter les dessins"""
        if not self.canvas.saved_drawings:
            QMessageBox.warning(self, "Erreur", "Aucun dessin à exporter.")
            return
        
        filename, _ = QFileDialog.getSaveFileName(
            self, "Exporter les dessins", 
            f"dessins_tactiles_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "Fichiers JSON (*.json)"
        )
        
        if filename:
            if self.canvas.export_drawings(filename):
                QMessageBox.information(self, "Succès", f"Dessins exportés vers:\n{filename}")
            else:
                QMessageBox.critical(self, "Erreur", "Échec de l'export.")
    
    def import_drawings(self):
        """Importer des dessins"""
        filename, _ = QFileDialog.getOpenFileName(
            self, "Importer des dessins", "",
            "Fichiers JSON (*.json)"
        )
        
        if filename:
            count = self.canvas.import_drawings(filename)
            if count > 0:
                self.update_info()
                self.update_drawings_list()  # Mettre à jour la liste
                QMessageBox.information(self, "Succès", f"{count} dessin(s) importé(s).")
            else:
                QMessageBox.critical(self, "Erreur", "Échec de l'import.")
    
    def update_info(self):
        """Mettre à jour les informations affichées"""
        current_points = len(self.canvas.current_drawing.points)
        self.current_info.setText(f"{current_points} points")
        
        saved_count = len(self.canvas.saved_drawings)
        self.saved_info.setText(f"{saved_count} dessins")
        
        # Mettre à jour la liste si elle n'est pas à jour
        if self.drawings_list.count() != saved_count:
            self.update_drawings_list()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Thème sombre
    app.setStyleSheet("""
        QWidget {
            background-color: #2E2E2E;
            color: white;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #555;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px 0 5px;
        }
        QPushButton {
            background-color: #555;
            color: white;
            border: 1px solid #777;
            padding: 8px;
            font-weight: bold;
        }
        QPushButton:hover {
            background-color: #666;
        }
        QLineEdit, QTextEdit {
            background-color: #3E3E3E;
            color: white;
            border: 1px solid #555;
            padding: 5px;
        }
    """)
    
    window = QMainWindow()
    window.setWindowTitle("🎨 Interface Tactile Simplifiée - Dessin et Sauvegarde")
    
    widget = SimplifiedTactileInterface()
    window.setCentralWidget(widget)
    
    window.resize(1200, 800)
    window.show()
    
    print("🎨 Interface tactile simplifiée lancée!")
    print("✏️ Dessinez avec la souris sur le layout physique")
    print("💾 Sauvegardez et exportez vos créations")
    
    sys.exit(app.exec())