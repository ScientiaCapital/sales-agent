import React from 'react';

interface BudgetProgressBarProps {
  utilization: number;
  status: 'OK' | 'WARNING' | 'CRITICAL' | 'BLOCKED';
  budget: number;
  spent: number;
  label: string;
}

const getStatusColor = (status: string): string => {
  switch (status) {
    case 'OK':
      return 'bg-green-500';
    case 'WARNING':
      return 'bg-yellow-500';
    case 'CRITICAL':
      return 'bg-orange-500';
    case 'BLOCKED':
      return 'bg-red-500';
    default:
      return 'bg-gray-500';
  }
};

const getStatusMessage = (status: string): string | null => {
  switch (status) {
    case 'WARNING':
      return 'Budget threshold reached. Monitor spending closely.';
    case 'CRITICAL':
      return 'Budget nearly exceeded! Consider cost optimization.';
    case 'BLOCKED':
      return 'Budget exceeded! API requests may be blocked.';
    default:
      return null;
  }
};

export const BudgetProgressBar: React.FC<BudgetProgressBarProps> = ({
  utilization,
  status,
  budget,
  spent,
  label,
}) => {
  const statusColor = getStatusColor(status);
  const statusMessage = getStatusMessage(status);
  const clampedUtilization = Math.min(utilization, 100);

  return (
    <div className="budget-bar p-4 bg-white rounded-lg shadow">
      <div className="flex justify-between items-center mb-2">
        <span className="text-sm font-medium text-gray-700">{label}</span>
        <span className="text-sm font-semibold text-gray-900">
          ${spent.toFixed(2)} / ${budget.toFixed(2)}
        </span>
      </div>

      <div className="relative">
        <div className="w-full bg-gray-200 rounded-full h-6 overflow-hidden">
          <div
            className={`h-6 rounded-full transition-all duration-300 ${statusColor} flex items-center justify-end pr-2`}
            style={{ width: `${clampedUtilization}%` }}
          >
            <span className="text-xs font-semibold text-white">
              {utilization.toFixed(1)}%
            </span>
          </div>
        </div>

        {/* Threshold markers */}
        <div className="absolute top-0 left-[80%] h-6 w-0.5 bg-gray-400 opacity-50" />
        <div className="absolute top-0 left-[95%] h-6 w-0.5 bg-gray-500 opacity-50" />
      </div>

      {/* Threshold labels */}
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>0%</span>
        <span className="absolute left-[80%] transform -translate-x-1/2">80%</span>
        <span className="absolute left-[95%] transform -translate-x-1/2">95%</span>
        <span>100%</span>
      </div>

      {/* Status message */}
      {statusMessage && (
        <div className="mt-3 flex items-start">
          <svg
            className="w-5 h-5 text-red-600 flex-shrink-0 mr-2"
            fill="currentColor"
            viewBox="0 0 20 20"
          >
            <path
              fillRule="evenodd"
              d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z"
              clipRule="evenodd"
            />
          </svg>
          <p className="text-sm text-red-600">{statusMessage}</p>
        </div>
      )}
    </div>
  );
};
