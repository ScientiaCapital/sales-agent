import React, { useState, useEffect } from 'react';
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend,
  ChartOptions,
} from 'chart.js';
import { Bar, Doughnut } from 'react-chartjs-2';

// Register Chart.js components
ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  ArcElement,
  Title,
  Tooltip,
  Legend
);

// Types
interface ABTestAnalysis {
  test_id: string;
  test_name: string;
  variant_a_name: string;
  variant_a_conversions: number;
  variant_a_participants: number;
  variant_a_conversion_rate: number;
  variant_a_confidence_interval: [number, number];
  variant_b_name: string;
  variant_b_conversions: number;
  variant_b_participants: number;
  variant_b_conversion_rate: number;
  variant_b_confidence_interval: [number, number];
  p_value: number;
  chi_square_statistic: number;
  is_significant: boolean;
  confidence_level: number;
  winner?: 'A' | 'B' | null;
  lift_percentage: number;
  minimum_sample_size: number;
  sample_adequacy: number;
  can_stop_early: boolean;
  recommendations: string[];
  days_remaining_estimate?: number;
}

interface ABTestAnalysisDashboardProps {
  testId: string;
}

/**
 * A/B Test Analysis Dashboard
 *
 * Comprehensive statistical analysis dashboard with Chart.js visualizations.
 * Displays conversion rates, confidence intervals, statistical significance,
 * and actionable recommendations.
 */
