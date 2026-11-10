from PySide6.QtWidgets import QPushButton, QColorDialog, QHBoxLayout, QLabel, QWidget, QSlider, QSpinBox, QDoubleSpinBox, QComboBox, QDialog, QVBoxLayout
from PySide6.QtGui import QColor, QPainter, QBrush
from PySide6.QtCore import Qt, Signal, QTimer, QRectF
import math

class ColorButton(QPushButton):
    colorChanged = Signal(str)

    def __init__(self, color="#FFFFFF", parent=None):
        super().__init__(parent)
        self.color = QColor(color)
        self.update_style()
        self.clicked.connect(self.choose_color)

    def update_style(self):
        self.setStyleSheet(f"ColorButton {{ background-color: {self.color.name()}; border: 1px solid #555; border-radius: 4px; min-width: 40px; min-height: 16px; max-height: 16px; padding: 0px; }}")

    def choose_color(self):
        dialog = QColorDialog(self.color, self)
        dialog.setWindowFlag(Qt.WindowType.Dialog)
        if dialog.exec() == QColorDialog.DialogCode.Accepted:
            color = dialog.selectedColor()
            self.color = color
            self.update_style()
            self.colorChanged.emit(self.color.name())

    def set_color(self, color):
        self.color = QColor(color)
        self.update_style()
        # Optional: emit the signal if needed by other components during preset load
        # self.colorChanged.emit(self.color.name())

    def get_color(self):
        return self.color.name()

def create_slider_row(label_text, min_val, max_val, default_val, step=1):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    
    label = QLabel(label_text)
    
    if isinstance(default_val, float):
        spinbox = QDoubleSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setValue(default_val)
    else:
        spinbox = QSpinBox()
        spinbox.setRange(min_val, max_val)
        spinbox.setSingleStep(step)
        spinbox.setValue(default_val)
        
    slider = QSlider(Qt.Horizontal)
    
    # Mapping logic for float vs int would go here, simplified for now
    
    layout.addWidget(label)
    layout.addWidget(slider)
    layout.addWidget(spinbox)
    return container, slider, spinbox

def create_combo_row(label_text, items, default_idx=0):
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    
    label = QLabel(label_text)
    combo = QComboBox()
    combo.addItems(items)
    combo.setCurrentIndex(default_idx)
    
    layout.addWidget(label)
    layout.addWidget(combo)
    return container, combo

class WaveLoaderWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedSize(60, 40)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update)
        self.timer.start(80)
        self.tick = 0

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        bar_count = 5
        bar_width = 6
        spacing = 4
        
        total_width = bar_count * bar_width + (bar_count - 1) * spacing
        start_x = (self.width() - total_width) / 2
        
        painter.setBrush(QBrush(QColor("#d97706")))
        painter.setPen(Qt.NoPen)
        
        for i in range(bar_count):
            # scale based on sine wave
            height_scale = (math.sin(self.tick * 0.3 + i * 0.8) + 1) / 2
            h = 10 + height_scale * 20
            
            x = start_x + i * (bar_width + spacing)
            y = (self.height() - h) / 2
            
            painter.drawRoundedRect(QRectF(x, y, bar_width, h), 3, 3)
            
        self.tick += 1

class LoadingOverlay(QWidget):
    def __init__(self, message="Loading...", parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WA_TranslucentBackground, True)
        self.setFixedSize(240, 160)
        
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setContentsMargins(0, 0, 0, 0)
        
        self.bg = QWidget(self)
        self.bg.setStyleSheet("""
            QWidget {
                background-color: rgba(15, 23, 42, 245);
                border-radius: 12px;
                border: 1px solid #3b82f6;
            }
        """)
        self.bg.setFixedSize(240, 160)
        
        bg_layout = QVBoxLayout(self.bg)
        bg_layout.setAlignment(Qt.AlignCenter)
        bg_layout.setSpacing(12)
        
        self.wave = WaveLoaderWidget()
        self.label = QLabel(message)
        self.label.setStyleSheet("color: #f8fafc; font-weight: bold; font-size: 13px; background: transparent; border: none;")
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        
        self.btn_minimize = QPushButton("Hide")
        self.btn_minimize.setStyleSheet("background: rgba(255,255,255,0.1); color: #94a3b8; border: 1px solid #475569; border-radius: 4px; padding: 2px 8px;")
        self.btn_minimize.setCursor(Qt.PointingHandCursor)
        self.btn_minimize.clicked.connect(self.hide)
        
        bg_layout.addWidget(self.wave, alignment=Qt.AlignCenter)
        bg_layout.addWidget(self.label, alignment=Qt.AlignCenter)
        bg_layout.addWidget(self.btn_minimize, alignment=Qt.AlignCenter)
        
        layout.addWidget(self.bg)
        self.center_on_parent()

    def center_on_parent(self):
        if self.parent():
            parent_geo = self.parent().rect()
            self.move((parent_geo.width() - self.width()) // 2, (parent_geo.height() - self.height()) // 2)

    def showEvent(self, event):
        self.center_on_parent()
        self.raise_()
        super().showEvent(event)

    def set_message(self, msg):
        self.label.setText(msg)

    def accept(self):
        self.hide()
        self.deleteLater()

