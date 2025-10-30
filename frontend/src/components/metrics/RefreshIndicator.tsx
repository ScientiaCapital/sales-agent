import React, { useEffect, useState } from 'react';

interface RefreshIndicatorProps {
  isRefreshing: boolean;
  lastRefresh: Date | null;
  onManualRefresh: () => void;
  autoRefreshInterval?: number; // in seconds
  className?: string;
}

/**
 * RefreshIndicator Component
 *
 * Shows auto-refresh status with countdown and manual refresh button
 */
export const RefreshIndicator: React.FC<RefreshIndicatorProps> = ({
  isRefreshing,
  lastRefresh,
  onManualRefresh,
  autoRefreshInterval = 30,
  className = '',
}) => {
  const [secondsUntilRefresh, setSecondsUntilRefresh] = useState(autoRefreshInterval);

  useEffect(() => {
    if (isRefreshing) {
      setSecondsUntilRefresh(autoRefreshInterval);
      return;
    }

    const interval = setInterval(() => {
      setSecondsUntilRefresh((prev) => {
        if (prev <= 1) {
          return autoRefreshInterval;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(interval);
  }, [isRefreshing, autoRefreshInterval]);

  const formatLastRefresh = (date: Date | null): string => {
    if (!date) return 'Never';

    const now = new Date();
    const diffSeconds = Math.floor((now.getTime() - date.getTime()) / 1000);

    if (diffSeconds < 60) return `${diffSeconds}s ago`;
    if (diffSeconds < 3600) return `${Math.floor(diffSeconds / 60)}m ago`;
    return `${Math.floor(diffSeconds / 3600)}h ago`;
  };

  return (
    <div className={`flex items-center gap-4 ${className}`}>
      {/* Auto-refresh status */}
      <div className="flex items-center gap-2 text-sm text-gray-600">
        <div
          className={`
            w-2 h-2 rounded-full
            ${isRefreshing ? 'bg-blue-500 animate-pulse' : 'bg-green-500'}
          `}
          aria-label={isRefreshing ? 'Refreshing' : 'Ready'}
        />
        <span>
          {isRefreshing
            ? 'Refreshing...'
            : `Next refresh in ${secondsUntilRefresh}s`}
        </span>
      </div>

      {/* Last refresh time */}
      <div className="text-sm text-gray-500">
        Last updated: {formatLastRefresh(lastRefresh)}
      </div>

      {/* Manual refresh button */}
      <button
        onClick={onManualRefresh}
        disabled={isRefreshing}
        className={`
          px-3 py-1 rounded-md text-sm font-medium transition-colors
          ${
            isRefreshing
              ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
              : 'bg-blue-50 text-blue-600 hover:bg-blue-100'
          }
        `}
        aria-label="Refresh now"
      >
        <svg
          className={`w-4 h-4 ${isRefreshing ? 'animate-spin' : ''}`}
          fill="none"
          stroke="currentColor"
          viewBox="0 0 24 24"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"
          />
        </svg>
      </button>
    </div>
  );
};
