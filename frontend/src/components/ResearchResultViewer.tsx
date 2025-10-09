/**
 * Research Result Viewer Component
 *
 * Displays completed research results with metadata and export options
 */

import { memo, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ResearchHistoryItem } from '../types';

interface ResearchResultViewerProps {
  result: ResearchHistoryItem;
  onClose?: () => void;
}

export const ResearchResultViewer = memo(({ result, onClose }: ResearchResultViewerProps) => {
  const [copied, setCopied] = useState(false);
  const [showMetadata, setShowMetadata] = useState(false);

  const handleCopy = async () => {
    if (result.final_output) {
      await navigator.clipboard.writeText(result.final_output);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const handleDownload = () => {
    if (!result.final_output) return;

    const blob = new Blob([result.final_output], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `research-${result.id}.md`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="bg-white rounded-lg shadow-lg border-2 border-indigo-500">
      {/* Header */}
      <div className="bg-gradient-to-r from-indigo-600 to-purple-600 text-white px-6 py-4 rounded-t-lg">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <span className="text-3xl">📄</span>
            <div>
              <h3 className="text-xl font-bold">Research Report</h3>
              <p className="text-sm text-indigo-100">
                {new Date(result.created_at).toLocaleString()}
              </p>
            </div>
          </div>

          {onClose && (
            <button
              onClick={onClose}
              className="text-white hover:bg-white/20 rounded-full p-2 transition-colors"
              aria-label="Close"
            >
              <svg className="w-6 h-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* Topic */}
      <div className="px-6 py-4 border-b border-gray-200 bg-gray-50">
        <h4 className="text-sm font-semibold text-gray-600 uppercase mb-1">Research Topic</h4>
        <p className="text-lg text-gray-900">{result.topic}</p>
      </div>

      {/* Content */}
      <div className="px-6 py-6 max-h-[600px] overflow-y-auto">
        {result.status === 'completed' && result.final_output ? (
          <div className="prose prose-indigo max-w-none">
            {result.format_style === 'markdown' ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>
                {result.final_output}
              </ReactMarkdown>
            ) : (
              <pre className="whitespace-pre-wrap text-sm text-gray-700 bg-gray-50 p-4 rounded">
                {result.final_output}
              </pre>
            )}
          </div>
        ) : result.status === 'error' ? (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4">
            <div className="flex items-center space-x-2 mb-2">
              <span className="text-red-600 text-2xl">⚠️</span>
              <h4 className="text-lg font-semibold text-red-900">Research Failed</h4>
            </div>
            <p className="text-red-700">{result.error || 'An unknown error occurred'}</p>
          </div>
        ) : (
          <div className="text-center py-8">
            <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-indigo-600 mx-auto"></div>
            <p className="mt-4 text-gray-600">Research in progress...</p>
          </div>
        )}
      </div>

      {/* Metadata Section */}
      {result.status === 'completed' && (
        <div className="px-6 py-4 border-t border-gray-200 bg-gray-50">
          <button
            onClick={() => setShowMetadata(!showMetadata)}
            className="flex items-center space-x-2 text-gray-700 hover:text-gray-900 font-medium"
          >
            <svg
              className={`w-5 h-5 transition-transform ${showMetadata ? 'rotate-90' : ''}`}
              fill="none"
              viewBox="0 0 24 24"
              stroke="currentColor"
            >
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
            </svg>
            <span>Research Metadata</span>
          </button>

          {showMetadata && (
            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-xs text-gray-500 uppercase">Latency</div>
                <div className="text-lg font-bold text-gray-900">
                  {result.total_latency_ms ? `${(result.total_latency_ms / 1000).toFixed(2)}s` : 'N/A'}
                </div>
              </div>

              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-xs text-gray-500 uppercase">Cost</div>
                <div className="text-lg font-bold text-gray-900">
                  {result.total_cost_usd ? `$${result.total_cost_usd.toFixed(6)}` : 'N/A'}
                </div>
              </div>

              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-xs text-gray-500 uppercase">Queries</div>
                <div className="text-lg font-bold text-gray-900">
                  {result.queries_generated?.length || 0}
                </div>
              </div>

              <div className="bg-white rounded-lg p-3 border border-gray-200">
                <div className="text-xs text-gray-500 uppercase">Results</div>
                <div className="text-lg font-bold text-gray-900">
                  {result.search_results_count || 0}
                </div>
              </div>

              {result.queries_generated && result.queries_generated.length > 0 && (
                <div className="col-span-2 md:col-span-4 bg-white rounded-lg p-3 border border-gray-200">
                  <div className="text-xs text-gray-500 uppercase mb-2">Queries Generated</div>
                  <ul className="list-disc list-inside space-y-1 text-sm text-gray-700">
                    {result.queries_generated.map((query, idx) => (
                      <li key={idx}>{query}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Action Buttons */}
      {result.status === 'completed' && result.final_output && (
        <div className="px-6 py-4 border-t border-gray-200 flex justify-end space-x-3">
          <button
            onClick={handleCopy}
            className="px-4 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 flex items-center space-x-2 transition-colors"
          >
            {copied ? (
              <>
                <svg className="w-5 h-5 text-green-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
                <span className="text-green-600">Copied!</span>
              </>
            ) : (
              <>
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                </svg>
                <span>Copy</span>
              </>
            )}
          </button>

          <button
            onClick={handleDownload}
            className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 flex items-center space-x-2 transition-colors"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
            </svg>
            <span>Download</span>
          </button>
        </div>
      )}
    </div>
  );
});

ResearchResultViewer.displayName = 'ResearchResultViewer';

export default ResearchResultViewer;
