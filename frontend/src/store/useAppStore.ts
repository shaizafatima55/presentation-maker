import { create } from 'zustand';
import { AppPhase, GenerateFormData, NodeStatus, SlideDeck, SlideItem, Theme } from '../types';

interface AppStore {
  // Phase
  phase: AppPhase;
  setPhase: (p: AppPhase) => void;
  
  // Session
  sessionId: string | null;
  setSessionId: (id: string) => void;
  
  // Form data
  formData: GenerateFormData;
  setFormData: (data: Partial<GenerateFormData>) => void;
  
  // Node statuses: Record<nodeId, NodeStatus>
  nodeStatuses: Record<string, NodeStatus>;
  nodeMessages: Record<string, string>;
  setNodeStatus: (node: string, status: NodeStatus, message?: string) => void;
  
  // Search progress
  searchProgress: number; // 0-1
  setSearchProgress: (p: number) => void;
  
  // HITL
  draftPlan: SlideItem[];
  setDraftPlan: (plan: SlideItem[]) => void;
  
  // Slide streaming
  streamingSlides: Record<number, string>; // slideIndex -> accumulated content
  addSlideToken: (slideIndex: number, token: string) => void;
  
  // Final deck
  finalDeck: SlideDeck | null;
  setFinalDeck: (deck: SlideDeck) => void;
  
  // Slide count computed
  computedSlideCount: number;
  setComputedSlideCount: (n: number) => void;
  
  // Error
  error: string | null;
  setError: (msg: string) => void;
  
  // Slide preview
  currentSlideIndex: number;
  setCurrentSlideIndex: (i: number) => void;
  
  // Theme
  selectedTheme: Theme;
  setSelectedTheme: (t: Theme) => void;
  
  // Reset
  reset: () => void;
}

const defaultFormData: GenerateFormData = {
  topic: '',
  duration_minutes: 20,
  audience: 'General',
  tone: 'professional',
  groq_api_key: '',
  tavily_api_key: '',
  theme: 'midnight-professional'
};

export const useAppStore = create<AppStore>((set) => ({
  phase: 'input',
  setPhase: (phase) => set({ phase }),
  
  sessionId: null,
  setSessionId: (sessionId) => set({ sessionId }),
  
  formData: defaultFormData,
  setFormData: (data) => set((state) => ({ formData: { ...state.formData, ...data } })),
  
  nodeStatuses: {},
  nodeMessages: {},
  setNodeStatus: (node, status, message) => set((state) => {
    const newNodeStatuses = { ...state.nodeStatuses, [node]: status };
    const newNodeMessages = { ...state.nodeMessages };
    if (message !== undefined) {
      newNodeMessages[node] = message;
    }
    return { nodeStatuses: newNodeStatuses, nodeMessages: newNodeMessages };
  }),
  
  searchProgress: 0,
  setSearchProgress: (searchProgress) => set({ searchProgress }),
  
  draftPlan: [],
  setDraftPlan: (draftPlan) => set({ draftPlan }),
  
  streamingSlides: {},
  addSlideToken: (slideIndex, token) => set((state) => ({
    streamingSlides: {
      ...state.streamingSlides,
      [slideIndex]: (state.streamingSlides[slideIndex] || '') + token
    }
  })),
  
  finalDeck: null,
  setFinalDeck: (finalDeck) => set({ finalDeck }),
  
  computedSlideCount: 0,
  setComputedSlideCount: (computedSlideCount) => set({ computedSlideCount }),
  
  error: null,
  setError: (error) => set({ error }),
  
  currentSlideIndex: 0,
  setCurrentSlideIndex: (currentSlideIndex) => set({ currentSlideIndex }),
  
  selectedTheme: 'midnight-professional',
  setSelectedTheme: (selectedTheme) => set({ selectedTheme }),
  
  reset: () => set({
    phase: 'input',
    sessionId: null,
    formData: defaultFormData,
    nodeStatuses: {},
    nodeMessages: {},
    searchProgress: 0,
    draftPlan: [],
    streamingSlides: {},
    finalDeck: null,
    computedSlideCount: 0,
    error: null,
    currentSlideIndex: 0,
    selectedTheme: 'midnight-professional',
  })
}));
