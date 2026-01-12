# Script Version: 1.0.0 | Phase 7: Production Release
# Description: Secure bootstrapping logic. Generates config files from internal defaults.

import sys
import os
import traceback
import json
import re
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from langchain_core.callbacks import BaseCallbackHandler

# --- FACTORY DEFAULTS (SECURE) ---
# These are compiled into the code. No external files are needed for defaults.

DEFAULT_ENV_TEMPLATE = """# Gauntlet Deep Research Configuration
# Created by Gauntlet v0.9.9
# ------------------------------------------------
# 1. Get an API Key from: https://openrouter.ai/keys
# 2. Paste it below inside the quotes.
# ------------------------------------------------
OPENROUTER_API_KEY=""
"""

DEFAULT_MODELS = {
  "models": [
    {
      "name": "Gemini 2.5 Flash Lite",
      "id": "google/gemini-2.5-flash-lite"
    },
    {
      "name": "Google: Gemini 3.0 Flash",
      "id": "google/gemini-3-flash-preview"
    }
  ]
}

DEFAULT_SETTINGS = {
    "api_timeout": 360,
    "font_size": 16,
    "parameters": {
        "max_iterations": 50,
        "max_gap_iterations": 3,
        "max_gaps_allowed": 0,
        "initial_search_depth": 2,
        "refinement_search_depth": 1,
        "search_queries_per_question": 3,
        "search_results_per_query": 5,
        "min_quality_score": 0.6,
        "academic_papers_per_query": 5
    },
    "roles": {
        "architect": {"model_id": "google/gemini-3-flash-preview", "temperature": 0.3},
        "researcher": {"model_id": "google/gemini-2.5-flash-lite", "temperature": 0.2},
        "auditor": {"model_id": "google/gemini-2.5-flash-lite", "temperature": 0.1},
        "writer": {"model_id": "google/gemini-3-flash-preview", "temperature": 0.4}
    },
    "news_feeds": []
}

DEFAULT_PROMPTS = {
  "decompose_topic": {
    "system": "You are a Senior Research Architect. Decompose the research topic into 5-10 specific, non-overlapping questions. Output ONLY valid JSON with no preamble. Format: {\"questions\": [{\"id\": 1, \"question\": \"...\", \"priority\": 3}]}. Priority scale: 1=foundational, 5=advanced.",
    "user_template": "Topic: {topic}\nConstraints: {constraints}\n\nJSON output:"
  },
  "gap_to_question": {
    "system": "You are a Research Strategist. Convert identified gaps into specific follow-up research questions. Output ONLY JSON: {\"questions\": [{\"related_question_id\": 1, \"question\": \"...\", \"priority\": 2}]}. Ensure you map the new question back to the related_question_id from the input.",
    "user_template": "Gaps:\n{gaps}\n\nGenerate follow-up questions in JSON:"
  },
  "refine_question": {
    "system": "You are a Research Supervisor. The user wants to refine a specific research question. Provide exactly 5 alternative variations that are more specific, broader, or focus on different angles. Output ONLY JSON: {\"options\": [\"Option 1\", \"Option 2\", \"Option 3\", \"Option 4\", \"Option 5\"]}",
    "user_template": "Original Question: {question}\n\nProvide 5 refined variations."
  },
  "search_query_generation": {
    "user_template": "Generate 3 diverse, highly specific search queries to answer this research question: '{question}'. Focus on finding academic papers and expert reports. Output ONLY JSON: {{\"queries\": [\"query1\", \"query2\"]}}"
  },
  "academic_keyword_extraction": {
    "system": "You are a Scholarly Librarian. Convert a research question into exactly 3 highly effective keywords for an academic database (arXiv). Focus on technical terms. Output ONLY JSON: {\"keywords\": \"keyword1 keyword2 keyword3\"}. Do NOT use sentences.",
    "user_template": "Question: {question}\n\nJSON output:"
  },
  "source_quality_assessment": {
    "user_template": "Evaluate the following source using this rubric:\n0.8-1.0: Peer-reviewed papers, government reports\n0.5-0.7: Expert blogs, reputable news\n0.0-0.4: Low quality\n\nOutput ONLY JSON: {{\"score\": 0.85, \"reason\": \"...\"}}\n\nURL: {url}\nTitle: {title}\nSnippet: {snippet}"
  },
  "knowledge_graph_extraction": {
    "system": "You are a Knowledge Engineer. Extract key entities and relationships. Output ONLY JSON: {\"triplets\": [{\"subject\": \"...\", \"predicate\": \"...\", \"object\": \"...\"}]}",
    "user_template": "Context: {context}\n\nJSON output:"
  },
  "gap_analysis": {
    "system": "You are a Senior Research Auditor. Identify specific gaps where information is missing. Output ONLY JSON: {\"gaps\": [{\"related_question_id\": 1, \"description\": \"...\"}]}. You MUST include the related_question_id for each gap.",
    "user_template": "Original Questions:\n{questions}\n\nRetrieved Knowledge:\n{context}\n\nJSON output:"
  },
  "section_writer": {
    "system": "You are a Professional Research Synthesizer. Write a detailed, formal research section (1000-1500 words). Output ONLY JSON: {\"section_text\": \"...markdown content...\"}",
    "user_template": "Research Question: {question}\n\nKnowledge Fragments:\n{fragments}"
  }
}

