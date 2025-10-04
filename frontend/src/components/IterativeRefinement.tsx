/**
 * Iterative Refinement Component
 * 
 * Visualizes 4-step lead qualification refinement process
 * Shows quality score progression and reasoning at each iteration
 */

import { memo } from 'react';
import { useRefinement } from '../hooks/useRefinement';
import type { RefinementStep } from '../types';

interface IterativeRefinementProps {
  leadId: number;
  autoStart?: boolean;
  onComplete?: (finalScore: number, improvement: number) => void;
}

/**
 * Step indicator component
 */
const StepIndicator = memo(({ 
  step, 
  currentStep, 
  score 
}: { 
  step: number; 
  currentStep: number; 
  score?: number;
}) => {
  const isActive = step === currentStep;
  const isCompleted = step < currentStep;
  const isPending = step > currentStep;

  return (
    <div className="flex items-center">
      <div
        className={`
          flex items-center justify-center w-10 h-10 rounded-full
          ${isActive ? 'bg-blue-600 text-white ring-4 ring-blue-200' : ''}
          ${isCompleted ? 'bg-green-600 text-white' : ''}
          ${isPending ? 'bg-gray-200 text-gray-500' : ''}
        `}
      >
        {isCompleted ? '✓' : step}
      </div>
      {score !== undefined && (
        <div className="ml-3">
          <div className="text-sm font-medium text-gray-900">Step {step}</div>
          <div className="text-xs text-gray-500">Score: {score}</div>
        </div>
      )}
    </div>
  );
});

StepIndicator.displayName = 'StepIndicator';

/**
 * Refinement step card component
 */
const RefinementStepCard = memo(({ step }: { step: RefinementStep }) => {
  return (
    <div className="bg-white rounded-lg shadow p-6 border-l-4 border-blue-500">
      <div className="flex justify-between items-start mb-3">
        <h4 className="text-lg font-semibold text-gray-900">
          Step {step.step}
        </h4>
        <div className="text-right">
          <div className="text-2xl font-bold text-blue-600">{step.score}</div>
          <div className="text-xs text-gray-500">Quality Score</div>
        </div>
      </div>

      <div className="mb-4">
        <h5 className="text-sm font-medium text-gray-700 mb-2">Reasoning:</h5>
        <p className="text-sm text-gray-600 leading-relaxed">
          {step.reasoning}
        </p>
      </div>

      {step.improvements.length > 0 && (
        <div>
          <h5 className="text-sm font-medium text-gray-700 mb-2">
            Improvements:
          </h5>
          <ul className="space-y-1">
            {step.improvements.map((improvement, idx) => (
              <li
                key={idx}
                className="text-sm text-gray-600 flex items-start"
              >
                <span className="text-green-500 mr-2">+</span>
                {improvement}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
});

RefinementStepCard.displayName = 'RefinementStepCard';

/**
 * Main Iterative Refinement component
 */
export const IterativeRefinement = memo(({
  leadId,
  autoStart = false,
  onComplete,
}: IterativeRefinementProps) => {
  const {
    isRefining,
    currentStep,
    steps,
    originalScore,
    finalScore,
    improvement,
    error,
    startRefinement,
    reset,
  } = useRefinement({ leadId, autoStart });

  // Call onComplete callback when refinement finishes
  if (!isRefining && finalScore !== null && onComplete) {
    onComplete(finalScore, improvement);
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex justify-between items-center">
        <div>
          <h3 className="text-2xl font-bold text-gray-900">
            Iterative Refinement
          </h3>
          <p className="text-sm text-gray-600 mt-1">
            4-step quality score enhancement process
          </p>
        </div>

        {!isRefining && steps.length === 0 && (
          <button
            onClick={startRefinement}
            className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
          >
            Start Refinement
          </button>
        )}

        {!isRefining && steps.length > 0 && (
          <button
            onClick={reset}
            className="px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700 transition-colors"
          >
            Reset
          </button>
        )}
      </div>

      {/* Error display */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <div className="flex-shrink-0">
              <span className="text-red-600">✕</span>
            </div>
            <div className="ml-3">
              <h3 className="text-sm font-medium text-red-800">Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Progress indicator */}
      {(isRefining || steps.length > 0) && (
        <div className="bg-gray-50 rounded-lg p-6">
          <div className="flex justify-between items-center mb-6">
            {[1, 2, 3, 4].map((step, idx) => (
              <div key={step} className="flex items-center flex-1">
                <StepIndicator
                  step={step}
                  currentStep={currentStep}
                  score={steps[idx]?.score}
                />
                {idx < 3 && (
                  <div className="flex-1 h-1 mx-4 bg-gray-200">
                    <div
                      className={`h-full transition-all duration-500 ${
                        step <= currentStep ? 'bg-blue-600' : 'bg-gray-200'
                      }`}
                      style={{
                        width: step < currentStep ? '100%' : '0%',
                      }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>

          {/* Score comparison */}
          {originalScore !== null && (
            <div className="grid grid-cols-3 gap-4 text-center">
              <div className="bg-white rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">Original</div>
                <div className="text-3xl font-bold text-gray-900">
                  {originalScore}
                </div>
              </div>

              <div className="flex items-center justify-center">
                <div className="text-center">
                  <div className="text-sm text-gray-600 mb-1">Improvement</div>
                  <div
                    className={`text-2xl font-bold ${
                      improvement > 0 ? 'text-green-600' : 'text-gray-400'
                    }`}
                  >
                    {improvement > 0 ? '+' : ''}
                    {improvement.toFixed(1)}%
                  </div>
                </div>
              </div>

              <div className="bg-white rounded-lg p-4">
                <div className="text-sm text-gray-600 mb-1">
                  {isRefining ? 'Current' : 'Final'}
                </div>
                <div className="text-3xl font-bold text-blue-600">
                  {finalScore ?? steps[steps.length - 1]?.score ?? originalScore}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Streaming indicator */}
      {isRefining && (
        <div className="flex items-center justify-center p-4 bg-blue-50 rounded-lg">
          <div className="animate-pulse flex items-center space-x-2">
            <div className="w-2 h-2 bg-blue-600 rounded-full"></div>
            <div className="w-2 h-2 bg-blue-600 rounded-full animation-delay-200"></div>
            <div className="w-2 h-2 bg-blue-600 rounded-full animation-delay-400"></div>
            <span className="ml-2 text-sm text-blue-700 font-medium">
              Refining quality score...
            </span>
          </div>
        </div>
      )}

      {/* Steps display */}
      <div className="space-y-4">
        {steps.map((step) => (
          <RefinementStepCard key={step.step} step={step} />
        ))}
      </div>
    </div>
  );
});

IterativeRefinement.displayName = 'IterativeRefinement';

export default IterativeRefinement;
