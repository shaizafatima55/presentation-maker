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


def _has_real_content(slide, i):
    """A slide that merely has the right keys isn't necessarily a slide
    with real content — a thin/malformed model response like
    {"title": "Slide 1", "bullets": []} used to pass the old "is it a
    dict" check and get accepted as-is. This checks it actually has
    something to show: at least one non-empty bullet, and a title that
    isn't just the auto-generated placeholder form."""
    if not isinstance(slide, dict):
        return False
    bullets = slide.get('bullets')
    has_bullets = isinstance(bullets, list) and any(
        isinstance(b, str) and b.strip() for b in bullets
    )
    title = slide.get('title')
    has_real_title = isinstance(title, str) and title.strip() and title.strip() != f"Slide {i + 1}"
    return has_bullets and has_real_title


def _normalize_slide(s, i):
    """Coerce every field to the type the exporter (and the plan-review
    UI) expects, regardless of what shape the LLM actually returned.
    Applied right after drafting AND right after synthesis — not just once
    at final export — so plan review and the final output are always
    working from the same consistently-shaped data."""
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


def _condensed_sources(sources):
    """Compact source reference reused across calls — avoids re-sending
    full 500-char content blocks repeatedly, which burns tokens fast once
    you're making several batch calls per plan."""
    return "\n".join(
        f"[{i + 1}] {s.get('title', '')}: {s.get('content', '')[:150]}"
        for i, s in enumerate(sources)
    )


async def _draft_slides_batch(client, sid, topic, duration_minutes, audience, tone,
                               sources_text, start_idx, batch_size, total_count):
    """Generates ONE small batch of slides instead of the whole deck in a
    single call. This is the actual fix for plans going blank at higher
    slide counts: a single call asking for 20-30 full slide objects at once
    was getting truncated by the model's output limit, producing invalid
    JSON that silently fell back to blank placeholders. Keeping each call's
    expected output small (a handful of slides) avoids truncation
    regardless of how many total slides are requested."""
    prompt = (f"Topic: {topic}\nDuration: {duration_minutes} min\nAudience: {audience}\nTone: {tone}\n"
              f"Sources:\n{sources_text}\n\n"
              f"This presentation has {total_count} slides total. Generate ONLY slides "
              f"{start_idx + 1} through {start_idx + batch_size} as a JSON array of exactly "
              f"{batch_size} slide objects, in order. Each slide MUST have: slide_num (use "
              f"{start_idx + 1} through {start_idx + batch_size} respectively), layout, title, "
              f"bullets (array of 3-5 strings), key_stat (object with value and label, or null), "
              f"speaker_note. Respond with ONLY the raw JSON array — no markdown fences, no "
              f"commentary, nothing before or after it.")

    res = await call_groq_with_retry(
        client, sid=sid, node_name=f'prioritization (slides {start_idx + 1}-{start_idx + batch_size})',
        model="openai/gpt-oss-20b",
        messages=[{'role': 'user', 'content': prompt}],
        temperature=0.3,
        max_tokens=4000,  # explicit ceiling per batch, generous enough for
                          # ~6 full slide objects without risking the same
                          # truncation problem
    )
    content = res.choices[0].message.content
    if content.startswith('```json'):
        content = content.split('```json')[1].split('```')[0].strip()
    elif content.startswith('```'):
        content = content.split('```')[1].split('```')[0].strip()
    batch = json.loads(content)
    if not _is_valid_slide_list(batch):
        raise ValueError(f"batch starting at slide {start_idx + 1} is not a valid slide list")
    if len(batch) != batch_size:
        # A batch returning fewer slides than asked used to pass as valid,
        # quietly shortening the deck. Now it's treated as a failure so the
        # caller can retry it.
        raise ValueError(f"batch starting at slide {start_idx + 1} returned {len(batch)} slides, expected {batch_size}")

    # FIX: this is the gap that let thin/empty slides through silently.
    # `_is_valid_slide_list` above only checks "is this a list of dicts" —
    # a slide like {"title": "Slide 1", "bullets": []} passes that check
    # fine. It has the right shape but no actual content, and used to sail
    # straight through to plan review looking exactly like your symptom:
    # a slide number with nothing in it. Now a batch containing any
    # content-empty slide is rejected here so the caller retries it instead
    # of silently accepting it.
    for j, slide in enumerate(batch):
        if not _has_real_content(slide, start_idx + j):
            raise ValueError(f"slide {start_idx + j + 1} in batch has no real content (empty bullets or placeholder title)")

    return batch


