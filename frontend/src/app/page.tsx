"use client";

import { useAppStore } from '../store/useAppStore';
import { useSSE } from '../hooks/useSSE';
import Header from '../components/Header';
import InputForm from '../components/InputForm';
import ProgressTracker from '../components/ProgressTracker';
import HITLPanel from '../components/HITLPanel';
import SlidePreview from '../components/SlidePreview';
import { Loader2 } from 'lucide-react';

function StreamingView() {
  const { streamingSlides, computedSlideCount, nodeMessages } = useAppStore();
  const slideCount = Object.keys(streamingSlides).length;

  return (
    <div className="h-full flex flex-col items-center justify-center p-8 gap-8">
      {/* Status */}
      <div className="text-center">
        <div className="flex items-center justify-center gap-3 mb-2">
          <Loader2 className="w-5 h-5 text-app-accent animate-spin" />
          <span className="text-app-text font-semibold text-lg">
            {nodeMessages['synthesis'] || 'Generating slide content...'}
          </span>
        </div>
        {computedSlideCount > 0 && (
          <p className="text-app-muted text-sm">
            {slideCount} of {computedSlideCount} slides generated
          </p>
        )}
      </div>

      {/* Progress bar */}
      {computedSlideCount > 0 && (
        <div className="w-full max-w-md">
          <div className="h-1.5 bg-app-border rounded-full overflow-hidden">
            <div
              className="h-full bg-app-accent rounded-full transition-all duration-300"
              style={{ width: `${(slideCount / computedSlideCount) * 100}%` }}
            />
          </div>
        </div>
      )}

      {/* Mini slide previews */}
      {slideCount > 0 && (
        <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3 w-full max-w-3xl">
          {Array.from({ length: Math.max(slideCount, 1) }).map((_, i) => {
            const hasContent = streamingSlides[i];
            const isBuilding = i === slideCount - 1 && slideCount < computedSlideCount;
            return (
              <div
                key={i}
                className={`aspect-video rounded-lg border flex items-center justify-center relative overflow-hidden
                  ${hasContent
                    ? 'bg-app-card border-app-accent/40'
                    : isBuilding
                    ? 'bg-app-card border-app-accent animate-pulse'
                    : 'bg-app-surface border-app-border opacity-40'
                  }`}
              >
                <span className="text-xs text-app-muted font-medium">{i + 1}</span>
                {isBuilding && (
                  <div className="absolute bottom-1 right-1 w-1.5 h-1.5 bg-app-accent rounded-full animate-ping" />
                )}
                {hasContent && (
                  <div className="absolute inset-0 p-2 overflow-hidden">
                    <div className="text-[7px] text-app-muted opacity-60 leading-tight line-clamp-5 font-mono">
                      {streamingSlides[i].slice(0, 120)}
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function GeneratingView() {
  const { nodeMessages } = useAppStore();

  return (
    <div className="h-full flex flex-col items-center justify-center p-8 gap-6">
      <div className="relative">
        <div className="w-16 h-16 rounded-full border-2 border-app-accent/20 flex items-center justify-center">
          <div className="w-12 h-12 rounded-full border-2 border-app-accent border-t-transparent animate-spin" />
        </div>
      </div>
      <div className="text-center">
        <p className="text-app-text font-semibold text-lg mb-1">
          {nodeMessages['search'] || nodeMessages['extract'] || nodeMessages['prioritization'] || 'Preparing your presentation...'}
        </p>
        <p className="text-app-muted text-sm">This usually takes 30–60 seconds</p>
      </div>
    </div>
  );
}

export default function PresentationMaker() {
  const { phase, sessionId, error, reset } = useAppStore();

  useSSE(sessionId);

  return (
    <div className="min-h-screen bg-app-bg text-app-text flex flex-col" style={{ height: '100vh' }}>
      <Header />

      <main className="flex-1 flex overflow-hidden">
        {/* INPUT PHASE */}
        {phase === 'input' && (
          <div className="flex-1 overflow-y-auto p-4 md:p-8">
            <InputForm />
          </div>
        )}

        {/* GENERATING / HITL / SYNTHESIZING PHASES */}
        {(phase === 'generating' || phase === 'synthesizing' || phase === 'hitl') && (
          <>
            <ProgressTracker />
            <div className="flex-1 overflow-y-auto">
              {phase === 'hitl' && <HITLPanel />}
              {phase === 'synthesizing' && <StreamingView />}
              {phase === 'generating' && <GeneratingView />}
            </div>
          </>
        )}

        {/* COMPLETE PHASE */}
        {phase === 'complete' && (
          <div className="flex-1 overflow-hidden">
            <SlidePreview />
          </div>
        )}

        {/* ERROR PHASE */}
        {phase === 'error' && (
          <div className="flex-1 flex items-center justify-center p-4">
            <div className="bg-app-card border border-red-900/40 rounded-xl p-8 max-w-md w-full text-center">
              <div className="w-14 h-14 rounded-full bg-red-500/10 flex items-center justify-center mx-auto mb-4">
                <svg className="w-7 h-7 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
              </div>
              <div className="text-red-400 mb-3 text-xl font-semibold">Something went wrong</div>
              <p className="text-app-muted text-sm mb-6 leading-relaxed">{error}</p>
              <button
                onClick={reset}
                className="bg-app-accent hover:bg-app-accent-hover text-white font-semibold rounded-lg px-6 py-3 transition-colors w-full"
              >
                Try Again
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
