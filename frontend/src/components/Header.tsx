import { Sparkles, Plus } from 'lucide-react';
import { useAppStore } from '../store/useAppStore';
import ThemeSelector from './ThemeSelector';

export default function Header() {
  const { phase, reset } = useAppStore();

  return (
    <header className="h-[56px] flex items-center justify-between px-6 bg-app-surface border-b border-app-border shrink-0 z-10">
      <div className="flex items-center gap-2 cursor-pointer" onClick={reset}>
        <Sparkles className="w-5 h-5 text-app-accent" />
        <span className="font-semibold text-lg bg-gradient-to-r from-[#7C6FE0] to-[#A78BFA] bg-clip-text text-transparent">
          AI Slide Maker
        </span>
      </div>
      
      <div className="flex items-center gap-4">
        <ThemeSelector />
        
        {phase === 'complete' && (
          <button 
            onClick={reset}
            className="flex items-center gap-2 text-sm font-medium bg-app-accent hover:bg-app-accent-hover text-white px-4 py-2 rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Presentation
          </button>
        )}
      </div>
    </header>
  );
}
