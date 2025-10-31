/**
 * Enrichment Dashboard Page
 *
 * Displays enrichment progress for imported leads:
 * - Total imported leads
 * - Enrichment status breakdown (completed/pending/failed)
 * - Average qualification score
 * - ATL contacts discovered
 * - Filterable lead list with ICP tier, score range, enrichment status
 * - Action buttons: trigger enrichment, export enriched list, view ATL contacts
 */

import { useState, useEffect, useMemo } from 'react';
import { apiClient } from '../services/api';
import type { Lead } from '../types';

interface EnrichmentMetrics {
  totalLeads: number;
  enrichmentCompleted: number;
  enrichmentPending: number;
  enrichmentFailed: number;
  avgQualificationScore: number;
  atlContactsDiscovered: number;
}

interface EnrichmentStatus {
  completed: number;
  pending: number;
  failed: number;
}

export function EnrichmentDashboard() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [metrics, setMetrics] = useState<EnrichmentMetrics | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Filter state
  const [icpFilter, setIcpFilter] = useState<string>(''); // Gold, Silver, Bronze, or empty
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);
  const [enrichmentStatusFilter, setEnrichmentStatusFilter] = useState<string>(''); // completed, pending, failed

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const leadsPerPage = 25;

  // Fetch leads and calculate metrics
  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // Fetch all leads (we'll filter client-side for now)
      const allLeads = await apiClient.listLeads(0, 1000);
      
      // Convert to Lead type
      const leadsWithFullData: Lead[] = allLeads.map(lead => ({
        ...lead,
        updated_at: lead.created_at,
        qualification_model: undefined,
        qualification_latency_ms: undefined,
        qualified_at: undefined,
        contact_phone: undefined,
        notes: undefined
      }));

      setLeads(leadsWithFullData);

      // Calculate metrics
      const enrichmentStatus: EnrichmentStatus = {
        completed: 0,
        pending: 0,
        failed: 0
      };

      let totalScore = 0;
      let scoredCount = 0;
      let atlCount = 0;

      leadsWithFullData.forEach(lead => {
        // Determine enrichment status based on data completeness
        const hasEmail = !!lead.contact_email;
        const hasWebsite = !!lead.company_website;
        const hasAdditionalData = !!lead.additional_data;

        if (hasEmail && hasWebsite && hasAdditionalData) {
          enrichmentStatus.completed++;
        } else if (hasEmail || hasWebsite) {
          enrichmentStatus.pending++;
        } else {
          enrichmentStatus.failed++;
        }

        // Calculate average qualification score
        if (lead.qualification_score !== null && lead.qualification_score !== undefined) {
          totalScore += lead.qualification_score;
          scoredCount++;
        }

        // Count ATL contacts (check additional_data for linkedin_url)
        if (lead.additional_data && typeof lead.additional_data === 'object') {
          const additional = lead.additional_data as any;
          if (additional.linkedin_url || additional.source === 'dealer-scraper-mvp') {
            atlCount++;
          }
        }
      });

      const calculatedMetrics: EnrichmentMetrics = {
        totalLeads: leadsWithFullData.length,
        enrichmentCompleted: enrichmentStatus.completed,
        enrichmentPending: enrichmentStatus.pending,
        enrichmentFailed: enrichmentStatus.failed,
        avgQualificationScore: scoredCount > 0 ? totalScore / scoredCount : 0,
        atlContactsDiscovered: atlCount
      };

      setMetrics(calculatedMetrics);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load enrichment data');
      console.error('Error fetching enrichment data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  // Filter and paginate leads
  const filteredLeads = useMemo(() => {
    let filtered = leads;

    // Filter by ICP tier (from additional_data)
    if (icpFilter) {
      filtered = filtered.filter(lead => {
        if (lead.additional_data && typeof lead.additional_data === 'object') {
          const additional = lead.additional_data as any;
          const tier = additional.icp_tier || additional.ICP_Tier;
          return tier && tier.toUpperCase() === icpFilter.toUpperCase();
        }
        return false;
      });
    }

    // Filter by qualification score range
    filtered = filtered.filter(lead => {
      const score = lead.qualification_score;
      if (score === null || score === undefined) return false;
      return score >= scoreRange[0] && score <= scoreRange[1];
    });

    // Filter by enrichment status
    if (enrichmentStatusFilter) {
      filtered = filtered.filter(lead => {
        const hasEmail = !!lead.contact_email;
        const hasWebsite = !!lead.company_website;
        const hasAdditionalData = !!lead.additional_data;

        if (enrichmentStatusFilter === 'completed') {
          return hasEmail && hasWebsite && hasAdditionalData;
        } else if (enrichmentStatusFilter === 'pending') {
          return (hasEmail || hasWebsite) && !(hasEmail && hasWebsite && hasAdditionalData);
        } else if (enrichmentStatusFilter === 'failed') {
          return !hasEmail && !hasWebsite;
        }
        return true;
      });
    }

    return filtered;
  }, [leads, icpFilter, scoreRange, enrichmentStatusFilter]);

  // Paginate filtered leads
  const paginatedLeads = useMemo(() => {
    const startIndex = (currentPage - 1) * leadsPerPage;
    return filteredLeads.slice(startIndex, startIndex + leadsPerPage);
  }, [filteredLeads, currentPage, leadsPerPage]);

  const totalPages = Math.ceil(filteredLeads.length / leadsPerPage);

  // Action handlers
  const handleTriggerEnrichment = async () => {
    // TODO: Implement trigger enrichment API call
    alert('Enrichment trigger feature coming soon!');
  };

  const handleExportEnrichedList = async () => {
    // TODO: Implement export enriched list
    alert('Export feature coming soon!');
  };

  const handleViewATLContacts = () => {
    // Filter to show only leads with ATL contacts
    setEnrichmentStatusFilter('completed');
    // Scroll to table
    window.scrollTo({ top: document.getElementById('leads-table')?.offsetTop || 0, behavior: 'smooth' });
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="p-6">
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <h3 className="text-red-800 font-semibold">Error Loading Data</h3>
          <p className="text-red-600 mt-1">{error}</p>
          <button
            onClick={fetchData}
            className="mt-3 px-4 py-2 bg-red-600 text-white rounded hover:bg-red-700"
          >
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="p-6 max-w-7xl mx-auto">
      {/* Header */}
      <div className="mb-6">
        <h1 className="text-3xl font-bold text-gray-900">Enrichment Dashboard</h1>
        <p className="text-gray-600 mt-1">Monitor lead enrichment progress and ATL contact discovery</p>
      </div>

      {/* Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">Total Imported Leads</h3>
            <p className="text-3xl font-bold text-gray-900 mt-2">{metrics.totalLeads}</p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">Enrichment Status</h3>
            <div className="mt-2 space-y-1">
              <div className="flex justify-between">
                <span className="text-green-600">Completed:</span>
                <span className="font-semibold">{metrics.enrichmentCompleted}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-yellow-600">Pending:</span>
                <span className="font-semibold">{metrics.enrichmentPending}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-red-600">Failed:</span>
                <span className="font-semibold">{metrics.enrichmentFailed}</span>
              </div>
            </div>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">Avg Qualification Score</h3>
            <p className="text-3xl font-bold text-gray-900 mt-2">
              {metrics.avgQualificationScore.toFixed(1)}
            </p>
          </div>

          <div className="bg-white rounded-lg shadow p-6">
            <h3 className="text-sm font-medium text-gray-500">ATL Contacts Discovered</h3>
            <p className="text-3xl font-bold text-blue-600 mt-2">{metrics.atlContactsDiscovered}</p>
          </div>
        </div>
      )}

      {/* Action Buttons */}
      <div className="mb-6 flex flex-wrap gap-3">
        <button
          onClick={handleTriggerEnrichment}
          className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition"
        >
          Trigger Enrichment
        </button>
        <button
          onClick={handleExportEnrichedList}
          className="px-4 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition"
        >
          Export Enriched List
        </button>
        <button
          onClick={handleViewATLContacts}
          className="px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700 transition"
        >
          View ATL Contacts
        </button>
        <button
          onClick={fetchData}
          className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition"
        >
          Refresh Data
        </button>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow p-4 mb-6">
        <h3 className="text-lg font-semibold mb-3">Filters</h3>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* ICP Tier Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              ICP Tier
            </label>
            <select
              value={icpFilter}
              onChange={(e) => {
                setIcpFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Tiers</option>
              <option value="GOLD">Gold</option>
              <option value="SILVER">Silver</option>
              <option value="BRONZE">Bronze</option>
            </select>
          </div>

          {/* Score Range Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Qualification Score Range
            </label>
            <div className="flex gap-2 items-center">
              <input
                type="number"
                min="0"
                max="100"
                value={scoreRange[0]}
                onChange={(e) => {
                  setScoreRange([parseInt(e.target.value) || 0, scoreRange[1]]);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
              <span className="text-gray-500">-</span>
              <input
                type="number"
                min="0"
                max="100"
                value={scoreRange[1]}
                onChange={(e) => {
                  setScoreRange([scoreRange[0], parseInt(e.target.value) || 100]);
                  setCurrentPage(1);
                }}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
              />
            </div>
          </div>

          {/* Enrichment Status Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Enrichment Status
            </label>
            <select
              value={enrichmentStatusFilter}
              onChange={(e) => {
                setEnrichmentStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
      </div>

      {/* Leads Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden" id="leads-table">
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Company Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  ICP Tier
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Qualification Score
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Enrichment Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Contact Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  LinkedIn
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {paginatedLeads.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-8 text-center text-gray-500">
                    No leads found matching filters
                  </td>
                </tr>
              ) : (
                paginatedLeads.map((lead) => {
                  const additional = lead.additional_data as any;
                  const icpTier = additional?.icp_tier || additional?.ICP_Tier || 'N/A';
                  const linkedinUrl = additional?.linkedin_url || null;

                  const hasEmail = !!lead.contact_email;
                  const hasWebsite = !!lead.company_website;
                  const hasAdditionalData = !!lead.additional_data;
                  let enrichmentStatus = 'failed';
                  let statusColor = 'bg-red-100 text-red-800';

                  if (hasEmail && hasWebsite && hasAdditionalData) {
                    enrichmentStatus = 'completed';
                    statusColor = 'bg-green-100 text-green-800';
                  } else if (hasEmail || hasWebsite) {
                    enrichmentStatus = 'pending';
                    statusColor = 'bg-yellow-100 text-yellow-800';
                  }

                  return (
                    <tr key={lead.id} className="hover:bg-gray-50">
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {lead.company_name}
                        </div>
                        {lead.company_website && (
                          <div className="text-xs text-gray-500">{lead.company_website}</div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${
                          icpTier === 'GOLD' ? 'bg-yellow-100 text-yellow-800' :
                          icpTier === 'SILVER' ? 'bg-gray-100 text-gray-800' :
                          icpTier === 'BRONZE' ? 'bg-orange-100 text-orange-800' :
                          'bg-gray-100 text-gray-500'
                        }`}>
                          {icpTier}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {lead.qualification_score !== null && lead.qualification_score !== undefined ? (
                          <span className="text-sm font-medium text-gray-900">
                            {lead.qualification_score.toFixed(1)}
                          </span>
                        ) : (
                          <span className="text-sm text-gray-400">N/A</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className={`px-2 py-1 text-xs font-semibold rounded-full ${statusColor}`}>
                          {enrichmentStatus}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {lead.contact_email || <span className="text-gray-400">N/A</span>}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {linkedinUrl ? (
                          <a
                            href={linkedinUrl}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-600 hover:text-blue-800 text-sm"
                          >
                            View Profile
                          </a>
                        ) : (
                          <span className="text-gray-400 text-sm">N/A</span>
                        )}
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="bg-gray-50 px-6 py-3 flex items-center justify-between border-t border-gray-200">
            <div className="text-sm text-gray-700">
              Showing {(currentPage - 1) * leadsPerPage + 1} to {Math.min(currentPage * leadsPerPage, filteredLeads.length)} of {filteredLeads.length} leads
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
              >
                Previous
              </button>
              <button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                className="px-3 py-2 border border-gray-300 rounded-lg text-sm disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-100"
              >
                Next
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

