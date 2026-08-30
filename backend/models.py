from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class GenerateRequest(BaseModel):
    topic: str
    duration_minutes: int
    audience: str
    tone: str
    groq_api_key: str
    tavily_api_key: str
    theme: str

class SlideItem(BaseModel):
    slide_num: int
    title: str
    bullets: List[str]
    layout: str
    key_stat: Optional[Dict[str, Any]] = None
    speaker_note: Optional[str] = None

class ReviewRequest(BaseModel):
    approved_plan: List[SlideItem]
    feedback: Optional[str] = None
