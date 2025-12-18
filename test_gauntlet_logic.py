# Script Version: 0.1.2 | Phase 0: Foundation
# Description: Verifies the research logic without the GUI.

import os
from dotenv import load_dotenv
from orchestrator import ResearchOrchestrator
from settings_manager import SettingsManager
from utils import setup_project_files

def test_research_flow():
    print("--- Gauntlet Logic Test v0.1.2 ---")
    setup_project_files()
    load_dotenv()
    
    settings = SettingsManager()
    model_id = settings.get("model_id")
    
    try:
        orchestrator = ResearchOrchestrator(model_id)
        topic = "The future of solid-state batteries in electric vehicles"
        print(f"[TEST] Running research on: {topic}")
        
        result = orchestrator.run(topic, model_id)
        
        print("\n--- Logs ---")
        for log in result['logs']:
            print(f"- {log}")
            
        if result['is_complete'] and len(result['final_report']) > 100:
            print("\n[SUCCESS] Phase 0 logic test passed.")
        else:
            print("\n[FAILURE] Report was not generated correctly.")
            
    except Exception as e:
        print(f"\n[CRASH] Test failed: {e}")

if __name__ == "__main__":
    test_research_flow()
