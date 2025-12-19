# Development Roadmap

## Phase 1: Agent Foundation (COMPLETED)
**Goal**: Build core agent roster with proper tools.
- Decompose Topic Agent
- Initial Search Agent (DuckDuckGo)
- Source Quality Agent (LLM Scoring)
- Academic Specialist Agent (arXiv, CrossRef, Semantic Scholar)
- Section Writer Agent (Synthesis)
- Source Manager (Rate-limiting, Deduplication, PDF Parsing)
- Manual Approval Gate (GUI Integration)

## Phase 2: LangGraph Orchestration (IN PROGRESS)
**Goal**: Implement proper graph-based workflow with cycles and quality gates.
- **Task 1**: Design Full StateGraph with nodes for all 13 agents.
- **Task 2**: Implement Phase 1 Subgraph (Exploration) with refinement loops.
- **Task 3**: Implement Phase 2 Subgraph (Deep Dive) with parallel specialist streams.
- **Task 4**: State Persistence (Save/Resume functionality).
- **Task 5**: Quality Gates (Automated re-research triggers).

## Phase 3: GUI Integration (UPCOMING)
**Goal**: Adapt interface for real-time research monitoring and steering.
- **Task 1**: Research Dashboard Sidebar (Metrics & Progress).
- **Task 2**: Live Research Journal (Filtered agent logs).
- **Task 3**: Steering Mechanism (Mid-research user guidance).
