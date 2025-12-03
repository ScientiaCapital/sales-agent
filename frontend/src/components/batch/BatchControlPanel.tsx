/**
 * BatchControlPanel - Batch job management and configuration
 *
 * Features:
 * - Start new batch jobs with company selection
 * - Priority queue selection (high/medium/low)
 * - Pipeline options configuration
 * - Pause/Resume/Cancel controls for active batches
 * - Rate limit status display
 *
 * API Integration:
 * - POST /batch/start - Start new batch
 * - POST /batch/{id}/pause - Pause batch
 * - POST /batch/{id}/resume - Resume batch
 * - POST /batch/{id}/cancel - Cancel batch
 * - GET /batch/rate-limits/status - Get rate limit status
 */

import React, { useState, useEffect, useCallback } from 'react';
import { Card, CardHeader, CardTitle, CardContent, CardDescription } from '../ui/card';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';

// ============================================================================
// Types
// ============================================================================

interface Company {
  id: string;
  name: string;
  domain?: string;
  icp_tier?: 'platinum' | 'gold' | 'silver' | 'bronze';
}

interface BatchStartRequest {
  name: string;
  company_ids: string[];
  priority: 'high' | 'medium' | 'low';
  options?: {
    skip_enrichment?: boolean;
    skip_marketing?: boolean;
    skip_bdr?: boolean;
  };
}

interface RateLimitStatus {
  apollo: {
    requests_this_minute: number;
    requests_this_hour: number;
    requests_this_day: number;
    credits_used_today: number;
    limits: {
      per_minute: number;
      per_hour: number;
      per_day: number;
      daily_credits: number;
    };
  };
  hunter: {
    remaining_monthly: number;
    limit_monthly: number;
  };
  browserbase: {
    active_sessions: number;
    max_sessions: number;
  };
  redis_connected: boolean;
}

interface ActiveBatch {
  id: string;
  name: string;
  status: string;
  percent_complete: number;
}

interface BatchControlPanelProps {
  companies?: Company[];
  onBatchStarted?: (batchId: string) => void;
  onBatchAction?: (action: 'pause' | 'resume' | 'cancel', batchId: string) => void;
  apiBaseUrl?: string;
}

// ============================================================================
// Helpers
// ============================================================================

const getTierBadgeVariant = (tier?: string): 'gold' | 'silver' | 'bronze' | 'secondary' => {
  switch (tier) {
    case 'platinum':
    case 'gold':
      return 'gold';
    case 'silver':
      return 'silver';
    case 'bronze':
      return 'bronze';
    default:
      return 'secondary';
  }
};

const getRateLimitColor = (used: number, limit: number): string => {
  const percent = (used / limit) * 100;
  if (percent >= 95) return 'text-red-600 bg-red-50';
  if (percent >= 80) return 'text-yellow-600 bg-yellow-50';
  return 'text-green-600 bg-green-50';
};

// ============================================================================
// Component
// ============================================================================

