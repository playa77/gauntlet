# Gauntlet Action Plan - Phase 2: Orchestration

## Phase 2: LangGraph Orchestration (Weeks 4-5)
**Goal**: Implement a non-linear, cyclical research workflow with quality gates.

### Day 1-2: Graph Architecture
1. Define the full `StateGraph` structure in `orchestrator.py`.
2. Implement conditional routing logic (e.g., "Should we search more?").
3. Create the `Exploration` subgraph (Decompose -> Search -> Assess -> Refine loop).

### Day 3-4: Quality Gates & Feedback
1. Implement `SourceQualityAgent` as a gatekeeper node.
2. If source quality average < 0.7, trigger the `InitialSearchAgent` with refined queries.
3. Implement `GapAnalyzerAgent` to identify missing information before synthesis.

### Day 5: Persistence & Checkpoints
1. Integrate LangGraph's `SqliteSaver` for state persistence.
2. Enable the system to resume research after a crash or manual pause.
3. Test state recovery via the GUI.

### Day 6: Deep Dive Subgraph
1. Implement parallel execution for `AcademicSpecialistAgent` and `ExpertOpinionAgent`.
2. Route findings from both into a unified `KnowledgeGraph` update node.

### Day 7: Integration & Verification
1. Connect the cyclical graph to the PyQt6 "Live Journal".
2. Verify that the "Approve & Research" button correctly enters the graph entry point.
3. Run end-to-end test: "The impact of 6G on rural IoT infrastructure."
