import asyncio, json, uuid
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware  
from fastapi.responses import FileResponse
from sse_starlette.sse import EventSourceResponse
from langgraph.types import Command

from models import GenerateRequest, ReviewRequest
from session_manager import create_session, get_session, emit, sessions, config_store
from graph.graph import graph
from graph.state import PresentationState

app = FastAPI(title='AI Presentation Maker')

app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], allow_credentials=True,
    allow_methods=['*'], allow_headers=['*']
)

@app.get("/")
async def root():
    return {"message": "AI Presentation Maker API is working"}


async def run_graph_task(session_id: str, initial_state: dict):
    config = {'configurable': {'thread_id': session_id}}
    config_store[session_id] = config
    try:
        async for event in graph.astream(initial_state, config, stream_mode='updates'):
            pass  # Nodes emit SSE events internally
    except Exception as e:
        import traceback
        await emit(session_id, 'error', {'message': str(e)})
        s = get_session(session_id)
        if s: s.status = 'error'
    finally:
        s = get_session(session_id)
        if s and s.status not in ['completed']:
            await s.queue.put(None)

@app.post('/api/generate')
async def start_generation(request: GenerateRequest):
    session_id = str(uuid.uuid4())
    await create_session(session_id)
    initial_state = {
        'session_id': session_id,
        'topic': request.topic,
        'duration_minutes': request.duration_minutes,
        'audience': request.audience,
        'tone': request.tone,
        'groq_api_key': request.groq_api_key,
        'tavily_api_key': request.tavily_api_key,
        'theme': request.theme,
        'slide_count': 0,
        'search_results': [],
        'source_map': [],
        'top_sources': [],
        'draft_plan': [],
        'hitl_approved_plan': None,
        'slides_content': [],
        'adjusted_slides': [],
        'final_deck': None,
        'pptx_path': None,
        'error': None,
    }
    task = asyncio.create_task(run_graph_task(session_id, initial_state))
    s = get_session(session_id)
    if s: s.task = task
    return {'session_id': session_id}

@app.get('/api/stream/{session_id}')
async def stream_events(session_id: str):
    s = get_session(session_id)
    if not s:
        raise HTTPException(404, 'Session not found')
    
    async def generator():
        while True:
            try:
                ev = await asyncio.wait_for(s.queue.get(), timeout=30)
                if ev is None:
                    break
                yield {'event': ev['event'], 'data': json.dumps(ev['data'])}
                if ev['event'] in ['complete', 'error']:
                    break
            except asyncio.TimeoutError:
                yield {'event': 'ping', 'data': '{}'}
    
    return EventSourceResponse(generator())

@app.post('/api/review/{session_id}')
async def submit_review(session_id: str, review: ReviewRequest):
    s = get_session(session_id)
    if not s:
        raise HTTPException(404, 'Session not found')
    config = config_store.get(session_id)
    if not config:
        raise HTTPException(400, 'Session config not found')
    
    approved = [item.model_dump() for item in review.approved_plan]
    
    async def resume():
        try:
            async for _ in graph.astream(
                Command(resume=approved), config, stream_mode='updates'
            ):
                pass
        except Exception as e:
            await emit(session_id, 'error', {'message': str(e)})
        finally:
            sess = get_session(session_id)
            if sess and sess.status != 'completed':
                await sess.queue.put(None)
    
    asyncio.create_task(resume())
    return {'status': 'resumed'}

@app.get('/api/download/{session_id}')
async def download_pptx(session_id: str):
    s = get_session(session_id)
    if not s or not s.pptx_path:
        raise HTTPException(404, 'Presentation not ready')
    return FileResponse(
        s.pptx_path,
        media_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
        filename=f'presentation.pptx'
    )

@app.get('/health')
async def health():
    return {'status': 'ok'}

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8000, reload=True)
