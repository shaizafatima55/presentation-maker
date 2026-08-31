"use client";

import { useState, useRef, useEffect } from 'react';
import { Check, ChevronDown } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import { themes } from '../themes';
import { Theme } from '../types';

export default function ThemeSelector() {
  const [isOpen, setIsOpen] = useState(false);
  const { selectedTheme, setSelectedTheme, setFormData } = useAppStore();
  const dropdownRef = useRef<HTMLDivElement>(null);

  const currentTheme = themes.find(t => t.id === selectedTheme) || themes[0];

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleSelect = (themeId: Theme) => {
    setSelectedTheme(themeId);
    setFormData({ theme: themeId });
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-app-border hover:bg-app-border/50 transition-colors text-sm"
      >
        <div 
          className="w-3 h-3 rounded-full" 
          style={{ backgroundColor: currentTheme.preview.accent }}
        />
        <span className="text-app-text">{currentTheme.name}</span>
        <ChevronDown className="w-4 h-4 text-app-muted" />
      </button>

      {isOpen && (
        <div className="absolute right-0 mt-2 w-64 bg-app-surface border border-app-border rounded-xl shadow-xl overflow-hidden z-50">
          <div className="p-2 space-y-1">
            {themes.map((theme) => (
              <button
                key={theme.id}
                onClick={() => handleSelect(theme.id as Theme)}
                className="w-full flex items-center justify-between p-2 hover:bg-app-border/50 rounded-lg transition-colors group"
              >
                <div className="flex items-center gap-3">
                  <div className="flex w-6 h-6 rounded-md overflow-hidden border border-app-border/50">
                    <div className="w-1/3 h-full" style={{ backgroundColor: theme.preview.bg }} />
                    <div className="w-1/3 h-full" style={{ backgroundColor: theme.preview.accent }} />
                    <div className="w-1/3 h-full" style={{ backgroundColor: theme.preview.text }} />
                  </div>
                  <span className={`text-sm ${selectedTheme === theme.id ? 'text-app-text font-medium' : 'text-app-muted group-hover:text-app-text'}`}>
                    {theme.name}
                  </span>
                </div>
                {selectedTheme === theme.id && <Check className="w-4 h-4 text-app-accent" />}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
