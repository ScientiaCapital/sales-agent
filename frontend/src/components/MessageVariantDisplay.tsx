/**
 * Message Variant Display Component
 *
 * Displays 3 AI-generated message variants side-by-side for A/B testing comparison
 */

import { useState } from 'react';
import type { MessageVariant, VariantAnalytics } from '../types';

interface MessageVariantDisplayProps {
  variants: MessageVariant[];
  analytics?: VariantAnalytics[];
  selectedVariant?: number;
  onSelect?: (variantIndex: number) => void;
}

const TONE_LABELS = {
  professional: 'Professional',
  friendly: 'Friendly',
  direct: 'Direct',
};

const TONE_COLORS = {
  professional: 'bg-blue-100 text-blue-800 border-blue-300',
  friendly: 'bg-green-100 text-green-800 border-green-300',
  direct: 'bg-purple-100 text-purple-800 border-purple-300',
};

export function MessageVariantDisplay({
  variants,
  analytics,
  selectedVariant,
  onSelect,
}: MessageVariantDisplayProps) {
  const [copiedIndex, setCopiedIndex] = useState<number | null>(null);

  const copyToClipboard = async (text: string, index: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIndex(index);
      setTimeout(() => setCopiedIndex(null), 2000);
    } catch (err) {
      console.error('Failed to copy text:', err);
    }
  };

  const getWinnerIndex = (): number | null => {
    if (!analytics || analytics.length === 0) return null;

    let maxReplyRate = 0;
    let winnerIndex: number | null = null;

    analytics.forEach((analytic) => {
      if (analytic.reply_rate > maxReplyRate && analytic.times_selected > 5) {
        maxReplyRate = analytic.reply_rate;
        winnerIndex = analytic.variant_number;
      }
    });

    return winnerIndex;
  };

  const winnerIndex = getWinnerIndex();

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
      {variants.map((variant, index) => {
        const variantAnalytics = analytics?.find((a) => a.variant_number === index);
        const isSelected = selectedVariant === index;
        const isWinner = winnerIndex === index;

        return (
          <div
            key={index}
            className={`relative border-2 rounded-lg p-6 transition-all ${
              isSelected
                ? 'border-indigo-500 shadow-lg'
                : 'border-gray-200 hover:border-gray-300'
            }`}
          >
            {/* Winner Badge */}
            {isWinner && (
              <div className="absolute top-0 right-0 -mt-2 -mr-2">
                <div className="bg-yellow-400 text-yellow-900 px-3 py-1 rounded-full text-xs font-bold flex items-center space-x-1">
                  <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 20 20">
                    <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z" />
                  </svg>
                  <span>Winner</span>
                </div>
              </div>
            )}

            {/* Variant Header */}
            <div className="mb-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-sm font-medium text-gray-500">
                  Variant {index}
                </span>
                {isSelected && (
                  <span className="inline-flex items-center px-2 py-1 rounded text-xs font-medium bg-indigo-100 text-indigo-800">
                    Selected
                  </span>
                )}
              </div>
              <div
                className={`inline-flex px-3 py-1 rounded-full text-sm font-semibold border ${
                  TONE_COLORS[variant.tone]
                }`}
              >
                {TONE_LABELS[variant.tone]}
              </div>
            </div>

            {/* Subject (for email) */}
            {variant.subject && (
              <div className="mb-4">
                <h4 className="text-xs font-medium text-gray-500 uppercase mb-1">Subject</h4>
                <p className="text-sm font-semibold text-gray-900">{variant.subject}</p>
              </div>
            )}

            {/* Body */}
            <div className="mb-4">
              <h4 className="text-xs font-medium text-gray-500 uppercase mb-1">Message</h4>
              <div className="bg-gray-50 rounded-md p-3 max-h-64 overflow-y-auto">
                <p className="text-sm text-gray-700 whitespace-pre-wrap">{variant.body}</p>
              </div>
            </div>

            {/* Performance Metrics */}
            {variantAnalytics && variantAnalytics.times_selected > 0 && (
              <div className="mb-4 border-t pt-4">
                <h4 className="text-xs font-medium text-gray-500 uppercase mb-3">Performance</h4>
                <div className="space-y-2">
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Sent</span>
                    <span className="text-sm font-semibold text-gray-900">
                      {variantAnalytics.times_selected}
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Opens</span>
                    <span className="text-sm font-semibold text-gray-900">
                      {variantAnalytics.times_opened} ({variantAnalytics.open_rate.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Clicks</span>
                    <span className="text-sm font-semibold text-gray-900">
                      {variantAnalytics.times_clicked} ({variantAnalytics.click_rate.toFixed(1)}%)
                    </span>
                  </div>
                  <div className="flex justify-between items-center">
                    <span className="text-xs text-gray-600">Replies</span>
                    <span className="text-sm font-semibold text-green-600">
                      {variantAnalytics.times_replied} ({variantAnalytics.reply_rate.toFixed(1)}%)
                    </span>
                  </div>
                </div>
              </div>
            )}

            {/* Action Buttons */}
            <div className="flex space-x-2">
              <button
                onClick={() => copyToClipboard(variant.body, index)}
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm font-medium text-gray-700 hover:bg-gray-50 flex items-center justify-center space-x-2"
              >
                {copiedIndex === index ? (
                  <>
                    <svg className="h-4 w-4 text-green-600" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clipRule="evenodd" />
                    </svg>
                    <span className="text-green-600">Copied!</span>
                  </>
                ) : (
                  <>
                    <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                    </svg>
                    <span>Copy</span>
                  </>
                )}
              </button>

              {onSelect && (
                <button
                  onClick={() => onSelect(index)}
                  disabled={isSelected}
                  className={`flex-1 px-3 py-2 rounded-md text-sm font-medium ${
                    isSelected
                      ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                      : 'bg-indigo-600 text-white hover:bg-indigo-700'
                  }`}
                >
                  {isSelected ? 'Selected' : 'Select'}
                </button>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}
