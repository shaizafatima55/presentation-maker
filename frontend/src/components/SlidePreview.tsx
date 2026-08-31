"use client";

import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight, Download, Eye } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { themes } from '../themes';
import { SlideItem } from '../types';

export default function SlidePreview() {
  const { finalDeck, currentSlideIndex, setCurrentSlideIndex, sessionId } = useAppStore();
  const [showNotes, setShowNotes] = useState(false);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (!finalDeck) return;
      if (e.key === 'ArrowRight') {
        setCurrentSlideIndex(Math.min(currentSlideIndex + 1, finalDeck.slides.length - 1));
      } else if (e.key === 'ArrowLeft') {
        setCurrentSlideIndex(Math.max(currentSlideIndex - 1, 0));
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [finalDeck, currentSlideIndex, setCurrentSlideIndex]);

  if (!finalDeck) return null;

  const slide = finalDeck.slides[currentSlideIndex];
  const theme = themes.find(t => t.id === finalDeck.theme) || themes[0];

  const handleDownload = () => {
    const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
    window.open(`${baseUrl}/api/download/${sessionId}`, '_blank');
  };

  return (
    <div className="h-full flex flex-col bg-app-bg">
      {/* Top bar */}
      <div className="h-14 shrink-0 border-b border-app-border flex items-center justify-between px-6 bg-app-surface">
        <div className="font-semibold text-app-text truncate max-w-md">
          {finalDeck.title}
        </div>
        
        <div className="flex items-center gap-4">
          <span className="text-sm text-app-muted">
            Slide {currentSlideIndex + 1} of {finalDeck.slides.length}
          </span>
          <button
            onClick={() => setShowNotes(!showNotes)}
            className={`p-2 rounded-lg transition-colors ${showNotes ? 'bg-app-accent/20 text-app-accent' : 'text-app-muted hover:text-app-text'}`}
            title="Toggle Speaker Notes"
          >
            <Eye className="w-4 h-4" />
          </button>
          <button
            onClick={handleDownload}
            className="flex items-center gap-2 bg-app-accent hover:bg-app-accent-hover text-white text-sm font-semibold rounded-lg px-4 py-2 transition-colors"
          >
            <Download className="w-4 h-4" />
            Download PPTX
          </button>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Slide viewer area */}
        <div className="flex-1 p-4 md:p-8 flex items-center justify-center relative bg-[#0a0a0c]">
          <div 
            className="w-full max-w-5xl aspect-video rounded-xl shadow-2xl overflow-hidden relative"
            style={{ backgroundColor: theme.preview.bg, color: theme.preview.text }}
          >
            <SlideRenderer slide={slide} theme={theme} />
          </div>
          
          {/* Overlay Navigation Controls */}
          <button
            onClick={() => setCurrentSlideIndex(Math.max(currentSlideIndex - 1, 0))}
            disabled={currentSlideIndex === 0}
            className="absolute left-4 p-3 rounded-full bg-black/50 text-white hover:bg-black/70 disabled:opacity-0 transition-all z-10"
          >
            <ChevronLeft className="w-6 h-6" />
          </button>
          <button
            onClick={() => setCurrentSlideIndex(Math.min(currentSlideIndex + 1, finalDeck.slides.length - 1))}
            disabled={currentSlideIndex === finalDeck.slides.length - 1}
            className="absolute right-4 p-3 rounded-full bg-black/50 text-white hover:bg-black/70 disabled:opacity-0 transition-all z-10"
          >
            <ChevronRight className="w-6 h-6" />
          </button>
        </div>

        {/* Side panel for notes */}
        {showNotes && (
          <div className="w-80 border-l border-app-border bg-app-surface flex flex-col shrink-0">
            <div className="p-4 border-b border-app-border font-semibold text-app-text">
              Speaker Notes
            </div>
            <div className="p-4 flex-1 overflow-y-auto text-app-muted text-sm whitespace-pre-wrap leading-relaxed">
              {slide.speaker_notes || 'No speaker notes for this slide.'}
            </div>
          </div>
        )}
      </div>

      {/* Thumbnail strip */}
      <div className="h-28 shrink-0 bg-app-surface border-t border-app-border p-4 flex gap-4 overflow-x-auto">
        {finalDeck.slides.map((s, idx) => (
          <button
            key={idx}
            onClick={() => setCurrentSlideIndex(idx)}
            className={`shrink-0 aspect-video h-full rounded-md border-2 overflow-hidden transition-all relative ${currentSlideIndex === idx ? 'border-app-accent ring-2 ring-app-accent/50' : 'border-transparent hover:border-app-border opacity-70 hover:opacity-100'}`}
          >
            <div 
              className="w-full h-full pointer-events-none transform origin-top-left scale-[0.2] w-[500%] h-[500%]"
              style={{ backgroundColor: theme.preview.bg, color: theme.preview.text }}
            >
               <SlideRenderer slide={s} theme={theme} isThumbnail={true} />
            </div>
            <div className="absolute bottom-1 right-1 bg-black/60 text-white text-[10px] px-1.5 rounded">
              {idx + 1}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}

// Subcomponent to render a slide based on its layout
function SlideRenderer({ slide, theme, isThumbnail = false }: { slide: SlideItem, theme: any, isThumbnail?: boolean }) {
  const p = isThumbnail ? 'p-8' : 'p-16';
  const tTitle = isThumbnail ? 'text-7xl mb-8' : 'text-5xl mb-8';
  const tSubtitle = isThumbnail ? 'text-4xl' : 'text-2xl opacity-80';
  
  if (slide.layout === 'title') {
    return (
      <div className={`w-full h-full flex flex-col items-center justify-center text-center ${p}`}>
        <h1 className={`${isThumbnail ? 'text-8xl mb-8' : 'text-6xl mb-6'} font-bold leading-tight`} style={{ color: theme.preview.primary }}>
          {slide.title}
        </h1>
        {slide.bullets[0] && (
          <p className={`${tSubtitle}`} style={{ color: theme.preview.accent }}>
            {slide.bullets[0]}
          </p>
        )}
      </div>
    );
  }

  if (slide.layout === 'statistics' && slide.key_stat) {
    return (
      <div className={`w-full h-full flex flex-col justify-center ${p}`}>
        <h2 className={`${tTitle} font-bold`} style={{ color: theme.preview.primary }}>
          {slide.title}
        </h2>
        <div className="flex items-center gap-16 mt-8">
          <div className="flex-1">
            <div className={`${isThumbnail ? 'text-[12rem]' : 'text-8xl'} font-black leading-none mb-4`} style={{ color: theme.preview.accent }}>
              {slide.key_stat.value}
            </div>
            <div className={`${isThumbnail ? 'text-5xl' : 'text-3xl'} font-medium`} style={{ color: theme.preview.text }}>
              {slide.key_stat.label}
            </div>
          </div>
          <div className="flex-1 space-y-6">
            {slide.bullets.map((b, i) => (
              <div key={i} className={`flex items-start gap-4 ${isThumbnail ? 'text-4xl mb-4' : 'text-xl'}`}>
                <span style={{ color: theme.preview.accent }}>•</span>
                <span>{b}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (slide.layout === 'closing') {
    return (
      <div className={`w-full h-full flex flex-col items-center justify-center text-center ${p}`} style={{ backgroundColor: theme.preview.accent }}>
        <h1 className={`${isThumbnail ? 'text-8xl' : 'text-6xl'} font-bold text-white mb-6`}>
          {slide.title}
        </h1>
        {slide.bullets[0] && (
          <p className={`${tSubtitle} text-white/90`}>
            {slide.bullets[0]}
          </p>
        )}
      </div>
    );
  }

  // Default content / two-column / quote (simplified for preview)
  return (
    <div className={`w-full h-full flex flex-col ${p}`}>
      <h2 className={`${tTitle} font-bold`} style={{ color: theme.preview.primary }}>
        {slide.title}
      </h2>
      <div className={`flex-1 flex flex-col justify-center ${isThumbnail ? 'space-y-6' : 'space-y-4'}`}>
        {slide.bullets.map((b, i) => (
           <div key={i} className={`flex items-start gap-4 ${isThumbnail ? 'text-4xl mb-6' : 'text-2xl mb-4'}`}>
             <span style={{ color: theme.preview.accent }}>•</span>
             <span className="leading-relaxed">{b}</span>
           </div>
        ))}
      </div>
    </div>
  );
}
