/**
 * Call Transcript Viewer Component
 *
 * Displays conversation transcripts with speaker labels, timestamps,
 * sentiment indicators, and keyword highlighting for pain points and buying signals
 */

import { useState, useEffect, useMemo, useRef } from 'react';
import { SentimentIndicator } from './SentimentIndicator';
import type { VoiceCall } from '../types';

interface TranscriptMessage {
  id: string;
  speaker: 'agent' | 'prospect';
  text: string;
  timestamp: string;
  sentiment?: number;
  keywords?: {
    painPoints?: string[];
    buyingSignals?: string[];
    objections?: string[];
  };
}

interface CallTranscriptViewerProps {
  call: VoiceCall;
  realTime?: boolean;
  onExport?: () => void;
}

export function CallTranscriptViewer({
  call,
  realTime = false,
  onExport
}: CallTranscriptViewerProps) {
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [highlightType, setHighlightType] = useState<'all' | 'painPoints' | 'buyingSignals' | 'objections'>('all');
  const [autoScroll, setAutoScroll] = useState(true);
  const transcriptEndRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);

  // Parse transcript into messages
  useEffect(() => {
    if (call.transcript) {
      // Parse the transcript - this is a simplified version
      // In production, transcript would come structured from backend
      const parsedMessages: TranscriptMessage[] = call.transcript
        .split('\n')
        .filter(line => line.trim())
        .map((line, index) => {
          const isAgent = line.toLowerCase().includes('agent:');
          const text = line.replace(/^(agent:|prospect:|customer:)/i, '').trim();

          return {
            id: `msg-${index}`,
            speaker: isAgent ? 'agent' : 'prospect',
            text,
            timestamp: new Date(Date.now() - (10 - index) * 60000).toISOString(),
            sentiment: Math.random() * 2 - 1, // Mock sentiment
            keywords: detectKeywords(text)
          };
        });

      setMessages(parsedMessages);
    }
  }, [call.transcript]);

  // Auto-scroll to bottom when new messages arrive (real-time mode)
  useEffect(() => {
    if (autoScroll && transcriptEndRef.current) {
      transcriptEndRef.current.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages, autoScroll]);

  // Detect keywords in text
  function detectKeywords(text: string): TranscriptMessage['keywords'] {
    const lowerText = text.toLowerCase();

    const painPoints = [
      'problem', 'issue', 'challenge', 'difficult', 'struggle',
      'frustrat', 'pain', 'concern', 'worry', 'obstacle'
    ].filter(keyword => lowerText.includes(keyword));

    const buyingSignals = [
      'interested', 'budget', 'timeline', 'decision', 'purchase',
      'implement', 'solution', 'pricing', 'demo', 'trial'
    ].filter(keyword => lowerText.includes(keyword));

    const objections = [
      'expensive', 'cost', 'competitor', 'not sure', 'think about',
      'maybe', 'concern', 'worry', 'question'
    ].filter(keyword => lowerText.includes(keyword));

    return {
      painPoints: painPoints.length > 0 ? painPoints : undefined,
      buyingSignals: buyingSignals.length > 0 ? buyingSignals : undefined,
      objections: objections.length > 0 ? objections : undefined
    };
  }

  // Filter messages based on search
  const filteredMessages = useMemo(() => {
    if (!searchQuery) return messages;

    return messages.filter(msg =>
      msg.text.toLowerCase().includes(searchQuery.toLowerCase())
    );
  }, [messages, searchQuery]);

  // Highlight text based on keywords
  const highlightText = (text: string, keywords?: TranscriptMessage['keywords']) => {
    if (!keywords || highlightType === 'all') return text;

    let highlightedText = text;
    const highlightMap: Record<string, string> = {
      painPoints: 'bg-red-100 text-red-800',
      buyingSignals: 'bg-green-100 text-green-800',
      objections: 'bg-yellow-100 text-yellow-800'
    };

    // Apply highlights based on selected type
    if (highlightType === 'painPoints' && keywords.painPoints) {
      keywords.painPoints.forEach(keyword => {
        const regex = new RegExp(`(${keyword})`, 'gi');
        highlightedText = highlightedText.replace(regex, `<span class="${highlightMap.painPoints} px-1 rounded">$1</span>`);
      });
    } else if (highlightType === 'buyingSignals' && keywords.buyingSignals) {
      keywords.buyingSignals.forEach(keyword => {
        const regex = new RegExp(`(${keyword})`, 'gi');
        highlightedText = highlightedText.replace(regex, `<span class="${highlightMap.buyingSignals} px-1 rounded">$1</span>`);
      });
    } else if (highlightType === 'objections' && keywords.objections) {
      keywords.objections.forEach(keyword => {
        const regex = new RegExp(`(${keyword})`, 'gi');
        highlightedText = highlightedText.replace(regex, `<span class="${highlightMap.objections} px-1 rounded">$1</span>`);
      });
    }

    return highlightedText;
  };

  // Format timestamp
  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('en-US', {
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };

  // Export transcript
  const handleExport = () => {
    const transcriptText = messages
      .map(msg => `[${formatTime(msg.timestamp)}] ${msg.speaker.toUpperCase()}: ${msg.text}`)
      .join('\n\n');

    const blob = new Blob([transcriptText], { type: 'text/plain' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `transcript-${call.id}.txt`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);

    onExport?.();
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header with controls */}
      <div className="border-b border-gray-200 pb-4 mb-4">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h3 className="text-lg font-semibold text-gray-900">Call Transcript</h3>
            <p className="text-sm text-gray-500 mt-1">
              Lead #{call.lead_id} • {new Date(call.started_at).toLocaleDateString()}
            </p>
          </div>
          <div className="flex gap-2">
            {realTime && (
              <button
                onClick={() => setAutoScroll(!autoScroll)}
                className={`px-3 py-1 text-sm rounded-md ${
                  autoScroll
                    ? 'bg-indigo-100 text-indigo-700'
                    : 'bg-gray-100 text-gray-700'
                }`}
              >
                {autoScroll ? 'Auto-scroll ON' : 'Auto-scroll OFF'}
              </button>
            )}
            <button
              onClick={handleExport}
              className="px-3 py-1 text-sm bg-white border border-gray-300 rounded-md hover:bg-gray-50"
            >
              Export
            </button>
          </div>
        </div>

        {/* Search and filters */}
        <div className="flex gap-4">
          <div className="flex-1">
            <input
              type="text"
              placeholder="Search transcript..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
          <select
            value={highlightType}
            onChange={(e) => setHighlightType(e.target.value as any)}
            className="px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
          >
            <option value="all">Show All</option>
            <option value="painPoints">Pain Points</option>
            <option value="buyingSignals">Buying Signals</option>
            <option value="objections">Objections</option>
          </select>
        </div>

        {/* Overall sentiment */}
        {call.sentiment_score !== undefined && (
          <div className="mt-3 flex items-center gap-2">
            <span className="text-sm text-gray-600">Overall Sentiment:</span>
            <SentimentIndicator score={call.sentiment_score} showTrend={false} />
          </div>
        )}
      </div>

      {/* Transcript messages */}
      <div
        ref={containerRef}
        className="flex-1 overflow-y-auto space-y-4 pr-2"
        style={{ maxHeight: '500px' }}
      >
        {filteredMessages.length === 0 ? (
          <div className="text-center py-8">
            <p className="text-gray-500">
              {searchQuery ? 'No messages match your search' : 'No transcript available'}
            </p>
          </div>
        ) : (
          filteredMessages.map((message) => (
            <div
              key={message.id}
              className={`flex gap-3 ${
                message.speaker === 'agent' ? 'justify-start' : 'justify-end'
              }`}
            >
              <div
                className={`max-w-[70%] ${
                  message.speaker === 'agent'
                    ? 'order-2'
                    : 'order-1'
                }`}
              >
                <div className="flex items-center gap-2 mb-1">
                  <span className={`text-xs font-medium ${
                    message.speaker === 'agent' ? 'text-blue-600' : 'text-gray-600'
                  }`}>
                    {message.speaker === 'agent' ? 'Agent' : 'Prospect'}
                  </span>
                  <span className="text-xs text-gray-400">
                    {formatTime(message.timestamp)}
                  </span>
                  {message.sentiment !== undefined && (
                    <SentimentIndicator
                      score={message.sentiment}
                      compact
                      showTrend={false}
                    />
                  )}
                </div>
                <div
                  className={`rounded-lg px-4 py-2 ${
                    message.speaker === 'agent'
                      ? 'bg-blue-50 text-blue-900'
                      : 'bg-gray-100 text-gray-900'
                  }`}
                >
                  <p
                    className="text-sm whitespace-pre-wrap"
                    dangerouslySetInnerHTML={{
                      __html: highlightText(message.text, message.keywords)
                    }}
                  />

                  {/* Keyword indicators */}
                  {message.keywords && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {message.keywords.painPoints && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-800">
                          Pain Point
                        </span>
                      )}
                      {message.keywords.buyingSignals && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-800">
                          Buying Signal
                        </span>
                      )}
                      {message.keywords.objections && (
                        <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-yellow-100 text-yellow-800">
                          Objection
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Speaker avatar */}
              <div className={`flex-shrink-0 ${
                message.speaker === 'agent' ? 'order-1' : 'order-2'
              }`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center ${
                  message.speaker === 'agent'
                    ? 'bg-blue-500 text-white'
                    : 'bg-gray-400 text-white'
                }`}>
                  {message.speaker === 'agent' ? 'A' : 'P'}
                </div>
              </div>
            </div>
          ))
        )}

        {/* Auto-scroll anchor */}
        <div ref={transcriptEndRef} />
      </div>

      {/* Statistics footer */}
      <div className="border-t border-gray-200 pt-4 mt-4">
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div>
            <span className="text-gray-500">Duration:</span>
            <span className="ml-2 font-medium">
              {call.duration_seconds ? `${Math.floor(call.duration_seconds / 60)}:${(call.duration_seconds % 60).toString().padStart(2, '0')}` : '--:--'}
            </span>
          </div>
          <div>
            <span className="text-gray-500">Messages:</span>
            <span className="ml-2 font-medium">{messages.length}</span>
          </div>
          <div>
            <span className="text-gray-500">Status:</span>
            <span className="ml-2 font-medium capitalize">{call.status}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CallTranscriptViewer;