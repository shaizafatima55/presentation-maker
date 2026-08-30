import json
from collections import defaultdict
from groq import AsyncGroq
from tavily import AsyncTavilyClient
from langgraph.types import interrupt
from session_manager import emit, get_session
from datetime import datetime


def _is_valid_slide_list(value):
    """A valid plan is a non-empty list where every item is a dict."""
    return isinstance(value, list) and len(value) > 0 and all(isinstance(s, dict) for s in value)


async def input_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'input', 'message': 'Parsing input and computing slide count'})
    d = state['duration_minutes']
    if d <= 9: count = 5
    elif d <= 20: count = 10
    elif d <= 39: count = 13
    elif d <= 59: count = 16
    else: count = 20
    await emit(sid, 'node_done', {'node': 'input', 'message': f'Computed {count} slides for {d} minutes'})
    return {'slide_count': count}


async def search_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'search', 'message': 'Searching for relevant information'})
    topic = state['topic']
    client = AsyncTavilyClient(api_key=state['tavily_api_key'])
    queries = [
        topic,
        f"{topic} statistics facts data",
        f"{topic} examples case studies",
        f"{topic} trends 2024 2025"
    ]
    all_results = []
    for q in queries:
        res = await client.search(q, max_results=5)
        results_count = len(res.get('results', []))
        all_results.extend(res.get('results', []))
        await emit(sid, 'search_progress', {'query': q, 'results_count': results_count, 'progress': (queries.index(q) + 1) / len(queries)})
    await emit(sid, 'node_done', {'node': 'search', 'message': f'Found {len(all_results)} search results'})
    return {'search_results': all_results}


async def extract_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'extract', 'message': 'Extracting and scoring sources'})
    results = state['search_results']
    topic_words = set(state['topic'].lower().split())
    unique_urls = {}
    for r in results:
        url = r.get('url')
        if not url or url in unique_urls: continue
        content = r.get('content', '')[:500]
        content_words = set(content.lower().split())
        overlap = len(topic_words.intersection(content_words))
        score = min(1.0, overlap / max(1, len(topic_words)))
        unique_urls[url] = {'url': url, 'title': r.get('title', ''), 'content': content, 'score': score}

    source_map = sorted(list(unique_urls.values()), key=lambda x: x['score'], reverse=True)
    await emit(sid, 'node_done', {'node': 'extract', 'message': f'Processed {len(source_map)} unique sources'})
    return {'source_map': source_map}


def _default_slide(i):
    return {"slide_num": i + 1, "title": f"Slide {i + 1}", "layout": "content",
            "bullets": [], "key_stat": None, "speaker_note": ""}


async def prioritization_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'prioritization', 'message': 'Prioritizing sources and drafting plan'})
    top = state['source_map'][:8]
    sources_text = json.dumps(top, indent=2)
    client = AsyncGroq(api_key=state['groq_api_key'])
    count = state['slide_count']
    prompt = (f"Topic: {state['topic']}\nDuration: {state['duration_minutes']} min\n"
              f"Audience: {state['audience']}\nTone: {state['tone']}\nSources:\n{sources_text}\n\n"
              f"Create a JSON array of EXACTLY {count} slides. Each slide MUST have: slide_num, layout, "
              f"title, bullets (array of 3-5 strings), key_stat (object with value and label, or null), "
              f"speaker_note. Do not include markdown formatting, just the raw JSON array.")

    try:
        res = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.3
        )
        content = res.choices[0].message.content
        if content.startswith('```json'):
            content = content.split('```json')[1].split('```')[0].strip()
        elif content.startswith('```'):
            content = content.split('```')[1].split('```')[0].strip()
        draft = json.loads(content)
        # CHANGED: guard against the model returning something that isn't a
        # proper list-of-dicts (e.g. a single object, a string, etc.)
        if not _is_valid_slide_list(draft):
            raise ValueError("prioritization_node: parsed draft is not a valid slide list")
    except Exception:
        draft = [_default_slide(i) for i in range(count)]

    await emit(sid, 'node_done', {'node': 'prioritization', 'message': 'Draft plan created'})
    return {'top_sources': top, 'draft_plan': draft}


