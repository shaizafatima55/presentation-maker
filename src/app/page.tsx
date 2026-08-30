"use client";

import React, { useState, useEffect } from 'react';
import { Eye, EyeOff, Loader2, CheckCircle2, Download, ChevronRight, Settings } from 'lucide-react';

const THEMES = [
  { id: 'minimal-light', name: 'Minimal Light', bg: '#FFFFFF', text: '#1A1A1A', accent: '#2563EB' },
  { id: 'midnight-pro', name: 'Midnight Professional', bg: '#0F172A', text: '#F1F5F9', accent: '#38BDF8' },
  { id: 'warm-neutral', name: 'Warm Neutral', bg: '#FAF7F2', text: '#2B2B2B', accent: '#D97706' },
  { id: 'forest-academic', name: 'Forest Academic', bg: '#F4F7F4', text: '#1B2E1F', accent: '#15803D' },
  { id: 'slate-coral', name: 'Slate & Coral', bg: '#1E293B', text: '#E2E8F0', accent: '#FB7185' },
  { id: 'mono-editorial', name: 'Monochrome Editorial', bg: '#FFFFFF', text: '#111111', accent: '#000000' },
  { id: 'deep-purple', name: 'Deep Purple Tech', bg: '#1A1230', text: '#EDE9FE', accent: '#A78BFA' },
];

type Step = 'config' | 'processing-plan' | 'review' | 'processing-slides' | 'preview';

