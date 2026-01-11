# Script Version: 0.4.0 | Phase 2: Orchestration
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
    iteration_status: str # For UI display of parallel activities
    
    # Knowledge Base (Accumulated via operator.add)
    logs: Annotated[List[str], operator.add]
    sources: Annotated[List[SourceMetadata], operator.add]
    knowledge_fragments: Annotated[List[Dict[str, Any]], operator.add]
    structured_entities: Annotated[List[Dict[str, Any]], operator.add] # New for Knowledge Graph
    
    # Analysis Results
    research_questions: List[ResearchQuestion]
    identified_gaps: List[str]
    source_quality_avg: float
    
    # Final Output
    final_report: str
