export type Theme = 'minimal-light' | 'midnight-professional' | 'warm-neutral' | 
  'forest-academic' | 'slate-coral' | 'monochrome-editorial' | 'deep-purple-tech';

export type NodeStatus = 'idle' | 'running' | 'done' | 'paused' | 'error';

export interface PipelineNode {
  id: string;
  label: string;
  description: string;
}

export interface SlideItem {
  slide_num: number;
  layout: 'title' | 'content' | 'two-column' | 'quote' | 'statistics' | 'closing';
  title: string;
  bullets: string[];
  key_stat?: { value: string; label: string; } | null;
  speaker_notes?: string;
  visual_suggestion?: string;
}

export interface SlideDeck {
  title: string;
  theme: string;
  duration_minutes: number;
  audience: string;
  tone: string;
  slides: SlideItem[];
  metadata: {
    sources: { url: string; title: string; }[];
    generated_at: string;
    slide_count: number;
  };
}

export interface GenerateFormData {
  topic: string;
  duration_minutes: number;
  audience: string;
  tone: string;
  groq_api_key: string;
  tavily_api_key: string;
  theme: Theme;
}

export type AppPhase = 'input' | 'generating' | 'hitl' | 'synthesizing' | 'complete' | 'error';
