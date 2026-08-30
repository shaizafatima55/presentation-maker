import json
from groq import AsyncGroq
from tavily import AsyncTavilyClient
from langgraph.types import interrupt
from session_manager import emit, get_session
from datetime import datetime
import os


# ============================================================
# HELPERS
# ============================================================

def clean_json_response(content: str):
    """Remove markdown code fences and parse JSON."""
    if not isinstance(content, str):
        raise ValueError("AI response is not a string")

    content = content.strip()

    if content.startswith("```json"):
        content = content.split("```json", 1)[1]
        content = content.split("```", 1)[0].strip()

    elif content.startswith("```"):
        content = content.split("```", 1)[1]
        content = content.split("```", 1)[0].strip()

    return json.loads(content)


def safe_slide(slide, index):
    """Normalize a slide so downstream nodes don't crash."""
    if not isinstance(slide, dict):
        slide = {}

    bullets = slide.get("bullets", [])

    if not isinstance(bullets, list):
        bullets = []

    bullets = [
        str(b)
        for b in bullets
        if b is not None
    ]

    return {
        "slide_num": index + 1,
        "layout": str(slide.get("layout", "content")),
        "title": str(slide.get("title", f"Slide {index + 1}")),
        "bullets": bullets,
        "key_stat": slide.get("key_stat"),
        "speaker_note": str(slide.get("speaker_note", "")),
    }


# ============================================================
# INPUT NODE
# ============================================================

async def input_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "input",
            "message": "Parsing input and computing slide count",
        },
    )

    d = state["duration_minutes"]

    if d <= 9:
        count = 5
    elif d <= 20:
        count = 10
    elif d <= 39:
        count = 13
    elif d <= 59:
        count = 16
    else:
        count = 20

    await emit(
        sid,
        "node_done",
        {
            "node": "input",
            "message": f"Computed {count} slides for {d} minutes",
        },
    )

    return {
        "slide_count": count
    }


# ============================================================
# SEARCH NODE
# ============================================================

async def search_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "search",
            "message": "Searching for relevant information",
        },
    )

    topic = state["topic"]

    client = AsyncTavilyClient(
        api_key=state["tavily_api_key"]
    )

    queries = [
        topic,
        f"{topic} statistics facts data",
        f"{topic} examples case studies",
        f"{topic} trends 2024 2025",
    ]

    all_results = []

    for index, query in enumerate(queries):
        try:
            res = await client.search(
                query,
                max_results=5,
            )

            if not isinstance(res, dict):
                res = {}

            results = res.get("results", [])

            if not isinstance(results, list):
                results = []

            valid_results = [
                item
                for item in results
                if isinstance(item, dict)
            ]

            all_results.extend(valid_results)

            await emit(
                sid,
                "search_progress",
                {
                    "query": query,
                    "results_count": len(valid_results),
                    "progress": (index + 1) / len(queries),
                },
            )

        except Exception as e:
            await emit(
                sid,
                "search_progress",
                {
                    "query": query,
                    "results_count": 0,
                    "progress": (index + 1) / len(queries),
                    "message": f"Search failed: {str(e)}",
                },
            )

    await emit(
        sid,
        "node_done",
        {
            "node": "search",
            "message": f"Found {len(all_results)} search results",
        },
    )

    return {
        "search_results": all_results
    }


# ============================================================
# EXTRACT NODE
# ============================================================

async def extract_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "extract",
            "message": "Extracting and scoring sources",
        },
    )

    results = state.get("search_results", [])

    if not isinstance(results, list):
        results = []

    topic = state.get("topic", "")

    if not isinstance(topic, str):
        topic = str(topic)

    topic_words = set(
        topic.lower().split()
    )

    unique_urls = {}

    for r in results:

        # Prevent "'str' object has no attribute 'get'"
        if not isinstance(r, dict):
            continue

        url = r.get("url")

        if not isinstance(url, str):
            continue

        if not url:
            continue

        if url in unique_urls:
            continue

        content = r.get("content", "")

        if not isinstance(content, str):
            content = str(content)

        content = content[:500]

        title = r.get("title", "")

        if not isinstance(title, str):
            title = str(title)

        content_words = set(
            content.lower().split()
        )

        overlap = len(
            topic_words.intersection(content_words)
        )

        score = min(
            1.0,
            overlap / max(1, len(topic_words))
        )

        unique_urls[url] = {
            "url": url,
            "title": title,
            "content": content,
            "score": score,
        }

    source_map = sorted(
        list(unique_urls.values()),
        key=lambda x: x["score"],
        reverse=True,
    )

    await emit(
        sid,
        "node_done",
        {
            "node": "extract",
            "message": f"Processed {len(source_map)} unique sources",
        },
    )

    return {
        "source_map": source_map
    }


