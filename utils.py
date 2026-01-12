# Script Version: 0.3.6 | Phase 5: Polish & Depth Control
# Description: Updated ModelTokenTracker to track by Role + Model.

import sys
import os
import traceback
import json
import re
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal
from langchain_core.callbacks import BaseCallbackHandler

def crash_handler(exctype, value, tb):
    """Global exception handler for uncaught exceptions."""
    print("\n" + "!"*60)
    print("[CRASH HANDLER] Uncaught Exception Detected")
    print("!"*60)
    traceback.print_exception(exctype, value, tb, file=sys.__stderr__)
    sys.exit(1)

def setup_project_files():
    """Ensures essential configuration files exist with valid defaults."""
    print("[INFO] Verifying project environment...")
    
    # .env
    if not Path(".env").exists():
        print("[INFO] Creating .env placeholder.")
        with open(".env", "w") as f:
            f.write('OPENROUTER_API_KEY="YOUR_API_KEY_HERE"\n')
            f.write('ACTIVE_MODEL_ID="YOUR_MODEL_ID_HERE"\n')
    else:
        with open(".env", "r") as f:
            content = f.read()
        if "ACTIVE_MODEL_ID" not in content:
            with open(".env", "a") as f:
                f.write('ACTIVE_MODEL_ID="YOUR_MODEL_ID_HERE"\n')

    # models.json
    if not Path("models.json").exists():
        print("[INFO] Creating template models.json.")
        default_models = {
            "models": [
                {"name": "User Model 1", "id": "YOUR_MODEL_ID_HERE"}
            ]
        }
        with open("models.json", "w") as f:
            json.dump(default_models, f, indent=2)

    # settings.json
    if not Path("settings.json").exists():
        print("[INFO] Creating default settings.json.")
        default_settings = {
            "api_timeout": 360,
            "font_size": 15,
            "model_id": "YOUR_MODEL_ID_HERE"
        }
        with open("settings.json", "w") as f:
            json.dump(default_settings, f, indent=4)

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
