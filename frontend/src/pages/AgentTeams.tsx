/**
 * Agent Teams Page
 * 
 * Multi-tenant customer dashboard with agent deployment controls
 */

import { useState, memo } from 'react';
import type { AgentDeployment, AgentStatus } from '../types';

export const AgentTeams = memo(() => {
  const [deployments] = useState<AgentDeployment[]>([
    {
      id: '1',
      customer_id: 'cust_001',
      customer_name: 'Acme Corp',
      agent_count: 5,
      status: 'active',
      leads_processed: 1250,
      messages_sent: 890,
      success_rate: 67.2,
      created_at: new Date().toISOString(),
    },
    {
      id: '2',
      customer_id: 'cust_002',
      customer_name: 'TechStart Inc',
      agent_count: 3,
      status: 'active',
      leads_processed: 520,
      messages_sent: 310,
      success_rate: 59.6,
      created_at: new Date().toISOString(),
    },
  ]);

  const [selectedDeployment, setSelectedDeployment] = useState<AgentDeployment | null>(null);

  const mockAgentStatuses: AgentStatus[] = selectedDeployment
    ? Array.from({ length: selectedDeployment.agent_count }, (_, i) => ({
        agent_id: `agent_${i + 1}`,
        deployment_id: selectedDeployment.id,
        status: i % 3 === 0 ? 'working' : 'idle',
        current_task: i % 3 === 0 ? 'Qualifying lead #425' : undefined,
        tasks_completed: Math.floor(Math.random() * 100),
        last_active: new Date(Date.now() - Math.random() * 3600000).toISOString(),
      }))
    : [];

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Agent Teams</h1>
        <p className="text-gray-600 mt-2">
          Manage multi-tenant agent deployments and monitor performance
        </p>
      </div>

      {/* Deployments Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {deployments.map((deployment) => (
          <div
            key={deployment.id}
            onClick={() => setSelectedDeployment(deployment)}
            className={`
              bg-white shadow rounded-lg p-6 cursor-pointer transition-all
              ${selectedDeployment?.id === deployment.id
                ? 'ring-2 ring-blue-500'
                : 'hover:shadow-lg'
              }
            `}
          >
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-lg font-semibold text-gray-900">
                  {deployment.customer_name}
                </h3>
                <p className="text-sm text-gray-500">{deployment.customer_id}</p>
              </div>
              <span
                className={`
                  px-2 py-1 text-xs font-medium rounded-full
                  ${deployment.status === 'active'
                    ? 'bg-green-100 text-green-800'
                    : deployment.status === 'paused'
                    ? 'bg-yellow-100 text-yellow-800'
                    : 'bg-gray-100 text-gray-800'
                  }
                `}
              >
                {deployment.status}
              </span>
            </div>

            <div className="space-y-3">
              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Agents</span>
                <span className="font-medium text-gray-900">
                  {deployment.agent_count}
                </span>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Leads Processed</span>
                <span className="font-medium text-gray-900">
                  {deployment.leads_processed.toLocaleString()}
                </span>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Messages Sent</span>
                <span className="font-medium text-gray-900">
                  {deployment.messages_sent.toLocaleString()}
                </span>
              </div>

              <div className="flex justify-between text-sm">
                <span className="text-gray-600">Success Rate</span>
                <span className="font-medium text-green-600">
                  {deployment.success_rate.toFixed(1)}%
                </span>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Agent Status Dashboard */}
      {selectedDeployment && (
        <div className="bg-white shadow rounded-lg p-6">
          <div className="flex justify-between items-center mb-6">
            <div>
              <h2 className="text-xl font-semibold text-gray-900">
                {selectedDeployment.customer_name} - Agent Status
              </h2>
              <p className="text-sm text-gray-500">
                Real-time agent activity monitoring
              </p>
            </div>

            <div className="flex space-x-2">
              <button className="px-4 py-2 bg-yellow-100 text-yellow-800 rounded-lg hover:bg-yellow-200">
                Pause All
              </button>
              <button className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                Deploy New Agent
              </button>
            </div>
          </div>

          {/* Agent Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {mockAgentStatuses.map((agent) => (
              <div
                key={agent.agent_id}
                className="border border-gray-200 rounded-lg p-4"
              >
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h4 className="font-medium text-gray-900">{agent.agent_id}</h4>
                    <p className="text-xs text-gray-500">
                      {new Date(agent.last_active).toLocaleTimeString()}
                    </p>
                  </div>

                  <span
                    className={`
                      flex items-center space-x-1 text-xs font-medium
                      ${agent.status === 'working'
                        ? 'text-blue-600'
                        : agent.status === 'idle'
                        ? 'text-gray-600'
                        : 'text-red-600'
                      }
                    `}
                  >
                    <span
                      className={`
                        w-2 h-2 rounded-full
                        ${agent.status === 'working'
                          ? 'bg-blue-600 animate-pulse'
                          : agent.status === 'idle'
                          ? 'bg-gray-400'
                          : 'bg-red-600'
                        }
                      `}
                    />
                    <span className="capitalize">{agent.status}</span>
                  </span>
                </div>

                {agent.current_task && (
                  <div className="mb-3">
                    <p className="text-sm text-gray-600">{agent.current_task}</p>
                  </div>
                )}

                <div className="flex justify-between text-sm">
                  <span className="text-gray-600">Completed</span>
                  <span className="font-medium text-gray-900">
                    {agent.tasks_completed}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Performance Chart Placeholder */}
          <div className="mt-6 p-6 bg-gray-50 rounded-lg">
            <h3 className="text-lg font-semibold mb-4">Performance Metrics</h3>
            <div className="h-48 bg-white rounded flex items-center justify-center">
              <p className="text-gray-500">Performance charts coming soon</p>
            </div>
          </div>
        </div>
      )}

      {!selectedDeployment && deployments.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-8 text-center">
          <p className="text-blue-800">
            Select a deployment to view agent details and real-time status
          </p>
        </div>
      )}
    </div>
  );
});

AgentTeams.displayName = 'AgentTeams';

export default AgentTeams;
