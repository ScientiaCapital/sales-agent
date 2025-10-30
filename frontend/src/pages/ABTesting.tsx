import React, { useState, useEffect } from 'react';

// Types
interface ABTest {
  id: number;
  test_id: string;
  test_name: string;
  test_description?: string;
  variant_a_name: string;
  variant_b_name: string;
  test_type: 'campaign' | 'agent_performance' | 'ui_element';
  status: 'draft' | 'running' | 'completed' | 'paused';
  participants_a: number;
  participants_b: number;
  conversions_a: number;
  conversions_b: number;
  conversion_rate_a?: number;
  conversion_rate_b?: number;
  statistical_significance?: number;
  confidence_level?: number;
  winner?: 'A' | 'B' | null;
  start_date?: string;
  end_date?: string;
  created_at: string;
}

interface ABTestCreate {
  test_name: string;
  test_description?: string;
  variant_a_name: string;
  variant_b_name: string;
  test_type: 'campaign' | 'agent_performance' | 'ui_element';
  campaign_id?: number;
  segment_filters?: Record<string, unknown>;
}

/**
 * A/B Testing Management Page
 *
 * Displays all A/B tests with filtering, statistics, and management actions.
 * Integrates with backend API at /api/v1/ab-tests
 */
export const ABTesting: React.FC = () => {
  const [tests, setTests] = useState<ABTest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState<string>('');
  const [testTypeFilter, setTestTypeFilter] = useState<string>('');
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedTest, setSelectedTest] = useState<ABTest | null>(null);

  // Fetch tests on mount and filter change
  useEffect(() => {
    fetchTests();
  }, [statusFilter, testTypeFilter]);

  const fetchTests = async () => {
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      if (statusFilter) params.append('status', statusFilter);
      if (testTypeFilter) params.append('test_type', testTypeFilter);

      const response = await fetch(`/api/v1/ab-tests?${params.toString()}`);

      if (!response.ok) {
        throw new Error(`Failed to fetch tests: ${response.statusText}`);
      }

      const data = await response.json();
      setTests(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load tests');
      console.error('Error fetching A/B tests:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateTest = async (testData: ABTestCreate) => {
    try {
      const response = await fetch('/api/v1/ab-tests', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(testData),
      });

      if (!response.ok) {
        throw new Error('Failed to create test');
      }

      setIsCreateModalOpen(false);
      fetchTests(); // Refresh list
    } catch (err) {
      console.error('Error creating test:', err);
      alert('Failed to create test');
    }
  };

  const handleStartTest = async (testId: string) => {
    try {
      const response = await fetch(`/api/v1/ab-tests/${testId}/start`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to start test');
      }

      fetchTests(); // Refresh list
    } catch (err) {
      console.error('Error starting test:', err);
      alert('Failed to start test');
    }
  };

  const handleStopTest = async (testId: string) => {
    try {
      const response = await fetch(`/api/v1/ab-tests/${testId}/stop`, {
        method: 'POST',
      });

      if (!response.ok) {
        throw new Error('Failed to stop test');
      }

      fetchTests(); // Refresh list
    } catch (err) {
      console.error('Error stopping test:', err);
      alert('Failed to stop test');
    }
  };

  const getStatusBadge = (status: string) => {
    const colors = {
      draft: 'bg-gray-100 text-gray-800',
      running: 'bg-blue-100 text-blue-800',
      completed: 'bg-green-100 text-green-800',
      paused: 'bg-yellow-100 text-yellow-800',
    };

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${colors[status] || 'bg-gray-100 text-gray-800'}`}>
        {status.toUpperCase()}
      </span>
    );
  };

  const getWinnerBadge = (winner: 'A' | 'B' | null | undefined, significance?: number) => {
    if (!winner) return <span className="text-gray-500 text-sm">No winner</span>;

    const isSignificant = significance && significance < 0.05;
    const color = isSignificant ? 'bg-green-100 text-green-800' : 'bg-yellow-100 text-yellow-800';

    return (
      <span className={`px-2 py-1 rounded-full text-xs font-semibold ${color}`}>
        Variant {winner} {isSignificant && '✓'}
      </span>
    );
  };

  if (loading && tests.length === 0) {
    return (
      <div className="max-w-7xl mx-auto p-6">
        <div className="flex justify-center items-center h-64">
          <div className="text-gray-500">Loading A/B tests...</div>
        </div>
      </div>
    );
  }

  return (
    <div className="max-w-7xl mx-auto p-6">
      {/* Header */}
      <div className="flex justify-between items-center mb-6">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">A/B Testing</h1>
          <p className="text-gray-600 mt-1">Manage and analyze experiment results</p>
        </div>
        <button
          onClick={() => setIsCreateModalOpen(true)}
          className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition"
          data-testid="create-test-button"
        >
          + Create New Test
        </button>
      </div>

      {/* Filters */}
      <div className="mb-6 flex gap-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Status</label>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="draft">Draft</option>
            <option value="running">Running</option>
            <option value="completed">Completed</option>
            <option value="paused">Paused</option>
          </select>
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Test Type</label>
          <select
            value={testTypeFilter}
            onChange={(e) => setTestTypeFilter(e.target.value)}
            className="border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
          >
            <option value="">All Types</option>
            <option value="campaign">Campaign</option>
            <option value="agent_performance">Agent Performance</option>
            <option value="ui_element">UI Element</option>
          </select>
        </div>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">
          {error}
        </div>
      )}

      {/* Tests Table */}
      <div className="bg-white rounded-lg shadow overflow-hidden" data-testid="ab-test-table">
        <table className="min-w-full divide-y divide-gray-200">
          <thead className="bg-gray-50">
            <tr>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Test Name
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Variants
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Status
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Participants
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Conversion Rates
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Winner
              </th>
              <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="bg-white divide-y divide-gray-200">
            {tests.length === 0 ? (
              <tr>
                <td colSpan={7} className="px-6 py-8 text-center text-gray-500">
                  No A/B tests found. Create one to get started.
                </td>
              </tr>
            ) : (
              tests.map((test) => (
                <tr
                  key={test.test_id}
                  className="hover:bg-gray-50 cursor-pointer"
                  onClick={() => setSelectedTest(test)}
                  data-testid="ab-test-row"
                >
                  <td className="px-6 py-4">
                    <div className="text-sm font-medium text-gray-900">{test.test_name}</div>
                    <div className="text-sm text-gray-500">{test.test_type}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">A: {test.variant_a_name}</div>
                    <div className="text-sm text-gray-900">B: {test.variant_b_name}</div>
                  </td>
                  <td className="px-6 py-4">
                    {getStatusBadge(test.status)}
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">A: {test.participants_a}</div>
                    <div className="text-sm text-gray-900">B: {test.participants_b}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-900">
                      A: {test.conversion_rate_a ? `${(test.conversion_rate_a * 100).toFixed(2)}%` : 'N/A'}
                    </div>
                    <div className="text-sm text-gray-900">
                      B: {test.conversion_rate_b ? `${(test.conversion_rate_b * 100).toFixed(2)}%` : 'N/A'}
                    </div>
                  </td>
                  <td className="px-6 py-4">
                    {getWinnerBadge(test.winner, test.statistical_significance)}
                  </td>
                  <td className="px-6 py-4 text-sm">
                    {test.status === 'draft' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStartTest(test.test_id);
                        }}
                        className="text-blue-600 hover:text-blue-800 mr-2"
                      >
                        Start
                      </button>
                    )}
                    {test.status === 'running' && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleStopTest(test.test_id);
                        }}
                        className="text-red-600 hover:text-red-800 mr-2"
                      >
                        Stop
                      </button>
                    )}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        setSelectedTest(test);
                      }}
                      className="text-gray-600 hover:text-gray-800"
                    >
                      View
                    </button>
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      {/* Create Test Modal */}
      {isCreateModalOpen && (
        <CreateTestModal
          onClose={() => setIsCreateModalOpen(false)}
          onCreate={handleCreateTest}
        />
      )}

      {/* Test Detail Modal */}
      {selectedTest && (
        <TestDetailModal
          test={selectedTest}
          onClose={() => setSelectedTest(null)}
          onRefresh={fetchTests}
        />
      )}
    </div>
  );
};

/**
 * Modal for creating new A/B test
 */
const CreateTestModal: React.FC<{
  onClose: () => void;
  onCreate: (data: ABTestCreate) => void;
}> = ({ onClose, onCreate }) => {
  const [formData, setFormData] = useState<ABTestCreate>({
    test_name: '',
    test_description: '',
    variant_a_name: 'Variant A',
    variant_b_name: 'Variant B',
    test_type: 'campaign',
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onCreate(formData);
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-md w-full">
        <h2 className="text-2xl font-bold mb-4">Create New A/B Test</h2>

        <form onSubmit={handleSubmit}>
          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Test Name *
            </label>
            <input
              type="text"
              value={formData.test_name}
              onChange={(e) => setFormData({ ...formData, test_name: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              required
              data-testid="test-name-input"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Description
            </label>
            <textarea
              value={formData.test_description}
              onChange={(e) => setFormData({ ...formData, test_description: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              rows={3}
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Test Type *
            </label>
            <select
              value={formData.test_type}
              onChange={(e) => setFormData({ ...formData, test_type: e.target.value as any })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              required
            >
              <option value="campaign">Campaign</option>
              <option value="agent_performance">Agent Performance</option>
              <option value="ui_element">UI Element</option>
            </select>
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Variant A Name *
            </label>
            <input
              type="text"
              value={formData.variant_a_name}
              onChange={(e) => setFormData({ ...formData, variant_a_name: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              required
              data-testid="variant-a-input"
            />
          </div>

          <div className="mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Variant B Name *
            </label>
            <input
              type="text"
              value={formData.variant_b_name}
              onChange={(e) => setFormData({ ...formData, variant_b_name: e.target.value })}
              className="w-full border border-gray-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-blue-500"
              required
              data-testid="variant-b-input"
            />
          </div>

          <div className="flex gap-3 justify-end">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
              data-testid="submit-test"
            >
              Create Test
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

/**
 * Modal for viewing test details and analysis
 */
const TestDetailModal: React.FC<{
  test: ABTest;
  onClose: () => void;
  onRefresh: () => void;
}> = ({ test, onClose, onRefresh }) => {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 max-w-4xl w-full max-h-screen overflow-y-auto">
        <div className="flex justify-between items-start mb-4">
          <div>
            <h2 className="text-2xl font-bold">{test.test_name}</h2>
            <p className="text-gray-600">{test.test_description}</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-700"
          >
            ✕
          </button>
        </div>

        {/* Statistical Summary */}
        <div className="grid grid-cols-2 gap-4 mb-6">
          <div className="bg-gray-50 p-4 rounded-lg">
            <h3 className="font-semibold mb-2">{test.variant_a_name}</h3>
            <p>Participants: {test.participants_a}</p>
            <p>Conversions: {test.conversions_a}</p>
            <p className="font-bold">
              Rate: {test.conversion_rate_a ? `${(test.conversion_rate_a * 100).toFixed(2)}%` : 'N/A'}
            </p>
          </div>

          <div className="bg-gray-50 p-4 rounded-lg">
            <h3 className="font-semibold mb-2">{test.variant_b_name}</h3>
            <p>Participants: {test.participants_b}</p>
            <p>Conversions: {test.conversions_b}</p>
            <p className="font-bold">
              Rate: {test.conversion_rate_b ? `${(test.conversion_rate_b * 100).toFixed(2)}%` : 'N/A'}
            </p>
          </div>
        </div>

        {/* Statistical Significance */}
        {test.statistical_significance !== undefined && (
          <div className="bg-blue-50 p-4 rounded-lg mb-4">
            <h3 className="font-semibold mb-2">Statistical Analysis</h3>
            <p data-testid="p-value">
              P-value: {test.statistical_significance.toFixed(4)}
            </p>
            <p data-testid="confidence-level">
              Confidence: {test.confidence_level ? `${(test.confidence_level * 100).toFixed(1)}%` : 'N/A'}
            </p>
            {test.winner && (
              <p className="mt-2 font-bold text-green-700" data-testid="winner-badge">
                Winner: Variant {test.winner}
              </p>
            )}
          </div>
        )}

        <div className="flex gap-3 justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
};

export default ABTesting;
