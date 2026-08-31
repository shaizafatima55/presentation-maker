# AI Presentation Maker

An AI-powered presentation generator using LangGraph, FastAPI, and Next.js 14.

## Features
- 🔄 LangGraph state pipeline with 8 nodes
- 👁️ Single HITL checkpoint — review & edit your plan before generation
- ⚡ SSE live streaming — watch slides generate token by token
- 📊 Smart slide count based on duration (10-20 min → 10 slides, 60 min → 20 slides)
- 🎨 7 presentation themes — applied to both UI and PPTX export
- 📥 PPTX download with proper layouts (title, content, statistics, quote, closing)

---

## Prerequisites

- Python 3.11+
- Node.js 18+
- [Groq API key](https://console.groq.com) — free tier available
- [Tavily API key](https://tavily.com) — free tier available

---

## Local Development

### 1. Backend

```bash
cd backend

# Create virtual environment
python -m venv venv

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the server
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Backend will be live at: **http://localhost:8000**

Health check: http://localhost:8000/health

### 2. Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server
npm run dev
```

Frontend will be live at: **http://localhost:3000**

---

## How to Use

1. Open **http://localhost:3000**
2. Enter your **Groq API Key** and **Tavily API Key** in the API Keys section
3. Type your **topic**, set **duration**, choose **audience** and **tone**
4. Select a **presentation theme** (7 options)
5. Click **Generate Presentation →**
6. Watch live progress as the pipeline runs:
   - Input Analysis → Web Search → Content Extraction → Source Prioritization
7. **HITL Review**: Edit slide titles and bullet points, reorder slides, then **Approve & Generate**
8. Watch slides generate in real-time
9. Browse the interactive slide previewer
10. Click **Download PPTX** to get your presentation file

---

## Project Structure

```
ai-presentation-maker/
├── backend/
│   ├── main.py                  # FastAPI app + SSE endpoints
│   ├── session_manager.py       # Per-session async queue store
│   ├── models.py                # Pydantic request/response models
│   ├── export.py                # python-pptx PPTX generation
│   ├── requirements.txt
│   ├── Dockerfile
│   └── graph/
│       ├── state.py             # LangGraph TypedDict state
│       ├── nodes.py             # 8 async pipeline nodes
│       └── graph.py             # StateGraph with MemorySaver
├── frontend/
│   ├── src/
│   │   ├── app/
│   │   │   ├── layout.tsx       # Next.js App Router root layout
│   │   │   ├── page.tsx         # Main interactive application page
│   │   │   └── globals.css      # Dark theme & animation styles
│   │   ├── components/
│   │   │   ├── Header.tsx
│   │   │   ├── InputForm.tsx    # API keys + topic + theme picker
│   │   │   ├── ProgressTracker.tsx # Live node status sidebar
│   │   │   ├── HITLPanel.tsx    # Editable plan review
│   │   │   ├── SlidePreview.tsx # Interactive 16:9 previewer
│   │   │   └── ThemeSelector.tsx
│   │   ├── hooks/useSSE.ts      # EventSource → Zustand
│   │   ├── store/useAppStore.ts # Zustand global state
│   │   ├── themes/index.ts      # 7 theme configs
│   │   └── types/index.ts
│   ├── Dockerfile               # Container definition for Next.js
│   ├── tailwind.config.ts       # Custom app-* color palette
│   ├── tsconfig.json
│   └── package.json
└── docker-compose.yml           # Orchestration for frontend & backend
```

---

## Slide Count Table

| Duration | Slides |
|---|---|
| 1–9 min | 5 |
| 10–20 min | 10 |
| 21–39 min | 13 |
| 40–59 min | 16 |
| 60+ min | 20 |

---

## 7 Presentation Themes

| Theme | Background | Accent |
|---|---|---|
| Minimal Light | White | Indigo |
| Midnight Professional | Navy | Sky Blue |
| Warm Neutral | Warm White | Amber |
| Forest Academic | Pale Green | Forest Green |
| Slate & Coral | Slate White | Coral Red |
| Monochrome Editorial | Light Gray | Dark Gray |
| Deep Purple Tech | Deep Indigo | Purple |

---

## Docker Deployment

```bash
# Build and run
docker-compose up --build

# Access
# Frontend: http://localhost:3000
# Backend:  http://localhost:8000
```

---

## Environment Variables (optional)

Create `backend/.env` to set default API keys (keys entered in UI always take priority):

```env
# Optional defaults — users can override in the UI
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
```