export const BatchControlPanel: React.FC<BatchControlPanelProps> = ({
  companies = [],
  onBatchStarted,
  onBatchAction,
  apiBaseUrl = '/api',
}) => {
  // Form state
  const [batchName, setBatchName] = useState('');
  const [selectedCompanyIds, setSelectedCompanyIds] = useState<Set<string>>(new Set());
  const [priority, setPriority] = useState<'high' | 'medium' | 'low'>('medium');
  const [skipEnrichment, setSkipEnrichment] = useState(false);
  const [skipMarketing, setSkipMarketing] = useState(false);
  const [skipBdr, setSkipBdr] = useState(false);

  // UI state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [rateLimits, setRateLimits] = useState<RateLimitStatus | null>(null);
  const [activeBatches, setActiveBatches] = useState<ActiveBatch[]>([]);
  const [searchFilter, setSearchFilter] = useState('');
  const [tierFilter, setTierFilter] = useState<string>('all');

  // Fetch rate limits
  const fetchRateLimits = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/batch/rate-limits/status`);
      if (res.ok) {
        const data = await res.json();
        setRateLimits(data);
      }
    } catch (err) {
      console.error('Failed to fetch rate limits:', err);
    }
  }, [apiBaseUrl]);

  // Fetch active batches
  const fetchActiveBatches = useCallback(async () => {
    try {
      const res = await fetch(`${apiBaseUrl}/batch/?status=running`);
      if (res.ok) {
        const data = await res.json();
        setActiveBatches(data);
      }
    } catch (err) {
      console.error('Failed to fetch active batches:', err);
    }
  }, [apiBaseUrl]);

  // Initial fetch and polling
  useEffect(() => {
    fetchRateLimits();
    fetchActiveBatches();

    const interval = setInterval(() => {
      fetchRateLimits();
      fetchActiveBatches();
    }, 30000); // Refresh every 30s

    return () => clearInterval(interval);
  }, [fetchRateLimits, fetchActiveBatches]);

  // Company selection handlers
  const toggleCompany = (id: string) => {
    setSelectedCompanyIds(prev => {
      const updated = new Set(prev);
      if (updated.has(id)) {
        updated.delete(id);
      } else {
        updated.add(id);
      }
      return updated;
    });
  };

  const selectAll = () => {
    setSelectedCompanyIds(new Set(filteredCompanies.map(c => c.id)));
  };

  const clearSelection = () => {
    setSelectedCompanyIds(new Set());
  };

  // Filter companies
  const filteredCompanies = companies.filter(c => {
    const matchesSearch = !searchFilter ||
      c.name.toLowerCase().includes(searchFilter.toLowerCase()) ||
      c.domain?.toLowerCase().includes(searchFilter.toLowerCase());
    const matchesTier = tierFilter === 'all' || c.icp_tier === tierFilter;
    return matchesSearch && matchesTier;
  });

  // Start batch
  const handleStartBatch = async () => {
    if (selectedCompanyIds.size === 0) {
      setError('Please select at least one company');
      return;
    }

    if (!batchName.trim()) {
      setError('Please enter a batch name');
      return;
    }

    // Check rate limits before starting
    if (rateLimits) {
      const apolloRemaining = rateLimits.apollo.limits.per_day - rateLimits.apollo.requests_this_day;
      if (apolloRemaining < selectedCompanyIds.size) {
        setError(`Insufficient Apollo quota. Need ${selectedCompanyIds.size}, have ${apolloRemaining} daily remaining.`);
        return;
      }
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const request: BatchStartRequest = {
        name: batchName.trim(),
        company_ids: Array.from(selectedCompanyIds),
        priority,
        options: {
          skip_enrichment: skipEnrichment,
          skip_marketing: skipMarketing,
          skip_bdr: skipBdr,
        },
      };

      const res = await fetch(`${apiBaseUrl}/batch/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(request),
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || 'Failed to start batch');
      }

      const data = await res.json();

      // Reset form
      setBatchName('');
      setSelectedCompanyIds(new Set());

      // Notify parent
      if (onBatchStarted) {
        onBatchStarted(data.batch_id);
      }

      // Refresh active batches
      fetchActiveBatches();

    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to start batch');
    } finally {
      setIsSubmitting(false);
    }
  };

  // Batch actions
  const handleBatchAction = async (action: 'pause' | 'resume' | 'cancel', batchId: string) => {
    try {
      const res = await fetch(`${apiBaseUrl}/batch/${batchId}/${action}`, {
        method: 'POST',
      });

      if (!res.ok) {
        const errorData = await res.json();
        throw new Error(errorData.detail || `Failed to ${action} batch`);
      }

      // Notify parent
      if (onBatchAction) {
        onBatchAction(action, batchId);
      }

      // Refresh active batches
      fetchActiveBatches();

    } catch (err) {
      setError(err instanceof Error ? err.message : `Failed to ${action} batch`);
    }
  };

  return (
    <div className="space-y-6">
      {/* Rate Limit Status */}
      {rateLimits && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">API Rate Limits</CardTitle>
            <CardDescription>Current usage across external services</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-4">
              {/* Apollo */}
              <div className={`p-3 rounded-lg ${getRateLimitColor(rateLimits.apollo.requests_this_day, rateLimits.apollo.limits.per_day)}`}>
                <div className="text-xs font-medium uppercase tracking-wide opacity-75">Apollo Daily</div>
                <div className="text-lg font-bold">
                  {rateLimits.apollo.requests_this_day} / {rateLimits.apollo.limits.per_day}
                </div>
                <div className="text-xs opacity-75">
                  Credits: {rateLimits.apollo.credits_used_today} / {rateLimits.apollo.limits.daily_credits}
                </div>
              </div>

              {/* Hunter */}
              <div className={`p-3 rounded-lg ${getRateLimitColor(rateLimits.hunter.limit_monthly - rateLimits.hunter.remaining_monthly, rateLimits.hunter.limit_monthly)}`}>
                <div className="text-xs font-medium uppercase tracking-wide opacity-75">Hunter Monthly</div>
                <div className="text-lg font-bold">
                  {rateLimits.hunter.remaining_monthly} remaining
                </div>
                <div className="text-xs opacity-75">
                  of {rateLimits.hunter.limit_monthly} total
                </div>
              </div>

              {/* Browserbase */}
              <div className={`p-3 rounded-lg ${getRateLimitColor(rateLimits.browserbase.active_sessions, rateLimits.browserbase.max_sessions)}`}>
                <div className="text-xs font-medium uppercase tracking-wide opacity-75">Browserbase</div>
                <div className="text-lg font-bold">
                  {rateLimits.browserbase.active_sessions} / {rateLimits.browserbase.max_sessions}
                </div>
                <div className="text-xs opacity-75">
                  active sessions
                </div>
              </div>
            </div>

            {/* Redis status */}
            <div className="mt-3 flex items-center text-xs">
              <span className={`w-2 h-2 rounded-full mr-2 ${rateLimits.redis_connected ? 'bg-green-500' : 'bg-red-500'}`} />
              Redis: {rateLimits.redis_connected ? 'Connected' : 'Disconnected'}
            </div>
          </CardContent>
        </Card>
      )}

      {/* Active Batches */}
      {activeBatches.length > 0 && (
        <Card>
          <CardHeader className="pb-3">
            <CardTitle className="text-sm font-medium">Active Batches</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {activeBatches.map(batch => (
                <div key={batch.id} className="flex items-center justify-between p-3 bg-gray-50 rounded-lg">
                  <div>
                    <div className="font-medium">{batch.name}</div>
                    <div className="text-xs text-gray-500">
                      {batch.percent_complete.toFixed(1)}% complete
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant={batch.status === 'running' ? 'info' : 'warning'}>
                      {batch.status}
                    </Badge>
                    {batch.status === 'running' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBatchAction('pause', batch.id)}
                      >
                        Pause
                      </Button>
                    )}
                    {batch.status === 'paused' && (
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBatchAction('resume', batch.id)}
                      >
                        Resume
                      </Button>
                    )}
                    <Button
                      variant="destructive"
                      size="sm"
                      onClick={() => handleBatchAction('cancel', batch.id)}
                    >
                      Cancel
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* New Batch Form */}
      <Card>
        <CardHeader>
          <CardTitle>Start New Batch</CardTitle>
          <CardDescription>
            Select companies to process through the lead enrichment pipeline
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Error Message */}
          {error && (
            <div className="bg-red-50 border border-red-200 rounded-lg p-3 text-sm text-red-600">
              {error}
            </div>
          )}

          {/* Batch Name */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Batch Name
            </label>
            <input
              type="text"
              value={batchName}
              onChange={(e) => setBatchName(e.target.value)}
              placeholder="December Enrichment Run"
              className="w-full px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
            />
          </div>

          {/* Priority Selection */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Priority Queue
            </label>
            <div className="flex gap-2">
              {(['high', 'medium', 'low'] as const).map(p => (
                <button
                  key={p}
                  onClick={() => setPriority(p)}
                  className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
                    priority === p
                      ? p === 'high' ? 'bg-red-100 text-red-700 border-2 border-red-500'
                        : p === 'medium' ? 'bg-yellow-100 text-yellow-700 border-2 border-yellow-500'
                        : 'bg-gray-100 text-gray-700 border-2 border-gray-500'
                      : 'bg-gray-50 text-gray-600 border border-gray-200 hover:bg-gray-100'
                  }`}
                >
                  {p.charAt(0).toUpperCase() + p.slice(1)}
                </button>
              ))}
            </div>
            <p className="text-xs text-gray-500 mt-1">
              High priority batches are processed first
            </p>
          </div>

          {/* Pipeline Options */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              Pipeline Options
            </label>
            <div className="space-y-2">
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={skipEnrichment}
                  onChange={(e) => setSkipEnrichment(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Skip Enrichment Stage</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={skipMarketing}
                  onChange={(e) => setSkipMarketing(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Skip Marketing Content Generation</span>
              </label>
              <label className="flex items-center">
                <input
                  type="checkbox"
                  checked={skipBdr}
                  onChange={(e) => setSkipBdr(e.target.checked)}
                  className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                />
                <span className="ml-2 text-sm text-gray-700">Skip BDR Draft Generation</span>
              </label>
            </div>
          </div>

          {/* Company Selection */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="block text-sm font-medium text-gray-700">
                Select Companies ({selectedCompanyIds.size} selected)
              </label>
              <div className="flex gap-2">
                <Button variant="ghost" size="sm" onClick={selectAll}>
                  Select All
                </Button>
                <Button variant="ghost" size="sm" onClick={clearSelection}>
                  Clear
                </Button>
              </div>
            </div>

            {/* Filters */}
            <div className="flex gap-2 mb-2">
              <input
                type="text"
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                placeholder="Search companies..."
                className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <select
                value={tierFilter}
                onChange={(e) => setTierFilter(e.target.value)}
                className="px-3 py-2 text-sm border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
              >
                <option value="all">All Tiers</option>
                <option value="platinum">Platinum</option>
                <option value="gold">Gold</option>
                <option value="silver">Silver</option>
                <option value="bronze">Bronze</option>
              </select>
            </div>

            {/* Company List */}
            <div className="border border-gray-200 rounded-lg max-h-60 overflow-y-auto">
              {filteredCompanies.length === 0 ? (
                <div className="p-4 text-center text-gray-500 text-sm">
                  No companies available
                </div>
              ) : (
                filteredCompanies.map(company => (
                  <div
                    key={company.id}
                    onClick={() => toggleCompany(company.id)}
                    className={`flex items-center justify-between px-3 py-2 cursor-pointer hover:bg-gray-50 border-b border-gray-100 last:border-0 ${
                      selectedCompanyIds.has(company.id) ? 'bg-blue-50' : ''
                    }`}
                  >
                    <div className="flex items-center">
                      <input
                        type="checkbox"
                        checked={selectedCompanyIds.has(company.id)}
                        onChange={() => toggleCompany(company.id)}
                        className="h-4 w-4 text-blue-600 rounded border-gray-300 focus:ring-blue-500"
                      />
                      <div className="ml-3">
                        <div className="text-sm font-medium">{company.name}</div>
                        {company.domain && (
                          <div className="text-xs text-gray-500">{company.domain}</div>
                        )}
                      </div>
                    </div>
                    {company.icp_tier && (
                      <Badge variant={getTierBadgeVariant(company.icp_tier)}>
                        {company.icp_tier}
                      </Badge>
                    )}
                  </div>
                ))
              )}
            </div>
          </div>

          {/* Submit Button */}
          <Button
            variant="primary"
            className="w-full"
            onClick={handleStartBatch}
            disabled={isSubmitting || selectedCompanyIds.size === 0}
          >
            {isSubmitting ? (
              <>
                <svg className="animate-spin -ml-1 mr-2 h-4 w-4" fill="none" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                Starting Batch...
              </>
            ) : (
              `Start Batch (${selectedCompanyIds.size} companies)`
            )}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};

export default BatchControlPanel;
