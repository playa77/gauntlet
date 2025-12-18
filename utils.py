# Script Version: 0.1.2 | Phase 0: Foundation
# Description: General-purpose utility functions for Gauntlet.

import sys
import os
import traceback
import json
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

def crash_handler(exctype, value, tb):
    """Global exception handler for uncaught exceptions."""
    print("\n[CRASH HANDLER] Uncaught Exception:", file=sys.stderr)
    traceback.print_exception(exctype, value, tb, file=sys.__stderr__)
    sys.exit(1)

def setup_project_files():
    """Ensures essential configuration files exist."""
    print("[INFO] Verifying project files...")
    
    # .env
    if not Path(".env").exists():
        print("[INFO] Creating .env placeholder.")
        with open(".env", "w") as f:
            f.write('OPENROUTER_API_KEY="YOUR_API_KEY_HERE"\n')

    # models.json
    if not Path("models.json").exists():
        print("[INFO] Creating default models.json.")
        default_models = {
            "models": [
                {"name": "Claude 3.5 Sonnet", "id": "anthropic/claude-3.5-sonnet"},
                {"name": "Claude 3.5 Haiku", "id": "anthropic/claude-3.5-haiku"},
                {"name": "GPT-4o", "id": "openai/gpt-4o"},
                {"name": "DeepSeek V3 (Free)", "id": "deepseek/deepseek-chat"}
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
            "model_id": "anthropic/claude-3.5-sonnet"
        }
        with open("settings.json", "w") as f:
            json.dump(default_settings, f, indent=4)

class EnvManager:
    """Helper to manage the .env file."""
    @staticmethod
    def get_api_key():
        if Path(".env").exists():
            with open(".env", "r") as f:
                for line in f:
                    if line.strip().startswith("OPENROUTER_API_KEY="):
                        parts = line.strip().split("=", 1)
                        if len(parts) == 2:
                            val = parts[1].strip().strip('"').strip("'")
                            return val
        return ""

class LogStream(QObject):
    """Redirects stdout to a PyQt signal."""
    log_signal = pyqtSignal(str)
    def write(self, text):
        if text.strip():
            self.log_signal.emit(str(text))
    def flush(self):
        pass
