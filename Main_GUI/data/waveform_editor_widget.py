"""
Interactive Waveform Editor – Universal Haptic Event Designer (UI File Only)
============================================================
Key points
----------
* Uses Qt Designer .ui file exclusively for layout
* Single graph showing either amplitude or frequency  
* ADSR parameters properly implemented
* Clean separation of UI and logic - no fallback UI code

Dependencies: `pip install pyqtgraph`
"""

from __future__ import annotations

import sys, os, typing as _t
import numpy as np
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QApplication, QWidget
from PyQt6 import uic
import pyqtgraph as pg

from event_data_model import HapticEvent, ParameterModifications


# ════════════════════════════════════════════════════════════════════════════
#  Helpers – editable scatter (drag / click)                                  
# ════════════════════════════════════════════════════════════════════════════
class _EditableScatter(pg.ScatterPlotItem):
    """Scatter points that can be dragged; emits a callback on change."""

    def __init__(self, x, y, *, color: str, callback: _t.Callable[[np.ndarray, np.ndarray], None]):
        super().__init__(x=x, y=y, symbol="o", size=8,
                         brush=pg.mkBrush(color), pen=pg.mkPen("black", width=0.5))
        self._callback = callback
        self._drag_index: int | None = None

    def _to_data(self):
        pts = self.getData()
        return np.array(pts[0]), np.array(pts[1])

    def mousePressEvent(self, ev):
        if ev.button() == Qt.MouseButton.LeftButton:
            pts_clicked = self.pointsAt(ev.pos())
            if pts_clicked:
                self._drag_index = self.points().index(pts_clicked[0])
            ev.accept()
        super().mousePressEvent(ev)

    def mouseMoveEvent(self, ev):
        if self._drag_index is None:
            super().mouseMoveEvent(ev)
            return
        new_pos = self.mapToView(ev.pos())
        x, y = self._to_data()
        x[self._drag_index] = float(new_pos.x())
        y[self._drag_index] = float(new_pos.y())
        order = np.argsort(x)
        x, y = x[order], y[order]
        self.setData(pos=np.column_stack((x, y)))
        self._callback(x, y)
        ev.accept()

    def mouseReleaseEvent(self, ev):
        self._drag_index = None
        super().mouseReleaseEvent(ev)