# ============================================================
# PRIORITIZATION NODE
# ============================================================

async def prioritization_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "prioritization",
            "message": "Prioritizing sources and drafting plan",
        },
    )

    source_map = state.get("source_map", [])

    if not isinstance(source_map, list):
        source_map = []

    top = [
        item
        for item in source_map
        if isinstance(item, dict)
    ][:8]

    count = int(state["slide_count"])

    sources_text = json.dumps(
        top,
        indent=2
    )

    client = AsyncGroq(
        api_key=state["groq_api_key"]
    )

    prompt = f"""
Topic: {state["topic"]}
Duration: {state["duration_minutes"]} minutes
Audience: {state["audience"]}
Tone: {state["tone"]}

Sources:
{sources_text}

Create a JSON array containing EXACTLY {count} slides.

Every slide MUST contain:
- slide_num
- layout
- title
- bullets (array of 3-5 strings)
- key_stat (object with value and label, or null)
- speaker_note

Return ONLY valid JSON.
Do not use markdown.
"""

    draft = []

    try:
        response = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.3,
        )

        content = (
            response.choices[0].message.content
            or ""
        )

        draft = clean_json_response(content)

        if not isinstance(draft, list):
            raise ValueError(
                "AI did not return a JSON array"
            )

    except Exception as e:
        print(
            f"Prioritization error: {e}"
        )

        draft = []

    # Normalize / fill slides
    normalized = []

    for i in range(count):

        if i < len(draft):
            slide = draft[i]
        else:
            slide = {}

        normalized.append(
            safe_slide(slide, i)
        )

    await emit(
        sid,
        "node_done",
        {
            "node": "prioritization",
            "message": "Draft plan created",
        },
    )

    return {
        "top_sources": top,
        "draft_plan": normalized,
    }


# ============================================================
# PLAN REVIEW / HITL
# ============================================================

async def plan_review_node(state):
    sid = state["session_id"]

    draft_plan = state.get(
        "draft_plan",
        []
    )

    await emit(
        sid,
        "hitl_pause",
        {
            "checkpoint": "plan_review",
            "draft_plan": draft_plan,
            "message": "Review and approve the presentation plan",
        },
    )

    approved = interrupt(
        draft_plan
    )

    await emit(
        sid,
        "hitl_resumed",
        {
            "checkpoint": "plan_review"
        },
    )

    return {
        "hitl_approved_plan": approved
    }


# ============================================================
# SYNTHESIS NODE
# ============================================================

async def synthesis_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "synthesis",
            "message": "Synthesizing slide content",
        },
    )

    client = AsyncGroq(
        api_key=state["groq_api_key"]
    )

    slides = (
        state.get("hitl_approved_plan")
        or state.get("draft_plan")
        or []
    )

    if not isinstance(slides, list):
        slides = []

    all_slides = []

    for i, raw_slide in enumerate(slides):

        slide = safe_slide(
            raw_slide,
            i
        )

        prompt = f"""
Write detailed presentation content
for this slide.

Return ONLY a valid JSON object.

Required fields:
slide_num
layout
title
bullets
key_stat
speaker_note

Draft slide:
{json.dumps(slide)}

Sources:
{json.dumps(state.get("top_sources", []))}

Tone:
{state["tone"]}

Audience:
{state["audience"]}
"""

        try:

            response = await client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.7,
            )

            content = (
                response.choices[0].message.content
                or ""
            )

            final_slide = clean_json_response(
                content
            )

            if not isinstance(
                final_slide,
                dict
            ):
                final_slide = slide

            final_slide = safe_slide(
                final_slide,
                i
            )

            await emit(
                sid,
                "slide_stream",
                {
                    "slide_index": i,
                    "slide_num": i + 1,
                    "token": "",
                },
            )

        except Exception as e:

            print(
                f"Synthesis error on slide {i + 1}: {e}"
            )

            final_slide = slide

        all_slides.append(
            final_slide
        )

    await emit(
        sid,
        "node_done",
        {
            "node": "synthesis",
            "message": "Finished synthesizing content",
        },
    )

    return {
        "slides_content": all_slides
    }


