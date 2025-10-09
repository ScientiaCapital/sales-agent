/**
 * useVoiceWebSocket Hook
 *
 * Specialized WebSocket hook for voice calls with low-latency audio streaming,
 * transcript updates, and sentiment analysis. Optimized for <100ms latency.
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import { useWebSocket } from './useWebSocket';

interface VoiceWebSocketOptions {
  sessionId: string | null;
  onTranscript?: (transcript: TranscriptChunk) => void;
  onAudioData?: (audioData: AudioData) => void;
  onSentiment?: (sentiment: SentimentData) => void;
  onStateChange?: (state: VoiceCallState) => void;
  onError?: (error: string) => void;
  enableHeartbeat?: boolean;
  reconnectAttempts?: number;
}

interface TranscriptChunk {
  text: string;
  speaker: 'agent' | 'prospect';
  timestamp: string;
  confidence?: number;
  isFinal?: boolean;
}

interface AudioData {
  samples: Float32Array;
  sampleRate: number;
  timestamp: number;
  channelCount: number;
}

interface SentimentData {
  score: number;
  label: 'positive' | 'neutral' | 'negative';
  confidence: number;
  timestamp: string;
  emotions?: Record<string, number>;
}

interface VoiceCallState {
  status: 'connecting' | 'connected' | 'talking' | 'listening' | 'processing' | 'disconnected';
  latencyMs?: number;
  packetLoss?: number;
  jitter?: number;
}

interface VoiceWebSocketReturn {
  isConnected: boolean;
  callState: VoiceCallState;
  latencyMs: number;
  sendAudioChunk: (audioData: ArrayBuffer) => void;
  sendControlMessage: (type: string, data?: any) => void;
  disconnect: () => void;
  metrics: {
    avgLatency: number;
    packetsSent: number;
    packetsReceived: number;
    packetLoss: number;
  };
}

/**
 * Voice-optimized WebSocket hook with audio streaming and real-time metrics
 */
