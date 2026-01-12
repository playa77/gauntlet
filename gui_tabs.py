# Script Version: 0.9.8 | Phase 6: Refactor
# Description: Factory functions for creating specific UI tabs.

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QTextEdit, QTableWidget, QHeaderView, 
    QTreeWidget, QHBoxLayout, QPushButton, QMenu
)
from PyQt6.QtGui import QAction

class TabFactory:
    @staticmethod
    def create_journal_tab():
        tab = QWidget()
        layout = QVBoxLayout(tab)
        journal = QTextEdit()
        journal.setReadOnly(True)
        layout.addWidget(journal)
        return tab, journal

    @staticmethod
    def create_sources_tab(double_click_handler):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Score", "Type", "Title", "URL"])
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        table.cellDoubleClicked.connect(double_click_handler)
        layout.addWidget(table)
        return tab, table

    @staticmethod
    def create_knowledge_tab():
        tab = QWidget()
        layout = QVBoxLayout(tab)
        tree = QTreeWidget()
        tree.setHeaderLabels(["Subject", "Predicate", "Object"])
        tree.setColumnWidth(0, 300)
        tree.setColumnWidth(1, 200)
        layout.addWidget(tree)
        return tab, tree

    @staticmethod
    def create_metrics_tab():
        tab = QWidget()
        layout = QVBoxLayout(tab)
        table = QTableWidget()
        table.setColumnCount(4)
        table.setHorizontalHeaderLabels(["Role / Model", "Input Tokens", "Output Tokens", "Total Tokens"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(table)
        return tab, table

    @staticmethod
    def create_report_tab(plan_editor, copy_handler, export_pdf_handler, export_docx_handler, parent_window):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        
        # Add Plan Editor (hidden by default)
        layout.addWidget(plan_editor)
        plan_editor.hide()

        # Report View Container
        container = QWidget()
        rv_layout = QVBoxLayout(container)
        
        # Toolbar
        toolbar = QHBoxLayout()
        copy_btn = QPushButton("Copy Markdown")
        copy_btn.clicked.connect(copy_handler)
        
        export_btn = QPushButton("Export...")
        export_menu = QMenu(parent_window)
        pdf_action = QAction("Export to PDF", parent_window)
        pdf_action.triggered.connect(export_pdf_handler)
        docx_action = QAction("Export to DOCX", parent_window)
        docx_action.triggered.connect(export_docx_handler)
        export_menu.addAction(pdf_action)
        export_menu.addAction(docx_action)
        export_btn.setMenu(export_menu)
        
        toolbar.addStretch()
        toolbar.addWidget(copy_btn)
        toolbar.addWidget(export_btn)
        rv_layout.addLayout(toolbar)
        
        # Report Text Area
        report_view = QTextEdit()
        report_view.setReadOnly(True)
        rv_layout.addWidget(report_view)
        
        layout.addWidget(container)
        
        return tab, container, report_view
