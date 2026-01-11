# Script Version: 0.8.0 | Phase 4: Advanced Features
# Description: Orchestrator with dynamic depth and manual refinement support.

import os
import json
import sqlite3
import sys
from typing import Dict, List, Literal, Generator
from langgraph.graph import StateGraph, END, START
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

from state import ResearchState
from agents import (
    DecomposeTopicAgent, InitialSearchAgent, SourceQualityAgent, 
    AcademicSpecialistAgent, SectionWriterAgent, GapAnalyzerAgent,
    KnowledgeGraphAgent, RefineQuestionAgent
)
from source_manager import SourceManager
from vector_store import VectorStore
from settings_manager import SettingsManager, PromptManager

class ResearchOrchestrator:
    def __init__(self, thread_id: str = "default_research"):
        print(f"[ORCHESTRATOR] Initializing Phase 4 Workflow...")
        load_dotenv()
        self.thread_id = thread_id
        self.api_key = os.getenv("OPENROUTER_API_KEY")
        
        self.settings_manager = SettingsManager()
        self.prompt_manager = PromptManager()
        self.settings = self.settings_manager.settings
        self.prompts = self.prompt_manager.prompts

        conn = sqlite3.connect("research_state.db", check_same_thread=False)
        self.memory = SqliteSaver(conn)
        
        self.source_manager = SourceManager(delay_ms=500)
        self.vector_store = VectorStore(persist_directory="./research_db")
        
        self.decompose_agent = DecomposeTopicAgent(self._get_llm("architect"), self.prompts, self.settings)
        self.refine_agent = RefineQuestionAgent(self._get_llm("architect"), self.prompts, self.settings)
        self.search_agent = InitialSearchAgent(self._get_llm("researcher"), self.prompts, self.source_manager, self.settings)
        self.quality_agent = SourceQualityAgent(self._get_llm("auditor"), self.prompts, self.settings)
        self.academic_agent = AcademicSpecialistAgent(self._get_llm("researcher"), self.prompts, self.source_manager, self.settings)
        self.gap_agent = GapAnalyzerAgent(self._get_llm("auditor"), self.prompts, self.settings)
        self.kg_agent = KnowledgeGraphAgent(self._get_llm("architect"), self.prompts, self.settings)
        self.writer_agent = SectionWriterAgent(self._get_llm("writer"), self.prompts, self.settings)
        
        self.workflow = self._build_graph()

    def _get_llm(self, role: str) -> ChatOpenAI:
        role_cfg = self.settings.get("roles", {}).get(role, {})
        model_id = role_cfg.get("model_id", "google/gemini-2.0-flash-lite-preview-02-05:free")
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
        
        # 1. Hard Limit (Safety Valve)
        max_iter = self.settings.get("parameters", {}).get("max_iterations", 25)
        if current_iter >= max_iter:
            print(f"[ORCHESTRATOR] Hit max iterations ({max_iter}). Finishing.")
            return "finish"

        # 2. Goal Check (Gaps)
        max_gaps = self.settings.get("parameters", {}).get("max_gaps_allowed", 0)
        current_gaps = len(state.get("identified_gaps", []))
        
        if current_gaps <= max_gaps:
            print(f"[ORCHESTRATOR] Gaps ({current_gaps}) <= Allowable ({max_gaps}). Finishing.")
            return "finish"

        print(f"[ORCHESTRATOR] Gaps ({current_gaps}) > Allowable ({max_gaps}). Continuing.")
        return "continue"

    def decompose_node(self, state: ResearchState) -> Dict:
        print(f"\n--- PHASE: PLANNING (Iteration {state.get('iteration_count', 0)}) ---")
        topic = state["research_topic"]
        
        # If this is a gap-filling iteration, focus on gaps
        if state.get("identified_gaps") and state.get("iteration_count", 0) > 0:
            topic = f"{topic} (Focusing on gaps: {', '.join(state['identified_gaps'])})"
            questions = self.decompose_agent.run(topic, state.get("user_constraints", {}))
        elif state.get("iteration_count", 0) == 0 and state.get("research_questions"):
            # If initial iteration and questions already exist (from manual plan approval)
            questions = state["research_questions"]
        else:
            questions = self.decompose_agent.run(topic, state.get("user_constraints", {}))
            
        return {
            "research_questions": questions, 
            "logs": [f"Iteration {state.get('iteration_count', 0)}: Generated {len(questions)} questions."],
            "iteration_status": "Planning complete."
        }

    def web_search_node(self, state: ResearchState) -> Dict:
        print("\n--- BRANCH: WEB SEARCH ---")
        iter_count = state.get("iteration_count", 0)
        depth = self.settings.get("parameters", {}).get("initial_search_depth", 2) if iter_count == 0 else self.settings.get("parameters", {}).get("refinement_search_depth", 1)
        
        candidates = self.search_agent.run(state["research_questions"], depth=depth)
        quality = self.quality_agent.run(candidates)
        
        min_score = self.settings.get("parameters", {}).get("min_quality_score", 0.6)
        for src in quality["sources"]:
            if src.get('score', 0) >= (min_score - 0.1):
                self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "web"})
        
        return {
            "sources": quality["sources"], 
            "source_quality_avg": quality["average_score"], 
            "logs": [f"Web branch found {len(quality['sources'])} sources (Depth {depth})."]
        }

    def academic_node(self, state: ResearchState) -> Dict:
        print("\n--- BRANCH: ACADEMIC SEARCH ---")
        iter_count = state.get("iteration_count", 0)
        depth = self.settings.get("parameters", {}).get("initial_search_depth", 2) if iter_count == 0 else self.settings.get("parameters", {}).get("refinement_search_depth", 1)

        academic = self.academic_agent.run(state["research_questions"], depth=depth)
        for src in academic:
            self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "academic"})
        
        return {
            "sources": academic, 
            "logs": [f"Academic branch found {len(academic)} papers (Depth {depth})."]
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
            section_text = self.writer_agent.run(q['question'], fragments)
            report_sections.append(f"## {q['question']}\n\n{section_text}")
        
        final_report = f"# {state['research_topic']}\n\n" + "\n\n".join(report_sections)
        return {"final_report": final_report, "is_complete": True}

    def run_stream(self, initial_state: ResearchState, recursion_limit: int = 25) -> Generator[Dict, None, None]:
        config = {"configurable": {"thread_id": self.thread_id}, "recursion_limit": recursion_limit}
        return self.workflow.stream(initial_state, config=config)

    def refine_question(self, question: str) -> List[str]:
        """Directly calls the RefineQuestionAgent."""
        return self.refine_agent.run(question)

    def generate_report_now(self, state: ResearchState) -> str:
        """Manually triggers synthesis on the provided state."""
        result = self.synthesis_node(state)
        return result["final_report"]
