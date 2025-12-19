# Script Version: 0.2.4 | Phase 1: Agent Foundation
# Description: LangGraph orchestrator managing the full Phase 1 linear workflow.
# Implementation: Added synthesis_node and integrated SectionWriterAgent.

import os
from typing import Dict, List
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from state import ResearchState
from agents import (
    DecomposeTopicAgent, 
    InitialSearchAgent, 
    SourceQualityAgent, 
    AcademicSpecialistAgent,
    SectionWriterAgent
)
from source_manager import SourceManager
from vector_store import VectorStore

class ResearchOrchestrator:
    def __init__(self, model_id: str):
        print(f"[ORCHESTRATOR] Initializing Full Phase 1 Workflow | Model: {model_id}")
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            raise ValueError("OpenRouter API Key is not configured in .env file.")

        self.llm = ChatOpenAI(
            model_name=model_id,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.2
        )
        
        # Initialize Utilities
        self.source_manager = SourceManager(delay_ms=500)
        self.vector_store = VectorStore(persist_directory="./research_db")
        
        # Initialize Agents
        self.decompose_agent = DecomposeTopicAgent(self.llm)
        self.search_agent = InitialSearchAgent(self.llm, self.source_manager)
        self.quality_agent = SourceQualityAgent(self.llm)
        self.academic_agent = AcademicSpecialistAgent(self.llm, self.source_manager)
        self.writer_agent = SectionWriterAgent(self.llm)
        
        self.workflow = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        
        # Define Nodes
        builder.add_node("decompose_node", self.decompose_node)
        builder.add_node("web_search_node", self.web_search_node)
        builder.add_node("academic_node", self.academic_node)
        builder.add_node("synthesis_node", self.synthesis_node)
        
        # Define Linear Flow
        builder.set_entry_point("decompose_node")
        builder.add_edge("decompose_node", "web_search_node")
        builder.add_edge("web_search_node", "academic_node")
        builder.add_edge("academic_node", "synthesis_node")
        builder.add_edge("synthesis_node", END)
        
        return builder.compile()

    def decompose_node(self, state: ResearchState) -> Dict:
        print("[ORCHESTRATOR] Node: Decompose Topic")
        questions = self.decompose_agent.run(state["research_topic"], state["user_constraints"])
        return {
            "research_questions": questions,
            "logs": state["logs"] + [f"Generated {len(questions)} research questions."],
            "current_phase": "planning"
        }

    def web_search_node(self, state: ResearchState) -> Dict:
        print("[ORCHESTRATOR] Node: Web Discovery")
        candidates = self.search_agent.run(state["research_questions"])
        qualified = self.quality_agent.run(candidates)
        
        for src in qualified:
            self.vector_store.add_source(
                src['snippet'], 
                {"url": src['url'], "title": src['title'], "type": "web"}
            )
            
        return {
            "sources": qualified,
            "logs": state["logs"] + [f"Web discovery found {len(qualified)} sources."],
            "current_phase": "exploration"
        }

    def academic_node(self, state: ResearchState) -> Dict:
        print("[ORCHESTRATOR] Node: Academic Deep-Dive")
        academic_sources = self.academic_agent.run(state["research_questions"])
        
        for src in academic_sources:
            self.vector_store.add_source(
                src['snippet'], 
                {"url": src['url'], "title": src['title'], "type": "academic"}
            )
            
        return {
            "sources": state["sources"] + academic_sources,
            "logs": state["logs"] + [f"Academic deep-dive found {len(academic_sources)} papers."],
            "current_phase": "deep_dive"
        }

    def synthesis_node(self, state: ResearchState) -> Dict:
        print("[ORCHESTRATOR] Node: Synthesis")
        report_sections = []
        
        # Process top 3 questions for the Phase 1 summary
        for q in state["research_questions"][:3]:
            # Query vector store for context
            context_results = self.vector_store.query_sources(q['question'], n_results=5)
            fragments = context_results.get('documents', [[]])[0]
            
            section_content = self.writer_agent.run(q['question'], fragments)
            report_sections.append(f"## {q['question']}\n\n{section_content}")
            
        final_report = f"# Research Report: {state['research_topic']}\n\n"
        final_report += "\n\n".join(report_sections)
        
        return {
            "final_report": final_report,
            "logs": state["logs"] + ["Synthesis complete. Final report generated."],
            "current_phase": "synthesis",
            "is_complete": True
        }

    def run_full(self, initial_state: ResearchState):
        """Executes the compiled workflow."""
        return self.workflow.invoke(initial_state)

    def plan_only(self, topic: str):
        """Helper for the GUI to just run the decomposition."""
        return self.decompose_agent.run(topic)
