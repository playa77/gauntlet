# Script Version: 0.5.0 | Phase 3: GUI Integration
# Description: Full GUI with Tabs, Real-time Streaming, and Visualization.
# Implementation: Implements QTabWidget, QTableWidget, and streaming ResearchWorker.

import sys
import os
import signal
import uuid
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTextEdit, QPushButton, QLabel, QSplitter, QMessageBox, QComboBox, 
    QStatusBar, QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QTreeWidget, QTreeWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QFont
from dotenv import load_dotenv

from orchestrator import ResearchOrchestrator
from utils import setup_project_files, LogStream, crash_handler
from settings_manager import SettingsManager, ModelManager

sys.excepthook = crash_handler

class ResearchWorker(QThread):
    """
    Worker thread that runs the LangGraph stream and emits signals
    for UI updates without freezing the main window.
    """
    log_signal = pyqtSignal(str)
    source_signal = pyqtSignal(list)
    entity_signal = pyqtSignal(list)
    report_signal = pyqtSignal(str)
    plan_ready = pyqtSignal(list)
    finished = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, topic, model_id, thread_id, mode="full", state=None):
        super().__init__()
        self.topic = topic
        self.model_id = model_id
        self.thread_id = thread_id
        self.mode = mode
        self.state = state
        self._is_running = True

    def stop(self):
        self._is_running = False

    def run(self):
        try:
            orchestrator = ResearchOrchestrator(thread_id=self.thread_id)
            
            if self.mode == "plan":
                self.log_signal.emit("[PLANNING] Decomposing topic...")
                questions = orchestrator.decompose_agent.run(self.topic)
                self.plan_ready.emit(questions)
            
            elif self.mode == "full":
                self.log_signal.emit("[START] Beginning research stream...")
                
                # Iterate over the graph stream
                for event in orchestrator.run_stream(self.state):
                    if not self._is_running:
                        self.log_signal.emit("[STOP] Research terminated by user.")
                        break
                    
                    # Event is a dict {node_name: node_output_dict}
                    for node_name, output in event.items():
                        self.log_signal.emit(f"[GRAPH] Node '{node_name}' completed.")
                        
                        # Handle Logs
                        if "logs" in output:
                            for log in output["logs"]:
                                self.log_signal.emit(f"[{node_name.upper()}] {log}")
                        
                        # Handle Sources
                        if "sources" in output:
                            self.source_signal.emit(output["sources"])
                            
                        # Handle Knowledge Graph Entities
                        if "structured_entities" in output:
                            self.entity_signal.emit(output["structured_entities"])
                            
                        # Handle Final Report
                        if "final_report" in output:
                            self.report_signal.emit(output["final_report"])

                self.finished.emit()
                
        except Exception as e:
            print(f"[ERROR] ResearchWorker failed: {e}")
            self.error.emit(str(e))

