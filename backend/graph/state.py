from typing import TypedDict, List, Optional, Dict, Any

class PresentationState(TypedDict):
    session_id: str
    topic: str
    duration_minutes: int
    audience: str
    tone: str
    groq_api_key: str
    tavily_api_key: str
    theme: str
    slide_count: int
    search_results: List[dict]
    source_map: List[dict]
    top_sources: List[dict]
    draft_plan: List[dict]
    hitl_approved_plan: Optional[List[dict]]
    slides_content: List[dict]
    adjusted_slides: List[dict]
    final_deck: Optional[dict]
    pptx_path: Optional[str]
    error: Optional[str]
