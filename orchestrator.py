# Script Version: 0.4.6 | Phase 2: Orchestration
# Description: Orchestrator using externalized prompts and role-based model selection.
# Implementation: Robust JSON loading and verbose terminal output for state transitions.

import os
import json
import sqlite3
import sys
from typing import Dict, List, Literal
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI

from state import ResearchState
from agents import (
    DecomposeTopicAgent, InitialSearchAgent, SourceQualityAgent, 
    AcademicSpecialistAgent, SectionWriterAgent, GapAnalyzerAgent
)
from source_manager import SourceManager
from vector_store import VectorStore

class ResearchOrchestrator:
    def __init__(self, thread_id: str = "default_research"):
        print(f"[ORCHESTRATOR] Initializing Cyclical Phase 2 Workflow...")
        self.thread_id = thread_id
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            print("[ERROR] OPENROUTER_API_KEY not found in environment.")
            sys.exit(1)

        # Load External Configs with Error Handling
        try:
            with open("prompts.json", "r") as f: 
                self.prompts = json.load(f)
            with open("models.json", "r") as f: 
                self.model_config = json.load(f)
            with open("settings.json", "r") as f: 
                self.settings = json.load(f)
            print("[ORCHESTRATOR] Configuration files loaded successfully.")
        except json.JSONDecodeError as e:
            print(f"[FATAL ERROR] Failed to parse configuration JSON: {e}")
            sys.exit(1)
        except FileNotFoundError as e:
            print(f"[FATAL ERROR] Configuration file missing: {e}")
            sys.exit(1)

        # Persistence: SQLite Checkpointer
        conn = sqlite3.connect("research_state.db", check_same_thread=False)
        self.memory = SqliteSaver(conn)
        
        # Utilities
        self.source_manager = SourceManager(delay_ms=500)
        self.vector_store = VectorStore(persist_directory="./research_db")
        
        # Initialize Agents with Role-Specific LLMs
        print("[ORCHESTRATOR] Initializing specialized agents...")
        self.decompose_agent = DecomposeTopicAgent(self._get_llm("architect"), self.prompts)
        self.search_agent = InitialSearchAgent(self._get_llm("researcher"), self.prompts, self.source_manager)
        self.quality_agent = SourceQualityAgent(self._get_llm("auditor"), self.prompts)
        self.academic_agent = AcademicSpecialistAgent(self._get_llm("researcher"), self.prompts, self.source_manager)
        self.gap_agent = GapAnalyzerAgent(self._get_llm("auditor"), self.prompts)
        self.writer_agent = SectionWriterAgent(self._get_llm("writer"), self.prompts)
        
        self.workflow = self._build_graph()

    def _get_llm(self, role: str) -> ChatOpenAI:
        """Retrieves role-specific model and temperature from models.json."""
        role_cfg = self.model_config.get("roles", {}).get(role, {})
        model_id = role_cfg.get("model_id", self.settings.get("model_id"))
        temp = role_cfg.get("temperature", 0.2)
        
        print(f"[ORCHESTRATOR] Role '{role}' using model: {model_id} (temp: {temp})")
        
        return ChatOpenAI(
            model_name=model_id,
            openai_api_key=self.api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=temp
        )

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        
        # Define Nodes
        builder.add_node("decompose_node", self.decompose_node)
        builder.add_node("web_search_node", self.web_search_node)
        builder.add_node("academic_node", self.academic_node)
        builder.add_node("gap_analysis_node", self.gap_analysis_node)
        builder.add_node("synthesis_node", self.synthesis_node)
        
        # Define Edges
        builder.add_edge(START, "decompose_node")
        builder.add_edge("decompose_node", "web_search_node")
        builder.add_edge("web_search_node", "academic_node")
        builder.add_edge("academic_node", "gap_analysis_node")
        
        # Conditional Routing
        builder.add_conditional_edges(
            "gap_analysis_node", 
            self.should_continue, 
            {"continue": "web_search_node", "finish": "synthesis_node"}
        )
        
        builder.add_edge("synthesis_node", END)
        return builder.compile(checkpointer=self.memory)

    def should_continue(self, state: ResearchState) -> Literal["continue", "finish"]:
        if state["iteration_count"] >= state["max_iterations"]:
            print("[ORCHESTRATOR] Max iterations reached.")
            return "finish"
        if not state.get("identified_gaps") or len(state["identified_gaps"]) == 0:
            print("[ORCHESTRATOR] No gaps identified.")
            return "finish"
        return "continue"

    def decompose_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: PLANNING ---")
        questions = self.decompose_agent.run(state["research_topic"], state["user_constraints"])
        return {
            "research_questions": questions, 
            "logs": [f"Generated {len(questions)} questions."], 
            "iteration_count": 0, 
            "max_iterations": 2
        }

    def web_search_node(self, state: ResearchState) -> Dict:
        print(f"\n--- PHASE: WEB DISCOVERY (Iteration {state['iteration_count']}) ---")
        target = state["research_questions"]
        if state.get("identified_gaps"):
            target = [{"id": 99, "question": g, "priority": 1} for g in state["identified_gaps"]]

        candidates = self.search_agent.run(target)
        quality = self.quality_agent.run(candidates)
        
        for src in quality["sources"]:
            if src.get('score', 0) >= 0.5:
                self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "web"})
        
        return {
            "sources": quality["sources"], 
            "source_quality_avg": quality["average_score"], 
            "logs": [f"Web found {len(quality['sources'])} sources."]
        }

    def academic_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: ACADEMIC DEEP-DIVE ---")
        academic = self.academic_agent.run(state["research_questions"])
        for src in academic:
            self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "academic"})
        return {
            "sources": academic, 
            "logs": [f"Academic found {len(academic)} papers."]
        }

    def gap_analysis_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: GAP ANALYSIS ---")
        context_results = self.vector_store.query_sources(state["research_topic"], n_results=10)
        context = context_results.get('documents', [[]])[0]
        
        gaps = self.gap_agent.run(state["research_questions"], context)
        return {
            "identified_gaps": gaps, 
            "iteration_count": state["iteration_count"] + 1, 
            "logs": [f"Gaps identified: {len(gaps)}"]
        }

    def synthesis_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: SYNTHESIS ---")
        report_sections = []
        for q in state["research_questions"][:5]:
            fragments = self.vector_store.query_sources(q['question'], n_results=8).get('documents', [[]])[0]
            report_sections.append(f"## {q['question']}\n\n{self.writer_agent.run(q['question'], fragments)}")
        
        final_report = f"# {state['research_topic']}\n\n" + "\n\n".join(report_sections)
        return {"final_report": final_report, "is_complete": True}

    def run_full(self, initial_state: ResearchState):
        config = {"configurable": {"thread_id": self.thread_id}}
        return self.workflow.invoke(initial_state, config=config)
