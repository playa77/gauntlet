# Script Version: 1.0.1
# Description: Automated build script for Gauntlet Deep Research.
# Usage: python build.py

import PyInstaller.__main__
import os
import shutil

def build():
    print("--- STARTING GAUNTLET BUILD PROCESS ---")
    
    # 1. Clean previous builds
    if os.path.exists("build"):
        shutil.rmtree("build")
    if os.path.exists("dist"):
        shutil.rmtree("dist")

    # 2. Define Build Arguments
    # Note: We do NOT bundle settings.json, .env, or models.json.
    # These are generated at runtime by utils.py to ensure security.
    
    args = [
        'gauntlet.py',                      # Main script
        '--name=GauntletResearch',          # Executable name
        '--noconsole',                      # Hide terminal
        '--clean',                          # Clean cache
        '--onedir',                         # Folder output
        
        # Collect heavy dependencies fully
        '--collect-all=chromadb',
        '--collect-all=langchain',
        '--collect-all=langgraph',
        '--collect-all=gradio_client',
        '--collect-all=uvicorn',
        
        # Explicit hidden imports
        '--hidden-import=tiktoken_ext.openai_public',
        '--hidden-import=chromadb.telemetry.product.posthog',
    ]

    print(f"Running PyInstaller with args: {args}")
    
    # 3. Run PyInstaller
    PyInstaller.__main__.run(args)
    
    print("\n--- BUILD COMPLETE ---")
    print("Executable is located in: dist/GauntletResearch/GauntletResearch.exe")

if __name__ == "__main__":
    build()
