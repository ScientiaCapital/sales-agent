/**
 * Conversations Page Component
 *
 * Real-time conversation intelligence dashboard with call history,
 * live transcripts, sentiment analysis, and WebSocket streaming
 */

import { useState, useEffect, useCallback, useMemo } from 'react';
import { VoiceAgent } from '../components/VoiceAgent';
import { CallTranscriptViewer } from '../components/CallTranscriptViewer';
import { SentimentIndicator } from '../components/SentimentIndicator';
import type { VoiceCall } from '../types';

interface ConversationFilter {
  dateRange: {
    start: Date | null;
    end: Date | null;
  };
  sentiment: 'all' | 'positive' | 'neutral' | 'negative';
  status: 'all' | 'connected' | 'ended' | 'failed';
  duration: 'all' | 'short' | 'medium' | 'long'; // short < 5min, medium 5-15min, long > 15min
}

export function Conversations() {
  const [calls, setCalls] = useState<VoiceCall[]>([]);
  const [selectedCall, setSelectedCall] = useState<VoiceCall | null>(null);
  const [activeCall, setActiveCall] = useState<VoiceCall | null>(null);
  const [showNewCall, setShowNewCall] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const [filter, setFilter] = useState<ConversationFilter>({
    dateRange: { start: null, end: null },
    sentiment: 'all',
    status: 'all',
    duration: 'all'
  });

  // Fetch call history
  useEffect(() => {
    fetchCallHistory();
  }, []);

  const fetchCallHistory = async () => {
    try {
      setIsLoading(true);
      const response = await fetch('/api/voice/sessions');
      if (response.ok) {
        const data = await response.json();
        setCalls(data.sessions || []);
      }
    } catch (error) {
      console.error('Failed to fetch call history:', error);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter calls based on current filters
  const filteredCalls = useMemo(() => {
    return calls.filter(call => {
      // Date range filter
      if (filter.dateRange.start || filter.dateRange.end) {
        const callDate = new Date(call.started_at);
        if (filter.dateRange.start && callDate < filter.dateRange.start) return false;
        if (filter.dateRange.end && callDate > filter.dateRange.end) return false;
      }

      // Sentiment filter
      if (filter.sentiment !== 'all' && call.sentiment_score !== undefined) {
        const sentiment = call.sentiment_score > 0.3 ? 'positive' :
                         call.sentiment_score < -0.3 ? 'negative' : 'neutral';
        if (filter.sentiment !== sentiment) return false;
      }

      // Status filter
      if (filter.status !== 'all' && call.status !== filter.status) {
        return false;
      }

      // Duration filter
      if (filter.duration !== 'all' && call.duration_seconds) {
        const duration = call.duration_seconds;
        if (filter.duration === 'short' && duration >= 300) return false;
        if (filter.duration === 'medium' && (duration < 300 || duration > 900)) return false;
        if (filter.duration === 'long' && duration <= 900) return false;
      }

      return true;
    });
  }, [calls, filter]);

  // Handle call completion
  const handleCallComplete = useCallback((call: VoiceCall) => {
    setCalls(prev => [call, ...prev]);
    setActiveCall(null);
    setShowNewCall(false);
    setSelectedCall(call);
  }, []);

  // Format duration for display
  const formatDuration = (seconds?: number) => {
    if (!seconds) return '00:00';
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  // Format date for display
  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: 'numeric',
      minute: '2-digit',
      hour12: true
    });
  };


  // Get status badge color
  const getStatusBadgeClass = (status: VoiceCall['status']) => {
    switch (status) {
      case 'connected':
        return 'bg-green-100 text-green-800';
      case 'ended':
        return 'bg-gray-100 text-gray-800';
      case 'failed':
        return 'bg-red-100 text-red-800';
      default:
        return 'bg-blue-100 text-blue-800';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex justify-between items-start">
          <div>
            <h2 className="text-2xl font-bold text-gray-900 mb-2">Conversation Intelligence</h2>
            <p className="text-gray-600">
              Real-time conversation analysis with sentiment tracking and AI-powered insights
            </p>
          </div>
          <button
            onClick={() => setShowNewCall(true)}
            className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
          >
            <svg className="w-5 h-5 mr-2" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z" />
            </svg>
            New Call
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-6">
        <h3 className="text-lg font-medium text-gray-900 mb-4">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Date Range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Date Range</label>
            <input
              type="date"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              onChange={(e) => setFilter(prev => ({
                ...prev,
                dateRange: { ...prev.dateRange, start: e.target.value ? new Date(e.target.value) : null }
              }))}
            />
          </div>

          {/* Sentiment Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Sentiment</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              value={filter.sentiment}
              onChange={(e) => setFilter(prev => ({ ...prev, sentiment: e.target.value as any }))}
            >
              <option value="all">All Sentiments</option>
              <option value="positive">Positive</option>
              <option value="neutral">Neutral</option>
              <option value="negative">Negative</option>
            </select>
          </div>

          {/* Status Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              value={filter.status}
              onChange={(e) => setFilter(prev => ({ ...prev, status: e.target.value as any }))}
            >
              <option value="all">All Statuses</option>
              <option value="connected">Connected</option>
              <option value="ended">Ended</option>
              <option value="failed">Failed</option>
            </select>
          </div>

          {/* Duration Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">Duration</label>
            <select
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:ring-indigo-500 focus:border-indigo-500"
              value={filter.duration}
              onChange={(e) => setFilter(prev => ({ ...prev, duration: e.target.value as any }))}
            >
              <option value="all">All Durations</option>
              <option value="short">{'< 5 minutes'}</option>
              <option value="medium">5-15 minutes</option>
              <option value="long">{'>  15 minutes'}</option>
            </select>
          </div>
        </div>
      </div>

      {/* Active Call Indicator */}
      {activeCall && (
        <div className="bg-green-50 border-l-4 border-green-400 p-4 rounded-lg">
          <div className="flex items-center">
            <div className="flex-shrink-0">
              <span className="relative flex h-3 w-3">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
              </span>
            </div>
            <div className="ml-3">
              <p className="text-sm font-medium text-green-800">
                Call in Progress with Lead #{activeCall.lead_id}
              </p>
            </div>
            <button
              onClick={() => setShowNewCall(true)}
              className="ml-auto text-green-600 hover:text-green-500"
            >
              View Call
            </button>
          </div>
        </div>
      )}

      {/* Call History Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        <div className="px-6 py-4 border-b border-gray-200">
          <h3 className="text-lg font-medium text-gray-900">Call History</h3>
        </div>

        {isLoading ? (
          <div className="p-12 text-center">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="mt-4 text-gray-500">Loading conversations...</p>
          </div>
        ) : filteredCalls.length === 0 ? (
          <div className="text-center py-12">
            <svg
              className="mx-auto h-12 w-12 text-gray-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
              />
            </svg>
            <h3 className="mt-2 text-sm font-medium text-gray-900">No conversations found</h3>
            <p className="mt-1 text-sm text-gray-500">
              {calls.length > 0 ? 'Try adjusting your filters' : 'Start a new call to begin tracking conversations'}
            </p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Lead / Company
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Status
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Duration
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Sentiment
                  </th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                    Date
                  </th>
                  <th className="relative px-6 py-3">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {filteredCalls.map((call) => (
                  <tr
                    key={call.id}
                    className="hover:bg-gray-50 cursor-pointer"
                    onClick={() => setSelectedCall(call)}
                  >
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">
                        Lead #{call.lead_id}
                      </div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <span className={`inline-flex px-2 py-1 text-xs font-semibold rounded-full ${getStatusBadgeClass(call.status)}`}>
                        {call.status}
                      </span>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDuration(call.duration_seconds)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <SentimentIndicator
                        score={call.sentiment_score}
                        showTrend={false}
                        compact
                      />
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {formatDate(call.started_at)}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-right text-sm font-medium">
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedCall(call);
                        }}
                        className="text-indigo-600 hover:text-indigo-900"
                      >
                        View
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* New Call Modal */}
      {showNewCall && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-2xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-medium text-gray-900">Voice Call</h3>
                <button
                  onClick={() => setShowNewCall(false)}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="p-6">
              <VoiceAgent
                leadId={1} // TODO: Get actual lead ID
                onCallComplete={handleCallComplete}
                onCallStart={(call) => setActiveCall(call)}
              />
            </div>
          </div>
        </div>
      )}

      {/* Call Details Modal */}
      {selectedCall && (
        <div className="fixed inset-0 bg-gray-500 bg-opacity-75 flex items-center justify-center z-50">
          <div className="bg-white rounded-lg max-w-4xl w-full mx-4 max-h-[90vh] overflow-y-auto">
            <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4">
              <div className="flex justify-between items-center">
                <h3 className="text-lg font-medium text-gray-900">Call Details</h3>
                <button
                  onClick={() => setSelectedCall(null)}
                  className="text-gray-400 hover:text-gray-500"
                >
                  <svg className="h-6 w-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>
            <div className="p-6">
              <CallTranscriptViewer call={selectedCall} />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}