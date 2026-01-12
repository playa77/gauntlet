# Script Version: 0.9.8 | Phase 6: Refactor
# Description: Background thread worker for research tasks.

from PyQt6.QtCore import QThread, pyqtSignal
from langgraph.errors import GraphRecursionError
from orchestrator import ResearchOrchestrator

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
