import sys
import unittest
from PySide6.QtWidgets import QApplication
from project.ui.main_window import MainWindow

class TestUI(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # We need a QApplication instance to create QWidgets
        if not QApplication.instance():
            cls.app = QApplication(sys.argv)
        else:
            cls.app = QApplication.instance()

    def test_main_window_initialization(self):
        try:
            window = MainWindow()
            self.assertIsNotNone(window)
            self.assertEqual(window.windowTitle(), "Tiny Word Editor Pro")
            print("MainWindow initialized successfully.")
        except Exception as e:
            self.fail(f"MainWindow initialization failed with error: {e}")

if __name__ == "__main__":
    unittest.main()
