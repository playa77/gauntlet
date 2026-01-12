# Script Version: 0.9.8 | Phase 6: Refactor
# Description: Custom widgets (PlanEditorWidget).

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QListWidget, QHBoxLayout, QPushButton, 
    QMenu, QMessageBox, QInputDialog, QListWidgetItem
)
from PyQt6.QtGui import QAction
from PyQt6.QtCore import Qt

class PlanEditorWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        
        self.list_widget = QListWidget()
        self.list_widget.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.list_widget.customContextMenuRequested.connect(self._show_context_menu)
        self.list_widget.setWordWrap(True) 
        self.layout.addWidget(self.list_widget)
        
        btn_layout = QHBoxLayout()
        self.add_btn = QPushButton("Add New Point")
        self.add_btn.clicked.connect(self._add_point)
        self.approve_btn = QPushButton("Approve Plan")
        self.approve_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        
        btn_layout.addWidget(self.add_btn)
        btn_layout.addStretch()
        btn_layout.addWidget(self.approve_btn)
        self.layout.addLayout(btn_layout)
        
        self.refine_callback = None

    def load_questions(self, questions):
        self.list_widget.clear()
        for q in questions:
            self._add_item(q)

    def _add_item(self, q_data):
        q_data.setdefault('priority', 1)
        q_data.setdefault('depth', 0)
        q_data.setdefault('status', 'pending')
        
        text = f"[P{q_data['priority']}] {q_data['question']}"
        item = QListWidgetItem(text)
        item.setData(Qt.ItemDataRole.UserRole, q_data)
        self.list_widget.addItem(item)

    def _show_context_menu(self, pos):
        item = self.list_widget.itemAt(pos)
        if not item: return
        
        menu = QMenu()
        refine_action = QAction("Refine with AI", self)
        edit_action = QAction("Edit Manually", self)
        delete_action = QAction("Delete", self)
        
        refine_action.triggered.connect(lambda: self._refine_item(item))
        edit_action.triggered.connect(lambda: self._edit_item(item))
        delete_action.triggered.connect(lambda: self._delete_item(item))
        
        menu.addAction(refine_action)
        menu.addAction(edit_action)
        menu.addAction(delete_action)
        menu.exec(self.list_widget.mapToGlobal(pos))

    def _delete_item(self, item):
        reply = QMessageBox.question(
            self, "Confirm Delete", 
            "Are you sure you want to remove this research point?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            row = self.list_widget.row(item)
            self.list_widget.takeItem(row)

    def _edit_item(self, item):
        q_data = item.data(Qt.ItemDataRole.UserRole)
        text, ok = QInputDialog.getText(self, "Edit Point", "Question:", text=q_data['question'])
        if ok and text:
            q_data['question'] = text
            item.setText(f"[P{q_data['priority']}] {text}")
            item.setData(Qt.ItemDataRole.UserRole, q_data)

    def _refine_item(self, item):
        if self.refine_callback:
            q_data = item.data(Qt.ItemDataRole.UserRole)
            self.refine_callback(q_data['question'], item)

    def _add_point(self):
        text, ok = QInputDialog.getText(self, "New Research Point", "Enter question:")
        if ok and text:
            q_data = {
                "id": self.list_widget.count() + 1, 
                "question": text, 
                "priority": 1,
                "depth": 0,
                "status": "pending"
            }
            self._add_item(q_data)

    def get_questions(self):
        questions = []
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            questions.append(item.data(Qt.ItemDataRole.UserRole))
        return questions
