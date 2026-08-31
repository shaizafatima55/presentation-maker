import json
import os
import asyncio
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


async def call_groq_with_retry(client, sid=None, node_name=None, retries=4, base_delay=2.0, **kwargs):
    """Wraps client.chat.completions.create with exponential backoff, but
    ONLY for rate-limit (429) errors. Any other exception is raised
    immediately — we never want a real failure silently swallowed and
    mistaken for "just retry harder".

    This directly targets the TPM 429 you're hitting: the Groq error even
    tells you the exact wait ("try again in 937.5ms") — a short backoff
    almost always clears it instead of failing the whole run.
    """
    last_err = None
    for attempt in range(retries):
        try:
            return await client.chat.completions.create(**kwargs)
        except Exception as e:
            last_err = e
            msg = str(e)
            is_rate_limit = "429" in msg or "rate_limit_exceeded" in msg.lower() or "rate limit" in msg.lower()
            if is_rate_limit and attempt < retries - 1:
                delay = base_delay * (2 ** attempt)
                if sid:
                    await emit(sid, 'node_retry', {
                        'node': node_name or 'groq_call',
                        'attempt': attempt + 1,
                        'retry_in_seconds': round(delay, 1),
                        'message': f'Rate limited — retrying in {delay:.1f}s (attempt {attempt + 1}/{retries})'
                    })
                await asyncio.sleep(delay)
                continue
            raise
    raise last_err


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
        res = await call_groq_with_retry(
            client, sid=sid, node_name='prioritization',
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
        if not _is_valid_slide_list(draft):
            raise ValueError("prioritization_node: parsed draft is not a valid slide list")
    except Exception as e:
        # CHANGED: this is what was hiding your real failures. Before, ANY
        # exception here — including the 429 — was silently caught and
        # replaced with blank "Slide 1", "Slide 2" placeholders, so the UI
        # showed empty cards as if generation had succeeded. Now we emit a
        # real error the frontend can display, and only fall back to
        # placeholders as a last resort so the pipeline doesn't hard-crash.
        await emit(sid, 'node_error', {
            'node': 'prioritization',
            'message': f'Failed to generate the plan: {str(e)[:200]}'
        })
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

    # CHANGED: this is the main fix for the rate limit. The old code did
    # `json.dumps(state['top_sources'])` — the FULL 8-source list, each with
    # up to 500 chars of raw content — INSIDE the per-slide loop, so the same
    # large block was retransmitted on every single slide's prompt. For a
    # 10-slide deck that's the same ~1500+ token dump sent 10 times in one
    # run, which is what blew through the 8000 TPM limit. Build one short
    # summary ONCE, outside the loop, and reuse it.
    sources_summary = "\n".join(
        f"[{i + 1}] {s.get('title', '')}: {s.get('content', '')[:150]}"
        for i, s in enumerate(state['top_sources'])
    )

    all_slides = []

    for i, slide in enumerate(slides):
        prompt = (f"Write detailed content for this slide as JSON object with same schema "
                  f"(slide_num, layout, title, bullets, key_stat, speaker_note).\n"
                  f"Draft: {json.dumps(slide)}\nSources:\n{sources_summary}\n"
                  f"Tone: {state['tone']}\nAudience: {state['audience']}")

        try:
            res = await call_groq_with_retry(
                client, sid=sid, node_name=f'synthesis (slide {i + 1})',
                model="openai/gpt-oss-20b",
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.7,
                stream=True
            )
        except Exception as e:
            # CHANGED: surface the real failure instead of silently
            # continuing as if nothing happened.
            await emit(sid, 'node_error', {
                'node': 'synthesis',
                'message': f'Failed to generate slide {i + 1}: {str(e)[:200]}'
            })
            all_slides.append(slide if isinstance(slide, dict) else _default_slide(i))
            continue

        collected_text = ""
        slide_num_for_ui = slide.get('slide_num', i + 1) if isinstance(slide, dict) else i + 1
        async for chunk in res:
            token = chunk.choices[0].delta.content or ""
            if token:
                collected_text += token
                await emit(sid, 'slide_stream', {'slide_index': i, 'slide_num': slide_num_for_ui, 'token': token})

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

        # CHANGED: small proactive throttle between slides. Optional, but
        # spreads token usage over time instead of bursting all 10 slides'
        # worth of requests back-to-back, which reduces how often you hit
        # the TPM ceiling in the first place. Tune or remove as needed.
        await asyncio.sleep(0.4)

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
        res = await call_groq_with_retry(
            client, sid=sid, node_name='tone',
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
    except Exception as e:
        # CHANGED: this failing is non-fatal (slides keep their existing
        # bullets, just untranslated to the target tone) so we don't block
        # the pipeline — but the frontend should still know it happened.
        await emit(sid, 'node_error', {
            'node': 'tone',
            'message': f'Tone adjustment failed, keeping original bullets: {str(e)[:200]}'
        })

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
    import tempfile
    # CHANGED: write to the platform's writable temp directory instead of a
    # path relative to the source file. On serverless platforms (Vercel,
    # AWS Lambda) everything except /tmp is read-only at runtime — writing
    # next to __file__ (under /var/task/...) fails with
    # "[Errno 30] Read-only file system". tempfile.gettempdir() resolves to
    # /tmp on serverless and to your normal system temp dir locally, so this
    # works in both environments without an environment check.
    output_dir = tempfile.gettempdir()
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
