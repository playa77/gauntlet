# Script Version: 0.9.5 | Phase 5: Polish & Depth Control
# Description: Adjusted Metrics table width for Role/Model display.

import sys
import os
import signal
import uuid
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTextEdit, QPushButton, QLabel, QSplitter, QMessageBox, QComboBox, 
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem, QListWidget, QListWidgetItem, QMenu,
    QInputDialog, QDialog, QAbstractItemView, QDialogButtonBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont, QAction
from dotenv import load_dotenv
from langgraph.errors import GraphRecursionError

from orchestrator import ResearchOrchestrator
from utils import setup_project_files, LogStream, crash_handler
from settings_manager import SettingsManager, ModelManager, PromptManager
from settings_ui import SettingsDialog

sys.excepthook = crash_handler

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

class ResearchWorker(QThread):
    log_signal = pyqtSignal(str)
    source_signal = pyqtSignal(list)
    entity_signal = pyqtSignal(list)
    report_signal = pyqtSignal(str)
    token_signal = pyqtSignal(dict) 
    plan_ready = pyqtSignal(list)
    refinement_ready = pyqtSignal(list, object)
    recursion_error = pyqtSignal()
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, topic, thread_id, mode="full", state=None, extra_data=None):
        super().__init__()
        self.topic = topic
        self.thread_id = thread_id
        self.mode = mode
        self.state = state
        self.extra_data = extra_data
        self._is_running = True
        self.orchestrator = None

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            self.orchestrator = ResearchOrchestrator(thread_id=self.thread_id)
            
            if self.mode == "plan":
                self.log_signal.emit("[PLANNING] Decomposing topic...")
                questions = self.orchestrator.decompose_agent.run(self.topic)
                self.plan_ready.emit(questions)
            
            elif self.mode == "refine":
                question = self.extra_data.get("question")
                item_ref = self.extra_data.get("item_ref")
                options = self.orchestrator.refine_question(question)
                self.refinement_ready.emit(options, item_ref)

            elif self.mode == "full":
                self.log_signal.emit("[START] Beginning research stream...")
                global_limit = self.extra_data.get("recursion_limit", 50) 
                
                try:
                    for event in self.orchestrator.run_stream(self.state, recursion_limit=global_limit):
                        if not self._is_running:
                            self.log_signal.emit("[STOP] Research terminated by user.")
                            break
                        
                        for node_name, output in event.items():
                            if output is None: continue 
                            
                            self.log_signal.emit(f"[GRAPH] Node '{node_name}' completed.")
                            
                            if "logs" in output:
                                for log in output["logs"]:
                                    self.log_signal.emit(f"[{node_name.upper()}] {log}")
                            
                            if "sources" in output:
                                self.source_signal.emit(output["sources"])
                                
                            if "structured_entities" in output:
                                self.entity_signal.emit(output["structured_entities"])
                                
                            if "final_report" in output:
                                self.report_signal.emit(output["final_report"])
                                
                            if "token_usage" in output:
                                self.token_signal.emit(output["token_usage"])
                    
                    self.finished.emit()

                except GraphRecursionError:
                    self.log_signal.emit("[ERROR] Global recursion safety valve hit!")
                    self.recursion_error.emit()
                
            elif self.mode == "generate_now":
                self.log_signal.emit("[SYSTEM] Forcing report generation...")
                report = self.orchestrator.generate_report_now(self.state)
                self.report_signal.emit(report)
                self.finished.emit()
                
        except Exception as e:
            print(f"[ERROR] ResearchWorker failed: {e}")
            self.error.emit(str(e))

