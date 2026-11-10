import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QIcon
from project.ui.main_window import MainWindow
from project.core.config import config

import logging

try:
    import project.cython_imports
except ImportError:
    pass

def setup_logging():
    log_dir = os.path.join(os.path.expanduser("~"), ".zetacap", "logs")
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, "zetacap.log")
    
    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)
        ]
    )
    logging.info("--- ZetaCap Application Started ---")

def main():
    if "--mcp" in sys.argv:
        from project.mcp_server import mcp
        mcp.run()
        sys.exit(0)
        
    setup_logging()
    app = QApplication(sys.argv)
    
    # Set application icon
    icon_path = 'icon.png'
    if hasattr(sys, '_MEIPASS'):
        icon_path = os.path.join(sys._MEIPASS, 'icon.png')
    
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    # Apply dark theme from file
    theme_path = os.path.join(os.path.dirname(__file__), 'ui', 'themes', 'dark_theme.qss')
    if hasattr(sys, '_MEIPASS'):
        theme_path = os.path.join(sys._MEIPASS, 'project', 'ui', 'themes', 'dark_theme.qss')
        
    if os.path.exists(theme_path):
        with open(theme_path, 'r') as f:
            app.setStyleSheet(f.read())
    config.load()
    
    window = MainWindow()
    window.show()
    
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
