/**
 * useRefinement Hook
 * 
 * Manages iterative refinement process with WebSocket streaming
 */

import { useState, useCallback, useEffect } from 'react';
import { useWebSocket } from './useWebSocket';
import { apiClient } from '../services/api';
import type { RefinementStep, StreamMessage } from '../types';

interface UseRefinementOptions {
  leadId: number;
  autoStart?: boolean;
}

interface UseRefinementReturn {
  isRefining: boolean;
  currentStep: number;
  steps: RefinementStep[];
  originalScore: number | null;
  finalScore: number | null;
  improvement: number;
  error: string | null;
  startRefinement: () => Promise<void>;
  reset: () => void;
}

/**
 * Hook for managing iterative refinement process
 * 
 * @example
 * ```tsx
 * const { steps, isRefining, startRefinement } = useRefinement({
 *   leadId: 123,
 *   autoStart: false
 * });
 * ```
 */
export function useRefinement(
  options: UseRefinementOptions
): UseRefinementReturn {
  const { leadId, autoStart = false } = options;

  const [isRefining, setIsRefining] = useState(false);
  const [currentStep, setCurrentStep] = useState(0);
  const [steps, setSteps] = useState<RefinementStep[]>([]);
  const [originalScore, setOriginalScore] = useState<number | null>(null);
  const [finalScore, setFinalScore] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [streamUrl, setStreamUrl] = useState<string | null>(null);

  /**
   * Handle WebSocket messages for refinement updates
   */
  const handleMessage = useCallback((message: StreamMessage) => {
    if (message.type === 'start') {
      setIsRefining(true);
      setError(null);
    } else if (message.type === 'chunk') {
      // Parse refinement step from chunk
      try {
        if (message.content) {
          const stepData = JSON.parse(message.content);
          
          if (stepData.step !== undefined) {
            const step: RefinementStep = {
              step: stepData.step,
              score: stepData.score,
              reasoning: stepData.reasoning,
              improvements: stepData.improvements || [],
              timestamp: message.timestamp,
            };

            setSteps((prev) => {
              const newSteps = [...prev];
              newSteps[stepData.step - 1] = step;
              return newSteps;
            });

            setCurrentStep(stepData.step);
            
            if (stepData.step === 1 && originalScore === null) {
              setOriginalScore(stepData.score);
            }
          }
        }
      } catch (err) {
        console.error('Failed to parse refinement step:', err);
      }
    } else if (message.type === 'complete') {
      setIsRefining(false);
      
      if (steps.length > 0) {
        const lastStep = steps[steps.length - 1];
        setFinalScore(lastStep.score);
      }
    } else if (message.type === 'error') {
      setIsRefining(false);
      setError(message.error || 'Refinement failed');
    }
  }, [originalScore, steps]);

  /**
   * WebSocket connection for streaming
   */
  const { isConnected, disconnect } = useWebSocket(streamUrl, {
    onMessage: handleMessage,
    onError: () => {
      setError('WebSocket connection error');
      setIsRefining(false);
    },
  });

  /**
   * Start refinement process
   */
  const startRefinement = useCallback(async () => {
    try {
      setError(null);
      setSteps([]);
      setCurrentStep(0);
      setOriginalScore(null);
      setFinalScore(null);

      // Start streaming workflow
      const response = await apiClient.startStream(leadId, 'qualification');
      const wsUrl = apiClient.getWebSocketURL(response.stream_id);
      
      setStreamUrl(wsUrl);
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Failed to start refinement';
      setError(errorMessage);
      setIsRefining(false);
    }
  }, [leadId]);

  /**
   * Reset refinement state
   */
  const reset = useCallback(() => {
    disconnect();
    setStreamUrl(null);
    setIsRefining(false);
    setCurrentStep(0);
    setSteps([]);
    setOriginalScore(null);
    setFinalScore(null);
    setError(null);
  }, [disconnect]);

  /**
   * Auto-start if enabled
   */
  useEffect(() => {
    if (autoStart) {
      startRefinement();
    }
  }, [autoStart, startRefinement]);

  /**
   * Calculate improvement percentage
   */
  const improvement =
    originalScore !== null && finalScore !== null
      ? ((finalScore - originalScore) / originalScore) * 100
      : 0;

  return {
    isRefining,
    currentStep,
    steps,
    originalScore,
    finalScore,
    improvement,
    error,
    startRefinement,
    reset,
  };
}

export default useRefinement;
