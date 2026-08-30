import asyncio
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

@dataclass
class Session:
    queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    status: str = 'running'  # running|hitl_paused|completed|error
    pptx_path: Optional[str] = None
    final_deck: Optional[dict] = None
    task: Optional[Any] = None

sessions: Dict[str, Session] = {}
config_store: Dict[str, dict] = {}

async def create_session(session_id: str) -> Session:
    s = Session()
    sessions[session_id] = s
    return s

def get_session(session_id: str) -> Optional[Session]:
    return sessions.get(session_id)

async def emit(session_id: str, event: str, data: dict):
    s = sessions.get(session_id)
    if s:
        await s.queue.put({'event': event, 'data': data})
