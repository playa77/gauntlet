# Script Version: 0.2.1 | Phase 3: GUI Integration
# Description: Added max_gaps_allowed and search_depth parameters.

import json
import sys
import os
from pathlib import Path
from typing import Dict, Any

class SettingsManager:
    """
    Manages application settings, including roles and numeric parameters.
    """
    DEFAULT_SETTINGS = {
        "api_timeout": 360,
        "font_size": 14,
        "parameters": {
            "max_iterations": 3,              # Hard limit (Safety valve)
            "max_gaps_allowed": 0,            # Goal (Stop if gaps <= this)
            "search_depth": 1,                # Recursive search depth (1-3)
            "search_queries_per_question": 3,
            "search_results_per_query": 5,
            "min_quality_score": 0.6,
            "academic_papers_per_query": 5
        },
        "roles": {
            "architect": {"model_id": "google/gemini-2.0-flash-lite-preview-02-05:free", "temperature": 0.3},
            "researcher": {"model_id": "google/gemini-2.0-flash-lite-preview-02-05:free", "temperature": 0.2},
            "auditor": {"model_id": "google/gemini-2.0-flash-lite-preview-02-05:free", "temperature": 0.1},
            "writer": {"model_id": "google/gemini-2.0-flash-lite-preview-02-05:free", "temperature": 0.4}
        }
    }

    def __init__(self, filename="settings.json"):
        self.filepath = Path(filename)
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if not self.filepath.exists():
            self.save() 
            return
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                self._deep_update(self.settings, data)
                print(f"[SETTINGS] Configuration loaded from {self.filepath}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to load settings: {e}", file=sys.stderr)

    def _deep_update(self, base_dict, update_dict):
        for key, value in update_dict.items():
            if isinstance(value, dict) and key in base_dict:
                self._deep_update(base_dict[key], value)
            else:
                base_dict[key] = value

    def save(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.settings, f, indent=4)
            print(f"[SETTINGS] Configuration saved to {self.filepath}")
        except IOError as e:
            print(f"[ERROR] Failed to save settings: {e}", file=sys.stderr)

    def get(self, key, default=None):
        return self.settings.get(key, default)
    
    def get_param(self, key):
        return self.settings.get("parameters", {}).get(key)

    def get_role(self, role_name):
        return self.settings.get("roles", {}).get(role_name, {})

    def set(self, key, value):
        self.settings[key] = value
        self.save()

    def set_param(self, key, value):
        if "parameters" not in self.settings:
            self.settings["parameters"] = {}
        self.settings["parameters"][key] = value
        self.save()

    def set_role(self, role, model_id, temp):
        if "roles" not in self.settings:
            self.settings["roles"] = {}
        self.settings["roles"][role] = {"model_id": model_id, "temperature": temp}
        self.save()


class ModelManager:
    def __init__(self, filename="models.json"):
        self.filepath = Path(filename)
        self.models = []
        self.load()

    def load(self):
        if not self.filepath.exists():
            self.models = []
            return
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                self.models = data.get("models", [])
        except Exception as e:
            print(f"[ERROR] Failed to load models.json: {e}")
            self.models = []

    def save(self):
        data = {"models": self.models}
        try:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"[ERROR] Failed to save models.json: {e}")

    def get_all(self):
        return self.models

    def add_model(self, name, model_id):
        if any(m['id'] == model_id for m in self.models):
            return False
        self.models.append({"name": name, "id": model_id})
        self.save()
        return True

    def delete_model(self, model_id):
        self.models = [m for m in self.models if m['id'] != model_id]
        self.save()


class PromptManager:
    def __init__(self, filename="prompts.json"):
        self.filepath = Path(filename)
        self.prompts = {}
        self.load()

    def load(self):
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, "r") as f:
                self.prompts = json.load(f)
        except Exception as e:
            print(f"[ERROR] Failed to load prompts.json: {e}")

    def save(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.prompts, f, indent=2)
        except IOError as e:
            print(f"[ERROR] Failed to save prompts.json: {e}")

    def get(self, key):
        return self.prompts.get(key, {})

    def set(self, key, system, user_template):
        self.prompts[key] = {
            "system": system,
            "user_template": user_template
        }
        self.save()
