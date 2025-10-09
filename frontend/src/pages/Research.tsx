/**
 * Research Viewer Page
 *
 * Complete research interface with:
 * - Research initiation form
 * - Real-time SSE streaming progress visualization
 * - Research history with localStorage persistence
 * - Results viewer with markdown rendering
 */

import { useState, useEffect } from 'react';
import { ResearchPipeline } from '../components/ResearchPipeline';
import { ResearchResultViewer } from '../components/ResearchResultViewer';
import type { ResearchResponse, ResearchHistoryItem } from '../types';

const STORAGE_KEY = 'research_history';
const MAX_HISTORY_ITEMS = 50;

export function Research() {
  // Form state
  const [topic, setTopic] = useState('');
  const [depth, setDepth] = useState<'shallow' | 'medium' | 'deep'>('medium');
  const [formatStyle, setFormatStyle] = useState<'markdown' | 'json' | 'plain'>('markdown');
  const [temperature, setTemperature] = useState(0.7);
  const [maxQueries, setMaxQueries] = useState(5);
  const [timeoutSeconds, setTimeoutSeconds] = useState(30);

  // Research state
  const [isResearching, setIsResearching] = useState(false);
  const [currentResearchTopic, setCurrentResearchTopic] = useState('');

  // History state
  const [history, setHistory] = useState<ResearchHistoryItem[]>([]);
  const [selectedResult, setSelectedResult] = useState<ResearchHistoryItem | null>(null);
  const [historyFilter, setHistoryFilter] = useState('all'); // all | completed | error

  // Load history from localStorage on mount
  useEffect(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        const parsed = JSON.parse(stored);
        setHistory(parsed);
      } catch (err) {
        console.error('Failed to load research history:', err);
      }
    }
  }, []);

  // Save history to localStorage whenever it changes
  useEffect(() => {
    if (history.length > 0) {
      try {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(history.slice(0, MAX_HISTORY_ITEMS)));
      } catch (err) {
        console.error('Failed to save research history:', err);
      }
    }
  }, [history]);

  const handleStartResearch = () => {
    if (!topic.trim() || topic.length < 10) {
      alert('Please enter a research topic (minimum 10 characters)');
      return;
    }

    setIsResearching(true);
    setCurrentResearchTopic(topic);
    setSelectedResult(null);

    // Add pending item to history
    const newItem: ResearchHistoryItem = {
      id: `research-${Date.now()}`,
      topic,
      depth,
      format_style: formatStyle,
      status: 'pending',
      created_at: new Date().toISOString(),
    };

    setHistory((prev) => [newItem, ...prev].slice(0, MAX_HISTORY_ITEMS));
  };

  const handleResearchComplete = (result: ResearchResponse) => {
    setIsResearching(false);

    // Update history with complete result
    const completedItem: ResearchHistoryItem = {
      id: `research-${Date.now()}`,
      topic: result.research_topic,
      depth,
      format_style: formatStyle,
      status: 'completed',
      final_output: result.final_output,
      total_latency_ms: result.total_latency_ms,
      total_cost_usd: result.total_cost_usd,
      queries_generated: result.queries_generated,
      search_results_count: result.search_results_count,
      agents_executed: result.agents_executed,
      created_at: new Date().toISOString(),
    };

    setHistory((prev) => {
      const withoutPending = prev.filter((item) => item.status !== 'pending');
      return [completedItem, ...withoutPending].slice(0, MAX_HISTORY_ITEMS);
    });

    setSelectedResult(completedItem);
  };

  const handleResearchError = (error: string) => {
    setIsResearching(false);

    // Update history with error
    const errorItem: ResearchHistoryItem = {
      id: `research-${Date.now()}`,
      topic: currentResearchTopic,
      depth,
      format_style: formatStyle,
      status: 'error',
      error,
      created_at: new Date().toISOString(),
    };

    setHistory((prev) => {
      const withoutPending = prev.filter((item) => item.status !== 'pending');
      return [errorItem, ...withoutPending].slice(0, MAX_HISTORY_ITEMS);
    });
  };

  const filteredHistory = history.filter((item) => {
    if (historyFilter === 'all') return true;
    return item.status === historyFilter;
  });

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-2xl font-bold text-gray-900 mb-2">Research Pipeline</h2>
        <p className="text-gray-600">
          AI-powered research reports combining web search, analysis, and synthesis via 5-agent pipeline.
        </p>
      </div>

      {/* Research Initiation Form */}
      {!isResearching && !selectedResult && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Start New Research</h3>

          <div className="space-y-4">
            {/* Topic Input */}
            <div>
              <label htmlFor="topic" className="block text-sm font-medium text-gray-700 mb-1">
                Research Topic *
              </label>
              <textarea
                id="topic"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                rows={3}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                placeholder="What would you like to research? (minimum 10 characters)"
              />
              <p className="mt-1 text-xs text-gray-500">{topic.length} / 200 characters</p>
            </div>

            {/* Depth Selector */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Research Depth</label>
              <div className="flex space-x-4">
                {(['shallow', 'medium', 'deep'] as const).map((level) => (
                  <label key={level} className="flex items-center">
                    <input
                      type="radio"
                      name="depth"
                      value={level}
                      checked={depth === level}
                      onChange={(e) => setDepth(e.target.value as typeof depth)}
                      className="mr-2"
                    />
                    <span className="capitalize">{level}</span>
                  </label>
                ))}
              </div>
            </div>

            {/* Format Style */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">Output Format</label>
              <select
                value={formatStyle}
                onChange={(e) => setFormatStyle(e.target.value as typeof formatStyle)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              >
                <option value="markdown">Markdown</option>
                <option value="json">JSON</option>
                <option value="plain">Plain Text</option>
              </select>
            </div>

            {/* Temperature Slider */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Temperature: {temperature.toFixed(1)}
              </label>
              <input
                type="range"
                min="0"
                max="1"
                step="0.1"
                value={temperature}
                onChange={(e) => setTemperature(parseFloat(e.target.value))}
                className="w-full"
              />
              <p className="text-xs text-gray-500">Controls creativity (0 = factual, 1 = creative)</p>
            </div>

            {/* Max Queries */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Max Queries: {maxQueries}
              </label>
              <input
                type="number"
                min="1"
                max="10"
                value={maxQueries}
                onChange={(e) => setMaxQueries(parseInt(e.target.value) || 1)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
              />
            </div>

            {/* Timeout */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">
                Timeout: {timeoutSeconds}s
              </label>
              <input
                type="range"
                min="1"
                max="60"
                value={timeoutSeconds}
                onChange={(e) => setTimeoutSeconds(parseInt(e.target.value))}
                className="w-full"
              />
            </div>

            {/* Submit Button */}
            <button
              onClick={handleStartResearch}
              disabled={topic.length < 10}
              className="w-full px-6 py-3 bg-indigo-600 text-white font-medium rounded-lg hover:bg-indigo-700 disabled:bg-gray-300 disabled:cursor-not-allowed transition-colors"
            >
              Start Research
            </button>
          </div>
        </div>
      )}

      {/* Active Research Display */}
      {isResearching && (
        <ResearchPipeline
          topic={currentResearchTopic}
          requestParams={{
            depth,
            format_style: formatStyle,
            temperature,
            max_queries: maxQueries,
            timeout_seconds: timeoutSeconds,
          }}
          onComplete={handleResearchComplete}
          onError={handleResearchError}
        />
      )}

      {/* Results Display */}
      {selectedResult && !isResearching && (
        <div>
          <ResearchResultViewer result={selectedResult} onClose={() => setSelectedResult(null)} />
          <div className="mt-4 text-center">
            <button
              onClick={() => {
                setSelectedResult(null);
                setTopic('');
              }}
              className="px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700"
            >
              Start New Research
            </button>
          </div>
        </div>
      )}

      {/* Research History */}
      {!isResearching && (
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-gray-900">Research History</h3>

            {/* Filter Buttons */}
            <div className="flex space-x-2">
              {['all', 'completed', 'error'].map((filter) => (
                <button
                  key={filter}
                  onClick={() => setHistoryFilter(filter)}
                  className={`px-3 py-1 rounded-lg text-sm font-medium transition-colors ${
                    historyFilter === filter
                      ? 'bg-indigo-600 text-white'
                      : 'bg-gray-200 text-gray-700 hover:bg-gray-300'
                  }`}
                >
                  {filter.charAt(0).toUpperCase() + filter.slice(1)}
                </button>
              ))}
            </div>
          </div>

          {/* History Grid */}
          {filteredHistory.length === 0 ? (
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
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <h4 className="mt-2 text-sm font-medium text-gray-900">No research history yet</h4>
              <p className="mt-1 text-sm text-gray-500">Start a research query to see results here.</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {filteredHistory.map((item) => (
                <button
                  key={item.id}
                  onClick={() => setSelectedResult(item)}
                  className="text-left bg-gray-50 rounded-lg p-4 border border-gray-200 hover:border-indigo-500 hover:shadow-md transition-all"
                >
                  <div className="flex items-start justify-between mb-2">
                    <span
                      className={`px-2 py-1 text-xs font-medium rounded-full ${
                        item.status === 'completed'
                          ? 'bg-green-100 text-green-700'
                          : item.status === 'error'
                          ? 'bg-red-100 text-red-700'
                          : 'bg-gray-200 text-gray-700'
                      }`}
                    >
                      {item.status}
                    </span>
                  </div>

                  <p className="text-sm font-medium text-gray-900 line-clamp-2 mb-2">{item.topic}</p>

                  <div className="flex items-center space-x-4 text-xs text-gray-500">
                    {item.total_latency_ms && (
                      <span>{(item.total_latency_ms / 1000).toFixed(1)}s</span>
                    )}
                    {item.total_cost_usd && <span>${item.total_cost_usd.toFixed(6)}</span>}
                  </div>

                  <div className="mt-2 text-xs text-gray-400">
                    {new Date(item.created_at).toLocaleDateString()}
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
