/**
 * Voice Agent Component
 *
 * Real-time voice call interface with WebSocket streaming, live waveform
 * visualization, transcript updates, and sentiment analysis
 */

/// <reference types="node" />
import { useState, useRef, useEffect, memo } from 'react';
import { useVoiceWebSocket } from '../hooks/useVoiceWebSocket';
import { SentimentIndicator } from './SentimentIndicator';
import type { VoiceCall, AudioWaveform } from '../types';

interface VoiceAgentProps {
  leadId: number;
  onCallComplete?: (call: VoiceCall) => void;
  onCallStart?: (call: VoiceCall) => void;
}

export const VoiceAgent = memo(({ leadId, onCallComplete, onCallStart }: VoiceAgentProps) => {
  const [callState, setCallState] = useState<VoiceCall['status']>('initializing');
  const [sessionId, setSessionId] = useState<string | null>(null);
  const [currentCall, setCurrentCall] = useState<VoiceCall | null>(null);
  const [isMuted, setIsMuted] = useState(false);
  const [isOnHold, setIsOnHold] = useState(false);
  const [duration, setDuration] = useState(0);
  const [transcript, setTranscript] = useState<string[]>([]);
  const [sentiment, setSentiment] = useState<number>(0);
  const [sentimentHistory, setSentimentHistory] = useState<number[]>([]);
  const [, setWaveformData] = useState<AudioWaveform[]>([]);

  // Refs for audio processing
  const timerRef = useRef<NodeJS.Timeout | null>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const analyserRef = useRef<AnalyserNode | null>(null);
  const mediaStreamRef = useRef<MediaStream | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const animationIdRef = useRef<number | null>(null);

  // WebSocket connection
  const {
    isConnected,
    latencyMs,
    sendAudioChunk,
    sendControlMessage,
    disconnect,
    metrics
  } = useVoiceWebSocket({
    sessionId,
    onTranscript: (chunk) => {
      // Add transcript chunk to display
      setTranscript(prev => [...prev, `${chunk.speaker}: ${chunk.text}`]);
    },
    onSentiment: (sentimentData) => {
      // Update sentiment display
      setSentiment(sentimentData.score);
      setSentimentHistory(prev => [...prev.slice(-29), sentimentData.score]);
    },
    onStateChange: (state) => {
      // Update call state based on WebSocket state
      if (state.status === 'connected') {
        setCallState('connected');
      } else if (state.status === 'disconnected') {
        setCallState('ended');
      }
    },
    onError: (error) => {
      console.error('Voice WebSocket error:', error);
      setCallState('failed');
    }
  });

  /**
   * Initialize audio context and microphone access
   */
  const initializeAudio = async () => {
    try {
      // Create audio context
      audioContextRef.current = new (window.AudioContext || (window as any).webkitAudioContext)({
        sampleRate: 16000
      });

      // Get microphone access
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
          sampleRate: 16000
        }
      });

      mediaStreamRef.current = stream;

      // Create audio nodes
      const source = audioContextRef.current.createMediaStreamSource(stream);
      const analyser = audioContextRef.current.createAnalyser();
      analyser.fftSize = 256;
      analyser.smoothingTimeConstant = 0.8;

      source.connect(analyser);
      analyserRef.current = analyser;

      // Start waveform visualization
      visualizeWaveform();

      // Start capturing audio chunks for WebSocket
      startAudioCapture(stream);

      return true;
    } catch (error) {
      console.error('Failed to initialize audio:', error);
      return false;
    }
  };

  /**
   * Visualize audio waveform at 60fps
   */
  const visualizeWaveform = () => {
    if (!analyserRef.current || !canvasRef.current) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    const analyser = analyserRef.current;
    const bufferLength = analyser.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);

    const draw = () => {
      animationIdRef.current = requestAnimationFrame(draw);

      analyser.getByteFrequencyData(dataArray);

      // Clear canvas
      ctx.fillStyle = 'rgba(255, 255, 255, 0.1)';
      ctx.fillRect(0, 0, canvas.width, canvas.height);

      // Draw frequency bars
      const barWidth = (canvas.width / bufferLength) * 2.5;
      let barHeight;
      let x = 0;

      for (let i = 0; i < bufferLength; i++) {
        barHeight = (dataArray[i] / 255) * canvas.height * 0.8;

        // Color based on frequency
        const hue = (i / bufferLength) * 120 + 200; // Blue to purple gradient
        ctx.fillStyle = `hsl(${hue}, 70%, 50%)`;

        ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);
        x += barWidth + 1;
      }

      // Update waveform data for React state
      const amplitude = dataArray.reduce((sum, val) => sum + val, 0) / bufferLength;
      setWaveformData(prev => {
        const newData = [...prev, { timestamp: Date.now(), amplitude }];
        return newData.slice(-50); // Keep last 50 points
      });
    };

    draw();
  };

  /**
   * Capture audio chunks and send via WebSocket
   */
  const startAudioCapture = (stream: MediaStream) => {
    const mediaRecorder = new MediaRecorder(stream, {
      mimeType: 'audio/webm',
      audioBitsPerSecond: 16000
    });

    mediaRecorder.ondataavailable = async (event) => {
      if (event.data.size > 0 && !isMuted) {
        // Convert blob to ArrayBuffer and send
        const arrayBuffer = await event.data.arrayBuffer();
        sendAudioChunk(arrayBuffer);
      }
    };

    // Capture audio in 100ms chunks for low latency
    mediaRecorder.start(100);
  };

  /**
   * Start voice call
   */
  const startCall = async () => {
    setCallState('ringing');

    // Initialize audio first
    const audioReady = await initializeAudio();
    if (!audioReady) {
      setCallState('failed');
      return;
    }

    try {
      // Create voice session via API
      const response = await fetch('/api/voice/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          lead_id: leadId,
          voice_id: 'a0e99841-438c-4a64-b679-ae501e7d6091',
          language: 'en',
          emotion: 'professional'
        })
      });

      if (!response.ok) {
        throw new Error('Failed to create voice session');
      }

      const data = await response.json();
      setSessionId(data.session_id);

      // Create call object
      const call: VoiceCall = {
        id: data.session_id,
        lead_id: leadId,
        status: 'connected',
        started_at: new Date().toISOString()
      };

      setCurrentCall(call);
      setCallState('connected');
      onCallStart?.(call);

      // Start duration timer
      timerRef.current = setInterval(() => {
        setDuration(prev => prev + 1);
      }, 1000);
    } catch (error) {
      console.error('Failed to start call:', error);
      setCallState('failed');
    }
  };

  /**
   * End voice call
   */
  const endCall = async () => {
    // Stop timer
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }

    // Stop audio
    if (mediaStreamRef.current) {
      mediaStreamRef.current.getTracks().forEach(track => track.stop());
      mediaStreamRef.current = null;
    }

    // Stop visualization
    if (animationIdRef.current) {
      cancelAnimationFrame(animationIdRef.current);
      animationIdRef.current = null;
    }

    // Close audio context
    if (audioContextRef.current) {
      await audioContextRef.current.close();
      audioContextRef.current = null;
    }

    // Disconnect WebSocket
    disconnect();

    // Update call state
    setCallState('ended');

    // Send end session request if we have a session
    if (sessionId) {
      try {
        await fetch(`/api/voice/sessions/${sessionId}`, {
          method: 'DELETE'
        });
      } catch (error) {
        console.error('Failed to end session:', error);
      }
    }

    // Create final call object
    if (currentCall) {
      const finalCall: VoiceCall = {
        ...currentCall,
        status: 'ended',
        duration_seconds: duration,
        transcript: transcript.join('\n'),
        sentiment_score: sentiment,
        ended_at: new Date().toISOString()
      };

      onCallComplete?.(finalCall);
    }
  };

  /**
   * Toggle mute
   */
  const toggleMute = () => {
    setIsMuted(!isMuted);
    sendControlMessage('adjust_mute', { muted: !isMuted });
  };

  /**
   * Toggle hold
   */
  const toggleHold = () => {
    setIsOnHold(!isOnHold);
    sendControlMessage('adjust_hold', { on_hold: !isOnHold });
  };

  /**
   * Transfer call
   */
  const transferCall = () => {
    sendControlMessage('transfer', { target_agent: 'supervisor' });
  };

  /**
   * Format duration as MM:SS
   */
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (animationIdRef.current) cancelAnimationFrame(animationIdRef.current);
      if (mediaStreamRef.current) {
        mediaStreamRef.current.getTracks().forEach(track => track.stop());
      }
      if (audioContextRef.current && audioContextRef.current.state !== 'closed') {
        audioContextRef.current.close();
      }
    };
  }, []);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-gradient-to-br from-purple-600 to-blue-600 rounded-2xl shadow-2xl p-8 text-white">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold mb-2">Voice Agent</h2>
          <p className="text-purple-100">AI-Powered Real-Time Conversations</p>
        </div>

        {/* Connection Status */}
        {isConnected && (
          <div className="bg-white/10 backdrop-blur rounded-lg p-3 mb-4">
            <div className="flex justify-between items-center text-sm">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
                <span>Connected</span>
              </div>
              <div className="flex gap-4">
                <span>Latency: {latencyMs}ms</span>
                <span>Loss: {(metrics.packetLoss * 100).toFixed(1)}%</span>
              </div>
            </div>
          </div>
        )}

        {/* Call Status */}
        <div className="bg-white/10 backdrop-blur rounded-lg p-6 mb-6">
          <div className="text-center">
            <div className="text-6xl mb-4">
              {callState === 'initializing' && '🎤'}
              {callState === 'ringing' && '📞'}
              {callState === 'connected' && '🗣️'}
              {callState === 'ended' && '✓'}
              {callState === 'failed' && '❌'}
            </div>

            <div className="text-2xl font-bold mb-2 capitalize">
              {callState === 'connected' ? 'In Call' : callState}
            </div>

            {callState === 'connected' && (
              <div className="text-4xl font-mono font-bold">
                {formatDuration(duration)}
              </div>
            )}
          </div>
        </div>

        {/* Live Waveform Visualization */}
        {callState === 'connected' && (
          <div className="bg-white/10 backdrop-blur rounded-lg p-4 mb-6">
            <canvas
              ref={canvasRef}
              width={600}
              height={100}
              className="w-full h-24 rounded"
              style={{ background: 'rgba(0,0,0,0.2)' }}
            />
          </div>
        )}

        {/* Sentiment Indicator */}
        {callState === 'connected' && (
          <div className="bg-white/10 backdrop-blur rounded-lg p-4 mb-6">
            <div className="flex justify-between items-center">
              <span className="text-sm font-medium">Live Sentiment:</span>
              <SentimentIndicator
                score={sentiment}
                history={sentimentHistory}
                showSparkline
                className="text-white"
              />
            </div>
          </div>
        )}

        {/* Controls */}
        <div className="flex justify-center space-x-4">
          {callState === 'initializing' && (
            <button
              onClick={startCall}
              className="px-8 py-4 bg-green-500 hover:bg-green-600 rounded-full text-white font-semibold text-lg shadow-lg transition-all transform hover:scale-105"
            >
              Start Call
            </button>
          )}

          {callState === 'connected' && (
            <>
              <button
                onClick={toggleMute}
                className={`
                  p-4 rounded-full shadow-lg transition-all transform hover:scale-105
                  ${isMuted ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-white/20 hover:bg-white/30'}
                `}
                title={isMuted ? 'Unmute' : 'Mute'}
              >
                <span className="text-2xl">{isMuted ? '🔇' : '🎤'}</span>
              </button>

              <button
                onClick={toggleHold}
                className={`
                  p-4 rounded-full shadow-lg transition-all transform hover:scale-105
                  ${isOnHold ? 'bg-orange-500 hover:bg-orange-600' : 'bg-white/20 hover:bg-white/30'}
                `}
                title={isOnHold ? 'Resume' : 'Hold'}
              >
                <span className="text-2xl">{isOnHold ? '⏸️' : '▶️'}</span>
              </button>

              <button
                onClick={transferCall}
                className="p-4 bg-white/20 hover:bg-white/30 rounded-full shadow-lg transition-all transform hover:scale-105"
                title="Transfer"
              >
                <span className="text-2xl">🔄</span>
              </button>

              <button
                onClick={endCall}
                className="px-8 py-4 bg-red-500 hover:bg-red-600 rounded-full text-white font-semibold text-lg shadow-lg transition-all transform hover:scale-105"
              >
                End Call
              </button>
            </>
          )}
        </div>

        {/* Call Info */}
        {callState === 'connected' && (
          <div className="mt-6 text-center">
            <div className="inline-flex items-center space-x-2 bg-white/10 backdrop-blur rounded-full px-4 py-2">
              <span className="w-2 h-2 bg-green-400 rounded-full animate-pulse" />
              <span className="text-sm">Lead #{leadId} • {metrics.avgLatency.toFixed(0)}ms avg latency</span>
            </div>
          </div>
        )}

        {callState === 'ended' && (
          <div className="mt-6 text-center">
            <p className="text-green-100 mb-4">Call completed successfully</p>
            <button
              onClick={() => {
                setCallState('initializing');
                setDuration(0);
                setWaveformData([]);
                setTranscript([]);
                setSentiment(0);
                setSentimentHistory([]);
                setSessionId(null);
              }}
              className="px-6 py-2 bg-white/20 hover:bg-white/30 rounded-lg"
            >
              Start New Call
            </button>
          </div>
        )}

        {callState === 'failed' && (
          <div className="mt-6 text-center">
            <p className="text-red-100 mb-4">Call failed. Please check your connection and try again.</p>
            <button
              onClick={() => {
                setCallState('initializing');
                setDuration(0);
              }}
              className="px-6 py-2 bg-white/20 hover:bg-white/30 rounded-lg"
            >
              Try Again
            </button>
          </div>
        )}
      </div>

      {/* Live Transcript (if call is active or ended) */}
      {(callState === 'connected' || callState === 'ended') && transcript.length > 0 && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Live Transcript
          </h3>
          <div className="max-h-64 overflow-y-auto space-y-2">
            {transcript.map((line, index) => (
              <div key={index} className="text-sm">
                <span className={line.startsWith('Agent:') ? 'text-blue-600 font-medium' : 'text-gray-600'}>
                  {line}
                </span>
              </div>
            ))}
          </div>

          {sentiment !== 0 && (
            <div className="mt-4 pt-4 border-t border-gray-200">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Overall Sentiment</span>
                <SentimentIndicator score={sentiment} compact showTrend={false} />
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
});

VoiceAgent.displayName = 'VoiceAgent';

export default VoiceAgent;