async def prioritization_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'prioritization', 'message': 'Prioritizing sources and drafting plan'})
    top = state['source_map'][:8]
    client = AsyncGroq(api_key=state['groq_api_key'])
    count = state['slide_count']
    sources_text = _condensed_sources(top)

    BATCH_SIZE = 6  # tune this down further (e.g. 4) if you still see
                     # truncation on very long/detailed topics

    draft = []
    any_batch_failed = False

    for start in range(0, count, BATCH_SIZE):
        batch_size = min(BATCH_SIZE, count - start)
        batch = None
        last_err = None

        # Retry THIS batch specifically (up to 2 attempts) before giving up
        # on it. A failure here only affects this batch's slides, not the
        # whole deck.
        for batch_attempt in range(2):
            try:
                batch = await _draft_slides_batch(
                    client, sid, state['topic'], state['duration_minutes'],
                    state['audience'], state['tone'], sources_text,
                    start, batch_size, count
                )
                break
            except Exception as e:
                last_err = e
                continue

        if batch is None:
            # FIX: the whole batch failing (whether from a JSON/rate-limit
            # error, or now also from a content-empty slide) doesn't mean
            # every slide in it needs to fall back to a blank placeholder.
            # Asking for ONE slide at a time is a much smaller ask than 6
            # at once, so it's meaningfully more likely to succeed even
            # when the full batch wasn't — this is what actually recovers
            # content instead of showing "Slide 1, 2, 3" with nothing in
            # them once slide counts get higher (more batches = more
            # chances for one to fail).
            await emit(sid, 'node_warning', {
                'node': 'prioritization',
                'message': f'Batch for slides {start + 1}-{start + batch_size} failed ({str(last_err)[:120]}), retrying individually'
            })
            batch = []
            for j in range(batch_size):
                slide_idx = start + j
                single = None
                for single_attempt in range(2):
                    try:
                        single_batch = await _draft_slides_batch(
                            client, sid, state['topic'], state['duration_minutes'],
                            state['audience'], state['tone'], sources_text,
                            slide_idx, 1, count
                        )
                        single = single_batch[0]
                        break
                    except Exception:
                        continue
                if single is None:
                    # Only NOW, after a full batch retry AND an individual
                    # retry both failed for this specific slide, does it
                    # become a true placeholder.
                    any_batch_failed = True
                    await emit(sid, 'node_error', {
                        'node': 'prioritization',
                        'message': f'Slide {slide_idx + 1} failed to generate even individually, using placeholder'
                    })
                    single = _default_slide(slide_idx)
                batch.append(single)

        # Normalize every slide's shape here, right after drafting — so
        # plan review always renders consistent data regardless of which
        # path (batch success, individual retry, or placeholder) produced it.
        batch = [_normalize_slide(s, start + j) for j, s in enumerate(batch)]
        draft.extend(batch)
        await emit(sid, 'node_progress', {
            'node': 'prioritization',
            'message': f'Drafted slides {start + 1}-{start + batch_size} of {count}'
        })
        await asyncio.sleep(0.3)  # small throttle between batches

    if any_batch_failed:
        await emit(sid, 'node_warning', {
            'node': 'prioritization',
            'message': 'Some slides used placeholder content because generation failed for that batch. Check the plan review screen for blank slides.'
        })

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

    # `resume_value` is whatever the frontend sends when it resumes the
    # interrupt. If the frontend sends the full edited slide list, use it.
    # If it sends anything else (a boolean, a status string like
    # "approved", a dict wrapper, etc.) fall back to the original
    # draft_plan instead of silently treating that value as the plan.
    if _is_valid_slide_list(resume_value):
        approved_plan = resume_value
    elif isinstance(resume_value, dict) and _is_valid_slide_list(resume_value.get('slides')):
        # in case the frontend wraps it like {"approved": true, "slides": [...]}
        approved_plan = resume_value['slides']
    else:
        approved_plan = state['draft_plan']

    return {'hitl_approved_plan': approved_plan}


