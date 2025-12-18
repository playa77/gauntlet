## Technical Specification

### System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    YaOG-Based GUI Layer                      │
│  (PyQt6 + QWebEngine - adapted for research monitoring)     │
└─────────────────────┬───────────────────────────────────────┘
                      │
┌─────────────────────▼───────────────────────────────────────┐
│              Research Orchestrator (LangGraph)               │
│  State machine managing phases, routing, quality gates      │
└─────────────────────┬───────────────────────────────────────┘
                      │
        ┌─────────────┼─────────────┬─────────────┐
        │             │             │             │
┌───────▼──────┐ ┌───▼────────┐ ┌──▼─────────┐ ┌▼──────────────┐
│   Agent      │ │  Knowledge │ │  Source    │ │  Output       │
│   Pool       │ │   Graph    │ │  Manager   │ │  Generator    │
│  (LangChain) │ │ (ChromaDB) │ │ (Web,PDF)  │ │  (Markdown)   │
└──────────────┘ └────────────┘ └────────────┘ └───────────────┘
```

### Component Specifications

#### 1. Research Orchestrator (LangGraph StateGraph)

**Core State Object**:
```python
class ResearchState(TypedDict):
    # Input
    research_topic: str
    user_constraints: Dict[str, Any]
    
    # Phase tracking
    current_phase: str  # "exploration", "deep_dive", "synthesis", "critique"
    phase_iteration: int
    
    # Knowledge accumulation
    research_questions: List[str]
    sources: List[Source]  # Papers, articles, etc.
    knowledge_fragments: List[KnowledgeFragment]
    outline: Optional[Outline]
    
    # Document building
    document_sections: Dict[str, str]  # section_id -> markdown content
    citations: List[Citation]
    
    # Quality metrics
    completeness_score: float
    source_quality_score: float
    coherence_score: float
    
    # Control flow
    needs_more_research: bool
    identified_gaps: List[str]
    
    # Human interaction
    user_feedback: Optional[str]
    paused: bool
```

**Graph Structure**:
```python
# Phase 1: EXPLORATION
graph.add_node("decompose_topic", decompose_topic_agent)
graph.add_node("initial_search", initial_search_agent)
graph.add_node("assess_sources", source_quality_agent)
graph.add_node("refine_questions", question_refinement_agent)

# Phase 2: DEEP DIVE
graph.add_node("academic_research", academic_specialist_agent)
graph.add_node("expert_analysis", expert_opinion_agent)
graph.add_node("cross_reference", fact_checker_agent)
graph.add_node("identify_gaps", gap_analyzer_agent)

# Phase 3: SYNTHESIS
graph.add_node("create_outline", outline_generator_agent)
graph.add_node("draft_section", section_writer_agent)
graph.add_node("check_coherence", coherence_checker_agent)

# Phase 4: CRITIQUE
graph.add_node("adversarial_review", critic_agent)
graph.add_node("completeness_audit", completeness_agent)
graph.add_node("final_polish", polish_agent)

# Quality gates (conditional routing)
graph.add_conditional_edges(
    "assess_sources",
    lambda state: "deep_dive" if state["source_quality_score"] > 0.7 
                  else "initial_search"
)

graph.add_conditional_edges(
    "identify_gaps",
    lambda state: "academic_research" if state["identified_gaps"] 
                  else "create_outline"
)

