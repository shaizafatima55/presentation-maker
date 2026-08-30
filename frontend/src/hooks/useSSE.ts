import { useEffect, useState } from 'react';
import { useAppStore } from '../store/useAppStore';

export const useSSE = (sessionId: string | null) => {
  const [isConnected, setIsConnected] = useState(false);
  const {
    setPhase,
    setNodeStatus,
    setSearchProgress,
    addSlideToken,
    setDraftPlan,
    setFinalDeck,
    setError,
    setComputedSlideCount,
  } = useAppStore();

  useEffect(() => {
    if (!sessionId) return;

   const eventSource = new EventSource(
  `${import.meta.env.VITE_API_URL}/api/stream/${sessionId}`
);


    eventSource.onopen = () => setIsConnected(true);

    const handleNodeStart = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setNodeStatus(data.node, 'running', data.message);
    };

    const handleNodeDone = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setNodeStatus(data.node, 'done', data.message);
      if (data.node === 'input' && data.slide_count) {
        setComputedSlideCount(data.slide_count);
      }
    };

    const handleSearchProgress = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setSearchProgress(data.progress);
    };

    const handleSlideStream = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      addSlideToken(data.slide_index, data.token);
      setPhase('synthesizing');
    };

    const handleHitlPause = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setDraftPlan(data.draft_plan);
      setPhase('hitl');
      setNodeStatus('plan_review', 'paused', data.message);
    };

    const handleHitlResumed = (e: MessageEvent) => {
      setPhase('generating');
      setNodeStatus('plan_review', 'done');
    };

    const handleComplete = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setFinalDeck(data.deck);
      setPhase('complete');
      eventSource.close();
      setIsConnected(false);
    };

    const handleError = (e: MessageEvent) => {
      const data = JSON.parse(e.data);
      setError(data.message || 'Stream error');
      setPhase('error');
      eventSource.close();
      setIsConnected(false);
    };

    eventSource.addEventListener('node_start', handleNodeStart);
    eventSource.addEventListener('node_done', handleNodeDone);
    eventSource.addEventListener('search_progress', handleSearchProgress);
    eventSource.addEventListener('slide_stream', handleSlideStream);
    eventSource.addEventListener('hitl_pause', handleHitlPause);
    eventSource.addEventListener('hitl_resumed', handleHitlResumed);
    eventSource.addEventListener('complete', handleComplete);
    eventSource.addEventListener('error', handleError);
    eventSource.addEventListener('error', (e: Event) => {
        console.error("SSE Error event", e);
    });

    return () => {
      eventSource.removeEventListener('node_start', handleNodeStart);
      eventSource.removeEventListener('node_done', handleNodeDone);
      eventSource.removeEventListener('search_progress', handleSearchProgress);
      eventSource.removeEventListener('slide_stream', handleSlideStream);
      eventSource.removeEventListener('hitl_pause', handleHitlPause);
      eventSource.removeEventListener('hitl_resumed', handleHitlResumed);
      eventSource.removeEventListener('complete', handleComplete);
      eventSource.removeEventListener('error', handleError);
      eventSource.close();
      setIsConnected(false);
    };
  }, [sessionId]);

  return { isConnected };
};
