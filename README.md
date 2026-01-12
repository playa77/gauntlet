# Gauntlet Deep Research

**Version:** 0.9.8  
**Phase:** 6 (Export & News Mode)

Gauntlet is a sophisticated, multi-agent research system designed to produce deep, comprehensive research reports. Unlike standard AI search tools that provide surface-level summaries, Gauntlet employs a graph-based orchestration of specialized agents to iteratively decompose topics, verify sources, analyze gaps, and synthesize findings into professional-grade documents (20-50 pages).

## Key Features

*   **Multi-Agent Architecture**: Powered by **LangGraph**, utilizing specialized agents for Planning, Web Search, Academic Research, Quality Auditing, and Writing.
*   **Iterative Deepening**: Automatically identifies information gaps and recursively performs follow-up research.
*   **News Mode & RSS**: Toggle "News Mode" to prioritize recent events, news APIs, and specific RSS feeds over general web results.
*   **Academic Rigor**: Dedicated agents for arXiv/Scholar integration and source quality scoring.
*   **Live Research Journal**: Watch the agents "think" and work in real-time via the PyQt6 GUI.
*   **Knowledge Graph**: Visualizes extracted entities and relationships.
*   **Export Options**: Generate reports in Markdown, PDF, or DOCX formats.
*   **Model Agnostic**: Configurable via OpenRouter to use various LLMs (Claude, GPT-4, Gemini, etc.).

## Installation

### Prerequisites
*   Python 3.11 or higher
*   An OpenRouter API Key (or OpenAI compatible key)

### Setup

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/yourusername/gauntlet-research.git
    cd gauntlet-research
    ```

2.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

3.  **Configure Environment:**
    The system will automatically generate a `.env` file on the first run. Open it and add your API key:
    ```env
    OPENROUTER_API_KEY="sk-or-..."
    ```

## Usage

Run the main application:

```bash
python gauntlet.py
```

1.  **Enter Topic**: Type your research topic in the top bar.
2.  **Select Mode**: Check "News Mode" if you want to focus on current events/RSS.
3.  **Generate Plan**: The system will decompose the topic into sub-questions.
4.  **Review & Approve**: Edit the research plan in the UI, then click "Approve & Research".
5.  **Monitor**: Watch the "Live Journal" as agents gather and synthesize data.
6.  **Export**: Go to the "Report" tab to copy Markdown or export to PDF/DOCX.

## Project Structure

*   **`gauntlet.py`**: Main entry point and UI controller.
*   **`orchestrator.py`**: LangGraph state machine managing agent workflows.
*   **`agents.py`**: Definitions for all specialized LangChain agents.
*   **`worker.py`**: Background thread handling the research loop to keep the UI responsive.
*   **`gui_*.py`**: Modularized UI components (Dialogs, Widgets, Tabs).
*   **`source_manager.py`**: Handles web scraping, PDF parsing, and RSS fetching with rate limiting.
*   **`vector_store.py`**: ChromaDB integration for persistent knowledge storage.
*   **`settings_manager.py`**: Manages `settings.json` and `models.json`.

## Configuration

*   **`settings.json`**: Adjust recursion limits, search depth, and font sizes.
*   **`models.json`**: Manage available LLM models.
*   **`prompts.json`**: Customize the system prompts for each agent.