export function useVoiceWebSocket({
  sessionId,
  onTranscript,
  onAudioData,
  onSentiment,
  onStateChange,
  onError,
  enableHeartbeat = true,
  reconnectAttempts = 5
}: VoiceWebSocketOptions): VoiceWebSocketReturn {
  const [callState, setCallState] = useState<VoiceCallState>({
    status: 'disconnected'
  });
  const [latencyMs, setLatencyMs] = useState(0);
  const [metrics, setMetrics] = useState({
    avgLatency: 0,
    packetsSent: 0,
    packetsReceived: 0,
    packetLoss: 0
  });

  // Performance tracking
  const pingTimestampRef = useRef<number>(0);
  const latencyHistoryRef = useRef<number[]>([]);
  const audioQueueRef = useRef<ArrayBuffer[]>([]);
  const processingRef = useRef(false);

  // WebSocket URL
  const wsUrl = sessionId ? `/api/voice/ws/${sessionId}` : null;

  // Base WebSocket hook
  const { isConnected, sendMessage, disconnect } = useWebSocket(wsUrl, {
    onMessage: handleMessage,
    onOpen: handleOpen,
    onClose: handleClose,
    onError: handleError,
    reconnectAttempts,
    reconnectDelay: 1000
  });

  // Heartbeat/ping interval
  useEffect(() => {
    if (!isConnected || !enableHeartbeat) return;

    const interval = setInterval(() => {
      pingTimestampRef.current = Date.now();
      sendMessage(JSON.stringify({ type: 'ping' }));
    }, 30000); // 30 second heartbeat

    return () => clearInterval(interval);
  }, [isConnected, enableHeartbeat, sendMessage]);

  // Process audio queue with requestAnimationFrame for smooth playback
  useEffect(() => {
    if (!isConnected) return;

    let animationId: number;

    const processAudioQueue = () => {
      if (audioQueueRef.current.length > 0 && !processingRef.current) {
        processingRef.current = true;

        // Process up to 10 audio chunks per frame to maintain 60fps
        const chunksToProcess = audioQueueRef.current.splice(0, 10);

        chunksToProcess.forEach(audioBuffer => {
          // Convert ArrayBuffer to Float32Array for audio processing
          const audioData: AudioData = {
            samples: new Float32Array(audioBuffer),
            sampleRate: 16000, // Default sample rate
            timestamp: Date.now(),
            channelCount: 1
          };

          onAudioData?.(audioData);
        });

        processingRef.current = false;
      }

      animationId = requestAnimationFrame(processAudioQueue);
    };

    animationId = requestAnimationFrame(processAudioQueue);

    return () => {
      if (animationId) {
        cancelAnimationFrame(animationId);
      }
    };
  }, [isConnected, onAudioData]);

  // Handle WebSocket open
  function handleOpen() {
    setCallState(prev => ({ ...prev, status: 'connected' }));
    latencyHistoryRef.current = [];
  }

  // Handle WebSocket close
  function handleClose() {
    setCallState(prev => ({ ...prev, status: 'disconnected' }));
    audioQueueRef.current = [];
  }

  // Handle WebSocket error
  function handleError(event: Event) {
    console.error('Voice WebSocket error:', event);
    onError?.('WebSocket connection error');
  }

  // Handle incoming WebSocket messages
  function handleMessage(message: any) {
    try {
      // Update metrics
      setMetrics(prev => ({
        ...prev,
        packetsReceived: prev.packetsReceived + 1
      }));

      switch (message.type) {
        case 'pong':
          // Calculate latency
          if (pingTimestampRef.current) {
            const latency = Date.now() - pingTimestampRef.current;
            setLatencyMs(latency);

            // Update latency history
            latencyHistoryRef.current.push(latency);
            if (latencyHistoryRef.current.length > 100) {
              latencyHistoryRef.current.shift();
            }

            // Calculate average latency
            const avgLatency = latencyHistoryRef.current.reduce((a, b) => a + b, 0) / latencyHistoryRef.current.length;
            setMetrics(prev => ({ ...prev, avgLatency }));

            // Update call state with latency
            setCallState(prev => ({ ...prev, latencyMs: latency }));
          }
          break;

        case 'state':
          // Voice call state update
          const newState: VoiceCallState = {
            status: message.status || 'connected',
            latencyMs: message.latency_ms,
            packetLoss: message.packet_loss,
            jitter: message.jitter
          };
          setCallState(newState);
          onStateChange?.(newState);
          break;

        case 'transcript':
          // Real-time transcript chunk
          const transcript: TranscriptChunk = {
            text: message.text,
            speaker: message.speaker || 'prospect',
            timestamp: message.timestamp || new Date().toISOString(),
            confidence: message.confidence,
            isFinal: message.is_final
          };
          onTranscript?.(transcript);
          break;

        case 'audio':
          // Incoming audio data - queue for processing
          if (message.data) {
            const audioBuffer = base64ToArrayBuffer(message.data);
            audioQueueRef.current.push(audioBuffer);
          }
          break;

        case 'sentiment':
          // Sentiment analysis update
          const sentiment: SentimentData = {
            score: message.score,
            label: message.sentiment || (message.score > 0.3 ? 'positive' : message.score < -0.3 ? 'negative' : 'neutral'),
            confidence: message.confidence || 0.8,
            timestamp: message.timestamp || new Date().toISOString(),
            emotions: message.emotions
          };
          onSentiment?.(sentiment);
          break;

        case 'error':
          console.error('Voice error:', message.error);
          onError?.(message.error);
          break;

        case 'complete':
          // Call completed
          setCallState(prev => ({ ...prev, status: 'disconnected' }));
          break;

        default:
          console.log('Unknown voice message type:', message.type);
      }
    } catch (error) {
      console.error('Failed to process voice message:', error);
    }
  }

  // Send audio chunk to server
  const sendAudioChunk = useCallback((audioData: ArrayBuffer) => {
    if (!isConnected) {
      console.warn('Cannot send audio: WebSocket not connected');
      return;
    }

    // Convert ArrayBuffer to base64 for transmission
    const base64Audio = arrayBufferToBase64(audioData);

    const message = {
      type: 'audio',
      data: base64Audio,
      sample_rate: 16000, // Default 16kHz
      format: 'pcm'
    };

    sendMessage(JSON.stringify(message));

    // Update metrics
    setMetrics(prev => ({
      ...prev,
      packetsSent: prev.packetsSent + 1
    }));
  }, [isConnected, sendMessage]);

  // Send control message (mute, hold, etc.)
  const sendControlMessage = useCallback((type: string, data?: any) => {
    if (!isConnected) {
      console.warn('Cannot send control message: WebSocket not connected');
      return;
    }

    const message = {
      type,
      ...data
    };

    sendMessage(JSON.stringify(message));
  }, [isConnected, sendMessage]);

  // Calculate packet loss
  useEffect(() => {
    const interval = setInterval(() => {
      if (metrics.packetsSent > 0) {
        const loss = 1 - (metrics.packetsReceived / metrics.packetsSent);
        setMetrics(prev => ({
          ...prev,
          packetLoss: Math.max(0, Math.min(1, loss))
        }));
      }
    }, 5000); // Update every 5 seconds

    return () => clearInterval(interval);
  }, [metrics.packetsSent, metrics.packetsReceived]);

  return {
    isConnected,
    callState,
    latencyMs,
    sendAudioChunk,
    sendControlMessage,
    disconnect,
    metrics
  };
}

// Utility functions for audio data conversion
function arrayBufferToBase64(buffer: ArrayBuffer): string {
  const bytes = new Uint8Array(buffer);
  let binary = '';
  for (let i = 0; i < bytes.byteLength; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}

function base64ToArrayBuffer(base64: string): ArrayBuffer {
  const binary = atob(base64);
  const buffer = new ArrayBuffer(binary.length);
  const bytes = new Uint8Array(buffer);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return buffer;
}

export default useVoiceWebSocket;