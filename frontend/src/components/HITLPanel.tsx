"use client";

import { useState } from 'react';
import { ArrowUp, ArrowDown, Plus, Trash2, Loader2, Check } from 'lucide-react';
import axios from 'axios';
import { useAppStore } from '../store/useAppStore';
import { SlideItem } from '../types';

export default function HITLPanel() {
  const { draftPlan, sessionId, setPhase } = useAppStore();
  const [plan, setPlan] = useState<SlideItem[]>(draftPlan);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleTitleChange = (idx: number, val: string) => {
    const newPlan = [...plan];
    newPlan[idx].title = val;
    setPlan(newPlan);
  };

  const handleBulletChange = (sIdx: number, bIdx: number, val: string) => {
    const newPlan = [...plan];
    newPlan[sIdx].bullets[bIdx] = val;
    setPlan(newPlan);
  };

  const addBullet = (sIdx: number) => {
    const newPlan = [...plan];
    newPlan[sIdx].bullets.push('New bullet point');
    setPlan(newPlan);
  };

  const removeBullet = (sIdx: number, bIdx: number) => {
    const newPlan = [...plan];
    newPlan[sIdx].bullets.splice(bIdx, 1);
    setPlan(newPlan);
  };

  const moveSlide = (idx: number, dir: 1 | -1) => {
    if (idx + dir < 0 || idx + dir >= plan.length) return;
    const newPlan = [...plan];
    const temp = newPlan[idx];
    newPlan[idx] = newPlan[idx + dir];
    newPlan[idx + dir] = temp;
    // update slide_nums
    newPlan.forEach((s, i) => s.slide_num = i + 1);
    setPlan(newPlan);
  };

  const handleApprove = async () => {
    setIsSubmitting(true);
    try {
      const baseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
      await axios.post(
        `${baseUrl}/api/review/${sessionId}`,
        { status: 'resumed', approved_plan: plan }
      );

      setPhase('generating');
    } catch (err) {
      console.error(err);
      alert('Failed to approve plan');
      setIsSubmitting(false);
    }
  };

  return (
    <div className="max-w-4xl mx-auto h-full flex flex-col">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-app-text">Review Your Presentation Plan</h1>
        <p className="text-app-muted">Approve or edit the slide plan before we generate the full content.</p>
      </div>
      
      <div className="flex-1 overflow-y-auto space-y-4 pr-2 pb-24">
        {plan.map((slide, sIdx) => (
          <div key={sIdx} className="bg-app-card border border-app-border rounded-xl p-5 flex gap-4 group">
            <div className="flex flex-col items-center justify-start gap-2 text-app-muted">
              <span className="text-sm font-semibold text-app-accent w-6 text-center">{slide.slide_num}</span>
              <button onClick={() => moveSlide(sIdx, -1)} disabled={sIdx === 0} className="hover:text-app-text disabled:opacity-30">
                <ArrowUp className="w-4 h-4" />
              </button>
              <button onClick={() => moveSlide(sIdx, 1)} disabled={sIdx === plan.length - 1} className="hover:text-app-text disabled:opacity-30">
                <ArrowDown className="w-4 h-4 text-app-muted" />
              </button>
            </div>
            
            <div className="flex-1 min-w-0 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[10px] uppercase font-bold text-app-muted bg-app-surface px-2 py-1 rounded tracking-wider">
                  {slide.layout}
                </span>
              </div>
              
              <input
                type="text"
                value={slide.title}
                onChange={(e) => handleTitleChange(sIdx, e.target.value)}
                className="w-full bg-transparent text-lg font-semibold text-app-text focus:outline-none focus:bg-app-surface focus:ring-1 focus:ring-app-accent rounded px-2 py-1 -ml-2 transition-colors"
              />
              
              <div className="space-y-2">
                {slide.bullets.map((bullet, bIdx) => (
                  <div key={bIdx} className="flex gap-2 items-start group/bullet">
                    <span className="text-app-muted mt-1">•</span>
                    <input
                      type="text"
                      value={bullet}
                      onChange={(e) => handleBulletChange(sIdx, bIdx, e.target.value)}
                      className="flex-1 bg-transparent text-sm text-app-muted focus:text-app-text focus:outline-none focus:bg-app-surface focus:ring-1 focus:ring-app-accent rounded px-2 py-1 -ml-2 transition-colors"
                    />
                    <button 
                      onClick={() => removeBullet(sIdx, bIdx)}
                      className="opacity-0 group-hover/bullet:opacity-100 text-red-400 hover:text-red-300 transition-opacity p-1"
                    >
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                ))}
              </div>
              
              <button 
                onClick={() => addBullet(sIdx)}
                className="text-xs text-app-accent hover:text-app-accent-hover flex items-center gap-1 font-medium transition-colors"
              >
                <Plus className="w-3 h-3" /> Add point
              </button>
            </div>
          </div>
        ))}
      </div>
      
      <div className="fixed bottom-0 left-64 right-0 p-4 bg-app-surface/90 backdrop-blur border-t border-app-border flex items-center justify-between z-20">
        <div className="text-sm text-app-muted">
          {plan.length} slides
        </div>
        <button
          onClick={handleApprove}
          disabled={isSubmitting}
          className="bg-app-accent hover:bg-app-accent-hover text-white font-semibold rounded-lg px-8 py-3 transition-colors disabled:opacity-50 flex items-center gap-2"
        >
          {isSubmitting ? <Loader2 className="w-5 h-5 animate-spin" /> : <Check className="w-5 h-5" />}
          Approve & Generate
        </button>
      </div>
    </div>
  );
}