async def plan_review_node(state):
    sid = state['session_id']
    await emit(sid, 'hitl_pause', {
        'checkpoint': 'plan_review',
        'draft_plan': state['draft_plan'],
        'message': 'Review and approve the presentation plan'
    })
    resume_value = interrupt(state['draft_plan'])
    await emit(sid, 'hitl_resumed', {'checkpoint': 'plan_review'})

    # CHANGED: this is the actual bug fix. `resume_value` is whatever the
    # frontend sends when it resumes the interrupt. If the frontend sends the
    # full edited slide list, use it. If it sends anything else (a boolean,
    # a status string like "approved", a dict wrapper, etc.) fall back to the
    # original draft_plan instead of silently treating that value as the plan.
    if _is_valid_slide_list(resume_value):
        approved_plan = resume_value
    elif isinstance(resume_value, dict) and _is_valid_slide_list(resume_value.get('slides')):
        # in case the frontend wraps it like {"approved": true, "slides": [...]}
        approved_plan = resume_value['slides']
    else:
        approved_plan = state['draft_plan']

    return {'hitl_approved_plan': approved_plan}


async def synthesis_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'synthesis', 'message': 'Synthesizing slide content'})
    client = AsyncGroq(api_key=state['groq_api_key'])

    # CHANGED: use the approved plan only if it's actually a valid slide list
    candidate = state.get('hitl_approved_plan')
    slides = candidate if _is_valid_slide_list(candidate) else state['draft_plan']

    all_slides = []

    for i, slide in enumerate(slides):
        prompt = (f"Write detailed content for this slide as JSON object with same schema "
                  f"(slide_num, layout, title, bullets, key_stat, speaker_note).\n"
                  f"Draft: {json.dumps(slide)}\nSources: {json.dumps(state['top_sources'])}\n"
                  f"Tone: {state['tone']}\nAudience: {state['audience']}")
        res = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.7,
            stream=True
        )
        collected_text = ""
        async for chunk in res:
            token = chunk.choices[0].delta.content or ""
            if token:
                collected_text += token
                await emit(sid, 'slide_stream', {'slide_index': i, 'slide_num': slide.get('slide_num', i + 1), 'token': token})

        try:
            text_clean = collected_text
            if text_clean.startswith('```json'):
                text_clean = text_clean.split('```json')[1].split('```')[0].strip()
            elif text_clean.startswith('```'):
                text_clean = text_clean.split('```')[1].split('```')[0].strip()
            final_slide = json.loads(text_clean)
            # CHANGED: guard against the model returning a non-dict (string,
            # number, list, etc.) — treat that as a parse failure too.
            if not isinstance(final_slide, dict):
                raise ValueError("synthesis_node: parsed slide is not an object")
        except Exception:
            # CHANGED: fall back to the ORIGINAL dict-shaped slide, never to
            # whatever `slide` happened to be if it wasn't already a dict.
            final_slide = slide if isinstance(slide, dict) else _default_slide(i)
        all_slides.append(final_slide)

    await emit(sid, 'node_done', {'node': 'synthesis', 'message': 'Finished synthesizing content'})
    return {'slides_content': all_slides}


