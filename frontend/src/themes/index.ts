export interface ThemeConfig {
  id: string;
  name: string;
  preview: { bg: string; primary: string; accent: string; text: string; };
}

export const themes: ThemeConfig[] = [
  { id: 'minimal-light', name: 'Minimal Light',
    preview: { bg: '#FFFFFF', primary: '#1A1A1A', accent: '#6366F1', text: '#374151' } },
  { id: 'midnight-professional', name: 'Midnight Professional',
    preview: { bg: '#0F172A', primary: '#E2E8F0', accent: '#38BDF8', text: '#CBD5E1' } },
  { id: 'warm-neutral', name: 'Warm Neutral',
    preview: { bg: '#FAFAF9', primary: '#292524', accent: '#D97706', text: '#44403C' } },
  { id: 'forest-academic', name: 'Forest Academic',
    preview: { bg: '#F0F4F0', primary: '#1C2B1A', accent: '#16A34A', text: '#1C2B1A' } },
  { id: 'slate-coral', name: 'Slate & Coral',
    preview: { bg: '#F8FAFC', primary: '#1E293B', accent: '#F43F5E', text: '#334155' } },
  { id: 'monochrome-editorial', name: 'Monochrome Editorial',
    preview: { bg: '#F5F5F5', primary: '#000000', accent: '#525252', text: '#262626' } },
  { id: 'deep-purple-tech', name: 'Deep Purple Tech',
    preview: { bg: '#1E1B4B', primary: '#E9D5FF', accent: '#A855F7', text: '#C4B5FD' } },
];
