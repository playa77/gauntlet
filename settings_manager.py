# Script Version: 0.1.3 | Phase 0: Foundation
# Description: Manages application settings and model configurations for Gauntlet.

import json
import sys
from pathlib import Path

class SettingsManager:
    """
    Handles loading and saving of user settings to a local JSON file.
    """
    DEFAULT_SETTINGS = {
        "api_timeout": 360,
        "font_size": 15,
        "model_id": "google/gemini-2.0-flash-lite-preview-02-05:free"
    }

    def __init__(self, filename="settings.json"):
        self.filepath = Path(filename)
        self.settings = self.DEFAULT_SETTINGS.copy()
        self.load()

    def load(self):
        if not self.filepath.exists():
            return
        try:
            with open(self.filepath, "r") as f:
                data = json.load(f)
                self.settings.update(data)
                print(f"[SETTINGS] Configuration loaded from {self.filepath}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[WARNING] Failed to load settings: {e}", file=sys.stderr)

    def save(self):
        try:
            with open(self.filepath, "w") as f:
                json.dump(self.settings, f, indent=4)
            print(f"[SETTINGS] Configuration saved to {self.filepath}")
        except IOError as e:
            print(f"[ERROR] Failed to save settings: {e}", file=sys.stderr)

    def get(self, key):
        return self.settings.get(key, self.DEFAULT_SETTINGS.get(key))

    def set(self, key, value):
        self.settings[key] = value
        self.save()


class ModelManager:
    """
    Handles loading and saving of model definitions to models.json.
    """
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
                print(f"[MODELS] {len(self.models)} models loaded from {self.filepath}")
        except (json.JSONDecodeError, IOError) as e:
            print(f"[ERROR] Failed to load models.json: {e}", file=sys.stderr)
            self.models = []

    def save(self):
        data = {"models": self.models}
        try:
            with open(self.filepath, "w") as f:
                json.dump(data, f, indent=2)
        except IOError as e:
            print(f"[ERROR] Failed to save models.json: {e}", file=sys.stderr)

    def get_all(self):
        return self.models

    def add_model(self, name, model_id):
        for m in self.models:
            if m['id'] == model_id:
                return False
        self.models.append({"name": name, "id": model_id})
        self.save()
        return True