# ════════════════════════════════════════════════════════════════════════════
#  Main Widget using UI File Only                                                               
# ════════════════════════════════════════════════════════════════════════════
class WaveformEditorWidget(QWidget):
    parameters_changed = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_event: HapticEvent | None = None
        self._show_amplitude = True  # True for amplitude, False for frequency
        self._load_ui()
        self._setup_plot()
        self._connect_signals()

    def _load_ui(self):
        """Load UI from .ui file"""
        ui_file_path = os.path.join(os.path.dirname(__file__), "waveform_editor.ui")
        uic.loadUi(ui_file_path, self)

    def _setup_plot(self):
        """Setup the plot widget"""
        self.plot_widget = pg.PlotWidget()
        self.plot_widget.setBackground("w")
        self.plot_widget.showGrid(x=True, y=True, alpha=0.2)
        self.plot_layout.addWidget(self.plot_widget)

    def _connect_signals(self):
        """Connect all widget signals"""
        # Graph selector
        self.graph_selector.currentTextChanged.connect(self._on_graph_type_changed)
        
        # Parameter spinboxes
        self.intensity_spinbox.valueChanged.connect(lambda v: self._set_param("intensity_multiplier", v))
        self.offset_spinbox.valueChanged.connect(lambda v: self._set_param("amplitude_offset", v))
        self.duration_spinbox.valueChanged.connect(lambda v: self._set_param("duration_scale", v))
        self.freq_shift_spinbox.valueChanged.connect(lambda v: self._set_param("frequency_shift", v))
        self.attack_spinbox.valueChanged.connect(lambda v: self._set_param("attack_time", v))
        self.decay_spinbox.valueChanged.connect(lambda v: self._set_param("decay_time", v))
        self.sustain_spinbox.valueChanged.connect(lambda v: self._set_param("sustain_level", v))
        self.release_spinbox.valueChanged.connect(lambda v: self._set_param("release_time", v))
        
        # Reset button
        self.reset_button.clicked.connect(self._reset_parameters)

    def _on_graph_type_changed(self, text):
        """Handle graph type selection"""
        self._show_amplitude = (text == "Amplitude")
        if self.current_event:
            self.plot_event(self.current_event)

    def _set_param(self, name: str, value: float):
        """Set a parameter and trigger update"""
        if not self.current_event: 
            return
        setattr(self.current_event.parameter_modifications, name, value)
        self.parameters_changed.emit()
        self.plot_event(self.current_event)

    def _reset_parameters(self):
        """Reset all parameters to defaults"""
        if not self.current_event: 
            return
        self.current_event.parameter_modifications = ParameterModifications()
        self.load_event(self.current_event)
        self.parameters_changed.emit()

    def plot_event(self, event: HapticEvent):
        """Plot the current event"""
        self.current_event = event
        self.plot_widget.clear()
        if not event or not event.waveform_data:
            return

        wf = event.waveform_data
        p = event.parameter_modifications

        if self._show_amplitude:
            self._plot_amplitude(wf, p, event)
        else:
            self._plot_frequency(wf, p, event)

    def _plot_amplitude(self, wf, p, event):
        """Plot amplitude envelope"""
        if not wf.amplitude:
            return
            
        self.plot_widget.setLabel('left', 'Amplitude')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setTitle("Amplitude Envelope")
        
        t_a = np.array([pt["time"] for pt in wf.amplitude])
        amp = np.array([pt["amplitude"] for pt in wf.amplitude])
        
        # Original waveform
        self.plot_widget.plot(t_a, amp, pen=pg.mkPen("#4a7", width=2), name="Original")
        
        # Modified waveform (with ADSR and other modifications)
        amp_mod = event.get_modified_waveform()
        if amp_mod is not None:
            dur_scale = p.duration_scale or 1.0
            t_mod = t_a * dur_scale
            
            # Plot modified waveform
            self.plot_widget.plot(t_mod, amp_mod, pen=pg.mkPen("#c34", width=2), name="Modified")
            
            # Editable scatter for modified - use original time scale for editing
            self._scatter = _EditableScatter(t_a, amp, color="#c34", callback=self._amp_moved)
            self.plot_widget.addItem(self._scatter)
        
        self.plot_widget.setLimits(yMin=-1.2, yMax=1.2)
        self.plot_widget.setYRange(-1.1, 1.1)

    def _plot_frequency(self, wf, p, event):
        """Plot frequency envelope"""
        if not wf.frequency:
            return
            
        self.plot_widget.setLabel('left', 'Frequency (Hz)')
        self.plot_widget.setLabel('bottom', 'Time (s)')
        self.plot_widget.setTitle("Frequency Envelope")
        
        t_f = np.array([pt["time"] for pt in wf.frequency])
        freq = np.array([pt["frequency"] for pt in wf.frequency])
        
        # Original frequency
        self.plot_widget.plot(t_f, freq, pen=pg.mkPen("#0a4", width=2), name="Original")
        
        # Modified frequency
        freq_mod = event.get_modified_frequency()
        if freq_mod is not None:
            dur_scale = p.duration_scale or 1.0
            t_f_mod = t_f * dur_scale
            self.plot_widget.plot(t_f_mod, freq_mod, pen=pg.mkPen("orange", width=2), name="Modified")
            
            # Editable scatter for modified - use original time scale
            self._scatter = _EditableScatter(t_f, freq, color="orange", callback=self._freq_moved)
            self.plot_widget.addItem(self._scatter)

    def _amp_moved(self, x: np.ndarray, y: np.ndarray):
        """Handle amplitude point movement"""
        if not self.current_event: 
            return
        # Update the original amplitude data when points are moved
        self.current_event.waveform_data.amplitude = [
            dict(time=float(tx), amplitude=float(ay)) for tx, ay in zip(x, y)
        ]
        # Trigger a replot to show ADSR effects on the modified curve
        self.plot_event(self.current_event)

    def _freq_moved(self, x: np.ndarray, y: np.ndarray):
        """Handle frequency point movement"""
        if not self.current_event: 
            return
        # Update the original frequency data when points are moved
        self.current_event.waveform_data.frequency = [
            dict(time=float(tx), frequency=float(fy)) for tx, fy in zip(x, y)
        ]
        # Trigger a replot to show modifications
        self.plot_event(self.current_event)

    def set_event(self, evt: HapticEvent):
        """Set the current event"""
        self.current_event = evt
        self.plot_event(evt)
        self.load_event(evt)

    def load_event(self, evt: HapticEvent):
        """Load event parameters into UI controls"""
        self.current_event = evt
        p = evt.parameter_modifications if evt else ParameterModifications()
        
        # Block signals to prevent recursive updates
        widgets = [
            self.intensity_spinbox, self.offset_spinbox, self.duration_spinbox,
            self.freq_shift_spinbox, self.attack_spinbox, self.decay_spinbox,
            self.sustain_spinbox, self.release_spinbox
        ]
        
        for widget in widgets:
            widget.blockSignals(True)
        
        # Set values
        self.intensity_spinbox.setValue(p.intensity_multiplier)
        self.offset_spinbox.setValue(p.amplitude_offset)
        self.duration_spinbox.setValue(p.duration_scale)
        self.freq_shift_spinbox.setValue(p.frequency_shift)
        self.attack_spinbox.setValue(p.attack_time)
        self.decay_spinbox.setValue(p.decay_time)
        self.sustain_spinbox.setValue(p.sustain_level)
        self.release_spinbox.setValue(p.release_time)
        
        # Unblock signals
        for widget in widgets:
            widget.blockSignals(False)

    def get_current_event(self):
        """Get the current event"""
        return self.current_event


# ════════════════════════════════════════════════════════════════════════════
#  Demo                                                             
# ════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    from event_data_model import HapticEvent
    app = QApplication(sys.argv)
    demo = WaveformEditorWidget()
    # Create a test event
    evt = HapticEvent.new_basic_oscillator("Sine")
    demo.set_event(evt)
    demo.resize(1200, 800)
    demo.show()
    sys.exit(app.exec())