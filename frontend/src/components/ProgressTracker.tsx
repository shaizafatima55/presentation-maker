"use client";

import { Check, Pause, AlertCircle, Loader2 } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import clsx from 'clsx';
import { PipelineNode } from '../types';

const PIPELINE_NODES: PipelineNode[] = [
  { id: 'input', label: 'Input Analysis', description: 'Analyzing topic & constraints' },
  { id: 'search', label: 'Web Search', description: 'Gathering up-to-date info' },
  { id: 'extract', label: 'Content Extraction', description: 'Parsing web sources' },
  { id: 'prioritization', label: 'Source Prioritization', description: 'Selecting best info' },
  { id: 'plan_review', label: 'Plan Review', description: 'HITL Checkpoint' },
  { id: 'synthesis', label: 'Content Synthesis', description: 'Drafting slides' },
  { id: 'tone', label: 'Tone Adjustment', description: 'Refining voice' },
  { id: 'final', label: 'Final Assembly', description: 'Formatting deck' },
];

export default function ProgressTracker() {
  const { nodeStatuses, nodeMessages, searchProgress, computedSlideCount } = useAppStore();

  return (
    <div className="w-64 bg-app-surface border-r border-app-border flex flex-col shrink-0">
      <div className="p-4 border-b border-app-border font-semibold text-app-text">
        Generation Pipeline
      </div>
      
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {PIPELINE_NODES.map((node, i) => {
          const status = nodeStatuses[node.id] || 'idle';
          const msg = nodeMessages[node.id] || node.description;
          const isLast = i === PIPELINE_NODES.length - 1;
          
          return (
            <div key={node.id} className="relative">
              {!isLast && (
                <div className="absolute left-[11px] top-7 bottom-[-24px] w-[2px] bg-app-border" />
              )}
              
              <div className="flex gap-4">
                <div className="relative mt-1">
                  {status === 'idle' && (
                    <div className="w-6 h-6 rounded-full border-2 border-app-border bg-app-surface z-10 relative" />
                  )}
                  {status === 'running' && (
                    <div className="w-6 h-6 rounded-full bg-app-accent z-10 relative flex items-center justify-center text-white pulse-ring">
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    </div>
                  )}
                  {status === 'done' && (
                    <div className="w-6 h-6 rounded-full bg-emerald-500 z-10 relative flex items-center justify-center text-white">
                      <Check className="w-3.5 h-3.5" />
                    </div>
                  )}
                  {status === 'paused' && (
                    <div className="w-6 h-6 rounded-full bg-amber-500 z-10 relative flex items-center justify-center text-white">
                      <Pause className="w-3 h-3" />
                    </div>
                  )}
                  {status === 'error' && (
                    <div className="w-6 h-6 rounded-full bg-red-500 z-10 relative flex items-center justify-center text-white">
                      <AlertCircle className="w-3.5 h-3.5" />
                    </div>
                  )}
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className={clsx(
                    "text-sm font-medium",
                    status === 'idle' ? "text-app-muted" : "text-app-text"
                  )}>
                    {node.label} {status === 'paused' && '⏸'}
                  </div>
                  <div className="text-xs text-app-muted mt-0.5 break-words">
                    {msg}
                  </div>
                  
                  {node.id === 'search' && status === 'running' && searchProgress > 0 && (
                    <div className="mt-2 h-1 w-full bg-app-border rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-app-accent transition-all duration-300"
                        style={{ width: `${searchProgress * 100}%` }}
                      />
                    </div>
                  )}
                  
                  {node.id === 'plan_review' && status === 'paused' && (
                    <div className="mt-2 text-[10px] uppercase font-bold text-amber-500 bg-amber-500/10 px-2 py-1 rounded w-fit tracking-wider">
                      Awaiting Review
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      
      {computedSlideCount > 0 && (
        <div className="p-4 border-t border-app-border text-sm text-app-muted flex items-center gap-2">
          <span>📊</span>
          <span>{computedSlideCount} slides planned</span>
        </div>
      )}
    </div>
  );
}
