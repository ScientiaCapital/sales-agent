/**
 * Campaigns Page
 *
 * Main campaign management interface with list/detail views and creation wizard
 */

import { useState, useEffect } from 'react';
import { apiClient } from '../services/api';
import { CampaignCreationWizard } from '../components/CampaignCreationWizard';
import { MessageVariantDisplay } from '../components/MessageVariantDisplay';
import { CampaignAnalyticsDashboard } from '../components/CampaignAnalyticsDashboard';
import type {
  CampaignResponse,
  CampaignCreateRequest,
  MessageResponse,
  AnalyticsResponse,
} from '../types';

type ViewMode = 'list' | 'detail';

const STATUS_COLORS = {
  draft: 'bg-gray-100 text-gray-800',
  active: 'bg-green-100 text-green-800',
  paused: 'bg-yellow-100 text-yellow-800',
  completed: 'bg-blue-100 text-blue-800',
  cancelled: 'bg-red-100 text-red-800',
};

const CHANNEL_ICONS = {
  email: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
      />
    </svg>
  ),
  linkedin: (
    <svg className="h-5 w-5" fill="currentColor" viewBox="0 0 24 24">
      <path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433c-1.144 0-2.063-.926-2.063-2.065 0-1.138.92-2.063 2.063-2.063 1.14 0 2.064.925 2.064 2.063 0 1.139-.925 2.065-2.064 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z" />
    </svg>
  ),
  sms: (
    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth={2}
        d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
      />
    </svg>
  ),
};

