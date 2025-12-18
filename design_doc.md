## Design Document

### Vision Statement
Build "Gauntlet", a multi-agent research system that produces genuinely deep, comprehensive research documents—not 2-page summaries, but thorough 20-50 page reports that rival human research quality. The system should run for hours, iteratively deepening its understanding, and produce work that demonstrates real insight rather than surface-level synthesis.

### Core Philosophy
- **Quality over speed**: Research takes time. A 4-hour runtime for exceptional output is better than 10 minutes for mediocrity.
- **Iterative deepening**: Agents don't just "search once and synthesize"—they identify gaps, pursue threads, challenge their own findings, and recursively improve.
- **Graph-based orchestration**: Use LangGraph to model complex research workflows with cycles, feedback loops, and dynamic routing.
- **Human-in-the-loop refinement**: Leverage YaOG's proven UI patterns for monitoring progress, steering research direction, and editing outputs mid-process.
- **Source quality obsession**: Academic papers > expert blogs > news > forums. Always prioritize primary sources.

### Why MACR Failed (Lessons Learned)
1. **Too linear**: Search → Draft → Done doesn't produce depth
2. **No iteration**: Agents didn't revisit or challenge their work
3. **Shallow synthesis**: Combined sources without understanding them
4. **No verification**: Accepted search results at face value
5. **Wrong granularity**: One "research agent" is too coarse; need specialized sub-agents

### The New Approach: The Research Gauntlet v2

Instead of a simple pipeline, we build a **multi-phase research workflow** with built-in quality gates:

```
Phase 1: EXPLORATION (30-60 min)
├─ Topic decomposition
├─ Initial broad searches
├─ Source quality assessment
└─ Research question refinement

Phase 2: DEEP DIVE (90-180 min)
├─ Parallel specialist research streams
├─ Academic paper analysis
├─ Expert opinion synthesis
├─ Cross-referencing and fact-checking
└─ Gap identification → recursive research

Phase 3: SYNTHESIS (60-90 min)
├─ Outline generation with evidence mapping
├─ Section-by-section drafting
├─ Internal consistency checking
├─ Citation verification
└─ Iterative refinement

Phase 4: CRITIQUE & POLISH (30-60 min)
├─ Adversarial review (find weaknesses)
├─ Completeness audit
├─ Final fact-checking pass
└─ Professional formatting
```

Each phase has **quality gates**: if output doesn't meet standards, loop back.

### Key Differentiators from MACR

| MACR (Old) | Research Gauntlet v2 (New) |
|------------|---------------------------|
| Linear pipeline | Cyclical graph with feedback |
| Single research pass | Iterative deepening with gap analysis |
| Generic "research agent" | 8+ specialized agents with distinct roles |
| No quality checks | Quality gates between phases |
| Fixed workflow | Dynamic routing based on content needs |
| No human oversight | Real-time monitoring + intervention |
| Search results → draft | Source analysis → structured knowledge → synthesis |
| 2-page summaries | 20-50 page deep dives |

### User Experience

**Starting Research**:
1. User enters research topic/question in YaOG-style chat interface
2. System presents research plan with estimated phases and duration
3. User can accept, modify scope, or add constraints
4. Research begins with real-time phase/agent status updates

**During Research** (leveraging YaOG patterns):
- Sidebar shows: Current phase, active agents, sources found, progress metrics
- Main view: Live "research journal" showing agent reasoning and findings
- User can: Pause, add guidance ("focus more on X"), upload relevant docs, steer direction
- Branching: If user disagrees with a direction, can branch to alternative research path

**Output**:
- Full research document (Markdown) with proper citations
- Source database (all papers/articles with metadata)
- Research graph visualization (topics → subtopics → evidence)
- Export to PDF, DOCX, or continue editing

---


