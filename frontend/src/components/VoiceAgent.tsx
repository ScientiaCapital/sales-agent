/**
 * Voice Agent Component
 * 
 * Voice call interface with Cartesia integration
 * Audio waveform visualization and microphone controls
 */

import { useState, useRef, useEffect, memo } from 'react';
import type { VoiceCall, AudioWaveform } from '../types';

interface VoiceAgentProps {
  leadId: number;
  onCallComplete?: (call: VoiceCall) => void;
}

export const VoiceAgent = memo(({ leadId, onCallComplete }: VoiceAgentProps) => {
  const [callState, setCallState] = useState<VoiceCall['status']>('initializing');
  const [isMuted, setIsMuted] = useState(false);
  const [duration, setDuration] = useState(0);
  const [waveformData, setWaveformData] = useState<AudioWaveform[]>([]);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  /**
   * Start voice call
   */
  const startCall = () => {
    setCallState('ringing');

    // Simulate call connection
    setTimeout(() => {
      setCallState('connected');

      // Start timer
      timerRef.current = setInterval(() => {
        setDuration((prev) => prev + 1);
      }, 1000);

      // Simulate waveform data
      const waveformInterval = setInterval(() => {
        setWaveformData((prev) => {
          const newData = [
            ...prev,
            {
              timestamp: Date.now(),
              amplitude: Math.random() * 100,
            },
          ];
          return newData.slice(-50); // Keep last 50 points
        });
      }, 100);

      return () => clearInterval(waveformInterval);
    }, 2000);
  };

  /**
   * End voice call
   */
  const endCall = () => {
    if (timerRef.current) {
      clearInterval(timerRef.current);
    }

    setCallState('ended');

    const call: VoiceCall = {
      id: Date.now().toString(),
      lead_id: leadId,
      status: 'ended',
      duration_seconds: duration,
      transcript: 'Mock call transcript...',
      sentiment_score: 0.75,
      started_at: new Date(Date.now() - duration * 1000).toISOString(),
      ended_at: new Date().toISOString(),
    };

    onCallComplete?.(call);
  };

  /**
   * Format duration as MM:SS
   */
  const formatDuration = (seconds: number) => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  useEffect(() => {
    return () => {
      if (timerRef.current) {
        clearInterval(timerRef.current);
      }
    };
  }, []);

  return (
    <div className="max-w-2xl mx-auto">
      <div className="bg-gradient-to-br from-purple-600 to-blue-600 rounded-2xl shadow-2xl p-8 text-white">
        {/* Header */}
        <div className="text-center mb-8">
          <h2 className="text-2xl font-bold mb-2">Voice Agent</h2>
          <p className="text-purple-100">AI-Powered Voice Calls</p>
        </div>

        {/* Call Status */}
        <div className="bg-white/10 backdrop-blur rounded-lg p-6 mb-6">
          <div className="text-center">
            <div className="text-6xl mb-4">
              {callState === 'initializing' && '🎤'}
              {callState === 'ringing' && '📞'}
              {callState === 'connected' && '🗣️'}
              {callState === 'ended' && '✓'}
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

        {/* Waveform Visualization */}
        {callState === 'connected' && (
          <div className="bg-white/10 backdrop-blur rounded-lg p-4 mb-6">
            <div className="flex items-end justify-center space-x-1 h-24">
              {waveformData.slice(-30).map((point, index) => (
                <div
                  key={index}
                  className="bg-white rounded-full w-2 transition-all duration-75"
                  style={{
                    height: `${Math.max(point.amplitude, 10)}%`,
                    opacity: 0.7 + (index / 30) * 0.3,
                  }}
                />
              ))}
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
                onClick={() => setIsMuted(!isMuted)}
                className={`
                  p-4 rounded-full shadow-lg transition-all transform hover:scale-105
                  ${isMuted ? 'bg-yellow-500 hover:bg-yellow-600' : 'bg-white/20 hover:bg-white/30'}
                `}
              >
                <span className="text-2xl">{isMuted ? '🔇' : '🎤'}</span>
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
              <span className="text-sm">Connected to Lead #{leadId}</span>
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
              }}
              className="px-6 py-2 bg-white/20 hover:bg-white/30 rounded-lg"
            >
              Start New Call
            </button>
          </div>
        )}
      </div>

      {/* Call Transcript (if ended) */}
      {callState === 'ended' && (
        <div className="mt-6 bg-white rounded-lg shadow p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">
            Call Transcript
          </h3>
          <div className="prose max-w-none">
            <p className="text-gray-600">
              Transcript will appear here after the call completes...
            </p>
          </div>

          <div className="mt-4 pt-4 border-t border-gray-200">
            <div className="flex justify-between text-sm">
              <span className="text-gray-600">Sentiment Score</span>
              <span className="font-medium text-green-600">75% Positive</span>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

VoiceAgent.displayName = 'VoiceAgent';

export default VoiceAgent;