async def _synthesize_one_slide(client, sid, slide, i, sources_summary, tone, audience, semaphore):
    """Generates one slide's full content. Pulled out of the loop so
    multiple slides can run concurrently instead of strictly one-at-a-time.

    FIX: the entire body — including starting the stream AND reading every
    chunk from it — is now inside one try/except. Previously the try/except
    only wrapped the call that started the stream; if an error happened
    mid-stream (which concurrency makes more likely, e.g. a rate limit
    tripped by another concurrent slide), it was completely uncaught. That
    exception then propagated out of asyncio.gather() in synthesis_node and
    cancelled every other in-flight slide task, wiping the whole deck's
    content — not just this slide's. Now, no matter where in this function
    something fails, we always fall back to the original draft slide
    instead of raising.
    """
    async with semaphore:
        slide_num_for_ui = slide.get('slide_num', i + 1) if isinstance(slide, dict) else i + 1
        try:
            prompt = (f"Write detailed content for this slide as JSON object with same schema "
                      f"(slide_num, layout, title, bullets, key_stat, speaker_note).\n"
                      f"Draft: {json.dumps(slide)}\nSources:\n{sources_summary}\n"
                      f"Tone: {tone}\nAudience: {audience}")

            res = await call_groq_with_retry(
                client, sid=sid, node_name=f'synthesis (slide {i + 1})',
                model="openai/gpt-oss-20b",
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0.7,
                max_tokens=1200,
                stream=True
            )

            collected_text = ""
            async for chunk in res:
                token = chunk.choices[0].delta.content or ""
                if token:
                    collected_text += token
                    await emit(sid, 'slide_stream', {'slide_index': i, 'slide_num': slide_num_for_ui, 'token': token})

            text_clean = collected_text
            if text_clean.startswith('```json'):
                text_clean = text_clean.split('```json')[1].split('```')[0].strip()
            elif text_clean.startswith('```'):
                text_clean = text_clean.split('```')[1].split('```')[0].strip()
            final_slide = json.loads(text_clean)
            if not isinstance(final_slide, dict):
                raise ValueError("synthesis_node: parsed slide is not an object")
            return final_slide

        except Exception as e:
            # Covers failures anywhere above: starting the stream, reading
            # chunks mid-stream, or parsing the final JSON. This slide falls
            # back to its draft content instead of taking the whole batch
            # down with it.
            await emit(sid, 'node_error', {
                'node': 'synthesis',
                'message': f'Failed to generate slide {i + 1}, using draft content: {str(e)[:200]}'
            })
            return _normalize_slide(slide, i)


async def synthesis_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'synthesis', 'message': 'Synthesizing slide content'})
    client = AsyncGroq(api_key=state['groq_api_key'])

    candidate = state.get('hitl_approved_plan')
    slides = candidate if _is_valid_slide_list(candidate) else state['draft_plan']
    sources_summary = _condensed_sources(state['top_sources'])

    # Slides no longer generate strictly one-at-a-time — up to
    # SYNTHESIS_CONCURRENCY run at once, capped by a semaphore so only that
    # many Groq requests are in flight simultaneously. Lower this if you
    # start seeing 429s again; raise it if you have TPM headroom.
    SYNTHESIS_CONCURRENCY = 3
    semaphore = asyncio.Semaphore(SYNTHESIS_CONCURRENCY)

    tasks = [
        _synthesize_one_slide(client, sid, slide, i, sources_summary, state['tone'], state['audience'], semaphore)
        for i, slide in enumerate(slides)
    ]

    # FIX: return_exceptions=True. Without this, the moment ANY one task
    # raised, gather() immediately raised too and cancelled every other
    # still-running task — which is why one bad slide could wipe content
    # for the entire deck, including slides that had already succeeded.
    # _synthesize_one_slide now shouldn't raise at all (it catches
    # internally), but this is a second layer of safety: if something truly
    # unexpected still escapes, we degrade that one slide to a placeholder
    # instead of losing the whole batch.
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_slides = []
    for i, r in enumerate(results):
        if isinstance(r, Exception):
            await emit(sid, 'node_error', {
                'node': 'synthesis',
                'message': f'Slide {i + 1} task raised unexpectedly, using placeholder: {str(r)[:200]}'
            })
            fallback = slides[i] if isinstance(slides[i], dict) else _default_slide(i)
            all_slides.append(_normalize_slide(fallback, i))
        else:
            all_slides.append(_normalize_slide(r, i))

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
        # Only apply the rewrite if it's shaped correctly; never trust
        # `adjusted[i]` to be a dict without checking.
        if _is_valid_slide_list(adjusted) and len(adjusted) == len(slides):
            for i, s in enumerate(slides):
                if isinstance(adjusted[i], dict) and 'bullets' in adjusted[i]:
                    s['bullets'] = adjusted[i]['bullets']
    except Exception as e:
        # This failing is non-fatal (slides keep their existing bullets,
        # just untranslated to the target tone) so we don't block the
        # pipeline — but the frontend should still know it happened.
        await emit(sid, 'node_error', {
            'node': 'tone',
            'message': f'Tone adjustment failed, keeping original bullets: {str(e)[:200]}'
        })

    await emit(sid, 'node_done', {'node': 'tone', 'message': f"Tone adjusted to {state['tone']}"})
    return {'adjusted_slides': slides}


async def final_node(state):
    sid = state['session_id']
    await emit(sid, 'node_start', {'node': 'final', 'message': 'Finalizing presentation'})

    # Deep-normalize every slide (not just check it's a dict) right before
    # export, so mismatched nested fields (e.g. key_stat coming back as a
    # string instead of an object) can never reach generate_pptx.
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
    # Write to the platform's writable temp directory instead of a path
    # relative to the source file. On serverless platforms (Vercel, AWS
    # Lambda) everything except /tmp is read-only at runtime — writing next
    # to __file__ (under /var/task/...) fails with "[Errno 30] Read-only
    # file system". tempfile.gettempdir() resolves to /tmp on serverless
    # and to your normal system temp dir locally, so this works in both
    # environments without an environment check.
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
