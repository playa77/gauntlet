# Script Version: 0.2.1 | Phase 1: Agent Foundation
# Description: Shared state definition for the research graph.

from typing import List, Dict, Any, TypedDict, Optional

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
    # Inputs
    research_topic: str
    user_constraints: Dict[str, Any]
    model_id: str
    
    # Progress Tracking
    current_phase: str
    logs: List[str]
    is_complete: bool
    
    # Knowledge Base
    research_questions: List[ResearchQuestion]
    sources: List[SourceMetadata]
    knowledge_fragments: List[Dict[str, Any]] # Insights extracted from sources
    
    # Final Output
    final_report: str
