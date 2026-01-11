# Script Version: 0.6.0 | Phase 3: GUI Integration
# Description: Orchestrator updated to support streaming execution for GUI feedback.
# Implementation: Added run_stream method to yield node outputs incrementally.

import os
import json
import sqlite3
import sys
from typing import Dict, List, Literal, Generator
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI

from state import ResearchState
from agents import (
    DecomposeTopicAgent, InitialSearchAgent, SourceQualityAgent, 
    AcademicSpecialistAgent, SectionWriterAgent, GapAnalyzerAgent,
    KnowledgeGraphAgent
)
from source_manager import SourceManager
from vector_store import VectorStore

class ResearchOrchestrator:
    def __init__(self, thread_id: str = "default_research"):
        print(f"[ORCHESTRATOR] Initializing Phase 3 Workflow (Streaming Enabled)...")
        self.thread_id = thread_id
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        if not self.api_key:
            print("[ERROR] OPENROUTER_API_KEY not found.")
            sys.exit(1)

        try:
            with open("prompts.json", "r") as f: self.prompts = json.load(f)
            with open("models.json", "r") as f: self.model_config = json.load(f)
            with open("settings.json", "r") as f: self.settings = json.load(f)
        except Exception as e:
            print(f"[FATAL ERROR] Config load failed: {e}")
            sys.exit(1)

        conn = sqlite3.connect("research_state.db", check_same_thread=False)
        self.memory = SqliteSaver(conn)
        
        self.source_manager = SourceManager(delay_ms=500)
        self.vector_store = VectorStore(persist_directory="./research_db")
        
        # Agents
        self.decompose_agent = DecomposeTopicAgent(self._get_llm("architect"), self.prompts)
        self.search_agent = InitialSearchAgent(self._get_llm("researcher"), self.prompts, self.source_manager)
        self.quality_agent = SourceQualityAgent(self._get_llm("auditor"), self.prompts)
        self.academic_agent = AcademicSpecialistAgent(self._get_llm("researcher"), self.prompts, self.source_manager)
        self.gap_agent = GapAnalyzerAgent(self._get_llm("auditor"), self.prompts)
        self.kg_agent = KnowledgeGraphAgent(self._get_llm("architect"), self.prompts)
        self.writer_agent = SectionWriterAgent(self._get_llm("writer"), self.prompts)
        
        self.workflow = self._build_graph()

    def _get_llm(self, role: str) -> ChatOpenAI:
        role_cfg = self.model_config.get("roles", {}).get(role, {})
        model_id = role_cfg.get("model_id", self.settings.get("model_id"))
        temp = role_cfg.get("temperature", 0.2)
        
        model_kwargs = {"response_format": {"type": "json_object"}}
        
        return ChatOpenAI(
            model_name=model_id,
            openai_api_key=self.api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=temp,
            request_timeout=60.0,
            max_retries=2,
            model_kwargs=model_kwargs
        )

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        
        builder.add_node("decompose_node", self.decompose_node)
        builder.add_node("web_search_node", self.web_search_node)
        builder.add_node("academic_node", self.academic_node)
        builder.add_node("knowledge_graph_node", self.knowledge_graph_node)
        builder.add_node("gap_analysis_node", self.gap_analysis_node)
        builder.add_node("synthesis_node", self.synthesis_node)
        
        builder.add_edge(START, "decompose_node")
        builder.add_edge("decompose_node", "web_search_node")
        builder.add_edge("decompose_node", "academic_node")
        
        # Fan-In to Knowledge Graph
        builder.add_edge("web_search_node", "knowledge_graph_node")
        builder.add_edge("academic_node", "knowledge_graph_node")
        
        builder.add_edge("knowledge_graph_node", "gap_analysis_node")
        
        builder.add_conditional_edges(
            "gap_analysis_node", 
            self.should_continue, 
            {"continue": "decompose_node", "finish": "synthesis_node"}
        )
        
        builder.add_edge("synthesis_node", END)
        return builder.compile(checkpointer=self.memory)

    def should_continue(self, state: ResearchState) -> Literal["continue", "finish"]:
        current_iter = state.get("iteration_count", 0)
        max_iter = state.get("max_iterations", 2)
        
        if state.get("source_quality_avg", 0) < 0.6 and current_iter < max_iter:
            print(f"[ORCHESTRATOR] Quality Gate: Avg score {state.get('source_quality_avg')} too low. Retrying...")
            return "continue"
            
        if current_iter >= max_iter:
            return "finish"
        if not state.get("identified_gaps"):
            return "finish"
        return "continue"

    def decompose_node(self, state: ResearchState) -> Dict:
        print(f"\n--- PHASE: PLANNING (Iteration {state.get('iteration_count', 0)}) ---")
        topic = state["research_topic"]
        if state.get("identified_gaps"):
            topic = f"{topic} (Focusing on gaps: {', '.join(state['identified_gaps'])})"
            
        questions = self.decompose_agent.run(topic, state.get("user_constraints", {}))
        return {
            "research_questions": questions, 
            "logs": [f"Iteration {state.get('iteration_count', 0)}: Generated {len(questions)} questions."],
            "iteration_status": "Planning complete."
        }

    def web_search_node(self, state: ResearchState) -> Dict:
        print("\n--- BRANCH: WEB SEARCH ---")
        candidates = self.search_agent.run(state["research_questions"])
        quality = self.quality_agent.run(candidates)
        
        for src in quality["sources"]:
            if src.get('score', 0) >= 0.5:
                self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "web"})
        
        return {
            "sources": quality["sources"], 
            "source_quality_avg": quality["average_score"], 
            "logs": [f"Web branch found {len(quality['sources'])} sources."]
        }

    def academic_node(self, state: ResearchState) -> Dict:
        print("\n--- BRANCH: ACADEMIC SEARCH ---")
        academic = self.academic_agent.run(state["research_questions"])
        for src in academic:
            self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "academic"})
        
        return {
            "sources": academic, 
            "logs": [f"Academic branch found {len(academic)} papers."]
        }

    def knowledge_graph_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: KNOWLEDGE STRUCTURING ---")
        context_results = self.vector_store.query_sources(state["research_topic"], n_results=15)
        fragments = context_results.get('documents', [[]])[0]
        
        entities = self.kg_agent.run(fragments)
        return {
            "structured_entities": entities,
            "logs": [f"Extracted {len(entities)} structured entities."]
        }

    def gap_analysis_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: GAP ANALYSIS ---")
        context_results = self.vector_store.query_sources(state["research_topic"], n_results=10)
        context = context_results.get('documents', [[]])[0]
        
        gaps = self.gap_agent.run(state["research_questions"], context)
        return {
            "identified_gaps": gaps, 
            "iteration_count": state.get("iteration_count", 0) + 1, 
            "logs": [f"Gaps identified: {len(gaps)}"]
        }

    def synthesis_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: FINAL SYNTHESIS ---")
        report_sections = []
        for q in state["research_questions"][:5]:
            fragments = self.vector_store.query_sources(q['question'], n_results=8).get('documents', [[]])[0]
            report_sections.append(f"## {q['question']}\n\n{self.writer_agent.run(q['question'], fragments)}")
        
        final_report = f"# {state['research_topic']}\n\n" + "\n\n".join(report_sections)
        return {"final_report": final_report, "is_complete": True}

    def run_full(self, initial_state: ResearchState):
        """Blocking execution of the full graph."""
        config = {"configurable": {"thread_id": self.thread_id}}
        return self.workflow.invoke(initial_state, config=config)

    def run_stream(self, initial_state: ResearchState) -> Generator[Dict, None, None]:
        """Streaming execution yielding node outputs."""
        config = {"configurable": {"thread_id": self.thread_id}}
        return self.workflow.stream(initial_state, config=config)
