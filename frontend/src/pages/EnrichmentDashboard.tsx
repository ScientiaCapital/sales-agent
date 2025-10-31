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
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '../components/ui/card';
import { Button } from '../components/ui/button';
import { Badge } from '../components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '../components/ui/table';
import { MetricsCard } from '../components/ui/metrics-card';

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
    <div className="p-6 space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <Card>
        <CardHeader>
          <CardTitle>Enrichment Dashboard</CardTitle>
          <CardDescription>
            Monitor lead enrichment progress and ATL contact discovery
          </CardDescription>
        </CardHeader>
      </Card>

      {/* Metrics Cards */}
      {metrics && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
          <MetricsCard
            title="Total Imported Leads"
            value={metrics.totalLeads}
            icon={undefined}
          />
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Enrichment Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-emerald-700">Completed:</span>
                <Badge variant="success">{metrics.enrichmentCompleted}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-amber-700">Pending:</span>
                <Badge variant="warning">{metrics.enrichmentPending}</Badge>
              </div>
              <div className="flex justify-between items-center">
                <span className="text-sm font-medium text-red-700">Failed:</span>
                <Badge variant="destructive">{metrics.enrichmentFailed}</Badge>
              </div>
            </CardContent>
          </Card>
          <MetricsCard
            title="Avg Qualification Score"
            value={metrics.avgQualificationScore.toFixed(1)}
            icon={undefined}
          />
          <MetricsCard
            title="ATL Contacts Discovered"
            value={metrics.atlContactsDiscovered}
            icon={undefined}
          />
        </div>
      )}

      {/* Action Buttons */}
      <Card>
        <CardContent className="pt-6">
          <div className="flex flex-wrap gap-3">
            <Button onClick={handleTriggerEnrichment} variant="primary" size="lg">
              Trigger Enrichment
            </Button>
            <Button onClick={handleExportEnrichedList} variant="success" size="lg">
              Export Enriched List
            </Button>
            <Button onClick={handleViewATLContacts} variant="secondary" size="lg">
              View ATL Contacts
            </Button>
            <Button onClick={fetchData} variant="outline" size="lg">
              Refresh Data
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Filters */}
      <Card>
        <CardHeader>
          <CardTitle>Filters</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* ICP Tier Filter */}
          <div>
            <label className="block text-base font-bold text-gray-800 mb-3">
              ICP Tier
            </label>
            <select
              value={icpFilter}
              onChange={(e) => {
                setIcpFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-5 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-base font-medium bg-white shadow-sm hover:border-gray-400 transition-colors"
            >
              <option value="">All Tiers</option>
              <option value="GOLD">Gold</option>
              <option value="SILVER">Silver</option>
              <option value="BRONZE">Bronze</option>
            </select>
          </div>

          {/* Score Range Filter */}
          <div>
            <label className="block text-base font-bold text-gray-800 mb-3">
              Qualification Score Range
            </label>
            <div className="flex gap-3 items-center">
              <input
                type="number"
                min="0"
                max="100"
                value={scoreRange[0]}
                onChange={(e) => {
                  setScoreRange([parseInt(e.target.value) || 0, scoreRange[1]]);
                  setCurrentPage(1);
                }}
                className="w-full px-5 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-base font-medium shadow-sm"
              />
              <span className="text-lg font-bold text-gray-600">-</span>
              <input
                type="number"
                min="0"
                max="100"
                value={scoreRange[1]}
                onChange={(e) => {
                  setScoreRange([scoreRange[0], parseInt(e.target.value) || 100]);
                  setCurrentPage(1);
                }}
                className="w-full px-5 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-base font-medium shadow-sm"
              />
            </div>
          </div>

          {/* Enrichment Status Filter */}
          <div>
            <label className="block text-base font-bold text-gray-800 mb-3">
              Enrichment Status
            </label>
            <select
              value={enrichmentStatusFilter}
              onChange={(e) => {
                setEnrichmentStatusFilter(e.target.value);
                setCurrentPage(1);
              }}
              className="w-full px-5 py-3 border-2 border-gray-300 rounded-xl focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-base font-medium bg-white shadow-sm hover:border-gray-400 transition-colors"
            >
              <option value="">All Statuses</option>
              <option value="completed">Completed</option>
              <option value="pending">Pending</option>
              <option value="failed">Failed</option>
            </select>
          </div>
        </div>
        </CardContent>
      </Card>

      {/* Leads Table */}
      <Card id="leads-table">
        <CardHeader>
          <CardTitle>Leads ({filteredLeads.length})</CardTitle>
          <CardDescription>Filtered and paginated lead list</CardDescription>
        </CardHeader>
        <CardContent className="p-0">
          <div className="overflow-x-auto">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Company Name</TableHead>
                  <TableHead>ICP Tier</TableHead>
                  <TableHead>Qualification Score</TableHead>
                  <TableHead>Enrichment Status</TableHead>
                  <TableHead>Contact Email</TableHead>
                  <TableHead>LinkedIn</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {paginatedLeads.length === 0 ? (
                  <TableRow>
                    <TableCell colSpan={6} className="text-center py-12">
                      <p className="text-lg font-medium text-slate-500">No leads found matching filters</p>
                    </TableCell>
                  </TableRow>
                ) : (
                  paginatedLeads.map((lead) => {
                    const additional = lead.additional_data as any;
                    const icpTier = additional?.icp_tier || additional?.ICP_Tier || 'N/A';
                    const linkedinUrl = additional?.linkedin_url || null;

                    const hasEmail = !!lead.contact_email;
                    const hasWebsite = !!lead.company_website;
                    const hasAdditionalData = !!lead.additional_data;
                    let enrichmentStatus = 'failed';
                    let statusVariant: 'success' | 'warning' | 'destructive' = 'destructive';

                    if (hasEmail && hasWebsite && hasAdditionalData) {
                      enrichmentStatus = 'completed';
                      statusVariant = 'success';
                    } else if (hasEmail || hasWebsite) {
                      enrichmentStatus = 'pending';
                      statusVariant = 'warning';
                    }

                    const tierVariant = icpTier === 'GOLD' ? 'gold' : icpTier === 'SILVER' ? 'silver' : icpTier === 'BRONZE' ? 'bronze' : 'secondary';

                    return (
                      <TableRow key={lead.id}>
                        <TableCell>
                          <div className="font-semibold text-slate-900">{lead.company_name}</div>
                          {lead.company_website && (
                            <div className="text-sm text-slate-500">{lead.company_website}</div>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={tierVariant as any}>{icpTier}</Badge>
                        </TableCell>
                        <TableCell>
                          {lead.qualification_score !== null && lead.qualification_score !== undefined ? (
                            <span className="font-semibold">{lead.qualification_score.toFixed(1)}</span>
                          ) : (
                            <span className="text-slate-400">N/A</span>
                          )}
                        </TableCell>
                        <TableCell>
                          <Badge variant={statusVariant}>{enrichmentStatus}</Badge>
                        </TableCell>
                        <TableCell className="text-slate-600">
                          {lead.contact_email || <span className="text-slate-400">N/A</span>}
                        </TableCell>
                        <TableCell>
                          {linkedinUrl ? (
                            <a href={linkedinUrl} target="_blank" rel="noopener noreferrer" className="text-blue-600 hover:underline font-medium">
                              View Profile
                            </a>
                          ) : (
                            <span className="text-slate-400">N/A</span>
                          )}
                        </TableCell>
                      </TableRow>
                    );
                  })
                )}
              </TableBody>
            </Table>
          </div>
        </CardContent>
        {totalPages > 1 && (
          <CardContent className="border-t flex items-center justify-between">
            <div className="text-sm text-slate-600">
              Showing <span className="font-semibold">{(currentPage - 1) * leadsPerPage + 1}</span> to{' '}
              <span className="font-semibold">{Math.min(currentPage * leadsPerPage, filteredLeads.length)}</span> of{' '}
              <span className="font-semibold">{filteredLeads.length}</span> leads
            </div>
            <div className="flex gap-2">
              <Button
                onClick={() => setCurrentPage(p => Math.max(1, p - 1))}
                disabled={currentPage === 1}
                variant="outline"
                size="sm"
              >
                Previous
              </Button>
              <Button
                onClick={() => setCurrentPage(p => Math.min(totalPages, p + 1))}
                disabled={currentPage === totalPages}
                variant="outline"
                size="sm"
              >
                Next
              </Button>
            </div>
          </CardContent>
        )}
      </Card>
    </div>
  );
}

