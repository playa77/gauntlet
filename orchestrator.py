# Script Version: 0.1.2 | Phase 0: Foundation
# Description: LangGraph orchestrator for the research workflow.

import time
import os
from typing import Dict
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from duckduckgo_search import DDGS
from state import ResearchState

class ResearchOrchestrator:
    def __init__(self, model_id: str):
        print(f"[ORCHESTRATOR] Initializing with model: {model_id}")
        
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key or api_key == "YOUR_API_KEY_HERE":
            raise ValueError("OpenRouter API Key is not configured in .env")

        self.llm = ChatOpenAI(
            model_name=model_id,
            openai_api_key=api_key,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.7
        )
        
        self.workflow = self._build_graph()

    def _build_graph(self):
        builder = StateGraph(ResearchState)
        builder.add_node("search_node", self.search_node)
        builder.add_node("synthesis_node", self.synthesis_node)
        builder.set_entry_point("search_node")
        builder.add_edge("search_node", "synthesis_node")
        builder.add_edge("synthesis_node", END)
        return builder.compile()

    def search_node(self, state: ResearchState) -> Dict:
        topic = state["research_topic"]
        print(f"[AGENT] Searching for: {topic}")
        
        # Good netizen delay
        time.sleep(0.5)
        
        results = []
        try:
            with DDGS() as ddgs:
                # Convert generator to list immediately to avoid runtime issues
                search_results = list(ddgs.text(topic, max_results=5))
                for r in search_results:
                    results.append(f"Source: {r['href']}\nTitle: {r['title']}\nSnippet: {r['body']}")
        except Exception as e:
            print(f"[ERROR] Search failed: {e}")
            results = [f"Search failed: {str(e)}"]

        return {
            "sources": results,
            "logs": state["logs"] + [f"Found {len(results)} sources."],
            "current_phase": "exploration"
        }

    def synthesis_node(self, state: ResearchState) -> Dict:
        topic = state["research_topic"]
        sources_text = "\n\n".join(state["sources"])
        print(f"[AGENT] Synthesizing report for: {topic}")
        
        time.sleep(0.5)

        prompt = f"""
        You are a senior research analyst. Topic: {topic}
        Sources: {sources_text}
        
        Produce a detailed Markdown research report.
        """
        
        try:
            response = self.llm.invoke(prompt)
            report = response.content
        except Exception as e:
            report = f"Synthesis failed: {str(e)}"
        
        return {
            "final_report": report,
            "logs": state["logs"] + ["Synthesis complete."],
            "current_phase": "synthesis",
            "is_complete": True
        }

    def run(self, topic: str, model_id: str):
        initial_state = {
            "research_topic": topic,
            "user_constraints": {},
            "current_phase": "starting",
            "logs": [f"Starting research on: {topic}"],
            "sources": [],
            "final_report": "",
            "is_complete": False,
            "model_id": model_id
        }
        return self.workflow.invoke(initial_state)
