/**
 * Research Pipeline Component
 *
 * 5-agent pipeline visualization with SSE streaming progress updates
 * Displays real-time progress through Query → Search → Summarize → Synthesize → Format stages
 */

import { memo, useEffect, useState, useRef } from 'react';
import type { ResearchSSEEvent, ResearchResponse } from '../types';

interface AgentState {
  name: string;
  role: 'query' | 'search' | 'summarize' | 'synthesize' | 'format';
  status: 'idle' | 'working' | 'completed' | 'error';
  progress: number;
  output?: string;
  latency_ms?: number;
  cost_usd?: number;
}

interface ResearchPipelineProps {
  topic: string;
  onComplete?: (result: ResearchResponse) => void;
  onError?: (error: string) => void;
  requestParams: {
    depth: string;
    format_style: string;
    temperature: number;
    max_queries: number;
    timeout_seconds: number;
  };
}

const AGENT_CONFIGS: Array<{ name: string; role: AgentState['role']; icon: string }> = [
  { name: 'Query Generator', role: 'query', icon: '🔍' },
  { name: 'Web Searcher', role: 'search', icon: '📡' },
  { name: 'Summarizer', role: 'summarize', icon: '📝' },
  { name: 'Synthesizer', role: 'synthesize', icon: '🧩' },
  { name: 'Formatter', role: 'format', icon: '✨' },
];

const AgentCard = memo(({ agent }: { agent: AgentState }) => {
  const statusColors = {
    idle: 'bg-gray-200 text-gray-700',
    working: 'bg-blue-100 text-blue-700 animate-pulse',
    completed: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  };

  const roleIcons: Record<string, string> = {
    query: '🔍',
    search: '📡',
    summarize: '📝',
    synthesize: '🧩',
    format: '✨',
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 border-l-4 border-indigo-500">
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center space-x-2">
          <span className="text-3xl">{roleIcons[agent.role]}</span>
          <div>
            <h4 className="font-semibold text-gray-900">{agent.name}</h4>
            <p className="text-xs text-gray-500 capitalize">{agent.role}</p>
          </div>
        </div>

        <span
          className={`
            px-2 py-1 text-xs font-medium rounded-full
            ${statusColors[agent.status]}
          `}
        >
          {agent.status}
        </span>
      </div>

      {/* Progress Bar */}
      <div className="mb-3">
        <div className="flex justify-between text-xs text-gray-600 mb-1">
          <span>Progress</span>
          <span>{agent.progress}%</span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className={`
              h-2 rounded-full transition-all duration-300
              ${
                agent.status === 'completed'
                  ? 'bg-green-600'
                  : agent.status === 'working'
                  ? 'bg-blue-600'
                  : 'bg-gray-400'
              }
            `}
            style={{ width: `${agent.progress}%` }}
          />
        </div>
      </div>

      {/* Metadata */}
      {(agent.latency_ms || agent.cost_usd) && (
        <div className="flex space-x-4 text-xs text-gray-600 mb-2">
          {agent.latency_ms && (
            <div>
              <span className="font-medium">Latency:</span> {agent.latency_ms}ms
            </div>
          )}
          {agent.cost_usd && (
            <div>
              <span className="font-medium">Cost:</span> ${agent.cost_usd.toFixed(6)}
            </div>
          )}
        </div>
      )}

      {/* Output Preview */}
      {agent.output && (
        <div className="mt-3 p-2 bg-gray-50 rounded text-xs text-gray-600 line-clamp-2">
          {typeof agent.output === 'string' ? agent.output : JSON.stringify(agent.output).slice(0, 100)}
        </div>
      )}

      {agent.status === 'working' && (
        <div className="mt-2 flex items-center space-x-1 text-xs text-blue-600">
          <div className="animate-pulse">⚡</div>
          <span>Processing...</span>
        </div>
      )}
    </div>
  );
});

AgentCard.displayName = 'AgentCard';

