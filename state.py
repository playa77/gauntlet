# Script Version: 0.3.1 | Phase 2: Orchestration
# Description: Shared state definition for the cyclical research graph.
# Implementation: Uses Annotated/operator.add for persistent accumulation of logs and sources.

from typing import List, Dict, Any, TypedDict, Annotated, Optional
import operator

class ResearchQuestion(TypedDict):
    id: int
    question: str
    priority: int
    status: str # "pending", "searching", "analyzed", "completed"

class SourceMetadata(TypedDict):
    url: str
    title: str
    snippet: str
    quality_score: float
    source_type: str # "web", "academic", "local"

class ResearchState(TypedDict):
    """
    The global state object passed between nodes in the LangGraph.
    """
    # Inputs & Config
    research_topic: str
    user_constraints: Dict[str, Any]
    model_id: str
    
    # Progress Tracking
    current_phase: str
    is_complete: bool
    iteration_count: int
    max_iterations: int
    
    # Knowledge Base (Accumulated via operator.add)
    # This ensures that every node's contribution is appended to the list
    logs: Annotated[List[str], operator.add]
    sources: Annotated[List[SourceMetadata], operator.add]
    knowledge_fragments: Annotated[List[Dict[str, Any]], operator.add]
    
    # Analysis Results
    research_questions: List[ResearchQuestion]
    identified_gaps: List[str]
    source_quality_avg: float
    
    # Final Output
    final_report: str
