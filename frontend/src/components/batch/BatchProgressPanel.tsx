/**
 * BatchProgressPanel - Real-time batch processing progress display
 *
 * Features:
 * - WebSocket connection for live updates
 * - Progress bar with percentage
 * - Lead-by-lead status breakdown
 * - Error display with retry capability
 * - Rate limit status display
 *
 * Connects to: /batch/ws/{batch_id}
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardFooter } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

// ============================================================================
// Types
// ============================================================================

interface BatchStatus {
  id: string;
  name: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'completed_with_errors' | 'failed' | 'cancelled';
  priority: 'high' | 'medium' | 'low';
  total_leads: number;
  processed_leads: number;
  successful_leads: number;
  failed_leads: number;
  skipped_leads: number;
  percent_complete: number;
  created_at?: string;
  started_at?: string;
  completed_at?: string;
  error_message?: string;
}

interface LeadProgress {
  id: string;
  company_id: string;
  company_name?: string;
  status: 'pending' | 'processing' | 'completed' | 'failed' | 'skipped';
  error_message?: string;
  latency_ms?: number;
}

interface WebSocketMessage {
  type: 'connected' | 'batch_started' | 'lead_started' | 'lead_completed' | 'lead_failed' |
        'batch_paused' | 'batch_resumed' | 'batch_completed' | 'batch_cancelled' | 'batch_failed' | 'progress';
  batch_id: string;
  lead_id?: string;
  company_id?: string;
  company_name?: string;
  status?: string;
  error?: string;
  latency_ms?: number;
  total?: number;
  processed?: number;
  successful?: number;
  failed?: number;
  skipped?: number;
  percent_complete?: number;
}

interface BatchProgressPanelProps {
  batchId: string;
  initialStatus?: BatchStatus;
  onRetryLead?: (leadId: string) => Promise<void>;
  onClose?: () => void;
  wsBaseUrl?: string;
}

// ============================================================================
// Status Helpers
// ============================================================================

const getStatusColor = (status: string): 'default' | 'success' | 'warning' | 'destructive' | 'info' | 'secondary' => {
  switch (status) {
    case 'completed':
      return 'success';
    case 'running':
    case 'processing':
      return 'info';
    case 'paused':
      return 'warning';
    case 'failed':
    case 'cancelled':
      return 'destructive';
    case 'completed_with_errors':
      return 'warning';
    default:
      return 'secondary';
  }
};

const getStatusLabel = (status: string): string => {
  switch (status) {
    case 'completed_with_errors':
      return 'Completed with Errors';
    default:
      return status.charAt(0).toUpperCase() + status.slice(1);
  }
};

const formatDuration = (ms: number): string => {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.round((ms % 60000) / 1000)}s`;
};

// ============================================================================
// Component
// ============================================================================

export const BatchProgressPanel: React.FC<BatchProgressPanelProps> = ({
  batchId,
  initialStatus,
  onRetryLead,
  onClose,
  wsBaseUrl = 'ws://localhost:8001',
}) => {
  const [status, setStatus] = useState<BatchStatus | null>(initialStatus || null);
  const [leads, setLeads] = useState<Map<string, LeadProgress>>(new Map());
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);
  const [recentActivity, setRecentActivity] = useState<string[]>([]);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  // Add activity log entry
  const addActivity = useCallback((message: string) => {
    setRecentActivity(prev => {
      const newActivity = [`${new Date().toLocaleTimeString()} - ${message}`, ...prev];
      return newActivity.slice(0, 10); // Keep last 10 entries
    });
  }, []);

  // Handle WebSocket messages
  const handleMessage = useCallback((event: MessageEvent) => {
    try {
      const data: WebSocketMessage = JSON.parse(event.data);

      switch (data.type) {
        case 'connected':
          addActivity('Connected to batch progress stream');
          break;

        case 'batch_started':
          setStatus(prev => prev ? { ...prev, status: 'running', started_at: new Date().toISOString() } : prev);
          addActivity('Batch processing started');
          break;

        case 'lead_started':
          if (data.lead_id) {
            setLeads(prev => {
              const updated = new Map(prev);
              updated.set(data.lead_id!, {
                id: data.lead_id!,
                company_id: data.company_id || '',
                company_name: data.company_name,
                status: 'processing',
              });
              return updated;
            });
            addActivity(`Processing: ${data.company_name || data.company_id}`);
          }
          break;

        case 'lead_completed':
          if (data.lead_id) {
            setLeads(prev => {
              const updated = new Map(prev);
              updated.set(data.lead_id!, {
                id: data.lead_id!,
                company_id: data.company_id || '',
                company_name: data.company_name,
                status: 'completed',
                latency_ms: data.latency_ms,
              });
              return updated;
            });
            addActivity(`Completed: ${data.company_name || data.company_id} (${formatDuration(data.latency_ms || 0)})`);
          }
          break;

        case 'lead_failed':
          if (data.lead_id) {
            setLeads(prev => {
              const updated = new Map(prev);
              updated.set(data.lead_id!, {
                id: data.lead_id!,
                company_id: data.company_id || '',
                company_name: data.company_name,
                status: 'failed',
                error_message: data.error,
              });
              return updated;
            });
            addActivity(`Failed: ${data.company_name || data.company_id} - ${data.error}`);
          }
          break;

        case 'progress':
          setStatus(prev => ({
            ...(prev || {} as BatchStatus),
            id: data.batch_id,
            total_leads: data.total || prev?.total_leads || 0,
            processed_leads: data.processed || prev?.processed_leads || 0,
            successful_leads: data.successful || prev?.successful_leads || 0,
            failed_leads: data.failed || prev?.failed_leads || 0,
            skipped_leads: data.skipped || prev?.skipped_leads || 0,
            percent_complete: data.percent_complete || prev?.percent_complete || 0,
            status: prev?.status || 'running',
            name: prev?.name || 'Batch Job',
            priority: prev?.priority || 'medium',
          }));
          break;

        case 'batch_paused':
          setStatus(prev => prev ? { ...prev, status: 'paused' } : prev);
          addActivity('Batch paused');
          break;

        case 'batch_resumed':
          setStatus(prev => prev ? { ...prev, status: 'running' } : prev);
          addActivity('Batch resumed');
          break;

        case 'batch_completed':
          setStatus(prev => prev ? { ...prev, status: 'completed', completed_at: new Date().toISOString() } : prev);
          addActivity('Batch completed successfully');
          break;

        case 'batch_cancelled':
          setStatus(prev => prev ? { ...prev, status: 'cancelled' } : prev);
          addActivity('Batch cancelled');
          break;

        case 'batch_failed':
          setStatus(prev => prev ? { ...prev, status: 'failed', error_message: data.error } : prev);
          addActivity(`Batch failed: ${data.error}`);
          break;
      }
    } catch (err) {
      console.error('Failed to parse WebSocket message:', err);
    }
  }, [addActivity]);

  // Connect to WebSocket
  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const wsUrl = `${wsBaseUrl}/batch/ws/${batchId}`;
    console.log('Connecting to WebSocket:', wsUrl);

    try {
      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setIsConnected(true);
        setConnectionError(null);
      };

      ws.onmessage = handleMessage;

      ws.onclose = (event) => {
        console.log('WebSocket closed:', event.code, event.reason);
        setIsConnected(false);
        wsRef.current = null;

        // Auto-reconnect unless closed intentionally or batch is done
        if (event.code !== 1000 && status?.status !== 'completed' && status?.status !== 'cancelled' && status?.status !== 'failed') {
          reconnectTimeoutRef.current = setTimeout(() => {
            console.log('Attempting to reconnect...');
            connect();
          }, 3000);
        }
      };

      ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        setConnectionError('Connection error. Retrying...');
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setConnectionError('Failed to connect');
    }
  }, [batchId, wsBaseUrl, handleMessage, status?.status]);

  // Effect: Connect on mount
  useEffect(() => {
    connect();

    return () => {
      if (reconnectTimeoutRef.current) {
        clearTimeout(reconnectTimeoutRef.current);
      }
      if (wsRef.current) {
        wsRef.current.close(1000, 'Component unmounted');
      }
    };
  }, [connect]);

  // Fetch initial status if not provided
  useEffect(() => {
    if (!initialStatus) {
      fetch(`/api/batch/${batchId}`)
        .then(res => res.json())
        .then(data => setStatus(data))
        .catch(err => console.error('Failed to fetch batch status:', err));
    }
  }, [batchId, initialStatus]);

  // Render
  if (!status) {
    return (
      <Card className="w-full">
        <CardContent className="py-8 text-center text-gray-500">
          Loading batch status...
        </CardContent>
      </Card>
    );
  }

  const failedLeads = Array.from(leads.values()).filter(l => l.status === 'failed');
  const processingLeads = Array.from(leads.values()).filter(l => l.status === 'processing');

  return (
    <Card className="w-full">
      <CardHeader className="pb-4">
        <div className="flex items-center justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              {status.name}
              <Badge variant={getStatusColor(status.status)}>
                {getStatusLabel(status.status)}
              </Badge>
            </CardTitle>
            <p className="text-sm text-gray-500 mt-1">
              Batch ID: {status.id.slice(0, 8)}... | Priority: {status.priority}
            </p>
          </div>
          <div className="flex items-center gap-2">
            {isConnected ? (
              <span className="flex items-center text-sm text-green-600">
                <span className="w-2 h-2 bg-green-500 rounded-full mr-2 animate-pulse" />
                Live
              </span>
            ) : (
              <span className="flex items-center text-sm text-gray-500">
                <span className="w-2 h-2 bg-gray-400 rounded-full mr-2" />
                {connectionError || 'Connecting...'}
              </span>
            )}
            {onClose && (
              <Button variant="ghost" size="sm" onClick={onClose}>
                Close
              </Button>
            )}
          </div>
        </div>
      </CardHeader>

      <CardContent className="space-y-6">
        {/* Progress Bar */}
        <div className="space-y-2">
          <div className="flex justify-between text-sm">
            <span className="text-gray-600">Progress</span>
            <span className="font-medium">{status.percent_complete.toFixed(1)}%</span>
          </div>
          <div className="w-full bg-gray-200 rounded-full h-4 overflow-hidden">
            <div
              className="h-4 rounded-full transition-all duration-500 ease-out bg-gradient-to-r from-blue-500 to-blue-600"
              style={{ width: `${Math.min(status.percent_complete, 100)}%` }}
            />
          </div>
          <div className="flex justify-between text-xs text-gray-500">
            <span>{status.processed_leads} / {status.total_leads} leads processed</span>
            {status.started_at && !status.completed_at && (
              <span>Started {new Date(status.started_at).toLocaleTimeString()}</span>
            )}
            {status.completed_at && (
              <span>Completed {new Date(status.completed_at).toLocaleTimeString()}</span>
            )}
          </div>
        </div>

        {/* Stats Grid */}
        <div className="grid grid-cols-4 gap-4">
          <div className="text-center p-3 bg-blue-50 rounded-lg">
            <div className="text-2xl font-bold text-blue-600">{status.total_leads}</div>
            <div className="text-xs text-blue-600">Total</div>
          </div>
          <div className="text-center p-3 bg-green-50 rounded-lg">
            <div className="text-2xl font-bold text-green-600">{status.successful_leads}</div>
            <div className="text-xs text-green-600">Successful</div>
          </div>
          <div className="text-center p-3 bg-red-50 rounded-lg">
            <div className="text-2xl font-bold text-red-600">{status.failed_leads}</div>
            <div className="text-xs text-red-600">Failed</div>
          </div>
          <div className="text-center p-3 bg-gray-50 rounded-lg">
            <div className="text-2xl font-bold text-gray-600">{status.skipped_leads}</div>
            <div className="text-xs text-gray-600">Skipped</div>
          </div>
        </div>

        {/* Currently Processing */}
        {processingLeads.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Currently Processing</h4>
            <div className="flex flex-wrap gap-2">
              {processingLeads.map(lead => (
                <Badge key={lead.id} variant="info" className="animate-pulse">
                  {lead.company_name || lead.company_id.slice(0, 8)}...
                </Badge>
              ))}
            </div>
          </div>
        )}

        {/* Failed Leads */}
        {failedLeads.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-red-700">Failed Leads</h4>
            <div className="bg-red-50 rounded-lg p-3 space-y-2 max-h-40 overflow-y-auto">
              {failedLeads.map(lead => (
                <div key={lead.id} className="flex items-center justify-between text-sm">
                  <div>
                    <span className="font-medium">{lead.company_name || lead.company_id.slice(0, 8)}...</span>
                    <span className="text-red-600 ml-2">{lead.error_message}</span>
                  </div>
                  {onRetryLead && (
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onRetryLead(lead.id)}
                      className="text-red-600 border-red-300 hover:bg-red-50"
                    >
                      Retry
                    </Button>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Activity Log */}
        {recentActivity.length > 0 && (
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-gray-700">Recent Activity</h4>
            <div className="bg-gray-50 rounded-lg p-3 max-h-32 overflow-y-auto">
              {recentActivity.map((activity, idx) => (
                <div key={idx} className="text-xs text-gray-600 py-0.5">
                  {activity}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Error Message */}
        {status.error_message && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-start">
              <svg className="w-5 h-5 text-red-600 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
              </svg>
              <div>
                <h4 className="text-sm font-medium text-red-800">Batch Error</h4>
                <p className="text-sm text-red-600 mt-1">{status.error_message}</p>
              </div>
            </div>
          </div>
        )}
      </CardContent>

      <CardFooter className="text-xs text-gray-500 border-t pt-4">
        <div className="flex justify-between w-full">
          <span>Created: {status.created_at ? new Date(status.created_at).toLocaleString() : 'N/A'}</span>
          <span>WebSocket: {isConnected ? 'Connected' : 'Disconnected'}</span>
        </div>
      </CardFooter>
    </Card>
  );
};

export default BatchProgressPanel;