export default function PresentationMaker() {
  const [step, setStep] = useState<Step>('config');
  
  // Form State
  const [apiKey, setApiKey] = useState('');
  const [showApiKey, setShowApiKey] = useState(false);
  const [topic, setTopic] = useState('');
  const [duration, setDuration] = useState(15);
  const [selectedTheme, setSelectedTheme] = useState(THEMES[0]);
  
  // Review State
  const [factCheck, setFactCheck] = useState(false);
  const [tone, setTone] = useState('Executive Professional');
  const [directives, setDirectives] = useState('');
  
  // Backend State
  const [summary, setSummary] = useState('');
  const [slidesBlueprint, setSlidesBlueprint] = useState<{title: string, desc: string}[]>([]);
  const [downloadUrl, setDownloadUrl] = useState('');
  
  // Processing State
  const [logs, setLogs] = useState<string[]>([]);
  const [currentAction, setCurrentAction] = useState('');

  const generatePlan = async () => {
    if (!apiKey.trim()) {
      alert("Please enter your Groq API Key.");
      return;
    }

    setStep('processing-plan');
    setCurrentAction("Executing LangGraph Research Node...");
    setLogs([`[${new Date().toISOString()}] Initializing connection to AI Agent backend...`]);

    try {
      const response = await fetch('http://localhost:8000/api/plan', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          api_key: apiKey, 
          topic, 
          duration, 
          theme: selectedTheme 
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Failed to generate plan");
      }
      
      setSummary(data.summary);
      setSlidesBlueprint(data.slides_blueprint);
      setLogs(prev => [...prev, `[${new Date().toISOString()}] Synthesis Complete.`]);
      setStep('review');
    } catch (err: any) {
      alert("Error: " + err.message);
      setStep('config');
    }
  };

  const compileSlides = async () => {
    if (!factCheck) {
      alert('Please acknowledge the fact verification checkpoint.');
      return;
    }
    
    setStep('processing-slides');
    setCurrentAction("Expanding slide content & building PPTX...");
    setLogs([`[${new Date().toISOString()}] Sending directives to content generation node...`]);

    try {
      const response = await fetch('http://localhost:8000/api/compile', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ 
          api_key: apiKey,
          topic,
          fact_check: factCheck,
          tone,
          directives,
          theme: selectedTheme,
          slides_blueprint: slidesBlueprint
        })
      });
      
      const data = await response.json();
      
      if (!response.ok) {
        throw new Error(data.detail || "Failed to compile presentation");
      }
      
      setDownloadUrl(data.download_url);
      setLogs(prev => [...prev, `[${new Date().toISOString()}] Compilation Complete. File Ready.`]);
      setStep('preview');
    } catch (err: any) {
      alert("Error: " + err.message);
      setStep('review');
    }
  };

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      <header className="bg-white border-b border-gray-200 px-6 py-4 flex items-center justify-between sticky top-0 z-10">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 bg-blue-600 rounded-lg flex items-center justify-center">
            <Settings className="w-5 h-5 text-white" />
          </div>
          <h1 className="text-xl font-semibold text-gray-900">Agentic AI Presentation Maker</h1>
        </div>
        <div className="flex gap-4 text-sm font-medium text-gray-500">
          <span className={step === 'config' ? 'text-blue-600' : ''}>1. Config</span>
          <ChevronRight className="w-4 h-4" />
          <span className={step === 'review' ? 'text-blue-600' : ''}>2. Review</span>
          <ChevronRight className="w-4 h-4" />
          <span className={step === 'preview' ? 'text-blue-600' : ''}>3. Output</span>
        </div>
      </header>

      <main className="flex-grow p-6 max-w-7xl mx-auto w-full">
        {step === 'config' && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8">
              <h2 className="text-2xl font-semibold mb-6">Presentation Parameters</h2>
              
              <div className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Groq API Key</label>
                  <div className="relative">
                    <input 
                      type={showApiKey ? 'text' : 'password'} 
                      value={apiKey}
                      onChange={(e) => setApiKey(e.target.value)}
                      className="w-full pl-4 pr-12 py-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all"
                      placeholder="gsk_..."
                    />
                    <button 
                      onClick={() => setShowApiKey(!showApiKey)}
                      className="absolute right-4 top-3 text-gray-400 hover:text-gray-600"
                    >
                      {showApiKey ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
                    </button>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">Topic Presentation Thesis</label>
                  <textarea 
                    value={topic}
                    onChange={(e) => setTopic(e.target.value)}
                    rows={4}
                    className="w-full p-4 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 focus:outline-none transition-all resize-none"
                    placeholder="Enter a detailed thesis or topic description..."
                  />
                </div>

                <div>
                  <div className="flex justify-between items-center mb-2">
                    <label className="block text-sm font-medium text-gray-700">Duration (Minutes)</label>
                    <span className="font-semibold text-blue-600">{duration} min</span>
                  </div>
                  <input 
                    type="range" 
                    min="10" 
                    max="60" 
                    step="5"
                    value={duration}
                    onChange={(e) => setDuration(parseInt(e.target.value))}
                    className="w-full h-2 bg-gray-200 rounded-lg appearance-none cursor-pointer accent-blue-600"
                  />
                  <div className="flex justify-between text-xs text-gray-400 mt-2">
                    <span>10m</span>
                    <span>60m</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-4">Structural Color Palette Theme</label>
                  <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                    {THEMES.map(theme => (
                      <button
                        key={theme.id}
                        onClick={() => setSelectedTheme(theme)}
                        className={`p-4 rounded-xl border-2 text-left transition-all ${selectedTheme.id === theme.id ? 'border-blue-600 shadow-md scale-[1.02]' : 'border-gray-100 hover:border-gray-200 hover:bg-gray-50'}`}
                      >
                        <div className="flex h-8 rounded-md overflow-hidden mb-3 border border-gray-100">
                          <div className="w-1/3" style={{ backgroundColor: theme.bg }}></div>
                          <div className="w-1/3" style={{ backgroundColor: theme.text }}></div>
                          <div className="w-1/3" style={{ backgroundColor: theme.accent }}></div>
                        </div>
                        <span className="text-sm font-medium text-gray-800">{theme.name}</span>
                      </button>
                    ))}
                  </div>
                </div>
              </div>

              <div className="mt-8 pt-6 border-t border-gray-100 flex justify-end">
                <button 
                  onClick={generatePlan}
                  disabled={!topic.trim() || !apiKey.trim()}
                  className="px-8 py-3 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  Generate Plan Blueprint
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          </div>
        )}

        {(step === 'processing-plan' || step === 'processing-slides') && (
          <div className="flex flex-col items-center justify-center h-[60vh] space-y-8 animate-in fade-in duration-500">
            <div className="relative">
              <div className="w-24 h-24 border-4 border-blue-100 rounded-full animate-pulse"></div>
              <Loader2 className="w-12 h-12 text-blue-600 animate-spin absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2" />
            </div>
            
            <div className="text-center space-y-2">
              <h3 className="text-xl font-semibold text-gray-900">{currentAction}</h3>
              <p className="text-gray-500">Processing via LangGraph Pipeline...</p>
            </div>

            <div className="w-full max-w-2xl bg-gray-900 rounded-xl p-4 font-mono text-sm text-green-400 overflow-hidden h-48 border border-gray-800 shadow-xl">
              <div className="flex flex-col justify-end h-full">
                {logs.map((log, i) => (
                  <div key={i} className="opacity-90 py-1">{log}</div>
                ))}
                <div className="animate-pulse">_</div>
              </div>
            </div>
          </div>
        )}

        {step === 'review' && (
          <div className="space-y-6 animate-in fade-in slide-in-from-bottom-4 duration-500">
            <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
              <div className="flex justify-between items-center mb-6">
                <h2 className="text-2xl font-bold text-gray-900">Plan Review Dashboard</h2>
                <div className="bg-blue-50 text-blue-700 px-4 py-1.5 rounded-full text-sm font-semibold">
                  Suggested Slides: {slidesBlueprint.length}
                </div>
              </div>

              <div className="grid lg:grid-cols-2 gap-8">
                <div className="space-y-6">
                  <div>
                    <h3 className="text-lg font-semibold border-b pb-2 mb-4">Factual Deep-Dive Summary</h3>
                    <div className="space-y-4 text-gray-600 leading-relaxed text-sm whitespace-pre-wrap">
                      {summary}
                    </div>
                  </div>
                </div>

                <div>
                  <h3 className="text-lg font-semibold border-b pb-2 mb-4">Slide Architecture Blueprint</h3>
                  <div className="space-y-3 max-h-96 overflow-y-auto pr-2">
                    {slidesBlueprint.map((slide, i) => (
                      <div key={i} className="flex gap-4 p-3 bg-gray-50 rounded-lg border border-gray-100">
                        <div className="w-8 h-8 shrink-0 bg-white border border-gray-200 rounded flex items-center justify-center font-bold text-gray-500 text-sm">
                          {i + 1}
                        </div>
                        <div>
                          <div className="font-semibold text-sm text-gray-900">{slide.title}</div>
                          <div className="text-xs text-gray-500 mt-1">{slide.desc}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <div className="bg-white p-8 rounded-xl shadow-sm border border-gray-200">
              <h3 className="text-lg font-semibold mb-6">Human-in-the-Loop Controls</h3>
              
              <div className="space-y-6">
                <label className="flex items-start gap-4 p-4 border border-blue-100 bg-blue-50/50 rounded-lg cursor-pointer">
                  <input 
                    type="checkbox" 
                    checked={factCheck}
                    onChange={(e) => setFactCheck(e.target.checked)}
                    className="mt-1 w-5 h-5 rounded border-gray-300 text-blue-600 focus:ring-blue-600"
                  />
                  <div>
                    <div className="font-semibold text-blue-900">Checkpoint 1: Fact Check Verification</div>
                    <div className="text-sm text-blue-700 mt-1">I acknowledge that I have reviewed the factual summary and structural blueprint above.</div>
                  </div>
                </label>

                <div>
                  <label className="block font-semibold mb-2">Checkpoint 2: Tone / Focus Mode</label>
                  <select 
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                    className="w-full p-3 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                  >
                    <option>Executive Professional</option>
                    <option>Detailed Academic</option>
                    <option>Startup Pitch</option>
                  </select>
                </div>

                <div>
                  <label className="block font-semibold mb-2">Checkpoint 3: Custom Directives</label>
                  <textarea 
                    value={directives}
                    onChange={(e) => setDirectives(e.target.value)}
                    rows={3}
                    placeholder="Provide detailed layout modifications and context alterations..."
                    className="w-full p-4 bg-gray-50 border border-gray-200 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none resize-none"
                  />
                </div>
              </div>

              <div className="mt-8 pt-6 border-t flex justify-between items-center">
                <button 
                  onClick={() => setStep('config')}
                  className="px-6 py-2 text-gray-600 hover:text-gray-900 font-medium"
                >
                  Back to Config
                </button>
                <button 
                  onClick={compileSlides}
                  className="px-8 py-3 bg-green-600 text-white rounded-lg font-bold hover:bg-green-700 transition-colors flex items-center gap-2 shadow-lg shadow-green-600/20"
                >
                  <CheckCircle2 className="w-5 h-5" />
                  Approve Plan & Compile Decks
                </button>
              </div>
            </div>
          </div>
        )}

        {step === 'preview' && (
          <div className="space-y-8 animate-in fade-in slide-in-from-bottom-4 duration-500 pb-20">
            <div className="flex justify-between items-center bg-white p-4 rounded-xl border border-gray-200 shadow-sm sticky top-20 z-10">
              <div>
                <h2 className="text-xl font-bold">Presentation Compiled</h2>
                <p className="text-sm text-gray-500">{slidesBlueprint.length} Slides • {selectedTheme.name} Theme</p>
              </div>
              <a 
                href={downloadUrl}
                download
                className="px-6 py-2.5 bg-blue-600 text-white rounded-lg font-medium hover:bg-blue-700 transition-colors flex items-center gap-2"
              >
                <Download className="w-4 h-4" />
                Download .PPTX
              </a>
            </div>

            <div className="space-y-12">
              <div 
                className="aspect-video w-full max-w-5xl mx-auto rounded-xl shadow-2xl overflow-hidden flex flex-col justify-center px-20 border border-gray-200"
                style={{ backgroundColor: selectedTheme.bg }}
              >
                <div className="w-16 h-2 mb-8" style={{ backgroundColor: selectedTheme.accent }}></div>
                <h1 className="text-6xl font-bold mb-6 leading-tight" style={{ color: selectedTheme.text }}>
                  {topic.substring(0, 50)}...
                </h1>
                <p className="text-xl opacity-80" style={{ color: selectedTheme.text }}>
                  Presentation output generated by AI Agent.
                </p>
              </div>
            </div>

            <div className="fixed bottom-0 left-0 right-0 bg-gray-900 border-t border-gray-800 p-3 flex items-center justify-center gap-4 text-xs font-mono text-gray-400 z-50">
              <span className="text-green-400">● Pipeline Active</span>
              <span className="opacity-50">|</span>
              <span>Trace: Config → Plan Synthesis → Approval → Compilation</span>
              <span className="opacity-50">|</span>
              <span>Port: 8000 Connected</span>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
