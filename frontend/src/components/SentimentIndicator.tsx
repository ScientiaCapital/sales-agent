/**
 * Sentiment Indicator Component
 *
 * Visual representation of sentiment with color coding, trend arrows,
 * and optional sparkline visualization for historical sentiment
 */

import { useMemo } from 'react';

interface SentimentIndicatorProps {
  score?: number;
  history?: number[];
  showTrend?: boolean;
  showSparkline?: boolean;
  compact?: boolean;
  className?: string;
}

export function SentimentIndicator({
  score,
  history = [],
  showTrend = true,
  showSparkline = false,
  compact = false,
  className = ''
}: SentimentIndicatorProps) {
  // Calculate sentiment label and color
  const { label, colorClass, bgClass, trend } = useMemo(() => {
    if (score === undefined) {
      return {
        label: 'Unknown',
        colorClass: 'text-gray-500',
        bgClass: 'bg-gray-100',
        trend: 'stable' as const
      };
    }

    // Calculate trend if history is available
    let trend: 'improving' | 'declining' | 'stable' = 'stable';
    if (history.length >= 2) {
      const recent = history.slice(-5);
      const avgRecent = recent.reduce((a, b) => a + b, 0) / recent.length;
      const older = history.slice(-10, -5);
      const avgOlder = older.length > 0 ? older.reduce((a, b) => a + b, 0) / older.length : avgRecent;

      if (avgRecent > avgOlder + 0.1) trend = 'improving';
      else if (avgRecent < avgOlder - 0.1) trend = 'declining';
    }

    if (score > 0.3) {
      return {
        label: 'Positive',
        colorClass: 'text-green-700',
        bgClass: 'bg-green-100',
        trend
      };
    } else if (score < -0.3) {
      return {
        label: 'Negative',
        colorClass: 'text-red-700',
        bgClass: 'bg-red-100',
        trend
      };
    } else {
      return {
        label: 'Neutral',
        colorClass: 'text-yellow-700',
        bgClass: 'bg-yellow-100',
        trend
      };
    }
  }, [score, history]);

  // Format score for display
  const formattedScore = score !== undefined ? (score * 100).toFixed(0) : '--';

  // Generate sparkline SVG path
  const sparklinePath = useMemo(() => {
    if (!showSparkline || history.length < 2) return '';

    const width = 60;
    const height = 20;
    const points = history.slice(-20); // Show last 20 points
    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = max - min || 1;

    return points.map((value, index) => {
      const x = (index / (points.length - 1)) * width;
      const y = height - ((value - min) / range) * height;
      return `${index === 0 ? 'M' : 'L'} ${x} ${y}`;
    }).join(' ');
  }, [history, showSparkline]);

  if (compact) {
    return (
      <div className={`inline-flex items-center gap-1 ${className}`}>
        <span className={`inline-block w-2 h-2 rounded-full ${
          score === undefined ? 'bg-gray-400' :
          score > 0.3 ? 'bg-green-500' :
          score < -0.3 ? 'bg-red-500' : 'bg-yellow-500'
        }`} />
        <span className={`text-xs font-medium ${colorClass}`}>
          {formattedScore}%
        </span>
        {showTrend && trend !== 'stable' && (
          <span className="text-xs">
            {trend === 'improving' ? '↑' : '↓'}
          </span>
        )}
      </div>
    );
  }

  return (
    <div className={`inline-flex items-center gap-2 ${className}`}>
      {/* Sentiment Badge */}
      <div className={`inline-flex items-center px-2.5 py-1 rounded-full ${bgClass}`}>
        <span className={`text-sm font-medium ${colorClass}`}>
          {label}
        </span>
      </div>

      {/* Score Display */}
      <div className="flex items-center gap-1">
        <span className={`text-lg font-semibold ${colorClass}`}>
          {formattedScore}%
        </span>

        {/* Trend Arrow */}
        {showTrend && trend !== 'stable' && (
          <span className={`text-sm ${trend === 'improving' ? 'text-green-600' : 'text-red-600'}`}>
            {trend === 'improving' ? (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M5.293 9.707a1 1 0 010-1.414l4-4a1 1 0 011.414 0l4 4a1 1 0 01-1.414 1.414L11 7.414V15a1 1 0 11-2 0V7.414L6.707 9.707a1 1 0 01-1.414 0z" clipRule="evenodd" />
              </svg>
            ) : (
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M14.707 10.293a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0l-4-4a1 1 0 111.414-1.414L9 12.586V5a1 1 0 012 0v7.586l2.293-2.293a1 1 0 011.414 0z" clipRule="evenodd" />
              </svg>
            )}
          </span>
        )}
      </div>

      {/* Sparkline */}
      {showSparkline && history.length >= 2 && (
        <div className="ml-2">
          <svg width="60" height="20" className="text-gray-400">
            <path
              d={sparklinePath}
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              className={colorClass}
            />
          </svg>
        </div>
      )}
    </div>
  );
}

export default SentimentIndicator;