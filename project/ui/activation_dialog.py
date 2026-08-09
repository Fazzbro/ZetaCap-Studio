import webbrowser
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QLineEdit, QPushButton, QCheckBox, QMessageBox, QFrame, QSizePolicy)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont, QCursor

from project.core.license_manager import LicenseManager
from project.core.config import config

class ActivationDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Activate ZetaCap")
        self.setFixedSize(500, 400)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self._setup_ui()
        self._apply_styles()
        
    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(30, 30, 30, 30)
        layout.setSpacing(15)
        
        # Title
        title = QLabel("Welcome to ZetaCap")
        title.setFont(QFont("Arial", 18, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        subtitle = QLabel("Please activate your license to continue using the software.")
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setWordWrap(True)
        subtitle.setStyleSheet("color: #AAAAAA; margin-bottom: 15px;")
        layout.addWidget(subtitle)
        
        # License Key Input
        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("Paste your Gumroad License Key here...")
        # Pre-fill if there's an invalid/expired one saved
        if config.GUMROAD_LICENSE_KEY:
            self.key_input.setText(config.GUMROAD_LICENSE_KEY)
        layout.addWidget(self.key_input)
        
        # Spacer
        layout.addSpacing(10)
        
        # Checkboxes
        self.cb_terms = QCheckBox("I agree to the Terms & Conditions")
        self.cb_terms.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(self.cb_terms)
        
        self.cb_privacy = QCheckBox("I agree to the Privacy Policy")
        self.cb_privacy.setCursor(QCursor(Qt.PointingHandCursor))
        layout.addWidget(self.cb_privacy)
        
        # Links label
        links_label = QLabel("<a href='https://your-zetacap-website.netlify.app/terms' style='color:#FF7300;'>View Terms</a> &nbsp;|&nbsp; <a href='https://your-zetacap-website.netlify.app/privacy' style='color:#FF7300;'>View Privacy Policy</a>")
        links_label.setOpenExternalLinks(True)
        links_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(links_label)
        
        layout.addStretch()
        
        # Buttons
        btn_layout = QHBoxLayout()
        
        self.btn_purchase = QPushButton("Purchase License")
        self.btn_purchase.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_purchase.clicked.connect(self._on_purchase_clicked)
        btn_layout.addWidget(self.btn_purchase)
        
        self.btn_activate = QPushButton("Activate ZetaCap")
        self.btn_activate.setCursor(QCursor(Qt.PointingHandCursor))
        self.btn_activate.clicked.connect(self._on_activate_clicked)
        btn_layout.addWidget(self.btn_activate)
        
        layout.addLayout(btn_layout)

    def _apply_styles(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #121212;
                color: #FFFFFF;
            }
            QLabel {
                color: #FFFFFF;
            }
            QLineEdit {
                background-color: #1E1E1E;
                color: #FFFFFF;
                border: 1px solid #333333;
                border-radius: 6px;
                padding: 10px;
                font-size: 14px;
            }
            QLineEdit:focus {
                border: 1px solid #FF7300;
            }
            QCheckBox {
                font-size: 13px;
                color: #DDDDDD;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                background-color: #1E1E1E;
                border: 1px solid #444444;
                border-radius: 4px;
            }
            QCheckBox::indicator:checked {
                background-color: #FF7300;
                border: 1px solid #FF7300;
            }
            QPushButton {
                background-color: #2A2A2A;
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #333333;
            }
        """)
        
        # Highlight Activate Button
        self.btn_activate.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFBD59, stop:0.5 #FF7300, stop:1 #E53900);
                color: #FFFFFF;
                border: none;
                border-radius: 6px;
                padding: 12px;
                font-weight: bold;
                font-size: 14px;
            }
            QPushButton:hover {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #FFC973, stop:0.5 #FF8822, stop:1 #F54900);
            }
        """)

    def _on_purchase_clicked(self):
        webbrowser.open("https://ytpack.gumroad.com/l/zetacap")

    def _on_activate_clicked(self):
        if not self.cb_terms.isChecked() or not self.cb_privacy.isChecked():
            QMessageBox.warning(self, "Required", "You must agree to the Terms & Conditions and Privacy Policy to continue.")
            return
            
        key = self.key_input.text().strip()
        if not key:
            QMessageBox.warning(self, "Required", "Please enter a License Key.")
            return
            
        self.btn_activate.setText("Verifying...")
        self.btn_activate.setEnabled(False)
        self.repaint() # Force UI update
        
        is_valid, msg = LicenseManager.verify_license(key)
        
        self.btn_activate.setText("Activate ZetaCap")
        self.btn_activate.setEnabled(True)
        
        if is_valid:
            QMessageBox.information(self, "Success", msg)
            config.GUMROAD_LICENSE_KEY = key
            config.save()
            self.accept()
        else:
            QMessageBox.critical(self, "Activation Failed", msg)
