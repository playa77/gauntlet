## Getting Started - Week 1 Action Plan

### Day 1-2: Repository Setup
1. Create new repo: `deep-research-synthesizer`
2. Copy YaOG codebase as base
3. Strip out: conversation history, message editing, regeneration
4. Keep: settings, model management, file upload, markdown rendering
5. Update README with new project description
6. Set up development environment

### Day 3-4: Core Dependencies
1. Install: `langgraph`, `langchain`, `chromadb`, `pypdf2`
2. Create basic state object: `ResearchState`
3. Implement minimal LangGraph (linear: input → search → write → output)
4. Test: "Explain quantum computing" → generates 1-page summary

### Day 5: First Agent
1. Implement `DecomposeTopicAgent`
2. Prompt engineering: topic string → 5 research questions
3. Test with 10 diverse topics
4. Verify output quality

### Day 6: Integration Test
1. Connect agent to GUI
2. User enters topic → shows generated questions
3. Manual approval step (button)
4. Commit: "Week 1 - Foundation complete"

### Day 7: Planning
1. Review Week 2 roadmap
2. Design `InitialSearchAgent` architecture
3. Research web search API options
4. Prepare for Phase 1 sprint
