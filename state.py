# Script Version: 0.4.2 | Phase 5: Polish & Depth Control
# Description: Added token_usage tracking with merge logic.

from typing import List, Dict, Any, TypedDict, Annotated, Optional
import operator

def merge_usage(current: Dict[str, Dict[str, int]], new_data: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
    """
    Deep merge dictionary for token usage accumulation.
    Structure: {"model_name": {"input": 10, "output": 20, "total": 30}}
    """
    if not current:
        return new_data.copy()
    
    merged = current.copy()
    for model, counts in new_data.items():
        if model not in merged:
            merged[model] = counts.copy()
        else:
            # Accumulate counts
            for k, v in counts.items():
                merged[model][k] = merged[model].get(k, 0) + v
    return merged

class ResearchQuestion(TypedDict):
    id: int
    question: str
    priority: int
    status: str # "pending", "searching", "analyzed", "completed"
    depth: int  # Recursion depth for this specific question lineage
    parent_id: Optional[int] # ID of the question that spawned this one

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
    iteration_count: int # Global loop counter (safety valve)
    
    # Knowledge Base (Accumulated via operator.add)
    logs: Annotated[List[str], operator.add]
    sources: Annotated[List[SourceMetadata], operator.add]
    knowledge_fragments: Annotated[List[Dict[str, Any]], operator.add]
    structured_entities: Annotated[List[Dict[str, Any]], operator.add]
    
    # Metrics
    token_usage: Annotated[Dict[str, Dict[str, int]], merge_usage]
    
    # Analysis Results
    research_questions: List[ResearchQuestion] # Mutable list of all questions
    identified_gaps: List[Dict[str, Any]] 
    source_quality_avg: float
    
    # Final Output
    final_report: str
