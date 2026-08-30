import json
from groq import AsyncGroq
from tavily import AsyncTavilyClient
from langgraph.types import interrupt
from session_manager import emit, get_session
from datetime import datetime


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
            "slide_count": count,
        },
    )

    return {"slide_count": count}


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

    for index, q in enumerate(queries):
        try:
            res = await client.search(
                q,
                max_results=5,
            )

            # Tavily normally returns a dictionary.
            # But protect against unexpected response types.
            if not isinstance(res, dict):
                res = {}

            results = res.get("results", [])

            if not isinstance(results, list):
                results = []

            # Only keep dictionary results.
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
                    "query": q,
                    "results_count": len(valid_results),
                    "progress": (index + 1) / len(queries),
                },
            )

        except Exception as e:
            await emit(
                sid,
                "search_progress",
                {
                    "query": q,
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

    # Important:
    # Make sure results is a list.
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

        # FIX:
        # Prevent "'str' object has no attribute 'get'"
        if not isinstance(r, dict):
            continue

        url = r.get("url")

        if not isinstance(url, str) or not url:
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
            overlap / max(1, len(topic_words)),
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

    top = state.get("source_map", [])

    if not isinstance(top, list):
        top = []

    top = [
        item
        for item in top
        if isinstance(item, dict)
    ][:8]

    sources_text = json.dumps(
        top,
        indent=2,
    )

    client = AsyncGroq(
        api_key=state["groq_api_key"]
    )

    count = state["slide_count"]

    prompt = f"""
Topic: {state["topic"]}
Duration: {state["duration_minutes"]} min
Audience: {state["audience"]}
Tone: {state["tone"]}

Sources:
{sources_text}

Create a JSON array of EXACTLY {count} slides.

Each slide MUST have:

- slide_num
- layout
- title
- bullets (array of 3-5 strings)
- key_stat (object with value and label, or null)
- speaker_note

Do not include markdown formatting.
Return ONLY the raw JSON array.
"""

    try:
        res = await client.chat.completions.create(
            model="openai/gpt-oss-20b",
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0.3,
        )

        content = res.choices[0].message.content or ""

        content = content.strip()

        if content.startswith("```json"):
            content = (
                content
                .split("```json", 1)[1]
                .split("```", 1)[0]
                .strip()
            )

        elif content.startswith("```"):
            content = (
                content
                .split("```", 1)[1]
                .split("```", 1)[0]
                .strip()
            )

        draft = json.loads(content)

        # Make sure AI returned a list.
        if not isinstance(draft, list):
            raise ValueError(
                "AI did not return a JSON array"
            )

        # Keep only dictionary slides.
        draft = [
            slide
            for slide in draft
            if isinstance(slide, dict)
        ]

        # If AI returned wrong number of slides,
        # fill missing slides safely.
        while len(draft) < count:
            index = len(draft) + 1

            draft.append(
                {
                    "slide_num": index,
                    "layout": "content",
                    "title": f"Slide {index}",
                    "bullets": [],
                    "key_stat": None,
                    "speaker_note": "",
                }
            )

        draft = draft[:count]

        # Normalize slide numbers.
        for i, slide in enumerate(draft):
            slide["slide_num"] = i + 1

            if "layout" not in slide:
                slide["layout"] = "content"

            if "title" not in slide:
                slide["title"] = f"Slide {i + 1}"

            if not isinstance(
                slide.get("bullets"),
                list,
            ):
                slide["bullets"] = []

            if "key_stat" not in slide:
                slide["key_stat"] = None

            if "speaker_note" not in slide:
                slide["speaker_note"] = ""

    except Exception as e:
        print(
            f"Prioritization AI error: {e}"
        )

        draft = [
            {
                "slide_num": i + 1,
                "title": f"Slide {i + 1}",
                "layout": "content",
                "bullets": [],
                "key_stat": None,
                "speaker_note": "",
            }
            for i in range(count)
        ]

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
        "draft_plan": draft,
    }


# ============================================================
# PLAN REVIEW / HITL NODE
# ============================================================

async def plan_review_node(state):
    sid = state["session_id"]

    await emit(
        sid,
        "hitl_pause",
        {
            "checkpoint": "plan_review",
            "draft_plan": state["draft_plan"],
            "message": "Review and approve the presentation plan",
        },
    )

    approved = interrupt(
        state["draft_plan"]
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

    for i, slide in enumerate(slides):

        # Protect against invalid HITL data.
        if not isinstance(slide, dict):
            slide = {
                "slide_num": i + 1,
                "layout": "content",
                "title": f"Slide {i + 1}",
                "bullets": [],
                "key_stat": None,
                "speaker_note": "",
            }

        prompt = f"""
Write detailed content for this slide as a JSON object.

The JSON object MUST contain:

slide_num
layout
title
bullets
key_stat
speaker_note

Draft:
{json.dumps(slide)}

Sources:
{json.dumps(state.get("top_sources", []))}

Tone:
{state["tone"]}

Audience:
{state["audience"]}

Return ONLY valid JSON.
"""

        try:
            res = await client.chat.completions.create(
                model="openai/gpt-oss-20b",
                messages=[
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                temperature=0.7,
                stream=True,
            )

            collected_text = ""

            async for chunk in res:

                if not chunk.choices:
                    continue

                token = (
                    chunk.choices[0]
                    .delta
                    .content
                    or ""
                )

                if token:
                    collected_text += token

                    await emit(
                        sid,
                        "slide_stream",
                        {
                            "slide_index": i,
                            "slide_num": slide.get(
                                "slide_num",
                                i + 1,
                            ),
                            "token": token,
                        },
                    )

            text_clean = collected_text.strip()

            if text_clean.startswith("```json"):
                text_clean = (
                    text_clean
                    .split("```json", 1)[1]
                    .split("```", 1)[0]
                    .strip()
                )

            elif text_clean.startswith("```"):
                text_clean = (
                    text_clean
                    .split("```", 1)[1]
                    .split("```", 1)[0]
                    .strip()
                )

            final_slide = json.loads(
                text_clean
            )

            if not isinstance(
                final_slide,
                dict,
            ):
                final_slide = slide

        except Exception as e:
            print(
                f"Synthesis error on slide {i + 1}: {e}"
            )

            final_slide = slide

        all_slides.append(final_slide)

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
        [],
    )

    if not isinstance(slides, list):
        slides = []

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
Rewrite the bullets for these slides
in a {state["tone"]} tone.

Keep the JSON structure unchanged.

Slides:
{json.dumps(slides)}

Return ONLY a JSON array.
"""

    try:
        res = await client.chat.completions.create(
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
            res.choices[0].message.content
            or ""
        )

        content = content.strip()

        if content.startswith("```json"):
            content = (
                content
                .split("```json", 1)[1]
                .split("```", 1)[0]
                .strip()
            )

        elif content.startswith("```"):
            content = (
                content
                .split("```", 1)[1]
                .split("```", 1)[0]
                .strip()
            )

        adjusted = json.loads(content)

        if (
            isinstance(adjusted, list)
            and len(adjusted) == len(slides)
        ):
            for i, adjusted_slide in enumerate(adjusted):

                if not isinstance(
                    adjusted_slide,
                    dict,
                ):
                    continue

                if "bullets" in adjusted_slide:
                    if isinstance(
                        adjusted_slide["bullets"],
                        list,
                    ):
                        slides[i]["bullets"] = (
                            adjusted_slide["bullets"]
                        )

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
        [],
    )

    if not isinstance(top_sources, list):
        top_sources = []

    source_urls = []

    for source in top_sources:
        if not isinstance(source, dict):
            continue

        url = source.get("url")

        if isinstance(url, str) and url:
            source_urls.append(url)

    deck = {
        "title": state["topic"],
        "theme": state["theme"],
        "duration_minutes": state["duration_minutes"],
        "audience": state["audience"],
        "tone": state["tone"],
        "slides": state.get(
            "adjusted_slides",
            [],
        ),
        "metadata": {
            "sources": source_urls,
            "generated_at": datetime.utcnow().isoformat(),
            "slide_count": state["slide_count"],
        },
    }

    from export import generate_pptx

    import os

     output_dir = "/tmp"

      pptx_path = os.path.join(
        output_dir,
      f"{sid}.pptx"
    )


    try:
        generate_pptx(
            deck,
            pptx_path,
        )
    except Exception as e:
        print(
            f"PPTX generation error: {e}"
        )
        raise

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