# Human intervention points
graph.add_node("human_checkpoint", human_review_node)
graph.add_edge("refine_questions", "human_checkpoint")
graph.add_edge("create_outline", "human_checkpoint")
```

#### 2. Agent Specifications

Each agent is a LangChain chain with specific tools and prompts:

**A. Decompose Topic Agent**
- **Role**: Break research topic into 5-10 sub-questions
- **Tools**: None (pure reasoning)
- **Output**: List of research questions with priorities
- **Quality metric**: Questions should be specific, answerable, non-overlapping

**B. Initial Search Agent**
- **Role**: Broad search to understand landscape
- **Tools**: `web_search`, `web_fetch`
- **Strategy**: 
  - 3-5 searches per sub-question
  - Prioritize .edu, .gov, known journals
  - Extract key terms for deeper searches
- **Output**: 20-50 candidate sources with quality ratings

**C. Source Quality Agent**
- **Role**: Evaluate source credibility and relevance
- **Scoring criteria**:
  - Primary vs secondary source
  - Author credentials
  - Publication venue quality
  - Recency (weighted by topic)
  - Citation count (for papers)
- **Output**: Filtered source list (top 60%) + quality scores

**D. Question Refinement Agent**
- **Role**: Based on initial findings, refine/expand research questions
- **Strategy**: Identify what's well-covered vs. gaps
- **Output**: Updated question list with depth indicators

**E. Academic Specialist Agent**
- **Role**: Deep dive into scholarly sources
- **Tools**: `web_search` (site:scholar.google.com), `web_fetch`, PDF extraction
- **Strategy**:
  - Find 5-10 key papers per sub-question
  - Extract methodology, findings, limitations
  - Map citation networks (what do papers cite?)
- **Output**: Academic knowledge fragments with metadata

**F. Expert Opinion Agent**
- **Role**: Find domain expert perspectives (blogs, interviews, talks)
- **Tools**: `web_search`, `web_fetch`
- **Strategy**: 
  - Identify recognized experts in field
  - Find their recent writings/statements
  - Extract nuanced takes not in papers
- **Output**: Expert perspective fragments

**G. Fact Checker Agent**
- **Role**: Verify claims across sources
- **Strategy**:
  - Identify factual claims in accumulated knowledge
  - Cross-reference across 3+ sources
  - Flag contradictions
  - Search for disconfirming evidence
- **Output**: Verified facts + confidence scores + contradictions

**H. Gap Analyzer Agent**
- **Role**: Identify what's still missing
- **Strategy**:
  - Compare research questions to accumulated knowledge
  - Identify thin areas
  - Suggest specific searches to fill gaps
- **Output**: Gap report → triggers recursive research or moves forward

**I. Outline Generator Agent**
- **Role**: Create document structure with evidence mapping
- **Strategy**:
  - Analyze knowledge graph for natural groupings
  - Create hierarchical outline (3-4 levels deep)
  - Map which sources/fragments support each section
  - Ensure logical flow
- **Output**: Detailed outline with evidence pointers

**J. Section Writer Agent**
- **Role**: Draft individual document sections
- **Input**: Outline section + relevant knowledge fragments + citations
- **Strategy**:
  - Write 1000-2000 words per section
  - Integrate multiple sources smoothly
  - Proper academic tone
  - Inline citations
- **Output**: Polished section with citations

**K. Coherence Checker Agent**
- **Role**: Ensure document flows and is internally consistent
- **Strategy**:
  - Check for contradictions between sections
  - Verify terminology consistency
  - Assess logical flow
  - Suggest transitions
- **Output**: Coherence report + suggested edits

**L. Critic Agent**
- **Role**: Adversarial review to find weaknesses
- **Strategy**:
  - "What would an expert critic say?"
  - Identify unsupported claims
  - Find logical gaps
  - Check for biases
- **Output**: Critique report → triggers revisions if serious issues

**M. Completeness Agent**
- **Role**: Final audit of research coverage
- **Strategy**:
  - Cross-check original questions vs. document
  - Verify all claims have citations
  - Check citation formatting
  - Ensure no orphaned sections
- **Output**: Completeness score + required fixes

**N. Polish Agent**
- **Role**: Final formatting and readability
- **Strategy**:
  - Fix formatting inconsistencies
  - Add executive summary
  - Create table of contents
  - Professional layout
- **Output**: Publication-ready document

#### 3. Knowledge Graph (ChromaDB)

**Collections**:
1. **`sources`**: All retrieved documents/papers
   - Metadata: URL, title, author, date, quality_score, source_type
   - Embeddings: Full text (chunked for long docs)

2. **`knowledge_fragments`**: Extracted insights
   - Content: Specific claim, fact, or insight
   - Metadata: source_ids (list), research_question_id, confidence, verification_status
   - Embeddings: Fragment text

3. **`document_sections`**: Draft content
   - Content: Section markdown
   - Metadata: outline_position, cited_fragments, draft_version
   - Embeddings: Section text

**Query Patterns**:
- "Find all fragments related to research question X"
- "What sources discuss topic Y?"
- "Which fragments support claim Z?"
- "Are there contradicting fragments about Q?"

#### 4. Source Manager

**Responsibilities**:
- Execute web searches with retry logic
- Fetch and cache web pages
- Extract text from PDFs (pypdf2, pdfplumber)
- Rate limiting to respect robots.txt
- Source deduplication

**API**:
```python
class SourceManager:
    def search(self, query: str, filters: Dict) -> List[SearchResult]
    def fetch_url(self, url: str) -> Document
    def extract_pdf(self, url: str) -> Document
    def get_cached(self, url: str) -> Optional[Document]
    def assess_quality(self, source: Source) -> float