export const ABTestAnalysisDashboard: React.FC<ABTestAnalysisDashboardProps> = ({ testId }) => {
  const [analysis, setAnalysis] = useState<ABTestAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetchAnalysis();
  }, [testId]);

  const fetchAnalysis = async () => {
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`/api/v1/ab-tests/${testId}/analysis`);

      if (!response.ok) {
        throw new Error('Failed to fetch analysis');
      }

      const data: ABTestAnalysis = await response.json();
      setAnalysis(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
      console.error('Error fetching analysis:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex justify-center items-center h-64">
        <div className="text-gray-500">Loading analysis...</div>
      </div>
    );
  }

  if (error || !analysis) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
        {error || 'Failed to load analysis'}
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Summary Cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <SummaryCard
          title="Statistical Significance"
          value={analysis.is_significant ? 'SIGNIFICANT' : 'NOT SIGNIFICANT'}
          subtitle={`p-value: ${analysis.p_value.toFixed(4)}`}
          color={analysis.is_significant ? 'green' : 'red'}
        />

        <SummaryCard
          title="Winner"
          value={analysis.winner ? `Variant ${analysis.winner}` : 'No Winner'}
          subtitle={analysis.lift_percentage ? `Lift: ${analysis.lift_percentage.toFixed(2)}%` : ''}
          color={analysis.winner ? 'blue' : 'gray'}
        />

        <SummaryCard
          title="Sample Adequacy"
          value={`${analysis.sample_adequacy.toFixed(1)}%`}
          subtitle={`Min required: ${analysis.minimum_sample_size}`}
          color={analysis.sample_adequacy >= 100 ? 'green' : 'yellow'}
        />
      </div>

      {/* Conversion Rate Comparison Chart */}
      <div className="bg-white p-6 rounded-lg shadow">
        <h3 className="text-lg font-semibold mb-4">Conversion Rate Comparison</h3>
        <ConversionRateChart analysis={analysis} />
      </div>

      {/* Two-Column Layout */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Sample Size Progress */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Sample Size Progress</h3>
          <SampleSizeChart analysis={analysis} />
        </div>

        {/* Statistical Details */}
        <div className="bg-white p-6 rounded-lg shadow">
          <h3 className="text-lg font-semibold mb-4">Statistical Details</h3>
          <StatisticalDetails analysis={analysis} />
        </div>
      </div>

      {/* Recommendations */}
      {analysis.recommendations.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 p-6 rounded-lg">
          <h3 className="text-lg font-semibold mb-3 flex items-center">
            <span className="mr-2">💡</span>
            Recommendations
          </h3>
          <ul className="space-y-2">
            {analysis.recommendations.map((rec, index) => (
              <li key={index} className="flex items-start">
                <span className="text-blue-600 mr-2">•</span>
                <span className="text-gray-700">{rec}</span>
              </li>
            ))}
          </ul>

          {analysis.can_stop_early && (
            <div className="mt-4 p-3 bg-green-100 rounded border border-green-300">
              <p className="text-green-800 font-semibold">
                ✓ Early Stopping Recommended
              </p>
              <p className="text-green-700 text-sm mt-1">
                Statistical significance achieved with adequate sample size.
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

/**
 * Summary Card Component
 */
const SummaryCard: React.FC<{
  title: string;
  value: string;
  subtitle: string;
  color: 'green' | 'blue' | 'red' | 'yellow' | 'gray';
}> = ({ title, value, subtitle, color }) => {
  const colorClasses = {
    green: 'bg-green-50 border-green-200 text-green-800',
    blue: 'bg-blue-50 border-blue-200 text-blue-800',
    red: 'bg-red-50 border-red-200 text-red-800',
    yellow: 'bg-yellow-50 border-yellow-200 text-yellow-800',
    gray: 'bg-gray-50 border-gray-200 text-gray-800',
  };

  return (
    <div className={`border rounded-lg p-4 ${colorClasses[color]}`}>
      <h4 className="text-sm font-medium opacity-75 mb-1">{title}</h4>
      <p className="text-2xl font-bold">{value}</p>
      <p className="text-sm mt-1 opacity-75">{subtitle}</p>
    </div>
  );
};

/**
 * Conversion Rate Bar Chart with Confidence Intervals
 */
const ConversionRateChart: React.FC<{ analysis: ABTestAnalysis }> = ({ analysis }) => {
  const data = {
    labels: [analysis.variant_a_name, analysis.variant_b_name],
    datasets: [
      {
        label: 'Conversion Rate (%)',
        data: [
          analysis.variant_a_conversion_rate * 100,
          analysis.variant_b_conversion_rate * 100,
        ],
        backgroundColor: [
          analysis.winner === 'A' ? 'rgba(34, 197, 94, 0.8)' : 'rgba(156, 163, 175, 0.8)',
          analysis.winner === 'B' ? 'rgba(34, 197, 94, 0.8)' : 'rgba(156, 163, 175, 0.8)',
        ],
        borderColor: [
          analysis.winner === 'A' ? 'rgba(34, 197, 94, 1)' : 'rgba(156, 163, 175, 1)',
          analysis.winner === 'B' ? 'rgba(34, 197, 94, 1)' : 'rgba(156, 163, 175, 1)',
        ],
        borderWidth: 2,
      },
    ],
  };

  const options: ChartOptions<'bar'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        display: false,
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            const value = context.parsed.y;
            const variantIndex = context.dataIndex;
            const ci = variantIndex === 0
              ? analysis.variant_a_confidence_interval
              : analysis.variant_b_confidence_interval;
            return [
              `Conversion Rate: ${value.toFixed(2)}%`,
              `95% CI: [${(ci[0] * 100).toFixed(2)}%, ${(ci[1] * 100).toFixed(2)}%]`,
            ];
          },
        },
      },
    },
    scales: {
      y: {
        beginAtZero: true,
        title: {
          display: true,
          text: 'Conversion Rate (%)',
        },
        ticks: {
          callback: function (value) {
            return value + '%';
          },
        },
      },
    },
  };

  return (
    <div style={{ height: '300px' }}>
      <Bar data={data} options={options} />
      <div className="mt-4 text-sm text-gray-600 text-center">
        <p>Green bars indicate the winner. Error bars show 95% confidence intervals.</p>
      </div>
    </div>
  );
};

/**
 * Sample Size Progress Doughnut Chart
 */
