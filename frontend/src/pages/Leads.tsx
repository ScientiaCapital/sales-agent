/**
 * Leads Page
 *
 * Lead management interface with CRUD operations, filtering, sorting, and pagination
 */

import { useState, useEffect, useMemo } from 'react';
import { apiClient } from '../services/api';
import { LeadDetailModal } from '../components/LeadDetailModal';
import { LeadQualificationForm } from '../components/LeadQualificationForm';
import type { Lead } from '../types';

export function Leads() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pagination state
  const [currentPage, setCurrentPage] = useState(1);
  const leadsPerPage = 25;

  // Filter state
  const [searchTerm, setSearchTerm] = useState('');
  const [industryFilter, setIndustryFilter] = useState('');
  const [scoreRange, setScoreRange] = useState<[number, number]>([0, 100]);

  // Sort state
  const [sortColumn, setSortColumn] = useState<keyof Lead>('created_at');
  const [sortDirection, setSortDirection] = useState<'asc' | 'desc'>('desc');

  // Modal state
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  const [showDetailModal, setShowDetailModal] = useState(false);
  const [showQualificationForm, setShowQualificationForm] = useState(false);

  // Fetch leads
  useEffect(() => {
    fetchLeads();
  }, [currentPage]);

  const fetchLeads = async () => {
    setIsLoading(true);
    setError(null);

    try {
      const skip = (currentPage - 1) * leadsPerPage;
      const allLeads = await apiClient.listLeads(skip, leadsPerPage);
      // Convert LeadListResponse to Lead by adding missing updated_at field
      const leadsWithFullData: Lead[] = allLeads.map(lead => ({
        ...lead,
        updated_at: lead.created_at, // Use created_at as fallback for updated_at
        qualification_model: undefined,
        qualification_latency_ms: undefined,
        qualified_at: undefined,
        contact_phone: undefined,
        notes: undefined
      }));
      setLeads(leadsWithFullData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load leads');
    } finally {
      setIsLoading(false);
    }
  };

  // Filter and sort leads client-side
  const filteredAndSortedLeads = useMemo(() => {
    let filtered = leads;

    // Apply search filter
    if (searchTerm) {
      filtered = filtered.filter((lead) =>
        lead.company_name.toLowerCase().includes(searchTerm.toLowerCase())
      );
    }

    // Apply industry filter
    if (industryFilter) {
      filtered = filtered.filter((lead) => lead.industry === industryFilter);
    }

    // Apply score range filter
    filtered = filtered.filter(
      (lead) =>
        !lead.qualification_score ||
        (lead.qualification_score >= scoreRange[0] &&
          lead.qualification_score <= scoreRange[1])
    );

    // Apply sorting
    filtered.sort((a, b) => {
      const aValue = a[sortColumn];
      const bValue = b[sortColumn];

      if (aValue === undefined && bValue === undefined) return 0;
      if (aValue === undefined) return 1;
      if (bValue === undefined) return -1;

      let comparison = 0;
      if (typeof aValue === 'string' && typeof bValue === 'string') {
        comparison = aValue.localeCompare(bValue);
      } else if (typeof aValue === 'number' && typeof bValue === 'number') {
        comparison = aValue - bValue;
      } else {
        comparison = String(aValue).localeCompare(String(bValue));
      }

      return sortDirection === 'asc' ? comparison : -comparison;
    });

    return filtered;
  }, [leads, searchTerm, industryFilter, scoreRange, sortColumn, sortDirection]);

  // Handle sort
  const handleSort = (column: keyof Lead) => {
    if (sortColumn === column) {
      setSortDirection(sortDirection === 'asc' ? 'desc' : 'asc');
    } else {
      setSortColumn(column);
      setSortDirection('asc');
    }
  };

  // Handle row click
  const handleRowClick = async (lead: Lead) => {
    try {
      const fullLead = await apiClient.getLead(lead.id);
      setSelectedLead(fullLead);
      setShowDetailModal(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load lead details');
    }
  };

  // Get unique industries for filter dropdown
  const industries = useMemo(() => {
    const uniqueIndustries = new Set(
      leads.filter((l) => l.industry).map((l) => l.industry!)
    );
    return Array.from(uniqueIndustries).sort();
  }, [leads]);

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleDateString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
    });
  };

  // Get score badge color
  const getScoreBadgeColor = (score?: number) => {
    if (!score) return 'bg-gray-100 text-gray-800';
    if (score >= 80) return 'bg-green-100 text-green-800';
    if (score >= 60) return 'bg-blue-100 text-blue-800';
    if (score >= 40) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <div className="max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Lead Management</h1>
          <p className="text-gray-600 mt-2">
            Manage and qualify leads with AI-powered insights
          </p>
        </div>
        <div className="flex space-x-3">
          <button
            onClick={() => (window.location.href = '/csv-import')}
            className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50 flex items-center space-x-2"
          >
            <span>📊</span>
            <span>Import CSV</span>
          </button>
          <button
            onClick={() => setShowQualificationForm(true)}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 flex items-center space-x-2"
          >
            <span>+</span>
            <span>New Lead</span>
          </button>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white shadow rounded-lg p-4">
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          {/* Search */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Search
            </label>
            <input
              type="text"
              placeholder="Search company name..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            />
          </div>

          {/* Industry Filter */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Industry
            </label>
            <select
              value={industryFilter}
              onChange={(e) => setIndustryFilter(e.target.value)}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500"
            >
              <option value="">All Industries</option>
              {industries.map((industry) => (
                <option key={industry} value={industry}>
                  {industry}
                </option>
              ))}
            </select>
          </div>

          {/* Score Range */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Score Range: {scoreRange[0]} - {scoreRange[1]}
            </label>
            <div className="flex items-center space-x-2">
              <input
                type="range"
                min="0"
                max="100"
                value={scoreRange[0]}
                onChange={(e) =>
                  setScoreRange([Number(e.target.value), scoreRange[1]])
                }
                className="w-full"
              />
              <input
                type="range"
                min="0"
                max="100"
                value={scoreRange[1]}
                onChange={(e) =>
                  setScoreRange([scoreRange[0], Number(e.target.value)])
                }
                className="w-full"
              />
            </div>
          </div>

          {/* Clear Filters */}
          <div className="flex items-end">
            <button
              onClick={() => {
                setSearchTerm('');
                setIndustryFilter('');
                setScoreRange([0, 100]);
              }}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Clear Filters
            </button>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <span className="text-red-600 mr-3">✕</span>
            <div>
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Table */}
      <div className="bg-white shadow rounded-lg overflow-hidden">
        {isLoading ? (
          <div className="p-12 text-center">
            <div className="inline-block animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600"></div>
            <p className="mt-4 text-gray-600">Loading leads...</p>
          </div>
        ) : filteredAndSortedLeads.length === 0 ? (
          <div className="text-center py-12">
            <div className="text-6xl mb-4">📋</div>
            <h3 className="text-lg font-medium text-gray-900">No leads found</h3>
            <p className="text-sm text-gray-500 mt-1">
              {searchTerm || industryFilter
                ? 'Try adjusting your filters'
                : 'Get started by qualifying your first lead'}
            </p>
          </div>
        ) : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th
                      onClick={() => handleSort('company_name')}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    >
                      <div className="flex items-center space-x-1">
                        <span>Company</span>
                        {sortColumn === 'company_name' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th
                      onClick={() => handleSort('industry')}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    >
                      <div className="flex items-center space-x-1">
                        <span>Industry</span>
                        {sortColumn === 'industry' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th
                      onClick={() => handleSort('qualification_score')}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    >
                      <div className="flex items-center space-x-1">
                        <span>Score</span>
                        {sortColumn === 'qualification_score' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                      Contact
                    </th>
                    <th
                      onClick={() => handleSort('created_at')}
                      className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider cursor-pointer hover:bg-gray-100"
                    >
                      <div className="flex items-center space-x-1">
                        <span>Created</span>
                        {sortColumn === 'created_at' && (
                          <span>{sortDirection === 'asc' ? '↑' : '↓'}</span>
                        )}
                      </div>
                    </th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {filteredAndSortedLeads.map((lead) => (
                    <tr
                      key={lead.id}
                      onClick={() => handleRowClick(lead)}
                      className="hover:bg-gray-50 cursor-pointer transition-colors"
                    >
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm font-medium text-gray-900">
                          {lead.company_name}
                        </div>
                        {lead.company_website && (
                          <div className="text-sm text-gray-500">
                            {lead.company_website}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <span className="text-sm text-gray-900">
                          {lead.industry || '-'}
                        </span>
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        {lead.qualification_score ? (
                          <span
                            className={`px-2 inline-flex text-xs leading-5 font-semibold rounded-full ${getScoreBadgeColor(
                              lead.qualification_score
                            )}`}
                          >
                            {lead.qualification_score.toFixed(1)}
                          </span>
                        ) : (
                          <span className="text-sm text-gray-400">-</span>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap">
                        <div className="text-sm text-gray-900">
                          {lead.contact_name || '-'}
                        </div>
                        {lead.contact_email && (
                          <div className="text-sm text-gray-500">
                            {lead.contact_email}
                          </div>
                        )}
                      </td>
                      <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                        {formatDate(lead.created_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            <div className="bg-white px-4 py-3 flex items-center justify-between border-t border-gray-200 sm:px-6">
              <div className="flex-1 flex justify-between sm:hidden">
                <button
                  onClick={() => setCurrentPage(Math.max(1, currentPage - 1))}
                  disabled={currentPage === 1}
                  className="relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                >
                  Previous
                </button>
                <button
                  onClick={() => setCurrentPage(currentPage + 1)}
                  disabled={filteredAndSortedLeads.length < leadsPerPage}
                  className="ml-3 relative inline-flex items-center px-4 py-2 border border-gray-300 text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50 disabled:opacity-50"
                >
                  Next
                </button>
              </div>
              <div className="hidden sm:flex-1 sm:flex sm:items-center sm:justify-between">
                <div>
                  <p className="text-sm text-gray-700">
                    Showing{' '}
                    <span className="font-medium">
                      {(currentPage - 1) * leadsPerPage + 1}
                    </span>{' '}
                    to{' '}
                    <span className="font-medium">
                      {Math.min(
                        currentPage * leadsPerPage,
                        filteredAndSortedLeads.length
                      )}
                    </span>{' '}
                    of{' '}
                    <span className="font-medium">
                      {filteredAndSortedLeads.length}
                    </span>{' '}
                    leads
                  </p>
                </div>
                <div>
                  <nav
                    className="relative z-0 inline-flex rounded-md shadow-sm -space-x-px"
                    aria-label="Pagination"
                  >
                    <button
                      onClick={() =>
                        setCurrentPage(Math.max(1, currentPage - 1))
                      }
                      disabled={currentPage === 1}
                      className="relative inline-flex items-center px-2 py-2 rounded-l-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                    >
                      Previous
                    </button>
                    <span className="relative inline-flex items-center px-4 py-2 border border-gray-300 bg-white text-sm font-medium text-gray-700">
                      Page {currentPage}
                    </span>
                    <button
                      onClick={() => setCurrentPage(currentPage + 1)}
                      disabled={filteredAndSortedLeads.length < leadsPerPage}
                      className="relative inline-flex items-center px-2 py-2 rounded-r-md border border-gray-300 bg-white text-sm font-medium text-gray-500 hover:bg-gray-50 disabled:opacity-50"
                    >
                      Next
                    </button>
                  </nav>
                </div>
              </div>
            </div>
          </>
        )}
      </div>

      {/* Modals */}
      {showDetailModal && selectedLead && (
        <LeadDetailModal
          lead={selectedLead}
          onClose={() => {
            setShowDetailModal(false);
            setSelectedLead(null);
          }}
        />
      )}

      {showQualificationForm && (
        <LeadQualificationForm
          onClose={() => setShowQualificationForm(false)}
          onSuccess={() => {
            setShowQualificationForm(false);
            fetchLeads();
          }}
        />
      )}
    </div>
  );
}
