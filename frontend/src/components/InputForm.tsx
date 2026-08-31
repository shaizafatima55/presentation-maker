"use client";

import { useState } from 'react';
import axios from 'axios';
import { Eye, EyeOff, Loader2 } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { themes } from '../themes';
import { Theme } from '../types';
import clsx from 'clsx';

export default function InputForm() {
  const { formData, setFormData, setSessionId, setPhase, setError } = useAppStore();
  const [showGroqKey, setShowGroqKey] = useState(false);
  const [showTavilyKey, setShowTavilyKey] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.topic || !formData.groq_api_key || !formData.tavily_api_key) return;

    setIsSubmitting(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      const res = await axios.post(
        `${baseUrl}/api/generate`,
        formData
      );

      setSessionId(res.data.session_id);
      setPhase('generating');
    } catch (err: any) {
      setError(err.response?.data?.message || err.message || 'Failed to start generation');
      setPhase('error');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isFormValid = formData.topic && formData.groq_api_key && formData.tavily_api_key;
  const computedSlides = Math.max(3, Math.floor(formData.duration_minutes / 2));

  return (
    <div className="max-w-3xl mx-auto space-y-8 pb-12">
      <div className="text-center space-y-2">
        <h1 className="text-3xl font-bold bg-gradient-to-r from-[#7C6FE0] to-[#A78BFA] bg-clip-text text-transparent">
          Create a New Presentation
        </h1>
        <p className="text-app-muted">AI-powered generation with human-in-the-loop review.</p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        
        {/* Section 1: API Keys */}
        <div className="bg-app-card border border-app-border rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-app-text">API Keys</h2>
          <p className="text-sm text-app-muted">Keys are used only for this session and never stored.</p>
          
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-app-text">Groq API Key</label>
              <div className="relative">
                <input
                  type={showGroqKey ? 'text' : 'password'}
                  placeholder="gsk_..."
                  value={formData.groq_api_key}
                  onChange={(e) => setFormData({ groq_api_key: e.target.value })}
                  className="w-full bg-app-surface border border-app-border rounded-lg pl-3 pr-10 py-2.5 text-app-text focus:border-app-accent focus:ring-1 focus:ring-app-accent outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowGroqKey(!showGroqKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-app-muted hover:text-app-text"
                >
                  {showGroqKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
            
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-app-text">Tavily API Key</label>
              <div className="relative">
                <input
                  type={showTavilyKey ? 'text' : 'password'}
                  placeholder="tvly-..."
                  value={formData.tavily_api_key}
                  onChange={(e) => setFormData({ tavily_api_key: e.target.value })}
                  className="w-full bg-app-surface border border-app-border rounded-lg pl-3 pr-10 py-2.5 text-app-text focus:border-app-accent focus:ring-1 focus:ring-app-accent outline-none transition-colors"
                />
                <button
                  type="button"
                  onClick={() => setShowTavilyKey(!showTavilyKey)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-app-muted hover:text-app-text"
                >
                  {showTavilyKey ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Section 2: Details */}
        <div className="bg-app-card border border-app-border rounded-xl p-6 space-y-6">
          <h2 className="text-lg font-semibold text-app-text">Presentation Details</h2>
          
          <div className="space-y-1.5">
            <label className="text-sm font-medium text-app-text">Topic</label>
            <textarea
              placeholder="e.g. The Future of Renewable Energy..."
              value={formData.topic}
              onChange={(e) => setFormData({ topic: e.target.value })}
              className="w-full bg-app-surface border border-app-border rounded-lg p-3 text-app-text focus:border-app-accent focus:ring-1 focus:ring-app-accent outline-none transition-colors min-h-[100px] resize-y"
            />
          </div>
          
          <div className="space-y-1.5">
            <div className="flex justify-between">
              <label className="text-sm font-medium text-app-text">Duration</label>
              <span className="text-sm text-app-accent">{formData.duration_minutes} min → ~{computedSlides} slides</span>
            </div>
            <input
              type="range"
              min="5"
              max="90"
              step="5"
              value={formData.duration_minutes}
              onChange={(e) => setFormData({ duration_minutes: Number(e.target.value) })}
              className="w-full accent-app-accent"
            />
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-app-text">Audience</label>
              <select
                value={formData.audience}
                onChange={(e) => setFormData({ audience: e.target.value })}
                className="w-full bg-app-surface border border-app-border rounded-lg p-2.5 text-app-text focus:border-app-accent focus:ring-1 focus:ring-app-accent outline-none transition-colors"
              >
                {['General', 'Students', 'Executives', 'Technical', 'Researchers'].map(a => (
                  <option key={a} value={a}>{a}</option>
                ))}
              </select>
            </div>
            
            <div className="space-y-1.5">
              <label className="text-sm font-medium text-app-text block">Tone</label>
              <div className="flex flex-wrap gap-2">
                {['professional', 'academic', 'casual', 'inspirational'].map(t => (
                  <button
                    key={t}
                    type="button"
                    onClick={() => setFormData({ tone: t })}
                    className={clsx(
                      "px-3 py-1.5 rounded-lg text-sm capitalize transition-colors border",
                      formData.tone === t 
                        ? "bg-app-accent/20 border-app-accent text-app-accent" 
                        : "bg-app-surface border-app-border text-app-muted hover:text-app-text"
                    )}
                  >
                    {t}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </div>

        {/* Section 3: Theme */}
        <div className="bg-app-card border border-app-border rounded-xl p-6 space-y-4">
          <h2 className="text-lg font-semibold text-app-text">Visual Theme</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {themes.map((theme) => (
              <button
                key={theme.id}
                type="button"
                onClick={() => setFormData({ theme: theme.id as Theme })}
                className={clsx(
                  "p-3 rounded-xl border text-left transition-all",
                  formData.theme === theme.id
                    ? "border-app-accent bg-app-accent/10 ring-1 ring-app-accent"
                    : "border-app-border bg-app-surface hover:border-app-muted"
                )}
              >
                <div className="flex w-full h-12 rounded-lg overflow-hidden border border-app-border/50 mb-2">
                  <div className="w-1/2 h-full" style={{ backgroundColor: theme.preview.bg }} />
                  <div className="w-1/4 h-full" style={{ backgroundColor: theme.preview.accent }} />
                  <div className="w-1/4 h-full" style={{ backgroundColor: theme.preview.text }} />
                </div>
                <div className="text-xs font-medium text-app-text truncate">{theme.name}</div>
              </button>
            ))}
          </div>
        </div>

        <button
          type="submit"
          disabled={!isFormValid || isSubmitting}
          className="w-full bg-app-accent hover:bg-app-accent-hover text-white font-semibold rounded-lg px-6 py-4 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex justify-center items-center gap-2 text-lg"
        >
          {isSubmitting ? (
            <>
              <Loader2 className="w-5 h-5 animate-spin" />
              Starting...
            </>
          ) : (
            'Generate Presentation →'
          )}
        </button>

      </form>
    </div>
  );
}