class GauntletUI(QMainWindow):
    def __init__(self, log_stream):
        super().__init__()
        self.setWindowTitle("Gauntlet Deep Research (v0.5.0)")
        self.resize(1400, 900)

        self.settings_manager = SettingsManager()
        self.model_manager = ModelManager()
        
        # Connect the stdout log stream to our journal
        self.log_stream = log_stream
        self.log_stream.log_signal.connect(self._append_log)

        self.current_research_state = None
        self.current_thread_id = str(uuid.uuid4())
        self.worker = None

        self._init_ui()
        self._populate_models()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- Top Bar: Input & Controls ---
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

        top_bar.addWidget(self.topic_input)
        top_bar.addWidget(self.action_btn)
        top_bar.addWidget(self.stop_btn)
        main_layout.addLayout(top_bar)

        # --- Model Selection ---
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(400)
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        main_layout.addLayout(model_row)

        # --- Main Content: Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Live Journal
        self.journal_tab = QWidget()
        journal_layout = QVBoxLayout(self.journal_tab)
        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas', monospace;")
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

        # Tab 3: Knowledge Graph
        self.kg_tab = QWidget()
        kg_layout = QVBoxLayout(self.kg_tab)
        self.kg_tree = QTreeWidget()
        self.kg_tree.setHeaderLabels(["Subject", "Predicate", "Object"])
        self.kg_tree.setColumnWidth(0, 300)
        self.kg_tree.setColumnWidth(1, 200)
        kg_layout.addWidget(self.kg_tree)
        self.tabs.addTab(self.kg_tab, "Knowledge")

        # Tab 4: Final Report
        self.report_tab = QWidget()
        report_layout = QVBoxLayout(self.report_tab)
        self.report_view = QTextEdit()
        self.report_view.setReadOnly(True)
        report_layout.addWidget(self.report_view)
        self.tabs.addTab(self.report_tab, "Report")

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _populate_models(self):
        self.model_combo.clear()
        models = self.model_manager.get_all()
        env_model = os.getenv("ACTIVE_MODEL_ID")
        
        # Add env model if not in list
        if env_model and env_model != "YOUR_MODEL_ID_HERE":
            if not any(m['id'] == env_model for m in models):
                self.model_combo.addItem(f"Env: {env_model}", env_model)

        for m in models:
            if m['id'] != "YOUR_MODEL_ID_HERE":
                self.model_combo.addItem(m['name'], m['id'])

        # Set selection
        idx = self.model_combo.findData(self.settings_manager.get("model_id"))
        if idx >= 0: self.model_combo.setCurrentIndex(idx)

    def _handle_action(self):
        if self.action_btn.text() == "Generate Plan":
            self._start_planning()
        elif self.action_btn.text() == "Approve & Research":
            self._start_research()

    def _start_planning(self):
        topic = self.topic_input.toPlainText().strip()
        if not topic: return

        self._set_busy(True)
        self.status_bar.showMessage("Generating Research Plan...")
        self.journal.clear()
        self.journal.append(f"--- STARTING PLAN FOR: {topic} ---")

        self.worker = ResearchWorker(topic, self.model_combo.currentData(), self.current_thread_id, mode="plan")
        self.worker.plan_ready.connect(self._on_plan_ready)
        self.worker.log_signal.connect(self._append_log)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_plan_ready(self, questions):
        self._set_busy(False)
        self.action_btn.setText("Approve & Research")
        self.action_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        self.status_bar.showMessage("Plan Ready. Review in Report tab.")

        # Initialize State
        self.current_research_state = {
            "research_topic": self.topic_input.toPlainText().strip(),
            "user_constraints": {},
            "model_id": self.model_combo.currentData(),
            "current_phase": "exploration",
            "logs": [],
            "research_questions": questions,
            "sources": [],
            "knowledge_fragments": [],
            "structured_entities": [],
            "identified_gaps": [],
            "iteration_count": 0,
            "max_iterations": 2,
            "final_report": "",
            "is_complete": False
        }

        # Show Plan in Report Tab
        plan_md = "### Proposed Research Plan\n\n"
        for q in questions:
            plan_md += f"- **[P{q.get('priority', 1)}]** {q.get('question')}\n"
        self.report_view.setMarkdown(plan_md)
        self.tabs.setCurrentIndex(3) # Switch to Report tab

    def _start_research(self):
        self._set_busy(True)
        self.action_btn.setText("Researching...")
        self.status_bar.showMessage("Research in progress...")
        self.tabs.setCurrentIndex(0) # Switch to Journal

        self.worker = ResearchWorker(
            None, 
            self.model_combo.currentData(), 
            self.current_thread_id, 
            mode="full", 
            state=self.current_research_state
        )
        
        # Connect Signals
        self.worker.log_signal.connect(self._append_log)
        self.worker.source_signal.connect(self._update_sources)
        self.worker.entity_signal.connect(self._update_entities)
        self.worker.report_signal.connect(self._update_report)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        
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
        self.action_btn.setStyleSheet("")
        self.status_bar.showMessage("Research Complete")
        self.tabs.setCurrentIndex(3) # Show final report

    def _on_error(self, err):
        self._set_busy(False)
        self.action_btn.setText("Generate Plan")
        self.status_bar.showMessage("Error occurred.")
        QMessageBox.critical(self, "Error", f"Process failed:\n\n{err}")

    def _set_busy(self, busy):
        self.topic_input.setEnabled(not busy)
        self.action_btn.setEnabled(not busy)
        self.stop_btn.setEnabled(busy)
        if not busy:
            self.stop_btn.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")

    @pyqtSlot(str)
    def _append_log(self, text):
        self.journal.append(text.strip())
        # Auto-scroll
        sb = self.journal.verticalScrollBar()
        sb.setValue(sb.maximum())

    @pyqtSlot(list)
    def _update_sources(self, sources):
        # We append new sources to the table
        current_rows = self.sources_table.rowCount()
        for src in sources:
            # Check for duplicates by URL
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

    def _open_url(self, row, col):
        url_item = self.sources_table.item(row, 3)
        if url_item:
            webbrowser.open(url_item.text())

def main():
    load_dotenv()
    setup_project_files()
    app = QApplication(sys.argv)
    
    # Log stream for capturing stdout/stderr if needed, 
    # though we primarily use signals now.
    log_stream = LogStream()
    sys.stdout = log_stream
    
    window = GauntletUI(log_stream)
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