```

#### 5. Output Generator

**Formats**:
- **Markdown** (primary): Full document with proper heading hierarchy
- **JSON**: Structured export with metadata
- **HTML**: For preview in YaOG web view
- **PDF** (via markdown → pandoc): Publication quality

**Citation Styles**:
- APA, MLA, Chicago (user selectable)
- Inline citations + bibliography
- Hyperlinked citations in HTML/PDF

### Modified YaOG Interface

**New UI Components**:

1. **Research Dashboard Sidebar** (replaces conversation history):
   ```
   [Research Topic]
   
   PHASE: Deep Dive (2/4)
   TIME: 1h 23m / ~4h
   
   Active Agents:
   ✓ Academic Specialist
   ⟳ Fact Checker
   
   Progress:
   Sources Found: 47
   Knowledge Fragments: 203
   Document: 35% complete
   Quality Score: 8.2/10
   
   [Pause] [Steer] [View Sources]
   ```

2. **Live Research Journal** (main view):
   - Real-time agent logs (filtered by verbosity)
   - Show reasoning: "Searching for papers on X because..."
   - Source discoveries with thumbnails
   - Phase transitions with summaries

3. **Document Editor Tab**:
   - Live preview of generated document
   - Inline editing (syncs back to knowledge graph)
   - Section-by-section approval workflow
   - Citation manager

4. **Source Explorer Tab**:
   - List of all sources with quality scores
   - Click to view full content
   - Manual source addition (user uploads)
   - Source graph visualization

5. **Research Graph Visualization**:
   - Topic → Questions → Sources → Fragments → Document
   - Interactive D3.js or NetworkX rendering
   - Click nodes to explore

**Interaction Patterns**:

- **Steering**: "Focus more on economic impacts" → adds weight to that research question
- **Branching**: "Explore alternative: environmental perspective" → creates parallel research thread
- **Human checkpoints**: System pauses at outline stage, asks "Approve this structure?"
- **Live editing**: User fixes section → agent incorporates feedback in next iteration

### Technology Stack

**Core**:
- Python 3.11+
- PyQt6 (GUI, reuse YaOG architecture)
- LangChain (agent primitives)
- LangGraph (workflow orchestration)
- ChromaDB (vector storage)

**LLM**:
- OpenRouter API (maintain YaOG's model flexibility)
- Primary: Claude Sonnet 4 (best reasoning for research)
- Fallback: GPT-4o, Gemini Pro

**Search & Retrieval**:
- Web search via Anthropic's web_search tool (if available via OpenRouter)
- Backup: SerpAPI or custom Google Scholar scraping
- PDF extraction: pypdf2, pdfplumber, pymupdf
- HTML parsing: BeautifulSoup4, trafilatura

**Data & Storage**:
- SQLite (research projects, metadata)
- ChromaDB (vector embeddings)
- File system (cached sources, generated documents)

**Visualization**:
- D3.js (graph rendering in QWebEngine)
- Matplotlib/Plotly (metrics visualization)

**Export**:
- Pandoc (Markdown → PDF/DOCX)
- python-markdown (Markdown → HTML)

### Quality Assurance Mechanisms

1. **Phase Gates**: Each phase has minimum quality thresholds
   - Exploration: ≥20 quality sources, ≥5 research questions
   - Deep Dive: ≥100 knowledge fragments, cross-referenced
   - Synthesis: Coherence score ≥0.75
   - Critique: No critical issues flagged

2. **Iterative Refinement Limits**:
   - Max 3 iterations per phase (prevent infinite loops)
   - Diminishing returns detection (if improvement < 5%, move on)

3. **Source Verification**:
   - Every claim must have ≥2 supporting sources (configurable)
   - Academic claims require academic sources
   - Recent events require recent sources (<6 months)

4. **Human Review Checkpoints**:
   - After exploration (approve research direction)
   - After outline generation (approve structure)
   - Optional: after each major section draft

5. **Automated Metrics**:
   - Citation density (citations per 1000 words)
   - Source diversity (multiple perspectives)
   - Claim verification rate (% of claims with support)
   - Readability scores (Flesch-Kincaid)

### Data Flow Example

```
User: "Deep research on the impact of microplastics on marine ecosystems"

↓ Decompose Topic Agent
Research Questions:
1. What are microplastics and their sources?
2. How do microplastics enter marine ecosystems?
3. Effects on marine organisms (ingestion, bioaccumulation)
4. Impact on food chains and human consumption
5. Current mitigation strategies and their effectiveness

↓ Initial Search Agent (parallel searches)
47 sources found:
- 12 peer-reviewed papers
- 8 government reports
- 15 news articles
- 12 expert blog posts

↓ Source Quality Agent
Filtered to 28 high-quality sources
Average quality score: 8.1/10

↓ Academic Specialist Agent
Deep dive into 10 key papers:
- "Microplastic ingestion by marine plankton" (Nature, 2023)
- "Bioaccumulation of plastics in fish" (Science, 2022)
[... processes each paper ...]

↓ Knowledge Graph
203 knowledge fragments stored:
- 45 about microplastic sources
- 67 about biological impacts
- 38 about food chain effects
- 53 about mitigation

↓ Gap Analyzer
Identified gaps:
- Limited data on long-term ecosystem changes
- Few studies on Arctic marine environments
→ Triggers additional searches

[2 more hours of iterative research...]

↓ Outline Generator
I. Introduction
II. Microplastics: Definition and Sources
   A. Types and composition
   B. Land-based sources
   C. Ocean-based sources
III. Pathways into Marine Ecosystems
[... 8 more sections ...]

↓ Section Writer Agent (parallel drafting)
Section II.A (1,847 words, 12 citations)
Section II.B (2,103 words, 15 citations)
[... 12 sections total ...]

↓ Coherence Checker
Issues found:
- Terminology inconsistency (microbeads vs. microplastics)
- Section IV.C lacks transition
→ Triggers revisions

↓ Critic Agent
Strengths:
- Comprehensive coverage of biological impacts
- Strong citation network
Weaknesses:
- Limited discussion of economic costs
- Could explore policy implications more
→ Optional: triggers additional research phase

↓ Final Document
42 pages, 23,000 words, 87 citations
Quality score: 9.1/10
Export to PDF, ready for review
```

---
