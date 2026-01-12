# Script Version: 0.9.8 | Phase 6: Refactor
# Description: Main application entry point. Aggressively refactored.

import sys
import signal
import uuid
import webbrowser
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget, 
    QTextEdit, QPushButton, QMessageBox, QStatusBar, QTabWidget, 
    QTableWidgetItem, QTreeWidgetItem, QFileDialog, QCheckBox
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QColor, QFont
from dotenv import load_dotenv

from utils import setup_project_files, LogStream, crash_handler
from settings_manager import SettingsManager, ModelManager, PromptManager
from settings_ui import SettingsDialog
from export_manager import ExportManager

# Imported Components
from gui_dialogs import RefinementDialog
from gui_widgets import PlanEditorWidget
from gui_tabs import TabFactory
from worker import ResearchWorker

sys.excepthook = crash_handler

class GauntletUI(QMainWindow):
    def __init__(self, log_stream):
        super().__init__()
        self.setWindowTitle("Gauntlet Deep Research (v0.9.8)")
        self.resize(1400, 900)

        self.settings_manager = SettingsManager()
        self.model_manager = ModelManager()
        self.prompt_manager = PromptManager()
        
        self.log_stream = log_stream
        self.log_stream.log_signal.connect(self._append_log)

        self.current_research_state = None
        self.current_thread_id = str(uuid.uuid4())
        self.worker = None
        self.token_totals = {}
        
        self.global_recursion_limit = self.settings_manager.get_param("max_iterations") or 50

        self._init_ui()
        self._apply_visual_settings()

    def _init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)

        # --- Top Bar ---
        top_bar = QHBoxLayout()
        self.topic_input = QTextEdit()
        self.topic_input.setPlaceholderText("Enter research topic...")
        self.topic_input.setMaximumHeight(60)
        
        self.news_mode_chk = QCheckBox("News Mode")
        self.news_mode_chk.setToolTip("Prioritize news sources and RSS feeds.")
        
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
        top_bar.addWidget(self.news_mode_chk)
        top_bar.addWidget(self.action_btn)
        top_bar.addWidget(self.stop_btn)
        top_bar.addWidget(self.settings_btn)
        main_layout.addLayout(top_bar)

        # --- Tabs ---
        self.tabs = QTabWidget()
        main_layout.addWidget(self.tabs)

        # Tab 1: Journal
        self.journal_tab, self.journal = TabFactory.create_journal_tab()
        self.tabs.addTab(self.journal_tab, "Live Journal")

        # Tab 2: Sources
        self.sources_tab, self.sources_table = TabFactory.create_sources_tab(self._open_url)
        self.tabs.addTab(self.sources_tab, "Sources")

        # Tab 3: Knowledge
        self.kg_tab, self.kg_tree = TabFactory.create_knowledge_tab()
        self.tabs.addTab(self.kg_tab, "Knowledge")
        
        # Tab 4: Metrics
        self.metrics_tab, self.metrics_table = TabFactory.create_metrics_tab()
        self.tabs.addTab(self.metrics_tab, "Metrics")

        # Tab 5: Report
        self.plan_editor = PlanEditorWidget()
        self.plan_editor.refine_callback = self._start_refinement
        self.plan_editor.approve_btn.clicked.connect(self._approve_plan)
        
        self.report_tab, self.report_view_container, self.report_view = TabFactory.create_report_tab(
            self.plan_editor, self._copy_report, self._export_pdf, self._export_docx, self
        )
        self.tabs.addTab(self.report_tab, "Report")

        # --- Status Bar ---
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def _apply_visual_settings(self):
        size = self.settings_manager.get("font_size", 14)
        app_font = QFont("Segoe UI", size)
        QApplication.instance().setFont(app_font)
        
        self.journal.setStyleSheet(f"background-color: #1e1e1e; color: #d4d4d4; font-family: 'Consolas', monospace; font-size: {size}pt;")
        self.report_view.setStyleSheet(f"font-family: 'Segoe UI', sans-serif; font-size: {size}pt; line-height: 1.6;")
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
        dlg = RefinementDialog(options, self.settings_manager.get("font_size", 14), self)
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
            "research_mode": "news" if self.news_mode_chk.isChecked() else "standard",
            "logs": [], "research_questions": questions, "sources": [],
            "knowledge_fragments": [], "structured_entities": [], "identified_gaps": [],
            "token_usage": {}, "iteration_count": 0, "final_report": "", "is_complete": False
        }
        self.token_totals = {} 
        self.metrics_table.setRowCount(0)
        self._start_research()

    def _start_research(self):
        self._set_busy(True)
        self.action_btn.setText("Researching...")
        self.status_bar.showMessage(f"Research in progress ({self.current_research_state['research_mode']} mode)...")
        self.tabs.setCurrentIndex(0)
        
        self.worker = ResearchWorker(None, self.current_thread_id, mode="full", state=self.current_research_state, extra_data={"recursion_limit": self.global_recursion_limit})
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
        btn_continue = msg.addButton("Continue (+20 steps)", QMessageBox.ButtonRole.ActionRole)
        btn_generate = msg.addButton("Generate Report Now", QMessageBox.ButtonRole.ActionRole)
        msg.addButton("Abort", QMessageBox.ButtonRole.RejectRole)
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
        self.worker = ResearchWorker(None, self.current_thread_id, mode="generate_now", state=self.current_research_state)
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
        self.news_mode_chk.setEnabled(not busy)
        if not busy: self.stop_btn.setStyleSheet("background-color: #8B0000; color: white; font-weight: bold;")

    def _copy_report(self):
        QApplication.clipboard().setText(self.report_view.toMarkdown())
        self.status_bar.showMessage("Report copied to clipboard!", 3000)

    def _export_pdf(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export PDF", "research_report.pdf", "PDF Files (*.pdf)")
        if filename:
            ExportManager.export_pdf(self.report_view, filename)
            self.status_bar.showMessage(f"Exported to {filename}", 3000)

    def _export_docx(self):
        filename, _ = QFileDialog.getSaveFileName(self, "Export DOCX", "research_report.docx", "Word Documents (*.docx)")
        if filename:
            ExportManager.export_docx(self.report_view.toMarkdown(), filename)
            self.status_bar.showMessage(f"Exported to {filename}", 3000)

    @pyqtSlot(str)
    def _append_log(self, text):
        self.journal.append(text.strip())
        self.journal.verticalScrollBar().setValue(self.journal.verticalScrollBar().maximum())

    @pyqtSlot(list)
    def _update_sources(self, sources):
        current_rows = self.sources_table.rowCount()
        for src in sources:
            if any(self.sources_table.item(r, 3).text() == src.get('url') for r in range(current_rows)): continue
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
        if not usage_delta: return
        for model, counts in usage_delta.items():
            if model not in self.token_totals: self.token_totals[model] = {"input": 0, "output": 0, "total": 0}
            self.token_totals[model]["input"] += counts.get("input", 0)
            self.token_totals[model]["output"] += counts.get("output", 0)
            self.token_totals[model]["total"] += counts.get("total", 0)
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
        if url_item: webbrowser.open(url_item.text())

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
