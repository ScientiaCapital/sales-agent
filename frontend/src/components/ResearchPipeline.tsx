/**
 * Research Pipeline Component
 * 
 * 5-agent pipeline visualization showing progress through
 * Query → Search → Summarize → Synthesize → Format stages
 */

import { memo } from 'react';
import type { ResearchAgent, ResearchPipeline as PipelineType } from '../types';

interface ResearchPipelineProps {
  pipeline: PipelineType;
}

const AgentCard = memo(({ agent }: { agent: ResearchAgent }) => {
  const statusColors = {
    idle: 'bg-gray-200 text-gray-700',
    working: 'bg-blue-100 text-blue-700',
    completed: 'bg-green-100 text-green-700',
    error: 'bg-red-100 text-red-700',
  };

  const roleIcons = {
    query: '🔍',
    search: '📡',
    summarize: '📝',
    synthesize: '🧩',
    format: '✨',
  };

  return (
    <div className="bg-white rounded-lg shadow p-4 border-l-4 border-blue-500">
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
              ${agent.status === 'completed'
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

      {/* Output Preview */}
      {agent.output && (
        <div className="mt-3 p-2 bg-gray-50 rounded text-xs text-gray-600 line-clamp-2">
          {agent.output}
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

export const ResearchPipeline = memo(({ pipeline }: ResearchPipelineProps) => {
  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-gradient-to-r from-blue-600 to-purple-600 text-white rounded-lg p-6">
        <h2 className="text-2xl font-bold mb-2">Research Pipeline</h2>
        <p className="text-blue-100">5-Agent Collaborative Research System</p>

        <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
          <div>
            <div className="text-sm opacity-80">Status</div>
            <div className="text-xl font-bold capitalize">{pipeline.status}</div>
          </div>
          <div>
            <div className="text-sm opacity-80">Progress</div>
            <div className="text-xl font-bold">{pipeline.total_progress}%</div>
          </div>
          <div>
            <div className="text-sm opacity-80">Lead ID</div>
            <div className="text-xl font-bold">#{pipeline.lead_id}</div>
          </div>
          <div>
            <div className="text-sm opacity-80">Agents</div>
            <div className="text-xl font-bold">{pipeline.agents.length}/5</div>
          </div>
        </div>
      </div>

      {/* Pipeline Flow */}
      <div className="relative">
        {/* Connecting Lines */}
        <div className="absolute left-1/2 top-0 bottom-0 w-1 bg-gradient-to-b from-blue-200 via-purple-200 to-blue-200 -z-10" />

        {/* Agent Cards */}
        <div className="space-y-6">
          {pipeline.agents.map((agent, index) => (
            <div key={agent.id} className="relative">
              {/* Step Number */}
              <div className="absolute -left-12 top-1/2 -translate-y-1/2">
                <div className="w-10 h-10 rounded-full bg-white border-4 border-blue-500 flex items-center justify-center font-bold text-blue-600">
                  {index + 1}
                </div>
              </div>

              {/* Agent Card */}
              <div className="ml-4">
                <AgentCard agent={agent} />
              </div>

              {/* Arrow Connector */}
              {index < pipeline.agents.length - 1 && (
                <div className="flex justify-center my-2">
                  <div className="text-2xl text-gray-400">↓</div>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Final Result */}
      {pipeline.status === 'completed' && pipeline.result && (
        <div className="bg-white rounded-lg shadow-lg p-6 border-2 border-green-500">
          <div className="flex items-center space-x-2 mb-4">
            <span className="text-3xl">📄</span>
            <h3 className="text-xl font-bold text-gray-900">Research Report</h3>
          </div>

          <div className="prose max-w-none">
            <p className="text-gray-700 whitespace-pre-wrap">{pipeline.result}</p>
          </div>

          <div className="mt-4 flex justify-end space-x-2">
            <button className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50">
              Export PDF
            </button>
            <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
              Share Report
            </button>
          </div>
        </div>
      )}

      {/* Error State */}
      {pipeline.status === 'error' && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-6">
          <div className="flex items-center space-x-2 mb-2">
            <span className="text-red-600 text-2xl">⚠️</span>
            <h3 className="text-lg font-semibold text-red-900">Pipeline Error</h3>
          </div>
          <p className="text-red-700">
            An error occurred during the research pipeline. Please try again.
          </p>
        </div>
      )}
    </div>
  );
});

ResearchPipeline.displayName = 'ResearchPipeline';

export default ResearchPipeline;
