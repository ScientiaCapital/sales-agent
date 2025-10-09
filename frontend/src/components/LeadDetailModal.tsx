/**
 * Lead Detail Modal
 *
 * Displays full lead information including qualification data
 */

import type { Lead } from '../types';

interface LeadDetailModalProps {
  lead: Lead;
  onClose: () => void;
}

export function LeadDetailModal({ lead, onClose }: LeadDetailModalProps) {
  // Get score badge color
  const getScoreBadgeColor = (score?: number) => {
    if (!score) return 'bg-gray-100 text-gray-800';
    if (score >= 80) return 'bg-green-100 text-green-800';
    if (score >= 60) return 'bg-blue-100 text-blue-800';
    if (score >= 40) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  // Format date
  const formatDate = (dateString: string) => {
    return new Date(dateString).toLocaleString('en-US', {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black bg-opacity-50 transition-opacity"
        onClick={onClose}
      ></div>

      {/* Modal */}
      <div className="flex min-h-full items-center justify-center p-4">
        <div className="relative bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto">
          {/* Header */}
          <div className="sticky top-0 bg-white border-b border-gray-200 px-6 py-4 flex justify-between items-center">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">
                {lead.company_name}
              </h2>
              {lead.industry && (
                <p className="text-sm text-gray-600 mt-1">{lead.industry}</p>
              )}
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 transition-colors"
            >
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </button>
          </div>

          {/* Content */}
          <div className="p-6 space-y-6">
            {/* Qualification Score */}
            {lead.qualification_score && (
              <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-lg p-6">
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900 mb-2">
                      Qualification Score
                    </h3>
                    <div className="flex items-center space-x-3">
                      <span
                        className={`px-4 py-2 text-2xl font-bold rounded-full ${getScoreBadgeColor(
                          lead.qualification_score
                        )}`}
                      >
                        {lead.qualification_score.toFixed(1)}
                      </span>
                      {lead.qualification_model && (
                        <span className="text-sm text-gray-600">
                          Model: {lead.qualification_model}
                        </span>
                      )}
                      {lead.qualification_latency_ms && (
                        <span className="text-sm text-gray-600">
                          Latency: {lead.qualification_latency_ms}ms
                        </span>
                      )}
                    </div>
                  </div>
                  {lead.qualified_at && (
                    <div className="text-right text-sm text-gray-600">
                      <div>Qualified</div>
                      <div className="font-medium">
                        {formatDate(lead.qualified_at)}
                      </div>
                    </div>
                  )}
                </div>

                {lead.qualification_reasoning && (
                  <div className="mt-4 pt-4 border-t border-blue-200">
                    <h4 className="text-sm font-semibold text-gray-700 mb-2">
                      AI Reasoning
                    </h4>
                    <p className="text-sm text-gray-700 whitespace-pre-wrap">
                      {lead.qualification_reasoning}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* Company Information */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Company Information
              </h3>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">
                    Company Name
                  </label>
                  <p className="text-sm text-gray-900">{lead.company_name}</p>
                </div>

                {lead.company_website && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Website
                    </label>
                    <a
                      href={lead.company_website}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-sm text-blue-600 hover:text-blue-800 underline"
                    >
                      {lead.company_website}
                    </a>
                  </div>
                )}

                {lead.company_size && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Company Size
                    </label>
                    <p className="text-sm text-gray-900">{lead.company_size}</p>
                  </div>
                )}

                {lead.industry && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Industry
                    </label>
                    <p className="text-sm text-gray-900">{lead.industry}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Contact Information */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Contact Information
              </h3>
              <div className="grid grid-cols-2 gap-4">
                {lead.contact_name && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Name
                    </label>
                    <p className="text-sm text-gray-900">{lead.contact_name}</p>
                  </div>
                )}

                {lead.contact_email && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Email
                    </label>
                    <a
                      href={`mailto:${lead.contact_email}`}
                      className="text-sm text-blue-600 hover:text-blue-800 underline"
                    >
                      {lead.contact_email}
                    </a>
                  </div>
                )}

                {lead.contact_phone && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Phone
                    </label>
                    <a
                      href={`tel:${lead.contact_phone}`}
                      className="text-sm text-blue-600 hover:text-blue-800"
                    >
                      {lead.contact_phone}
                    </a>
                  </div>
                )}

                {lead.contact_title && (
                  <div>
                    <label className="block text-sm font-medium text-gray-500 mb-1">
                      Title
                    </label>
                    <p className="text-sm text-gray-900">{lead.contact_title}</p>
                  </div>
                )}
              </div>
            </div>

            {/* Notes */}
            {lead.notes && (
              <div>
                <h3 className="text-lg font-semibold text-gray-900 mb-4">
                  Notes
                </h3>
                <div className="bg-gray-50 rounded-lg p-4">
                  <p className="text-sm text-gray-700 whitespace-pre-wrap">
                    {lead.notes}
                  </p>
                </div>
              </div>
            )}

            {/* Metadata */}
            <div>
              <h3 className="text-lg font-semibold text-gray-900 mb-4">
                Metadata
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">
                    Lead ID
                  </label>
                  <p className="text-sm text-gray-900">#{lead.id}</p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">
                    Created
                  </label>
                  <p className="text-sm text-gray-900">
                    {formatDate(lead.created_at)}
                  </p>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-500 mb-1">
                    Updated
                  </label>
                  <p className="text-sm text-gray-900">
                    {formatDate(lead.updated_at)}
                  </p>
                </div>
              </div>
            </div>
          </div>

          {/* Footer */}
          <div className="sticky bottom-0 bg-gray-50 border-t border-gray-200 px-6 py-4 flex justify-end space-x-3">
            <button
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Close
            </button>
            <button
              disabled
              className="px-4 py-2 bg-blue-600 text-white rounded-lg opacity-50 cursor-not-allowed"
              title="Edit functionality coming soon"
            >
              Edit (Coming Soon)
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
