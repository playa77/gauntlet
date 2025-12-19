# Script Version: 0.1.3 | Phase 0: Foundation
# Description: General-purpose utility functions for Gauntlet.

import sys
import os
import traceback
import json
from pathlib import Path
from PyQt6.QtCore import QObject, pyqtSignal

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

    # models.json
    if not Path("models.json").exists():
        print("[INFO] Creating default models.json.")
        default_models = {
            "models": [
                {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"},
                {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"},
                {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"},
                {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"},
                {"name": "Gemini 2.5 Flash Lite", "id": "google/gemini-2.5-flash-lite"}
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
            "model_id": "google/gemini-2.5-flash-lite"
        }
        with open("settings.json", "w") as f:
            json.dump(default_settings, f, indent=4)

class LogStream(QObject):
    """Redirects stdout to a PyQt signal for the Live Journal view."""
    log_signal = pyqtSignal(str)
    
    def write(self, text):
        if text.strip():
            self.log_signal.emit(str(text))
            
    def flush(self):
        pass
