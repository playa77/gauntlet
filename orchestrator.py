# Script Version: 0.9.4 | Phase 5: Polish & Depth Control
# Description: Updated to use multiple token trackers (one per role).

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
from utils import ModelTokenTracker

class ResearchOrchestrator:
    def __init__(self, thread_id: str = "default_research"):
        print(f"[ORCHESTRATOR] Initializing Phase 5 Workflow...")
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
        
        # Registry for all active trackers
        self.trackers = []
        
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
        
        # Create a specific tracker for this role instance
        tracker = ModelTokenTracker(role)
        self.trackers.append(tracker)
        
        return ChatOpenAI(
            model_name=model_id,
            openai_api_key=self.api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=temp,
            request_timeout=60.0,
            max_retries=2,
            model_kwargs=model_kwargs,
            callbacks=[tracker] 
        )

    def _collect_token_usage(self) -> Dict[str, Dict[str, int]]:
        """Aggregates usage from all role trackers."""
        total_delta = {}
        for tracker in self.trackers:
            delta = tracker.get_and_reset_delta()
            for key, counts in delta.items():
                if key not in total_delta:
                    total_delta[key] = counts.copy()
                else:
                    total_delta[key]["input"] += counts["input"]
                    total_delta[key]["output"] += counts["output"]
                    total_delta[key]["total"] += counts["total"]
        return total_delta

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
        pending_questions = [q for q in state.get("research_questions", []) if q.get("status") == "pending"]
        
        if not pending_questions:
            print("[ORCHESTRATOR] No pending questions left. Finishing.")
            return "finish"

        current_iter = state.get("iteration_count", 0)
        max_iter = self.settings.get("parameters", {}).get("max_iterations", 50)
        if current_iter >= max_iter:
            print(f"[ORCHESTRATOR] Hit global safety limit ({max_iter}). Finishing.")
            return "finish"

        print(f"[ORCHESTRATOR] {len(pending_questions)} questions pending. Continuing.")
        return "continue"

    def decompose_node(self, state: ResearchState) -> Dict:
        print(f"\n--- PHASE: PLANNING (Iteration {state.get('iteration_count', 0)}) ---")
        topic = state["research_topic"]
        current_questions = state.get("research_questions", [])
        
        result = {}
        
        if state.get("identified_gaps") and state.get("iteration_count", 0) > 0:
            gaps = state["identified_gaps"]
            new_questions_data = self.decompose_agent.generate_from_gaps(gaps)
            
            max_id = max([q['id'] for q in current_questions]) if current_questions else 0
            new_questions = []
            for nq in new_questions_data:
                parent_depth = 0
                related_q_id = nq.get("related_question_id")
                if related_q_id:
                    parent = next((q for q in current_questions if q['id'] == related_q_id), None)
                    if parent: parent_depth = parent.get("depth", 0)
                
                max_id += 1
                new_questions.append({
                    "id": max_id,
                    "question": nq["question"],
                    "priority": nq.get("priority", 2),
                    "status": "pending",
                    "depth": parent_depth + 1,
                    "parent_id": related_q_id
                })
            
            for q in current_questions:
                if q["status"] == "pending": q["status"] = "analyzed"
            
            result = {
                "research_questions": current_questions + new_questions,
                "logs": [f"Generated {len(new_questions)} follow-up questions from gaps."]
            }

        elif state.get("iteration_count", 0) == 0 and state.get("research_questions"):
            result = {
                "logs": ["Starting with manual plan."],
                "iteration_status": "Planning complete."
            }
        else:
            questions = self.decompose_agent.run(topic, state.get("user_constraints", {}))
            formatted_qs = []
            for i, q in enumerate(questions):
                formatted_qs.append({
                    "id": i + 1,
                    "question": q["question"],
                    "priority": q.get("priority", 1),
                    "status": "pending",
                    "depth": 0,
                    "parent_id": None
                })
            result = {
                "research_questions": formatted_qs, 
                "logs": [f"Generated {len(formatted_qs)} initial questions."]
            }
            
        result["token_usage"] = self._collect_token_usage()
        return result

    def web_search_node(self, state: ResearchState) -> Dict:
        print("\n--- BRANCH: WEB SEARCH ---")
        max_rounds = self.settings.get("parameters", {}).get("max_gap_iterations", 3)
        active_questions = [q for q in state["research_questions"] if q["status"] == "pending" and q["depth"] < max_rounds]
        
        if not active_questions:
            return {"logs": ["No active questions for search."], "token_usage": self._collect_token_usage()}

        search_depth_param = self.settings.get("parameters", {}).get("initial_search_depth", 2) if state.get("iteration_count", 0) == 0 else self.settings.get("parameters", {}).get("refinement_search_depth", 1)
        
        candidates = self.search_agent.run(active_questions, depth=search_depth_param)
        quality = self.quality_agent.run(candidates)
        
        min_score = self.settings.get("parameters", {}).get("min_quality_score", 0.6)
        for src in quality["sources"]:
            if src.get('score', 0) >= (min_score - 0.1):
                self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "web"})
        
        return {
            "sources": quality["sources"], 
            "source_quality_avg": quality["average_score"], 
            "logs": [f"Web branch searched {len(active_questions)} questions, found {len(quality['sources'])} sources."],
            "token_usage": self._collect_token_usage()
        }

    def academic_node(self, state: ResearchState) -> Dict:
        print("\n--- BRANCH: ACADEMIC SEARCH ---")
        max_rounds = self.settings.get("parameters", {}).get("max_gap_iterations", 3)
        active_questions = [q for q in state["research_questions"] if q["status"] == "pending" and q["depth"] < max_rounds]
        
        if not active_questions:
            return {"logs": ["Skipping academic search."], "token_usage": self._collect_token_usage()}

        search_depth_param = self.settings.get("parameters", {}).get("initial_search_depth", 2) if state.get("iteration_count", 0) == 0 else self.settings.get("parameters", {}).get("refinement_search_depth", 1)

        academic = self.academic_agent.run(active_questions, depth=search_depth_param)
        for src in academic:
            self.vector_store.add_source(src['snippet'], {"url": src['url'], "title": src['title'], "type": "academic"})
        
        return {
            "sources": academic, 
            "logs": [f"Academic branch found {len(academic)} papers."],
            "token_usage": self._collect_token_usage()
        }

    def knowledge_graph_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: KNOWLEDGE STRUCTURING ---")
        active_questions = [q for q in state["research_questions"] if q["status"] == "pending"]
        if not active_questions: 
            return {"token_usage": self._collect_token_usage()}
        
        combined_query = " ".join([q['question'] for q in active_questions])
        context_results = self.vector_store.query_sources(combined_query, n_results=15)
        fragments = context_results.get('documents', [[]])[0]
        entities = self.kg_agent.run(fragments)
        return {
            "structured_entities": entities,
            "logs": [f"Extracted {len(entities)} structured entities."],
            "token_usage": self._collect_token_usage()
        }

    def gap_analysis_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: GAP ANALYSIS ---")
        active_questions = [q for q in state["research_questions"] if q["status"] == "pending"]
        
        if not active_questions:
            return {
                "identified_gaps": [], 
                "iteration_count": state.get("iteration_count", 0) + 1,
                "token_usage": self._collect_token_usage()
            }

        context_results = self.vector_store.query_sources(state["research_topic"], n_results=10)
        context = context_results.get('documents', [[]])[0]
        
        gaps = self.gap_agent.run(active_questions, context)
        
        return {
            "identified_gaps": gaps, 
            "iteration_count": state.get("iteration_count", 0) + 1, 
            "logs": [f"Gaps identified: {len(gaps)}"],
            "token_usage": self._collect_token_usage()
        }

    def synthesis_node(self, state: ResearchState) -> Dict:
        print("\n--- PHASE: FINAL SYNTHESIS ---")
        report_sections = []
        all_questions = sorted(state["research_questions"], key=lambda x: x['id'])
        
        for q in all_questions:
            fragments = self.vector_store.query_sources(q['question'], n_results=8).get('documents', [[]])[0]
            section_text = self.writer_agent.run(q['question'], fragments)
            report_sections.append(f"## {q['question']}\n\n{section_text}")
        
        final_report = f"# {state['research_topic']}\n\n" + "\n\n".join(report_sections)
        return {
            "final_report": final_report, 
            "is_complete": True,
            "token_usage": self._collect_token_usage()
        }

    def run_stream(self, initial_state: ResearchState, recursion_limit: int = 50) -> Generator[Dict, None, None]:
        config = {"configurable": {"thread_id": self.thread_id}, "recursion_limit": recursion_limit}
        return self.workflow.stream(initial_state, config=config)

    def refine_question(self, question: str) -> List[str]:
        return self.refine_agent.run(question)

    def generate_report_now(self, state: ResearchState) -> str:
        result = self.synthesis_node(state)
        return result["final_report"]