def crash_handler(exctype, value, tb):
    """Global exception handler for uncaught exceptions."""
    print("\n" + "!"*60)
    print("[CRASH HANDLER] Uncaught Exception Detected")
    print("!"*60)
    traceback.print_exception(exctype, value, tb, file=sys.__stderr__)
    sys.exit(1)

def bootstrap_configuration():
    """
    Checks for configuration files in the application directory.
    If missing, generates them from the internal defaults defined above.
    """
    print("[BOOTSTRAP] Verifying configuration...")
    
    # Determine the directory where the executable/script is located
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.abspath(__file__))

    # Helper to write JSON safely
    def write_json(filename, data):
        path = os.path.join(app_dir, filename)
        if not os.path.exists(path):
            print(f"[BOOTSTRAP] Generating default {filename}...")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"[ERROR] Could not write {filename}: {e}")

    # Helper to write Text safely
    def write_text(filename, content):
        path = os.path.join(app_dir, filename)
        if not os.path.exists(path):
            print(f"[BOOTSTRAP] Generating default {filename}...")
            try:
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception as e:
                print(f"[ERROR] Could not write {filename}: {e}")

    # Execute Bootstrapping
    write_text(".env", DEFAULT_ENV_TEMPLATE)
    write_json("settings.json", DEFAULT_SETTINGS)
    write_json("models.json", DEFAULT_MODELS)
    write_json("prompts.json", DEFAULT_PROMPTS)

def extract_json_from_text(text: str):
    """Robustly extracts JSON from a string."""
    try:
        match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text)
        if match:
            return json.loads(match.group(1))
        
        list_match = re.search(r'\[\s*\{.*\}\s*\]', text, re.DOTALL)
        if list_match:
            return json.loads(list_match.group(0))
            
        obj_match = re.search(r'\{.*\}', text, re.DOTALL)
        if obj_match:
            return json.loads(obj_match.group(0))

        return json.loads(text)
    except json.JSONDecodeError:
        print(f"[WARNING] JSON extraction failed for text: {text[:100]}...")
        return None

class LogStream(QObject):
    """Redirects stdout to a PyQt signal for the Live Journal view."""
    log_signal = pyqtSignal(str)
    
    def write(self, text):
        if text.strip():
            self.log_signal.emit(str(text))
            
    def flush(self):
        pass

class ModelTokenTracker(BaseCallbackHandler):
    """Tracks token usage per role and model."""
    def __init__(self, role_name: str):
        self.role_name = role_name
        self.delta_usage = {} # Reset after every node read

    def on_llm_end(self, response, **kwargs):
        if response.llm_output and "token_usage" in response.llm_output:
            usage = response.llm_output["token_usage"]
            model = response.llm_output.get("model_name", "unknown_model")
            
            # Composite key to distinguish roles using the same model
            key = f"Role: {self.role_name} | Model: {model}"
            
            if key not in self.delta_usage:
                self.delta_usage[key] = {"input": 0, "output": 0, "total": 0}
            
            self.delta_usage[key]["input"] += usage.get("prompt_tokens", 0)
            self.delta_usage[key]["output"] += usage.get("completion_tokens", 0)
            self.delta_usage[key]["total"] += usage.get("total_tokens", 0)

    def get_and_reset_delta(self):
        """Returns accumulated usage since last call and resets."""
        data = self.delta_usage.copy()
        self.delta_usage = {}
        return data
