import React from 'react';

export type TimeRange = '24h' | '7d' | '30d' | '90d';

interface TimeRangeSelectorProps {
  selectedRange: TimeRange;
  onRangeChange: (range: TimeRange) => void;
  className?: string;
}

const timeRangeOptions: { value: TimeRange; label: string }[] = [
  { value: '24h', label: 'Last 24 Hours' },
  { value: '7d', label: 'Last 7 Days' },
  { value: '30d', label: 'Last 30 Days' },
  { value: '90d', label: 'Last 90 Days' },
];

/**
 * TimeRangeSelector Component
 *
 * Allows users to select a time range for metrics filtering
 */
export const TimeRangeSelector: React.FC<TimeRangeSelectorProps> = ({
  selectedRange,
  onRangeChange,
  className = '',
}) => {
  return (
    <div className={`flex gap-2 ${className}`}>
      {timeRangeOptions.map((option) => (
        <button
          key={option.value}
          onClick={() => onRangeChange(option.value)}
          className={`
            px-4 py-2 rounded-lg text-sm font-medium transition-colors
            ${
              selectedRange === option.value
                ? 'bg-blue-600 text-white shadow-md'
                : 'bg-white text-gray-700 hover:bg-gray-100 border border-gray-300'
            }
          `}
          aria-pressed={selectedRange === option.value}
          aria-label={`Select ${option.label}`}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
};
