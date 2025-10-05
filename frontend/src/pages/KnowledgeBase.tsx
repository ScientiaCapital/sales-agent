/**
 * Knowledge Base Page
 * 
 * Document upload, ICP criteria management, and vector search
 */

import { useState, useCallback, memo } from 'react';
import type { Document, ICPCriteria, VectorSearchResult } from '../types';

export const KnowledgeBase = memo(() => {
  const [documents, setDocuments] = useState<Document[]>([]);
  const [icpCriteria] = useState<ICPCriteria[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<VectorSearchResult[]>([]);
  const [isSearching, setIsSearching] = useState(false);

  /**
   * Handle document upload
   */
  const handleUpload = useCallback(async (file: File) => {
    // Mock implementation - replace with actual API call
    const newDoc: Document = {
      id: Date.now().toString(),
      name: file.name,
      type: file.name.endsWith('.pdf')
        ? 'pdf'
        : file.name.endsWith('.docx')
        ? 'docx'
        : 'txt',
      size: file.size,
      uploaded_at: new Date().toISOString(),
      processed: false,
    };

    setDocuments((prev) => [newDoc, ...prev]);

    // Simulate processing
    setTimeout(() => {
      setDocuments((prev) =>
        prev.map((doc) =>
          doc.id === newDoc.id
            ? { ...doc, processed: true, vector_count: 42 }
            : doc
        )
      );
    }, 2000);
  }, []);

  /**
   * Handle vector search
   */
  const handleSearch = useCallback(async () => {
    if (!searchQuery) return;

    setIsSearching(true);

    // Mock implementation - replace with actual API call
    setTimeout(() => {
      const mockResults: VectorSearchResult[] = [
        {
          document_id: '1',
          document_name: 'ICP_Definition.pdf',
          chunk_text:
            'Ideal customer profile includes companies with 50-200 employees in SaaS industry...',
          similarity_score: 0.95,
        },
        {
          document_id: '2',
          document_name: 'Sales_Strategy.docx',
          chunk_text:
            'Target decision makers with CTO or VP Engineering titles...',
          similarity_score: 0.87,
        },
      ];

      setSearchResults(mockResults);
      setIsSearching(false);
    }, 1000);
  }, [searchQuery]);

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Knowledge Base</h1>
        <p className="text-gray-600 mt-2">
          Manage documents and ICP criteria for AI-powered qualification
        </p>
      </div>

      {/* Vector Search */}
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-xl font-semibold mb-4">Vector Search</h2>

        <div className="flex gap-3">
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
            placeholder="Search knowledge base..."
            className="flex-1 px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSearch}
            disabled={isSearching || !searchQuery}
            className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
          >
            {isSearching ? 'Searching...' : 'Search'}
          </button>
        </div>

        {/* Search Results */}
        {searchResults.length > 0 && (
          <div className="mt-4 space-y-3">
            {searchResults.map((result) => (
              <div
                key={result.document_id}
                className="p-4 border border-gray-200 rounded-lg hover:border-blue-300"
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-medium text-gray-900">
                    {result.document_name}
                  </h3>
                  <span className="text-sm text-blue-600">
                    {(result.similarity_score * 100).toFixed(0)}% match
                  </span>
                </div>
                <p className="text-sm text-gray-600">{result.chunk_text}</p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Document Upload */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">Documents</h2>

          <label className="block mb-4">
            <div className="border-2 border-dashed border-gray-300 rounded-lg p-8 text-center hover:border-blue-500 cursor-pointer">
              <input
                type="file"
                accept=".pdf,.docx,.txt,.md"
                onChange={(e) => e.target.files?.[0] && handleUpload(e.target.files[0])}
                className="hidden"
              />
              <div className="text-4xl mb-2">📁</div>
              <p className="text-sm text-gray-600">
                Drop files or click to upload
              </p>
              <p className="text-xs text-gray-500 mt-1">
                PDF, DOCX, TXT, MD
              </p>
            </div>
          </label>

          <div className="space-y-2">
            {documents.map((doc) => (
              <div
                key={doc.id}
                className="flex items-center justify-between p-3 border border-gray-200 rounded-lg"
              >
                <div className="flex items-center space-x-3">
                  <span className="text-2xl">
                    {doc.type === 'pdf'
                      ? '📄'
                      : doc.type === 'docx'
                      ? '📝'
                      : '📃'}
                  </span>
                  <div>
                    <div className="font-medium text-gray-900">{doc.name}</div>
                    <div className="text-xs text-gray-500">
                      {(doc.size / 1024).toFixed(1)} KB
                      {doc.processed && ` • ${doc.vector_count} vectors`}
                    </div>
                  </div>
                </div>

                {!doc.processed && (
                  <span className="text-xs text-yellow-600">Processing...</span>
                )}
                {doc.processed && (
                  <span className="text-xs text-green-600">✓ Ready</span>
                )}
              </div>
            ))}
          </div>
        </div>

        {/* ICP Criteria */}
        <div className="bg-white shadow rounded-lg p-6">
          <h2 className="text-xl font-semibold mb-4">ICP Criteria</h2>

          <div className="space-y-3">
            {icpCriteria.map((criteria) => (
              <div
                key={criteria.id}
                className="p-4 border border-gray-200 rounded-lg"
              >
                <div className="flex justify-between items-start mb-2">
                  <h3 className="font-medium text-gray-900">{criteria.name}</h3>
                  <span className="text-sm text-blue-600">
                    Weight: {criteria.weight}
                  </span>
                </div>
                <p className="text-sm text-gray-600">{criteria.description}</p>
              </div>
            ))}

            {icpCriteria.length === 0 && (
              <div className="text-center py-8 text-gray-500">
                <p className="mb-2">No ICP criteria defined</p>
                <button className="text-blue-600 hover:underline">
                  Add criteria
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});

KnowledgeBase.displayName = 'KnowledgeBase';

export default KnowledgeBase;
