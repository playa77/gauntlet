# Script Version: 0.1.2 | Phase 0: Foundation
# Description: Shared state definition for the research graph.

from typing import List, Dict, Any, TypedDict

class ResearchState(TypedDict):
    research_topic: str
    user_constraints: Dict[str, Any]
    current_phase: str
    logs: List[str]
    sources: List[str]
    final_report: str
    is_complete: bool
    model_id: str
