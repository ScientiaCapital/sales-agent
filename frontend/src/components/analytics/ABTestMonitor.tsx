import React, { useState, useEffect, useRef } from 'react';

// Types
interface ABTestAnalysis {
  test_id: string;
  test_name: string;
  variant_a_name: string;
  variant_a_conversions: number;
  variant_a_participants: number;
  variant_a_conversion_rate: number;
  variant_b_name: string;
  variant_b_conversions: number;
  variant_b_participants: number;
  variant_b_conversion_rate: number;
  p_value: number;
  is_significant: boolean;
  winner?: 'A' | 'B' | null;
  lift_percentage: number;
  sample_adequacy: number;
  can_stop_early: boolean;
  recommendations: string[];
}

interface ABTestMonitorProps {
  testId: string;
  refreshInterval?: number; // milliseconds, default 30000 (30 seconds)
  onSignificanceAchieved?: (analysis: ABTestAnalysis) => void;
}

/**
 * Real-Time A/B Test Monitor
 *
 * Live monitoring component with automatic updates every 30 seconds.
 * Features:
 * - Auto-refresh with configurable interval
 * - Participant count ticker animation
 * - Conversion rate trend visualization
 * - Alert when statistical significance achieved
 * - Progressive disclosure of recommendations
 */
export const ABTestMonitor: React.FC<ABTestMonitorProps> = ({
  testId,
  refreshInterval = 30000,
  onSignificanceAchieved,
}) => {
  const [analysis, setAnalysis] = useState<ABTestAnalysis | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());
  const [countdown, setCountdown] = useState(refreshInterval / 1000);
  const [history, setHistory] = useState<ABTestAnalysis[]>([]);
  const [alertShown, setAlertShown] = useState(false);

  const intervalRef = useRef<NodeJS.Timeout | null>(null);
  const countdownRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    // Initial fetch
    fetchAnalysis();

    // Set up auto-refresh
    intervalRef.current = setInterval(() => {
      fetchAnalysis();
      setCountdown(refreshInterval / 1000);
    }, refreshInterval);

    // Set up countdown timer
    countdownRef.current = setInterval(() => {
      setCountdown((prev) => Math.max(prev - 1, 0));
    }, 1000);

    // Cleanup on unmount
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
      if (countdownRef.current) clearInterval(countdownRef.current);
    };
  }, [testId, refreshInterval]);

  const fetchAnalysis = async () => {
    try {
      const response = await fetch(`/api/v1/ab-tests/${testId}/analysis`);

      if (!response.ok) {
        throw new Error('Failed to fetch analysis');
      }

      const data: ABTestAnalysis = await response.json();
      setAnalysis(data);
      setLastUpdate(new Date());
      setLoading(false);
      setError(null);

      // Add to history (keep last 10 updates)
      setHistory((prev) => {
        const newHistory = [...prev, data];
        return newHistory.slice(-10);
      });

      // Check for significance alert
      if (
        data.is_significant &&
        data.sample_adequacy >= 80 &&
        !alertShown &&
        onSignificanceAchieved
      ) {
        setAlertShown(true);
        onSignificanceAchieved(data);
        showNotification('Test reached statistical significance!', 'success');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to load analysis');
      setLoading(false);
      console.error('Error fetching analysis:', err);
    }
  };

  const showNotification = (message: string, type: 'success' | 'warning' | 'info') => {
    // Simple notification (in production, use a toast library like react-hot-toast)
    const notification = document.createElement('div');
    notification.textContent = message;
    notification.style.cssText = `
      position: fixed;
      top: 20px;
      right: 20px;
      padding: 16px 24px;
      background: ${type === 'success' ? '#10b981' : type === 'warning' ? '#f59e0b' : '#3b82f6'};
      color: white;
      border-radius: 8px;
      box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
      z-index: 9999;
      font-weight: 500;
    `;
    document.body.appendChild(notification);

    setTimeout(() => {
      notification.remove();
    }, 5000);
  };

  const formatTimestamp = (date: Date): string => {
    return date.toLocaleTimeString('en-US', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  };

  const getParticipantChange = (): { a: number; b: number } | null => {
    if (history.length < 2) return null;

    const current = history[history.length - 1];
    const previous = history[history.length - 2];

    return {
      a: current.variant_a_participants - previous.variant_a_participants,
      b: current.variant_b_participants - previous.variant_b_participants,
    };
  };

  if (loading && !analysis) {
    return (
      <div className="flex justify-center items-center h-32">
        <div className="animate-pulse text-gray-500">Initializing monitor...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
        <p className="font-semibold">Monitor Error</p>
        <p className="text-sm">{error}</p>
      </div>
    );
  }

  if (!analysis) {
    return null;
  }

  const participantChange = getParticipantChange();

  return (
    <div className="space-y-4">
      {/* Status Bar */}
      <div className="bg-gradient-to-r from-blue-500 to-blue-600 text-white p-4 rounded-lg shadow">
        <div className="flex justify-between items-center">
          <div>
            <h3 className="font-semibold text-lg">Live Monitoring: {analysis.test_name}</h3>
            <p className="text-sm opacity-90">Last updated: {formatTimestamp(lastUpdate)}</p>
          </div>
          <div className="text-right">
            <div className="flex items-center gap-2">
              <div className="w-3 h-3 bg-green-400 rounded-full animate-pulse"></div>
              <span className="text-sm font-medium">Live</span>
            </div>
            <p className="text-xs opacity-75">Next update in {countdown}s</p>
          </div>
        </div>
      </div>

      {/* Live Metrics Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* Variant A Metrics */}
        <div className="bg-white p-6 rounded-lg shadow border-l-4 border-blue-500">
          <h4 className="text-lg font-semibold mb-3">{analysis.variant_a_name}</h4>

          <div className="space-y-3">
            <MetricRow
              label="Participants"
              value={analysis.variant_a_participants}
              change={participantChange?.a}
              isWinner={analysis.winner === 'A'}
            />

            <MetricRow
              label="Conversions"
              value={analysis.variant_a_conversions}
              isWinner={analysis.winner === 'A'}
            />

            <div className="pt-3 border-t">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Conversion Rate</span>
                <span className={`text-2xl font-bold ${analysis.winner === 'A' ? 'text-green-600' : 'text-gray-900'}`}>
                  {(analysis.variant_a_conversion_rate * 100).toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Sparkline (if history exists) */}
            {history.length > 2 && (
              <div className="pt-3">
                <p className="text-xs text-gray-500 mb-1">Rate Trend</p>
                <Sparkline
                  data={history.map((h) => h.variant_a_conversion_rate * 100)}
                  color="blue"
                />
              </div>
            )}
          </div>
        </div>

        {/* Variant B Metrics */}
        <div className="bg-white p-6 rounded-lg shadow border-l-4 border-purple-500">
          <h4 className="text-lg font-semibold mb-3">{analysis.variant_b_name}</h4>

          <div className="space-y-3">
            <MetricRow
              label="Participants"
              value={analysis.variant_b_participants}
              change={participantChange?.b}
              isWinner={analysis.winner === 'B'}
            />

            <MetricRow
              label="Conversions"
              value={analysis.variant_b_conversions}
              isWinner={analysis.winner === 'B'}
            />

            <div className="pt-3 border-t">
              <div className="flex justify-between items-center">
                <span className="text-sm text-gray-600">Conversion Rate</span>
                <span className={`text-2xl font-bold ${analysis.winner === 'B' ? 'text-green-600' : 'text-gray-900'}`}>
                  {(analysis.variant_b_conversion_rate * 100).toFixed(2)}%
                </span>
              </div>
            </div>

            {/* Sparkline (if history exists) */}
            {history.length > 2 && (
              <div className="pt-3">
                <p className="text-xs text-gray-500 mb-1">Rate Trend</p>
                <Sparkline
                  data={history.map((h) => h.variant_b_conversion_rate * 100)}
                  color="purple"
                />
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Statistical Status */}
      <div className={`p-4 rounded-lg border-2 ${
        analysis.is_significant
          ? 'bg-green-50 border-green-300'
          : 'bg-yellow-50 border-yellow-300'
      }`}>
        <div className="flex items-center justify-between">
          <div>
            <p className="font-semibold">
              {analysis.is_significant ? '✓ Statistically Significant' : '⏳ Building Significance'}
            </p>
            <p className="text-sm text-gray-600 mt-1">
              P-value: {analysis.p_value.toFixed(4)} | Sample Adequacy: {analysis.sample_adequacy.toFixed(1)}%
            </p>
          </div>
          {analysis.can_stop_early && (
            <div className="bg-green-600 text-white px-4 py-2 rounded-lg font-semibold">
              Ready to Stop
            </div>
          )}
        </div>
      </div>

      {/* Progressive Recommendations */}
      {analysis.recommendations.length > 0 && (
        <div className="bg-white p-4 rounded-lg shadow">
          <h4 className="font-semibold mb-2 flex items-center">
            <span className="mr-2">💡</span>
            Live Recommendations
          </h4>
          <ul className="space-y-1">
            {analysis.recommendations.slice(0, 3).map((rec, index) => (
              <li key={index} className="text-sm text-gray-700 flex items-start">
                <span className="text-blue-600 mr-2">•</span>
                {rec}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
};

/**
 * Metric Row Component with Change Indicator
 */
const MetricRow: React.FC<{
  label: string;
  value: number;
  change?: number;
  isWinner?: boolean;
}> = ({ label, value, change, isWinner }) => {
  return (
    <div className="flex justify-between items-center">
      <span className="text-sm text-gray-600">{label}</span>
      <div className="flex items-center gap-2">
        <span className={`text-lg font-semibold ${isWinner ? 'text-green-600' : 'text-gray-900'}`}>
          {value.toLocaleString()}
        </span>
        {change !== undefined && change > 0 && (
          <span className="text-xs text-green-600 font-medium">
            +{change}
          </span>
        )}
        {isWinner && (
          <span className="text-green-600 text-sm">★</span>
        )}
      </div>
    </div>
  );
};

/**
 * Simple Sparkline Chart
 */
const Sparkline: React.FC<{
  data: number[];
  color: 'blue' | 'purple';
}> = ({ data, color }) => {
  if (data.length < 2) return null;

  const width = 200;
  const height = 40;
  const padding = 4;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((value, index) => {
    const x = (index / (data.length - 1)) * (width - 2 * padding) + padding;
    const y = height - padding - ((value - min) / range) * (height - 2 * padding);
    return `${x},${y}`;
  }).join(' ');

  const colorMap = {
    blue: '#3b82f6',
    purple: '#a855f7',
  };

  return (
    <svg width={width} height={height} className="w-full">
      <polyline
        points={points}
        fill="none"
        stroke={colorMap[color]}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
};

export default ABTestMonitor;
