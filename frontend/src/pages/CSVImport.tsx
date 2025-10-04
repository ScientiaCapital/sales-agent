/**
 * CSV Import Page
 * 
 * Bulk lead import with drag-drop, progress tracking, and preview
 */

import { useState, useCallback, memo } from 'react';
import { apiClient } from '../services/api';
import type { CSVImportProgress } from '../types';

export const CSVImport = memo(() => {
  const [file, setFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [progress, setProgress] = useState<CSVImportProgress | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [importedLeads, setImportedLeads] = useState<number>(0);

  /**
   * Handle file drop
   */
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);

    const droppedFile = e.dataTransfer.files[0];
    if (droppedFile && droppedFile.name.endsWith('.csv')) {
      setFile(droppedFile);
      setError(null);
    } else {
      setError('Please drop a CSV file');
    }
  }, []);

  /**
   * Handle file selection
   */
  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFile = e.target.files?.[0];
      if (selectedFile) {
        setFile(selectedFile);
        setError(null);
      }
    },
    []
  );

  /**
   * Upload CSV file
   */
  const handleUpload = useCallback(async () => {
    if (!file) return;

    setIsUploading(true);
    setError(null);
    setProgress(null);

    try {
      const result = await apiClient.importCSV(file);
      
      setProgress({
        total: result.total || 0,
        processed: result.processed || 0,
        succeeded: result.succeeded || 0,
        failed: result.failed || 0,
        errors: result.errors || [],
      });

      setImportedLeads(result.succeeded || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Import failed');
    } finally {
      setIsUploading(false);
    }
  }, [file]);

  /**
   * Reset form
   */
  const handleReset = useCallback(() => {
    setFile(null);
    setProgress(null);
    setError(null);
    setImportedLeads(0);
  }, []);

  const progressPercentage = progress
    ? (progress.processed / progress.total) * 100
    : 0;

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h1 className="text-3xl font-bold text-gray-900">CSV Import</h1>
        <p className="text-gray-600 mt-2">
          Bulk import leads from CSV files. Target: 1,000 leads in &lt;5 seconds
        </p>
      </div>

      {/* Upload Area */}
      <div className="bg-white shadow rounded-lg p-6">
        <div
          className={`
            border-2 border-dashed rounded-lg p-12 text-center
            transition-colors cursor-pointer
            ${isDragging ? 'border-blue-500 bg-blue-50' : 'border-gray-300'}
            ${file ? 'bg-green-50 border-green-500' : ''}
          `}
          onDragOver={(e) => {
            e.preventDefault();
            setIsDragging(true);
          }}
          onDragLeave={() => setIsDragging(false)}
          onDrop={handleDrop}
          onClick={() => document.getElementById('file-input')?.click()}
        >
          <input
            id="file-input"
            type="file"
            accept=".csv"
            onChange={handleFileSelect}
            className="hidden"
          />

          {!file ? (
            <div>
              <div className="text-6xl mb-4">📄</div>
              <p className="text-lg font-medium text-gray-900 mb-2">
                Drop CSV file here or click to browse
              </p>
              <p className="text-sm text-gray-500">
                Accepts .csv files only
              </p>
            </div>
          ) : (
            <div>
              <div className="text-6xl mb-4">✓</div>
              <p className="text-lg font-medium text-gray-900 mb-2">
                {file.name}
              </p>
              <p className="text-sm text-gray-500">
                {(file.size / 1024).toFixed(2)} KB
              </p>
            </div>
          )}
        </div>

        {/* Actions */}
        {file && !progress && (
          <div className="mt-6 flex justify-end space-x-3">
            <button
              onClick={handleReset}
              className="px-4 py-2 border border-gray-300 rounded-lg text-gray-700 hover:bg-gray-50"
            >
              Cancel
            </button>
            <button
              onClick={handleUpload}
              disabled={isUploading}
              className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50"
            >
              {isUploading ? 'Uploading...' : 'Upload & Import'}
            </button>
          </div>
        )}
      </div>

      {/* Error */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <span className="text-red-600 mr-3">✕</span>
            <div>
              <h3 className="text-sm font-medium text-red-800">Import Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}

      {/* Progress */}
      {isUploading && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Importing leads...</h3>
          <div className="w-full bg-gray-200 rounded-full h-4">
            <div
              className="bg-blue-600 h-4 rounded-full transition-all duration-300"
              style={{ width: `${progressPercentage}%` }}
            />
          </div>
          <div className="mt-2 flex justify-between text-sm text-gray-600">
            <span>Processing...</span>
            <span>{Math.round(progressPercentage)}%</span>
          </div>
        </div>
      )}

      {/* Results */}
      {progress && !isUploading && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">Import Complete</h3>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
            <div className="text-center p-4 bg-gray-50 rounded-lg">
              <div className="text-3xl font-bold text-gray-900">
                {progress.total}
              </div>
              <div className="text-sm text-gray-600 mt-1">Total Rows</div>
            </div>

            <div className="text-center p-4 bg-green-50 rounded-lg">
              <div className="text-3xl font-bold text-green-600">
                {progress.succeeded}
              </div>
              <div className="text-sm text-gray-600 mt-1">Succeeded</div>
            </div>

            <div className="text-center p-4 bg-red-50 rounded-lg">
              <div className="text-3xl font-bold text-red-600">
                {progress.failed}
              </div>
              <div className="text-sm text-gray-600 mt-1">Failed</div>
            </div>

            <div className="text-center p-4 bg-blue-50 rounded-lg">
              <div className="text-3xl font-bold text-blue-600">
                {progress.processed}
              </div>
              <div className="text-sm text-gray-600 mt-1">Processed</div>
            </div>
          </div>

          {progress.errors.length > 0 && (
            <div className="border-t pt-4">
              <h4 className="font-medium text-gray-900 mb-2">Errors:</h4>
              <ul className="space-y-1">
                {progress.errors.slice(0, 5).map((err, idx) => (
                  <li key={idx} className="text-sm text-red-600">
                    • {err}
                  </li>
                ))}
                {progress.errors.length > 5 && (
                  <li className="text-sm text-gray-500">
                    ... and {progress.errors.length - 5} more errors
                  </li>
                )}
              </ul>
            </div>
          )}

          <button
            onClick={handleReset}
            className="mt-6 w-full px-4 py-2 bg-gray-600 text-white rounded-lg hover:bg-gray-700"
          >
            Import Another File
          </button>
        </div>
      )}

      {/* Preview Table (Imported Leads) */}
      {importedLeads > 0 && (
        <div className="bg-white shadow rounded-lg p-6">
          <h3 className="text-lg font-semibold mb-4">
            {importedLeads} leads imported successfully
          </h3>
          <p className="text-sm text-gray-600">
            View imported leads in the Leads dashboard
          </p>
        </div>
      )}

      {/* CSV Format Guide */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-6">
        <h3 className="text-lg font-semibold text-blue-900 mb-3">
          CSV Format Guide
        </h3>
        <div className="space-y-2 text-sm text-blue-800">
          <p>
            <strong>Required columns:</strong> company_name, industry,
            company_website
          </p>
          <p>
            <strong>Optional columns:</strong> company_size, contact_name,
            contact_email, contact_phone, contact_title, notes
          </p>
          <div className="mt-4 p-3 bg-white rounded border border-blue-300">
            <code className="text-xs">
              company_name,industry,company_website,contact_email
              <br />
              TechCorp,SaaS,https://techcorp.com,john@techcorp.com
              <br />
              DataInc,Analytics,https://datainc.com,jane@datainc.com
            </code>
          </div>
        </div>
      </div>
    </div>
  );
});

CSVImport.displayName = 'CSVImport';

export default CSVImport;
