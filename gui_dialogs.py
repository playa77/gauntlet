# Script Version: 0.9.8 | Phase 6: Refactor
# Description: Dialogs for the GUI (RefinementDialog).

from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, 
    QAbstractItemView, QDialogButtonBox, QMessageBox
)

class RefinementDialog(QDialog):
    def __init__(self, options, font_size=14, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Refine Research Point")
        self.resize(600, 400)
        self.selected_option = None
        
        layout = QVBoxLayout(self)
        
        lbl = QLabel("Select the best variation for this research point:")
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"font-size: {font_size}pt;")
        layout.addWidget(lbl)
        
        self.list_widget = QListWidget()
        self.list_widget.setWordWrap(True)
        self.list_widget.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.list_widget.setStyleSheet(f"font-size: {font_size}pt; padding: 5px;")
        
        for opt in options:
            item = QListWidgetItem(opt)
            self.list_widget.addItem(item)
            
        layout.addWidget(self.list_widget)
        
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def accept(self):
        if self.list_widget.currentItem():
            self.selected_option = self.list_widget.currentItem().text()
            super().accept()
        else:
            QMessageBox.warning(self, "Selection Required", "Please select an option.")