export function Campaigns() {
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [campaigns, setCampaigns] = useState<CampaignResponse[]>([]);
  const [selectedCampaign, setSelectedCampaign] = useState<CampaignResponse | null>(null);
  const [messages, setMessages] = useState<MessageResponse[]>([]);
  const [analytics, setAnalytics] = useState<AnalyticsResponse | null>(null);
  const [showWizard, setShowWizard] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterStatus, setFilterStatus] = useState<string>('');
  const [generatingMessages, setGeneratingMessages] = useState(false);
  const [activating, setActivating] = useState(false);

  useEffect(() => {
    loadCampaigns();
  }, [filterStatus]);

  const loadCampaigns = async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await apiClient.listCampaigns(filterStatus || undefined);
      setCampaigns(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load campaigns');
    } finally {
      setLoading(false);
    }
  };

  const handleCreateCampaign = async (request: CampaignCreateRequest) => {
    try {
      const newCampaign = await apiClient.createCampaign(request);
      setCampaigns((prev) => [newCampaign, ...prev]);
      setShowWizard(false);
      // Automatically open the new campaign
      handleViewCampaign(newCampaign);
    } catch (err) {
      throw err; // Propagate error to wizard
    }
  };

  const handleViewCampaign = async (campaign: CampaignResponse) => {
    setSelectedCampaign(campaign);
    setViewMode('detail');

    try {
      // Load campaign messages and analytics
      const [messagesData, analyticsData] = await Promise.all([
        apiClient.getCampaignMessages(campaign.id),
        apiClient.getCampaignAnalytics(campaign.id),
      ]);
      setMessages(messagesData);
      setAnalytics(analyticsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load campaign details');
    }
  };

  const handleGenerateMessages = async () => {
    if (!selectedCampaign) return;

    try {
      setGeneratingMessages(true);
      setError(null);
      await apiClient.generateMessages(selectedCampaign.id);

      // Reload messages and update campaign
      const [messagesData, updatedCampaigns] = await Promise.all([
        apiClient.getCampaignMessages(selectedCampaign.id),
        apiClient.listCampaigns(),
      ]);

      setMessages(messagesData);
      setCampaigns(updatedCampaigns);

      const updatedCampaign = updatedCampaigns.find((c) => c.id === selectedCampaign.id);
      if (updatedCampaign) {
        setSelectedCampaign(updatedCampaign);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate messages');
    } finally {
      setGeneratingMessages(false);
    }
  };

  const handleActivateCampaign = async () => {
    if (!selectedCampaign) return;

    try {
      setActivating(true);
      setError(null);
      const result = await apiClient.activateCampaign(selectedCampaign.id);

      // Update campaign status
      setSelectedCampaign(result.campaign);
      setCampaigns((prev) =>
        prev.map((c) => (c.id === result.campaign.id ? result.campaign : c))
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to activate campaign');
    } finally {
      setActivating(false);
    }
  };

  const handleBackToList = () => {
    setViewMode('list');
    setSelectedCampaign(null);
    setMessages([]);
    setAnalytics(null);
    setError(null);
  };

  if (loading && campaigns.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
          <p className="mt-4 text-gray-600">Loading campaigns...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="bg-white shadow rounded-lg p-6">
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-2xl font-bold text-gray-900">
              {viewMode === 'list' ? 'Campaign Manager' : selectedCampaign?.name}
            </h2>
            <p className="text-gray-600 mt-1">
              {viewMode === 'list'
                ? 'Create and manage multi-channel outreach campaigns with AI-powered message generation'
                : 'Campaign details and analytics'}
            </p>
          </div>
          {viewMode === 'list' ? (
            <button
              onClick={() => setShowWizard(true)}
              className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-indigo-500"
            >
              <svg
                className="-ml-1 mr-2 h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 4v16m8-8H4"
                />
              </svg>
              Create Campaign
            </button>
          ) : (
            <button
              onClick={handleBackToList}
              className="inline-flex items-center px-4 py-2 border border-gray-300 shadow-sm text-sm font-medium rounded-md text-gray-700 bg-white hover:bg-gray-50"
            >
              <svg
                className="-ml-1 mr-2 h-5 w-5"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M10 19l-7-7m0 0l7-7m-7 7h18"
                />
              </svg>
              Back to List
            </button>
          )}
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-md p-4">
          <div className="flex">
            <svg
              className="h-5 w-5 text-red-400"
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
              />
            </svg>
            <p className="ml-3 text-sm text-red-800">{error}</p>
          </div>
        </div>
      )}

      {/* List View */}
      {viewMode === 'list' && (
        <>
          {/* Filters */}
          <div className="bg-white shadow rounded-lg p-4">
            <div className="flex items-center space-x-4">
              <label htmlFor="status-filter" className="text-sm font-medium text-gray-700">
                Filter by Status:
              </label>
              <select
                id="status-filter"
                value={filterStatus}
                onChange={(e) => setFilterStatus(e.target.value)}
                className="px-3 py-2 border border-gray-300 rounded-md focus:outline-none focus:ring-2 focus:ring-indigo-500"
              >
                <option value="">All Statuses</option>
                <option value="draft">Draft</option>
                <option value="active">Active</option>
                <option value="paused">Paused</option>
                <option value="completed">Completed</option>
              </select>
            </div>
          </div>

          {/* Campaign List */}
          {campaigns.length === 0 ? (
            <div className="bg-white shadow rounded-lg p-12">
              <div className="text-center">
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
                    d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                  />
                </svg>
                <h3 className="mt-2 text-sm font-medium text-gray-900">No campaigns yet</h3>
                <p className="mt-1 text-sm text-gray-500">
                  {filterStatus
                    ? 'No campaigns match the selected filter'
                    : 'Launch your first outreach campaign with AI-generated messages'}
                </p>
                {!filterStatus && (
                  <div className="mt-6">
                    <button
                      onClick={() => setShowWizard(true)}
                      className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700"
                    >
                      Create Campaign
                    </button>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {campaigns.map((campaign) => (
                <div
                  key={campaign.id}
                  onClick={() => handleViewCampaign(campaign)}
                  className="bg-white shadow rounded-lg p-6 cursor-pointer hover:shadow-lg transition-shadow"
                >
                  <div className="flex items-center justify-between mb-4">
                    <span
                      className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-medium ${
                        STATUS_COLORS[campaign.status]
                      }`}
                    >
                      {campaign.status}
                    </span>
                    <div className="text-gray-400">{CHANNEL_ICONS[campaign.channel]}</div>
                  </div>

                  <h3 className="text-lg font-semibold text-gray-900 mb-2">{campaign.name}</h3>

                  <div className="space-y-2 text-sm text-gray-600">
                    <div className="flex justify-between">
                      <span>Messages</span>
                      <span className="font-semibold text-gray-900">
                        {campaign.total_messages}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Sent</span>
                      <span className="font-semibold text-gray-900">{campaign.total_sent}</span>
                    </div>
                    <div className="flex justify-between">
                      <span>Replies</span>
                      <span className="font-semibold text-green-600">
                        {campaign.total_replied}
                      </span>
                    </div>
                    <div className="flex justify-between">
                      <span>Cost</span>
                      <span className="font-semibold text-gray-900">
                        ${campaign.total_cost.toFixed(2)}
                      </span>
                    </div>
                  </div>

                  <div className="mt-4 pt-4 border-t border-gray-200 text-xs text-gray-500">
                    Created {new Date(campaign.created_at).toLocaleDateString()}
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Detail View */}
      {viewMode === 'detail' && selectedCampaign && (
        <div className="space-y-6">
          {/* Campaign Metadata */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-1">Status</h4>
                <span
                  className={`inline-flex items-center px-3 py-1 rounded-full text-sm font-medium ${
                    STATUS_COLORS[selectedCampaign.status]
                  }`}
                >
                  {selectedCampaign.status}
                </span>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-1">Channel</h4>
                <div className="flex items-center space-x-2">
                  {CHANNEL_ICONS[selectedCampaign.channel]}
                  <span className="text-base capitalize">{selectedCampaign.channel}</span>
                </div>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-1">Min Score</h4>
                <p className="text-base font-semibold">
                  {selectedCampaign.min_qualification_score || 'N/A'}
                </p>
              </div>
              <div>
                <h4 className="text-sm font-medium text-gray-500 mb-1">Target Industries</h4>
                <p className="text-base">
                  {selectedCampaign.target_industries?.length || 0} selected
                </p>
              </div>
            </div>
          </div>

          {/* Action Buttons */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex items-center space-x-4">
              {selectedCampaign.status === 'draft' && (
                <button
                  onClick={handleGenerateMessages}
                  disabled={generatingMessages}
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50"
                >
                  {generatingMessages ? (
                    <>
                      <svg
                        className="animate-spin -ml-1 mr-2 h-5 w-5 text-white"
                        xmlns="http://www.w3.org/2000/svg"
                        fill="none"
                        viewBox="0 0 24 24"
                      >
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        ></circle>
                        <path
                          className="opacity-75"
                          fill="currentColor"
                          d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                        ></path>
                      </svg>
                      Generating...
                    </>
                  ) : (
                    'Generate Messages'
                  )}
                </button>
              )}

              {selectedCampaign.status === 'draft' && messages.length > 0 && (
                <button
                  onClick={handleActivateCampaign}
                  disabled={activating}
                  className="inline-flex items-center px-4 py-2 border border-transparent shadow-sm text-sm font-medium rounded-md text-white bg-green-600 hover:bg-green-700 disabled:opacity-50"
                >
                  {activating ? 'Activating...' : 'Activate Campaign'}
                </button>
              )}
            </div>
          </div>

          {/* Messages Section */}
          {messages.length > 0 && (
            <div className="bg-white shadow rounded-lg p-6">
              <h3 className="text-lg font-bold text-gray-900 mb-4">
                Messages ({messages.length})
              </h3>
              <div className="space-y-6">
                {messages.slice(0, 3).map((message) => (
                  <div key={message.id} className="border-t pt-4 first:border-t-0 first:pt-0">
                    <div className="mb-4">
                      <h4 className="text-sm font-medium text-gray-700 mb-2">
                        Message #{message.id} - Lead {message.lead_id}
                      </h4>
                      <MessageVariantDisplay
                        variants={message.variants}
                        selectedVariant={message.selected_variant}
                      />
                    </div>
                  </div>
                ))}
                {messages.length > 3 && (
                  <p className="text-sm text-gray-500 text-center">
                    Showing 3 of {messages.length} messages
                  </p>
                )}
              </div>
            </div>
          )}

          {/* Analytics Section */}
          {analytics && selectedCampaign.status !== 'draft' && (
            <CampaignAnalyticsDashboard analytics={analytics} />
          )}
        </div>
      )}

      {/* Creation Wizard Modal */}
      {showWizard && (
        <CampaignCreationWizard
          onComplete={handleCreateCampaign}
          onCancel={() => setShowWizard(false)}
        />
      )}
    </div>
  );
}