const SampleSizeChart: React.FC<{ analysis: ABTestAnalysis }> = ({ analysis }) => {
  const currentTotal = analysis.variant_a_participants + analysis.variant_b_participants;
  const requiredTotal = analysis.minimum_sample_size;
  const percentage = Math.min((currentTotal / requiredTotal) * 100, 100);
  const remaining = Math.max(requiredTotal - currentTotal, 0);

  const data = {
    labels: ['Current Participants', 'Remaining'],
    datasets: [
      {
        data: [currentTotal, remaining],
        backgroundColor: [
          percentage >= 100 ? 'rgba(34, 197, 94, 0.8)' : percentage >= 80 ? 'rgba(251, 191, 36, 0.8)' : 'rgba(239, 68, 68, 0.8)',
          'rgba(229, 231, 235, 0.5)',
        ],
        borderColor: [
          percentage >= 100 ? 'rgba(34, 197, 94, 1)' : percentage >= 80 ? 'rgba(251, 191, 36, 1)' : 'rgba(239, 68, 68, 1)',
          'rgba(229, 231, 235, 1)',
        ],
        borderWidth: 2,
      },
    ],
  };

  const options: ChartOptions<'doughnut'> = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: {
        position: 'bottom',
      },
      tooltip: {
        callbacks: {
          label: function (context) {
            const label = context.label || '';
            const value = context.parsed;
            return `${label}: ${value}`;
          },
        },
      },
    },
  };

  return (
    <div>
      <div style={{ height: '250px' }}>
        <Doughnut data={data} options={options} />
      </div>
      <div className="mt-4 text-center">
        <p className="text-2xl font-bold">{percentage.toFixed(1)}%</p>
        <p className="text-sm text-gray-600">Sample Adequacy</p>
        <p className="text-xs text-gray-500 mt-1">
          {currentTotal} / {requiredTotal} participants
        </p>
        {analysis.days_remaining_estimate && (
          <p className="text-xs text-gray-500 mt-1">
            Est. {analysis.days_remaining_estimate} days remaining
          </p>
        )}
      </div>
    </div>
  );
};

/**
 * Statistical Details Panel
 */
const StatisticalDetails: React.FC<{ analysis: ABTestAnalysis }> = ({ analysis }) => {
  return (
    <div className="space-y-4">
      <DetailRow
        label="P-value"
        value={analysis.p_value.toFixed(6)}
        color={analysis.p_value < 0.05 ? 'green' : 'red'}
      />

      <DetailRow
        label="Chi-Square Statistic"
        value={analysis.chi_square_statistic.toFixed(4)}
        color="gray"
      />

      <DetailRow
        label="Confidence Level"
        value={`${(analysis.confidence_level * 100).toFixed(1)}%`}
        color="blue"
      />

      <div className="border-t pt-4">
        <h4 className="font-semibold mb-2">Variant A ({analysis.variant_a_name})</h4>
        <DetailRow
          label="Participants"
          value={analysis.variant_a_participants.toString()}
          color="gray"
        />
        <DetailRow
          label="Conversions"
          value={analysis.variant_a_conversions.toString()}
          color="gray"
        />
        <DetailRow
          label="Conversion Rate"
          value={`${(analysis.variant_a_conversion_rate * 100).toFixed(2)}%`}
          color="gray"
        />
        <DetailRow
          label="95% Confidence Interval"
          value={`[${(analysis.variant_a_confidence_interval[0] * 100).toFixed(2)}%, ${(analysis.variant_a_confidence_interval[1] * 100).toFixed(2)}%]`}
          color="gray"
        />
      </div>

      <div className="border-t pt-4">
        <h4 className="font-semibold mb-2">Variant B ({analysis.variant_b_name})</h4>
        <DetailRow
          label="Participants"
          value={analysis.variant_b_participants.toString()}
          color="gray"
        />
        <DetailRow
          label="Conversions"
          value={analysis.variant_b_conversions.toString()}
          color="gray"
        />
        <DetailRow
          label="Conversion Rate"
          value={`${(analysis.variant_b_conversion_rate * 100).toFixed(2)}%`}
          color="gray"
        />
        <DetailRow
          label="95% Confidence Interval"
          value={`[${(analysis.variant_b_confidence_interval[0] * 100).toFixed(2)}%, ${(analysis.variant_b_confidence_interval[1] * 100).toFixed(2)}%]`}
          color="gray"
        />
      </div>

      {analysis.lift_percentage !== 0 && (
        <div className="border-t pt-4">
          <DetailRow
            label="Lift"
            value={`${analysis.lift_percentage > 0 ? '+' : ''}${analysis.lift_percentage.toFixed(2)}%`}
            color={analysis.lift_percentage > 0 ? 'green' : 'red'}
          />
        </div>
      )}
    </div>
  );
};

/**
 * Detail Row Component
 */
const DetailRow: React.FC<{
  label: string;
  value: string;
  color: 'green' | 'blue' | 'red' | 'gray';
}> = ({ label, value, color }) => {
  const colorClasses = {
    green: 'text-green-700',
    blue: 'text-blue-700',
    red: 'text-red-700',
    gray: 'text-gray-900',
  };

  return (
    <div className="flex justify-between items-center py-1">
      <span className="text-sm text-gray-600">{label}:</span>
      <span className={`text-sm font-semibold ${colorClasses[color]}`}>{value}</span>
    </div>
  );
};

export default ABTestAnalysisDashboard;