class GauntletUI(QMainWindow):
    def __init__(self, log_stream):
        super().__init__()
        self.setWindowTitle("Gauntlet Deep Research (v0.9.5)")
        self.resize(1400, 900)

        self.settings_manager = SettingsManager()
        self.model_manager = ModelManager()
        self.prompt_manager = PromptManager()
        
        self.log_stream = log_stream
        self.log_stream.log_signal.connect(self._append_log)

        self.current_research_state = None
        self.current_thread_id = str(uuid.uuid4())
        self.worker = None
        
        self.global_recursion_limit = self.settings_manager.get_param("max_iterations") or 50

        self._init_ui()
        self._apply_visual_settings()
        
        self.token_totals = {} 

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        
        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText("Enter research topic...")
        self.topic_input.setMaximumHeight(60)
        
        self.action_btn = QPushButton("Generate Plan")
        self.action_btn.setFixedWidth(150)
        self.action_btn.setFixedHeight(60)
        self.action_btn.clicked.connect(self._handle_action)

        self.stop_btn = QPushButton("Stop")
        self.stop_btn.setFixedWidth(80)
        self.stop_btn.setFixedHeight(60)
        self.stop_btn.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")
        self.stop_btn.clicked.connect(self._stop_research)
        self.stop_btn.setEnabled(False)
        
        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setFixedWidth(100)
        self.settings_btn.setFixedHeight(60)
        self.settings_btn.clicked.connect(self._open_settings)

        top_bar.addWidget(self.topic_input)
        top_bar.addWidget(self.action_btn)
        top_bar.addWidget(self.stop_btn)
        top_bar.addWidget(self.settings_btn)
        main_layout.addLayout(top_bar)

        # --- Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Journal
        self.journal_tab = QWidget()
        journal_layout = QVBoxLayout(self.journal_tab)
        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        journal_layout.addWidget(self.journal)
        self.tabs.addTab(self.journal_tab, "Live Journal")

        # Tab 2: Sources
        self.sources_tab = QWidget()
        sources_layout = QVBoxLayout(self.sources_tab)
        self.sources_table = QTableWidget()
        self.sources_table.setColumnCount(4)
        self.sources_table.setHorizontalHeaderLabels(["Score", "Type", "Title", "URL"])
        self.sources_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        self.sources_table.cellDoubleClicked.connect(self._open_url)
        sources_layout.addWidget(self.sources_table)
        self.tabs.addTab(self.sources_tab, "Sources")

        # Tab 3: Knowledge
        self.kg_tab = QWidget()
        kg_layout = QVBoxLayout(self.kg_tab)
        self.kg_tree = QTreeWidget()
        self.kg_tree.setHeaderLabels(["Subject", "Predicate", "Object"])
        self.kg_tree.setColumnWidth(0, 300)
        self.kg_tree.setColumnWidth(1, 200)
        kg_layout.addWidget(self.kg_tree)
        self.tabs.addTab(self.kg_tab, "Knowledge")
        
        # Tab 4: Metrics
        self.metrics_tab = QWidget()
        metrics_layout = QVBoxLayout(self.metrics_tab)
        self.metrics_table = QTableWidget()
        self.metrics_table.setColumnCount(4)
        self.metrics_table.setHorizontalHeaderLabels(["Role / Model", "Input Tokens", "Output Tokens", "Total Tokens"])
        # Set first column to stretch to fit the longer Role/Model string
        self.metrics_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        metrics_layout.addWidget(self.metrics_table)
        self.tabs.addTab(self.metrics_tab, "Metrics")

        # Tab 5: Report / Plan Editor
        self.report_tab = QWidget()
        self.report_layout = QVBoxLayout(self.report_tab)
        
        self.plan_editor = PlanEditorWidget()
        self.plan_editor.refine_callback = self._start_refinement
        self.plan_editor.approve_btn.clicked.connect(self._approve_plan)
        self.plan_editor.hide()
        self.report_layout.addWidget(self.plan_editor)

        self.report_view_container = QWidget()
        rv_layout = QVBoxLayout(self.report_view_container)
        report_toolbar = QHBoxLayout()
        copy_btn = QPushButton("Copy Markdown")
        copy_btn.clicked.connect(self._copy_report)
        report_toolbar.addStretch()
        report_toolbar.addWidget(copy_btn)
        rv_layout.addLayout(report_toolbar)
        
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        rv_layout.addWidget(self.report_view)
        
        self.report_layout.addWidget(self.report_view_container)
        self.tabs.addTab(self.report_tab, "Report")

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _apply_visual_settings(self):
        size = self.settings_manager.get("font_size", 14)
        app_font = QFont("Segoe UI", size)
        QApplication.instance().setFont(app_font)
        
        journal_css = f"""
            background-color: #1e1e1e; 
            color: #d4d4d4; 
            font-family: 'Consolas', 'Monaco', monospace; 
            font-size: {size}pt;
        """
        self.journal.setStyleSheet(journal_css)
        
        report_css = f"""
            font-family: 'Segoe UI', sans-serif;
            font-size: {size}pt;
            line-height: 1.6;
        """
        self.report_view.setStyleSheet(report_css)
        self.topic_input.setStyleSheet(f"font-size: {size}pt;")

    def _open_settings(self):
        dlg = SettingsDialog(self.settings_manager, self.model_manager, self.prompt_manager, self)
        if dlg.exec():
            self.settings_manager.load()
            self.prompt_manager.load()
            self._apply_visual_settings()
            self.global_recursion_limit = self.settings_manager.get_param("max_iterations") or 50
            self.status_bar.showMessage("Settings updated.")

    def _handle_action(self):
        if self.action_btn.text() == "Generate Plan":
            self._start_planning()
        elif self.action_btn.text() == "Approve & Research":
            self._approve_plan()

    def _start_planning(self):
        topic = self.topic_input.toPlainText().strip()
        if not topic: return

        self._set_busy(True)
        self.status_bar.showMessage("Generating Research Plan...")
        self.journal.clear()
        self.journal.append(f"--- STARTING PLAN FOR: {topic} ---")

        self.worker = ResearchWorker(topic, self.current_thread_id, mode="plan")
        self.worker.plan_ready.connect(self._on_plan_ready)
        self.worker.log_signal.connect(self._append_log)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_plan_ready(self, questions):
        self._set_busy(False)
        self.status_bar.showMessage("Plan Ready. Review in Report tab.")
        self.report_view_container.hide()
        self.plan_editor.load_questions(questions)
        self.plan_editor.show()
        self.tabs.setCurrentIndex(4) 
        self.action_btn.setEnabled(False)

    def _start_refinement(self, question, item_ref):
        self.status_bar.showMessage("Refining question...")
        self.worker = ResearchWorker(None, self.current_thread_id, mode="refine", extra_data={"question": question, "item_ref": item_ref})
        self.worker.refinement_ready.connect(self._on_refinement_ready)
        self.worker.start()

    def _on_refinement_ready(self, options, item_ref):
        self.status_bar.showMessage("Refinement options ready.")
        if not options:
            QMessageBox.warning(self, "Refine", "No suggestions generated.")
            return
        
        font_size = self.settings_manager.get("font_size", 14)
        dlg = RefinementDialog(options, font_size, self)
        
        if dlg.exec():
            opt = dlg.selected_option
            data = item_ref.data(Qt.ItemDataRole.UserRole)
            data['question'] = opt
            item_ref.setText(f"[P{data.get('priority', 1)}] {opt}")
            item_ref.setData(Qt.ItemDataRole.UserRole, data)

    def _approve_plan(self):
        questions = self.plan_editor.get_questions()
        if not questions: return

        self.plan_editor.hide()
        self.report_view_container.show()
        self.report_view.clear()
        
        self.current_research_state = {
            "research_topic": self.topic_input.toPlainText().strip(),
            "user_constraints": {},
            "current_phase": "exploration",
            "logs": [],
            "research_questions": questions,
            "sources": [],
            "knowledge_fragments": [],
            "structured_entities": [],
            "identified_gaps": [],
            "token_usage": {},
            "iteration_count": 0,
            "final_report": "",
            "is_complete": False
        }
        
        self.token_totals = {} 
        self.metrics_table.setRowCount(0)
        
        self._start_research()

    def _start_research(self):
        self._set_busy(True)
        self.action_btn.setText("Researching...")
        self.status_bar.showMessage("Research in progress...")
        self.tabs.setCurrentIndex(0)

        limit = self.global_recursion_limit
        
        self.worker = ResearchWorker(
            None, 
            self.current_thread_id, 
            mode="full", 
            state=self.current_research_state,
            extra_data={"recursion_limit": limit}
        )
        
        self.worker.log_signal.connect(self._append_log)
        self.worker.source_signal.connect(self._update_sources)
        self.worker.entity_signal.connect(self._update_entities)
        self.worker.report_signal.connect(self._update_report)
        self.worker.token_signal.connect(self._update_metrics)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.recursion_error.connect(self._on_recursion_error)
        
        self.worker.start()

    def _on_recursion_error(self):
        self._set_busy(False)
        msg = QMessageBox(self)
        msg.setWindowTitle("Safety Valve Reached")
        msg.setText(f"The research hit the global safety limit of {self.global_recursion_limit} steps.")
        msg.setInformativeText("This usually means some topics are very deep. What would you like to do?")
        
        btn_continue = msg.addButton("Continue (+20 steps)", QMessageBox.ButtonRole.ActionRole)
        btn_generate = msg.addButton("Generate Report Now", QMessageBox.ButtonRole.ActionRole)
        btn_abort = msg.addButton("Abort", QMessageBox.ButtonRole.RejectRole)
        
        msg.exec()
        
        if msg.clickedButton() == btn_continue:
            self.global_recursion_limit += 20
            self.journal.append(f"[SYSTEM] Increasing global safety limit to {self.global_recursion_limit}...")
            self._start_research() 
        elif msg.clickedButton() == btn_generate:
            self._generate_report_now()
        else:
            self._on_finished()

    def _generate_report_now(self):
        self.journal.append("[SYSTEM] Forcing report generation...")
        self.worker = ResearchWorker(
            None, 
            self.current_thread_id, 
            mode="generate_now", 
            state=self.current_research_state
        )
        self.worker.report_signal.connect(self._update_report)
        self.worker.finished.connect(self._on_finished)
        self.worker.start()

    def _stop_research(self):
        if self.worker and self.worker.isRunning():
            self.worker.stop()
            self.journal.append("\n[SYSTEM] Stopping research worker...")
            self.status_bar.showMessage("Stopping...")
            self.stop_btn.setEnabled(False)

    def _on_finished(self):
        self._set_busy(False)
        self.action_btn.setText("Generate Plan")
        self.action_btn.setEnabled(True)
        self.status_bar.showMessage("Research Complete")
        self.tabs.setCurrentIndex(4) 

    def _on_error(self, err):
        self._set_busy(False)
        self.action_btn.setText("Generate Plan")
        self.status_bar.showMessage("Error occurred.")
        QMessageBox.critical(self, "Error", f"Process failed:\n\n{err}")

    def _set_busy(self, busy):
        self.topic_input.setEnabled(not busy)
        self.action_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        self.settings_btn.setEnabled(not busy)
        if not busy:
            self.stop_btn.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")

    def _copy_report(self):
        clipboard = QApplication.clipboard()
        clipboard.setText(self.report_view.toMarkdown())
        self.status_bar.showMessage("Report copied to clipboard!", 3000)

    @pyqtSlot(str)
    def _append_log(self, text):
        self.journal.append(text.strip())
        sb = self.journal.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(list)
    def _update_sources(self, sources):
        current_rows = self.sources_table.rowCount()
        for src in sources:
            duplicate = False
            for r in range(current_rows):
                if self.sources_table.item(r, 3).text() == src.get('url'):
                    duplicate = True
                    break
            if duplicate: continue

            row = self.sources_table.rowCount()
            self.sources_table.insertRow(row)
            
            score = float(src.get('score', 0))
            score_item = QTableWidgetItem(f"{score:.2f}")
            if score > 0.7: score_item.setBackground(QColor("#d4edda"))
            elif score < 0.4: score_item.setBackground(QColor("#f8d7da"))
            
            self.sources_table.setItem(row, 0, score_item)
            self.sources_table.setItem(row, 1, QTableWidgetItem(src.get('source_type', 'web')))
            self.sources_table.setItem(row, 2, QTableWidgetItem(src.get('title', 'No Title')))
            self.sources_table.setItem(row, 3, QTableWidgetItem(src.get('url', '')))

    @pyqtSlot(list)
    def _update_entities(self, entities):
        for ent in entities:
            item = QTreeWidgetItem(self.kg_tree)
            item.setText(0, ent.get("subject", "?"))
            item.setText(1, ent.get("predicate", "?"))
            item.setText(2, ent.get("object", "?"))

    @pyqtSlot(str)
    def _update_report(self, markdown):
        self.report_view.setMarkdown(markdown)

    @pyqtSlot(dict)
    def _update_metrics(self, usage_delta):
        """Updates the Metrics tab with new token usage data."""
        if not usage_delta: return
        
        for model, counts in usage_delta.items():
            if model not in self.token_totals:
                self.token_totals[model] = {"input": 0, "output": 0, "total": 0}
            
            self.token_totals[model]["input"] += counts.get("input", 0)
            self.token_totals[model]["output"] += counts.get("output", 0)
            self.token_totals[model]["total"] += counts.get("total", 0)

        # Refresh Table
        self.metrics_table.setRowCount(0)
        for model, counts in self.token_totals.items():
            row = self.metrics_table.rowCount()
            self.metrics_table.insertRow(row)
            self.metrics_table.setItem(row, 0, QTableWidgetItem(model))
            self.metrics_table.setItem(row, 1, QTableWidgetItem(str(counts["input"])))
            self.metrics_table.setItem(row, 2, QTableWidgetItem(str(counts["output"])))
            self.metrics_table.setItem(row, 3, QTableWidgetItem(str(counts["total"])))

    def _open_url(self, row, col):
        url_item = self.sources_table.item(row, 3)
        if url_item:
            webbrowser.open(url_item.text())

def main():
    load_dotenv()
    setup_project_files()
    app = QApplication(sys.argv)
    log_stream = LogStream()
    sys.stdout = log_stream
    window = GauntletUI(log_stream)
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
