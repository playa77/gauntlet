# Script Version: 0.1.2 | Phase 0: Foundation
# Description: Main GUI for Gauntlet. Handles background threading and UI updates.

import sys
import os
import signal
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTextEdit, QPushButton, QLabel, QSplitter, QMessageBox, QComboBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QThread, pyqtSignal
from dotenv import load_dotenv

from orchestrator import ResearchOrchestrator
from utils import setup_project_files, LogStream, crash_handler
from settings_manager import SettingsManager, ModelManager

sys.excepthook = crash_handler

class ResearchWorker(QThread):
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)

    def __init__(self, topic, model_id):
        super().__init__()
        self.topic = topic
        self.model_id = model_id

    def run(self):
        try:
            orchestrator = ResearchOrchestrator(self.model_id)
            result = orchestrator.run(self.topic, self.model_id)
            self.finished.emit(result)
        except Exception as e:
            self.error.emit(str(e))

class GauntletUI(QMainWindow):
    def __init__(self, log_signal):
        super().__init__()
        self.setWindowTitle("Gauntlet Deep Research (v0.1.2)")
        self.resize(1200, 800)
        
        self.settings_manager = SettingsManager()
        self.model_manager = ModelManager()
        
        self.log_signal = log_signal
        self.log_signal.connect(self._append_log)
        
        self._init_ui()
        self._populate_models()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)

        # Input Area
        input_row = QHBoxLayout()
        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText("Enter research topic...")
        self.topic_input.setMaximumHeight(60)
        self.start_btn = QPushButton("Start Research")
        self.start_btn.setFixedWidth(150)
        self.start_btn.setFixedHeight(60)
        self.start_btn.clicked.connect(self._start_research)
        input_row.addWidget(self.topic_input)
        input_row.addWidget(self.start_btn)
        layout.addLayout(input_row)

        # Model Selection
        model_row = QHBoxLayout()
        model_row.addWidget(QLabel("Model:"))
        self.model_combo = QComboBox()
        self.model_combo.setFixedWidth(300)
        model_row.addWidget(self.model_combo)
        model_row.addStretch()
        layout.addLayout(model_row)

        # Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)
        self.journal = QTextEdit()
        self.journal.setReadOnly(True)
        self.journal.setStyleSheet("background-color: #1e1e1e; color: #d4d4d4; font-family: monospace;")
        
        self.preview = QTextEdit()
        self.preview.setReadOnly(True)
        
        splitter.addWidget(self.journal)
        splitter.addWidget(self.preview)
        layout.addWidget(splitter)

    def _populate_models(self):
        for m in self.model_manager.get_all():
            self.model_combo.addItem(m['name'], m['id'])
        idx = self.model_combo.findData(self.settings_manager.get("model_id"))
        if idx >= 0: self.model_combo.setCurrentIndex(idx)

    def _start_research(self):
        topic = self.topic_input.toPlainText().strip()
        model_id = self.model_combo.currentData()
        if not topic: return

        self.start_btn.setEnabled(False)
        self.journal.append(f"\n>>> Researching: {topic} using {model_id}\n")
        self.settings_manager.set("model_id", model_id)

        self.worker = ResearchWorker(topic, model_id)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

    def _on_finished(self, result):
        self.start_btn.setEnabled(True)
        self.preview.setMarkdown(result.get("final_report", ""))
        print("[UI] Research process completed successfully.")

    def _on_error(self, err):
        self.start_btn.setEnabled(True)
        QMessageBox.critical(self, "Error", err)

    @pyqtSlot(str)
    def _append_log(self, text):
        self.journal.append(text.strip())

def main():
    setup_project_files()
    load_dotenv()
    app = QApplication(sys.argv)
    log_stream = LogStream()
    sys.stdout = log_stream
    window = GauntletUI(log_stream.log_signal)
    
    signal.signal(signal.SIGINT, lambda *args: QApplication.quit())
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main()