# ============================================================
# TONE NODE
# ============================================================

async def tone_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "tone",
            "message": "Adjusting tone",
        },
    )

    slides = state.get(
        "slides_content",
        []
    )

    if not isinstance(slides, list):
        slides = []

    # Professional needs no extra Groq call.
    if state["tone"].lower() == "professional":

        await emit(
            sid,
            "node_done",
            {
                "node": "tone",
                "message": "Professional tone retained",
            },
        )

        return {
            "adjusted_slides": slides
        }

    client = AsyncGroq(
        api_key=state["groq_api_key"]
    )

    prompt = f"""
Rewrite only the bullets of these slides
in a {state["tone"]} tone.

Keep the exact JSON array structure.

Slides:
{json.dumps(slides)}

Return ONLY valid JSON.
"""

    try:

        response = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.5,
        )

        content = (
            response.choices[0].message.content
            or ""
        )

        adjusted = clean_json_response(
            content
        )

        if (
            isinstance(adjusted, list)
            and len(adjusted) == len(slides)
        ):

            for i, adjusted_slide in enumerate(adjusted):

                if not isinstance(
                    adjusted_slide,
                    dict
                ):
                    continue

                bullets = adjusted_slide.get(
                    "bullets"
                )

                if isinstance(
                    bullets,
                    list
                ):
                    slides[i]["bullets"] = [
                        str(b)
                        for b in bullets
                    ]

    except Exception as e:

        print(
            f"Tone adjustment error: {e}"
        )

    await emit(
        sid,
        "node_done",
        {
            "node": "tone",
            "message": f"Tone adjusted to {state['tone']}",
        },
    )

    return {
        "adjusted_slides": slides
    }


# ============================================================
# FINAL NODE
# ============================================================

async def final_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "node_start",
        {
            "node": "final",
            "message": "Finalizing presentation",
        },
    )

    top_sources = state.get(
        "top_sources",
        []
    )

    if not isinstance(
        top_sources,
        list
    ):
        top_sources = []

    source_urls = []

    for source in top_sources:

        if not isinstance(
            source,
            dict
        ):
            continue

        url = source.get("url")

        if isinstance(
            url,
            str
        ) and url:

            source_urls.append(url)

    slides = state.get(
        "adjusted_slides",
        []
    )

    if not isinstance(
        slides,
        list
    ):
        slides = []

    deck = {
        "title": state["topic"],
        "theme": state["theme"],
        "duration_minutes": state["duration_minutes"],
        "audience": state["audience"],
        "tone": state["tone"],
        "slides": slides,
        "metadata": {
            "sources": source_urls,
            "generated_at": datetime.utcnow().isoformat(),
            "slide_count": state["slide_count"],
        },
    }

    # ========================================================
    # IMPORTANT:
    # Vercel filesystem is read-only except /tmp
    # ========================================================

    from export import generate_pptx

    pptx_path = os.path.join(
        "/tmp",
        f"{sid}.pptx"
    )

    generate_pptx(
        deck,
        pptx_path
    )

    s = get_session(sid)

    if s:

        s.pptx_path = pptx_path
        s.final_deck = deck
        s.status = "completed"

    await emit(
        sid,
        "node_done",
        {
            "node": "final",
            "message": "Presentation generated",
        },
    )

    await emit(
        sid,
        "complete",
        {
            "deck": deck
        },
    )

    if s:
        await s.queue.put(None)

    return {
        "final_deck": deck,
        "pptx_path": pptx_path,
    }
