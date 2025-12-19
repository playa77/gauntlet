# Script Version: 0.2.1 | Phase 1: Agent Foundation
# Description: LangGraph orchestrator managing the multi-agent workflow.

import os
from typing import Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI

from state import ResearchState
from agents import DecomposeTopicAgent

class ResearchOrchestrator:
    def __init__(self, model_id: str):
        print(f"[ORCHESTRATOR] Initializing Phase 1 with model: {model_id}")
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            raise ValueError("OpenRouter API Key is not configured in .env file.")

        self.llm = ChatOpenAI(
            model_name=model_id,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.2 # Low temperature for structural decomposition
        )
        
        # Initialize Agents
        self.decompose_agent = DecomposeTopicAgent(self.llm)
        
        self.workflow = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        
        # Define Nodes
        builder.add_node("decompose_node", self.decompose_node)
        builder.add_node("search_node", self.search_node_placeholder)
        
        # Define Flow
        builder.set_entry_point("decompose_node")
        builder.add_edge("decompose_node", "search_node")
        builder.add_edge("search_node", END)
        
        return builder.compile()

    def decompose_node(self, state: ResearchState) -> Dict:
        """Node to break down the topic into research questions."""
        print("[ORCHESTRATOR] Entering Decompose Node...")
        questions = self.decompose_agent.run(state["research_topic"], state["user_constraints"])
        
        # Initialize question status
        for q in questions:
            q["status"] = "pending"
            
        return {
            "research_questions": questions,
            "logs": state["logs"] + [f"Decomposed topic into {len(questions)} questions."],
            "current_phase": "exploration"
        }

    def search_node_placeholder(self, state: ResearchState) -> Dict:
        """Temporary placeholder for the Phase 2 search agent integration."""
        print("[ORCHESTRATOR] Search node reached (Phase 1 Placeholder)")
        
        # Construct a simple summary for the UI preview
        summary = f"# Research Plan: {state['research_topic']}\n\n"
        summary += "## Identified Research Questions\n\n"
        for q in state["research_questions"]:
            summary += f"- **Priority {q.get('priority', 'N/A')}**: {q.get('question', 'N/A')}\n"
            
        return {
            "logs": state["logs"] + ["Search phase initiated (Placeholder)."],
            "is_complete": True,
            "final_report": summary
        }

    def run(self, topic: str, model_id: str):
        initial_state = {
            "research_topic": topic,
            "user_constraints": {},
            "current_phase": "starting",
            "logs": [f"Starting Phase 1 research on: {topic}"],
            "research_questions": [],
            "sources": [],
            "knowledge_fragments": [],
            "final_report": "",
            "is_complete": False,
            "model_id": model_id
        }
        return self.workflow.invoke(initial_state)
