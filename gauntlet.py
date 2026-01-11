# Script Version: 0.4.1 | Phase 2: Orchestration
# Description: GUI with Enhanced Status for Parallel Phases.
# Implementation: Updated status bar to show iteration and parallel status.

import sys
import os
import signal
import uuid
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTextEdit, QPushButton, QLabel, QSplitter, QMessageBox, QComboBox, QStatusBar
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal
from dotenv import load_dotenv

from orchestrator import ResearchOrchestrator
from utils import setup_project_files, LogStream, crash_handler
from settings_manager import SettingsManager, ModelManager

sys.excepthook = crash_handler

class ResearchWorker(QThread):
    finished = pyqtSignal(dict)
    plan_ready = pyqtSignal(list)
    error = pyqtSignal(str)

    def __init__(self, topic, model_id, thread_id, mode="full", state=None):
        super().__init__()
        self.topic = topic
        self.model_id = model_id
        self.thread_id = thread_id
        self.mode = mode
        self.state = state

    def run(self):
        try:
            orchestrator = ResearchOrchestrator(thread_id=self.thread_id)
            if self.mode == "plan":
                questions = orchestrator.decompose_agent.run(self.topic)
                self.plan_ready.emit(questions)
            else:
                result = orchestrator.run_full(self.state)
                self.finished.emit(result)
        except Exception as e:
            print(f"[ERROR] ResearchWorker failed: {e}")
            self.error.emit(str(e))

class GauntletUI(QMainWindow):
    def __init__(self, log_signal):
        super().__init__()
        self.setWindowTitle("Gauntlet Deep Research (v0.4.1)")
        self.resize(1200, 800)

        self.settings_manager = SettingsManager()
        self.model_manager = ModelManager()
        self.log_signal = log_signal
        self.log_signal.connect(self._append_log)

        self.current_research_state = None
        self.current_thread_id = str(uuid.uuid4())

        self._init_ui()
        self._populate_models()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        input_row = QHBoxLayout()
        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText("Enter research topic...")
        self.topic_input.setMaximumHeight(60)

        self.action_btn = QPushButton("Generate Plan")
        self.action_btn.setFixedWidth(150)
        self.action_btn.setFixedHeight(60)
        self.action_btn.clicked.connect(self._handle_action)

        input_row.addWidget(self.topic_input)
        input_row.addWidget(self.action_btn)
        layout.addLayout(input_row)

        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(400)
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        layout.addLayout(model_row)

        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas', 'Monaco', monospace;")

        self.preview = QTextEdit()
        self.preview.setReadOnly(True)

        splitter.addWidget(self.journal)
        splitter.addWidget(self.preview)
        layout.addWidget(splitter)

        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _populate_models(self):
        self.model_combo.clear()
        models = self.model_manager.get_all()
        env_model = os.getenv("ACTIVE_MODEL_ID")
        if env_model and env_model != "YOUR_MODEL_ID_HERE":
            if not any(m['id'] == env_model for m in models):
                self.model_combo.addItem(f"Env: {env_model}", env_model)

        for m in models:
            if m['id'] != "YOUR_MODEL_ID_HERE":
                self.model_combo.addItem(m['name'], m['id'])

        idx = self.model_combo.findData(self.settings_manager.get("model_id"))
        if idx >= 0: self.model_combo.setCurrentIndex(idx)

    def _handle_action(self):
        if self.action_btn.text() == "Generate Plan":
            self._start_planning()
        elif self.action_btn.text() == "Approve & Research":
            self._start_research()

    def _start_planning(self):
        topic = self.topic_input.toPlainText().strip()
        model_id = self.model_combo.currentData()
        if not topic: return

        self.action_btn.setEnabled(False)
        self.status_bar.showMessage("Generating Research Plan...")

        self.worker = ResearchWorker(topic, model_id, self.current_thread_id, mode="plan")
        self.worker.plan_ready.connect(self._on_plan_ready)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_plan_ready(self, questions):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Approve & Research")
        self.action_btn.setStyleSheet("background-color: #2d5a27; color: white; font-weight: bold;")
        self.status_bar.showMessage("Plan Ready for Approval")

        self.current_research_state = {
            "research_topic": self.topic_input.toPlainText().strip(),
            "user_constraints": {},
            "model_id": self.model_combo.currentData(),
            "current_phase": "exploration",
            "logs": [f"Plan approved with {len(questions)} questions."],
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

        plan_md = "### Proposed Research Plan\n\n"
        for q in questions:
            plan_md += f"- [{q.get('priority', 1)}] {q.get('question')}\n"
        self.preview.setMarkdown(plan_md)

    def _start_research(self):
        self.action_btn.setEnabled(False)
        self.action_btn.setText("Researching...")
        self.status_bar.showMessage("Phase: Parallel Discovery (Iteration 0)")

        self.worker = ResearchWorker(None, self.model_combo.currentData(), self.current_thread_id, mode="full", state=self.current_research_state)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, result):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Generate Plan")
        self.action_btn.setStyleSheet("")
        self.preview.setMarkdown(result.get("final_report", ""))
        self.status_bar.showMessage("Research Complete")

    def _on_error(self, err):
        self.action_btn.setEnabled(True)
        self.action_btn.setText("Generate Plan")
        self.status_bar.showMessage("Error occurred.")
        QMessageBox.critical(self, "Error", f"Process failed:\n\n{err}")

    @pyqtSlot(str)
    def _append_log(self, text):
        self.journal.append(text.strip())
        if "PHASE:" in text or "BRANCH:" in text:
            self.status_bar.showMessage(text.strip())

def main():
    load_dotenv()
    setup_project_files()
    app = QApplication(sys.argv)
    log_stream = LogStream()
    sys.stdout = log_stream
    window = GauntletUI(log_stream.log_signal)
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