export const ResearchPipeline = memo(({ topic, onComplete, onError, requestParams }: ResearchPipelineProps) => {
  const [agents, setAgents] = useState<AgentState[]>(
    AGENT_CONFIGS.map((config) => ({
      ...config,
      status: 'idle' as const,
      progress: 0,
    }))
  );
  const [overallProgress, setOverallProgress] = useState(0);
  const [pipelineStatus, setPipelineStatus] = useState<'pending' | 'running' | 'completed' | 'error'>('pending');
  const eventSourceRef = useRef<AbortController | null>(null);

  useEffect(() => {
    // Start SSE connection
    const controller = new AbortController();
    eventSourceRef.current = controller;

    const startResearch = async () => {
      setPipelineStatus('running');

      const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8001';
      const url = `${API_BASE_URL}/api/v1/research/stream`;

      try {
        const response = await fetch(url, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            topic,
            depth: requestParams.depth,
            format_style: requestParams.format_style,
            temperature: requestParams.temperature,
            stream: true,
            max_queries: requestParams.max_queries,
            timeout_seconds: requestParams.timeout_seconds,
          }),
          signal: controller.signal,
        });

        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`);
        }

        const reader = response.body?.getReader();
        const decoder = new TextDecoder();

        if (!reader) {
          throw new Error('Response body is null');
        }

        let buffer = '';

        while (true) {
          const { done, value } = await reader.read();

          if (done) break;

          buffer += decoder.decode(value, { stream: true });
          const lines = buffer.split('\n\n');
          buffer = lines.pop() || '';

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              const data = line.slice(6);
              try {
                const event: ResearchSSEEvent = JSON.parse(data);
                handleSSEEvent(event);
              } catch (err) {
                console.error('Failed to parse SSE event:', err);
              }
            }
          }
        }
      } catch (err) {
        if (err instanceof Error && err.name !== 'AbortError') {
          console.error('Research streaming error:', err);
          setPipelineStatus('error');
          onError?.(err.message);
        }
      }
    };

    startResearch();

    return () => {
      controller.abort();
    };
  }, [topic, requestParams, onError]);

  const handleSSEEvent = (event: ResearchSSEEvent) => {
    switch (event.type) {
      case 'pipeline_start':
        setAgents((prev) =>
          prev.map((agent, idx) => ({
            ...agent,
            status: idx === 0 ? 'working' : 'idle',
            progress: idx === 0 ? 10 : 0,
          }))
        );
        break;

      case 'agent_start':
        if (event.agent) {
          setAgents((prev) =>
            prev.map((agent) =>
              agent.name.toLowerCase().includes(event.agent!.toLowerCase())
                ? { ...agent, status: 'working', progress: 25 }
                : agent
            )
          );
        }
        break;

      case 'agent_complete':
        if (event.agent) {
          setAgents((prev) =>
            prev.map((agent) =>
              agent.name.toLowerCase().includes(event.agent!.toLowerCase())
                ? {
                    ...agent,
                    status: 'completed',
                    progress: 100,
                    output: event.output ? JSON.stringify(event.output).slice(0, 100) : undefined,
                    latency_ms: event.latency_ms,
                    cost_usd: event.cost_usd,
                  }
                : agent
            )
          );

          // Calculate overall progress
          setAgents((current) => {
            const completedCount = current.filter((a) => a.status === 'completed').length;
            const progress = (completedCount / current.length) * 100;
            setOverallProgress(progress);
            return current;
          });
        }
        break;

      case 'final':
        setPipelineStatus('completed');
        setOverallProgress(100);
        if (event.result) {
          onComplete?.(event.result);
        }
        break;

      case 'error':
        setPipelineStatus('error');
        onError?.(event.message || 'Research pipeline failed');
        setAgents((prev) =>
          prev.map((agent) =>
            agent.status === 'working' ? { ...agent, status: 'error', progress: 0 } : agent
          )
        );
        break;
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white rounded-lg p-6">
        <h2 className="text-2xl font-bold mb-2">Research Pipeline</h2>
        <p className="text-indigo-100">5-Agent Collaborative Research System</p>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-3 gap-4">
          <div>
            <div className="text-sm opacity-80">Status</div>
            <div className="text-xl font-bold capitalize">{pipelineStatus}</div>
          </div>
          <div>
            <div className="text-sm opacity-80">Overall Progress</div>
            <div className="text-xl font-bold">{Math.round(overallProgress)}%</div>
          </div>
          <div className="col-span-2 md:col-span-1">
            <div className="text-sm opacity-80">Topic</div>
            <div className="text-lg font-semibold truncate">{topic}</div>
          </div>
        </div>

        {/* Overall Progress Bar */}
        <div className="mt-4">
          <div className="w-full bg-white/20 rounded-full h-3">
            <div
              className="bg-white h-3 rounded-full transition-all duration-300"
              style={{ width: `${overallProgress}%` }}
            />
          </div>
        </div>
      </div>

      {/* Pipeline Flow */}
      <div className="relative">
        {/* Connecting Lines */}
        <div className="absolute left-1/2 top-0 bottom-0 w-1 bg-gradient-to-b from-indigo-200 via-purple-200 to-indigo-200 -z-10 hidden md:block" />

        {/* Agent Cards */}
        <div className="space-y-6">
          {agents.map((agent, index) => (
            <div key={agent.name} className="relative">
              {/* Step Number */}
              <div className="absolute -left-12 top-1/2 -translate-y-1/2 hidden md:block">
                <div className="w-10 h-10 rounded-full bg-white border-4 border-indigo-500 flex items-center justify-center font-bold text-indigo-600">
                  {index + 1}
                </div>
              </div>

              {/* Agent Card */}
              <div className="ml-0 md:ml-4">
                <AgentCard agent={agent} />
              </div>

              {/* Arrow Connector */}
              {index < agents.length - 1 && (
                <div className="flex justify-center my-2">
                  <div className="text-2xl text-gray-400">↓</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error State */}
      {pipelineStatus === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-red-600 text-2xl">⚠️</span>
            <h3 className="text-lg font-semibold text-red-900">Pipeline Error</h3>
          </div>
          <p className="text-red-700">An error occurred during the research pipeline. Please try again.</p>
        </div>
      )}
    </div>
  );
});

ResearchPipeline.displayName = 'ResearchPipeline';

export default ResearchPipeline;