async def tone_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'tone', 'message': 'Adjusting tone'})
    slides = state['slides_content']
    if state['tone'].lower() == 'professional':
        await emit(sid, 'node_done', {'node': 'tone', 'message': 'Professional tone retained'})
        return {'adjusted_slides': slides}

    client = AsyncGroq(api_key=state['groq_api_key'])
    prompt = f"Rewrite the bullets for these slides in a {state['tone']} tone. Keep JSON structure.\nSlides: {json.dumps(slides)}"
    try:
        res = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[{'role': 'user', 'content': prompt}],
            temperature=0.5
        )
        content = res.choices[0].message.content
        if content.startswith('```json'):
            content = content.split('```json')[1].split('```')[0].strip()
        elif content.startswith('```'):
            content = content.split('```')[1].split('```')[0].strip()
        adjusted = json.loads(content)
        # CHANGED: only apply the rewrite if it's shaped correctly; never
        # trust `adjusted[i]` to be a dict without checking.
        if _is_valid_slide_list(adjusted) and len(adjusted) == len(slides):
            for i, s in enumerate(slides):
                if isinstance(adjusted[i], dict) and 'bullets' in adjusted[i]:
                    s['bullets'] = adjusted[i]['bullets']
    except Exception:
        pass

    await emit(sid, 'node_done', {'node': 'tone', 'message': f"Tone adjusted to {state['tone']}"})
    return {'adjusted_slides': slides}


def _normalize_slide(s, i):
    """Coerce every field to the type the exporter expects, regardless of
    what shape the LLM actually returned. This is the deep version of the
    dict-check in final_node — it guards the FIELDS inside each slide, not
    just the slide object itself."""
    if not isinstance(s, dict):
        return _default_slide(i)

    slide_num = s.get('slide_num')
    if not isinstance(slide_num, int):
        slide_num = i + 1

    title = s.get('title')
    if not isinstance(title, str):
        title = str(title) if title is not None else f"Slide {i + 1}"

    layout = s.get('layout')
    if not isinstance(layout, str):
        layout = "content"

    bullets = s.get('bullets')
    if isinstance(bullets, str):
        # model sometimes returns one big string instead of a list
        bullets = [b.strip("-• ").strip() for b in bullets.split("\n") if b.strip()]
    elif not isinstance(bullets, list):
        bullets = []
    else:
        bullets = [b if isinstance(b, str) else str(b) for b in bullets]

    # CHANGED: this is the field most likely causing your current error.
    # key_stat must be a dict with value/label, or None — never a bare string.
    key_stat = s.get('key_stat')
    if isinstance(key_stat, dict):
        value = key_stat.get('value')
        label = key_stat.get('label')
        key_stat = {'value': value if value is not None else '', 'label': label if label is not None else ''}
    elif isinstance(key_stat, str) and key_stat.strip():
        # model returned a bare string like "40%" instead of an object —
        # salvage it into the expected shape instead of dropping it
        key_stat = {'value': key_stat.strip(), 'label': ''}
    else:
        key_stat = None

    speaker_note = s.get('speaker_note')
    if not isinstance(speaker_note, str):
        speaker_note = str(speaker_note) if speaker_note is not None else ''

    return {
        'slide_num': slide_num,
        'layout': layout,
        'title': title,
        'bullets': bullets,
        'key_stat': key_stat,
        'speaker_note': speaker_note,
    }


async def final_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'final', 'message': 'Finalizing presentation'})

    # CHANGED: deep-normalize every slide (not just check it's a dict) right
    # before export, so mismatched nested fields (e.g. key_stat coming back
    # as a string instead of an object) can never reach generate_pptx.
    safe_slides = [_normalize_slide(s, i) for i, s in enumerate(state['adjusted_slides'])]

    deck = {
        'title': state['topic'],
        'theme': state['theme'],
        'duration_minutes': state['duration_minutes'],
        'audience': state['audience'],
        'tone': state['tone'],
        'slides': safe_slides,
        'metadata': {
            'sources': [s['url'] for s in state['top_sources']],
            'generated_at': datetime.utcnow().isoformat(),
            'slide_count': state['slide_count']
        }
    }

    from export import generate_pptx
    import os
    output_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    pptx_path = os.path.join(output_dir, f"{sid}.pptx")
    generate_pptx(deck, pptx_path)

    s = get_session(sid)
    if s:
        s.pptx_path = pptx_path
        s.final_deck = deck
        s.status = 'completed'

    await emit(sid, 'node_done', {'node': 'final', 'message': 'Presentation generated'})
    await emit(sid, 'complete', {'deck': deck})
    if s:
        await s.queue.put(None)

    return {'final_deck': deck, 'pptx_path': pptx_path}
