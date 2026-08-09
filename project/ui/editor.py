from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, 
                               QTableWidget, QTableWidgetItem, QHeaderView, 
                               QPushButton, QLineEdit, QLabel, QCheckBox)
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QUndoStack, QUndoCommand, QKeySequence, QShortcut

class TableEditCommand(QUndoCommand):
    def __init__(self, table, row, col, old_text, new_text):
        super().__init__()
        self.table = table
        self.row = row
        self.col = col
        self.old_text = old_text
        self.new_text = new_text

    def undo(self):
        self.table.blockSignals(True)
        self.table.item(self.row, self.col).setText(self.old_text)
        self.table.blockSignals(False)

    def redo(self):
        self.table.blockSignals(True)
        self.table.item(self.row, self.col).setText(self.new_text)
        self.table.blockSignals(False)

class EditorWidget(QWidget):
    override_request = Signal(int, int) # row, col

    def __init__(self):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Toolbar
        toolbar = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search & Filter Words...")
        
        self.search_mode = QCheckBox("Search-Only Mode")
        self.unselect_btn = QPushButton("Deselect Word(s)")
        self.reset_btn = QPushButton("Reset Override")
        
        toolbar.addWidget(QLabel("🔍"))
        toolbar.addWidget(self.search_input)
        toolbar.addWidget(self.search_mode)
        toolbar.addWidget(self.unselect_btn)
        toolbar.addWidget(self.reset_btn)
        
        layout.addLayout(toolbar)
        
        # Table
        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(["ID", "Word", "Start", "End", "Color", "Font", "X Nudge", "Y Nudge"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        
        layout.addWidget(self.table)
        
        # Undo/Redo Setup
        self.undo_stack = QUndoStack(self)
        self.shortcut_undo = QShortcut(QKeySequence("Ctrl+Z"), self)
        self.shortcut_undo.activated.connect(self.undo_stack.undo)
        
        self.shortcut_redo = QShortcut(QKeySequence("Ctrl+Shift+Z"), self)
        self.shortcut_redo.activated.connect(self.undo_stack.redo)
        
        self._is_populating = False
        
        # We need to track the old value before it changes
        self.table.cellDoubleClicked.connect(self.on_cell_double_clicked)
        self.table.cellChanged.connect(self.on_cell_changed)
        self._current_edit_text = ""
        
    def on_cell_double_clicked(self, row, col):
            
        item = self.table.item(row, col)
        if item:
            self._current_edit_text = item.text()
            
    def on_cell_changed(self, row, col):
        if self._is_populating:
            return
            
        item = self.table.item(row, col)
        if not item: return
        new_text = item.text()
        
        if new_text != self._current_edit_text:
            cmd = TableEditCommand(self.table, row, col, self._current_edit_text, new_text)
            self.undo_stack.push(cmd)
            self._current_edit_text = new_text  # Update for consecutive changes
        
    def populate_data(self, words_data):
        self._is_populating = True
        self.table.setRowCount(len(words_data))
        for row, data in enumerate(words_data):
            self.table.setItem(row, 0, QTableWidgetItem(str(data.get('id', row))))
            self.table.setItem(row, 1, QTableWidgetItem(data.get('word', '')))
            self.table.setItem(row, 2, QTableWidgetItem(f"{data.get('start', 0):.2f}"))
            self.table.setItem(row, 3, QTableWidgetItem(f"{data.get('end', 0):.2f}"))
            self.table.setItem(row, 4, QTableWidgetItem(data.get('color', 'Default')))
            self.table.setItem(row, 5, QTableWidgetItem(data.get('font', 'None')))
            self.table.setItem(row, 6, QTableWidgetItem(str(data.get('x_nudge', 0.0))))
            self.table.setItem(row, 7, QTableWidgetItem(str(data.get('y_nudge', 0.0))))
        self._is_populating = False
        self.undo_stack.clear()
