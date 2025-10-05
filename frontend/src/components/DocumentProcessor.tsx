/**
 * Document Processor Component
 * 
 * PDF upload and analysis UI with job matching results display
 */

import { useState, useCallback, memo } from 'react';
import type { DocumentAnalysis } from '../types';

interface DocumentProcessorProps {
  onAnalysisComplete?: (analysis: DocumentAnalysis) => void;
}

export const DocumentProcessor = memo(({ onAnalysisComplete }: DocumentProcessorProps) => {
  const [file, setFile] = useState<File | null>(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [analysis, setAnalysis] = useState<DocumentAnalysis | null>(null);
  const [error, setError] = useState<string | null>(null);

  /**
   * Handle file upload and processing
   */
  const handleFileUpload = useCallback(async (uploadedFile: File) => {
    setFile(uploadedFile);
    setError(null);
    setIsProcessing(true);

    // Simulate document processing
    setTimeout(() => {
      const mockAnalysis: DocumentAnalysis = {
        id: Date.now().toString(),
        document_id: Date.now().toString(),
        candidate_name: 'John Doe',
        extracted_skills: [
          'React',
          'TypeScript',
          'Node.js',
          'Python',
          'AWS',
          'Docker',
          'GraphQL',
          'PostgreSQL',
        ],
        experience_years: 8,
        job_matches: [
          {
            job_id: 'job_001',
            job_title: 'Senior Full-Stack Engineer',
            company: 'TechCorp Inc',
            match_score: 92,
            key_skills: ['React', 'TypeScript', 'Node.js', 'AWS'],
            reasoning:
              'Strong alignment with required skills. 8 years of experience matches senior level requirements. Proven expertise in modern web technologies.',
          },
          {
            job_id: 'job_002',
            job_title: 'Lead Frontend Developer',
            company: 'StartupXYZ',
            match_score: 87,
            key_skills: ['React', 'TypeScript', 'GraphQL'],
            reasoning:
              'Excellent frontend skills with strong React and TypeScript experience. GraphQL expertise is a plus.',
          },
          {
            job_id: 'job_003',
            job_title: 'DevOps Engineer',
            company: 'CloudScale Ltd',
            match_score: 73,
            key_skills: ['AWS', 'Docker', 'Python'],
            reasoning:
              'Good infrastructure skills with AWS and Docker. Python experience is valuable for automation.',
          },
        ],
        processed_at: new Date().toISOString(),
      };

      setAnalysis(mockAnalysis);
      setIsProcessing(false);
      onAnalysisComplete?.(mockAnalysis);
    }, 3000);
  }, [onAnalysisComplete]);

  /**
   * Reset processor
   */
  const handleReset = useCallback(() => {
    setFile(null);
    setAnalysis(null);
    setError(null);
  }, []);

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      {/* Header */}
      <div>
        <h2 className="text-2xl font-bold text-gray-900">Document Processor</h2>
        <p className="text-gray-600 mt-1">
          Upload resumes for AI-powered skill extraction and job matching
        </p>
      </div>

      {/* Upload Area */}
      {!file && (
        <div
          className="border-2 border-dashed border-gray-300 rounded-lg p-12 text-center hover:border-blue-500 cursor-pointer transition-colors"
          onClick={() => document.getElementById('doc-input')?.click()}
        >
          <input
            id="doc-input"
            type="file"
            accept=".pdf,.docx,.doc"
            onChange={(e) => e.target.files?.[0] && handleFileUpload(e.target.files[0])}
            className="hidden"
          />

          <div className="text-6xl mb-4">📄</div>
          <p className="text-lg font-medium text-gray-900 mb-2">
            Upload Resume or CV
          </p>
          <p className="text-sm text-gray-500">
            Supports PDF, DOC, DOCX formats
          </p>
        </div>
      )}

      {/* Processing State */}
      {isProcessing && (
        <div className="bg-white shadow rounded-lg p-8 text-center">
          <div className="inline-block animate-spin text-6xl mb-4">⚙️</div>
          <h3 className="text-xl font-semibold text-gray-900 mb-2">
            Analyzing Document...
          </h3>
          <p className="text-gray-600">
            Extracting skills and matching with available positions
          </p>

          <div className="mt-4 max-w-md mx-auto">
            <div className="w-full bg-gray-200 rounded-full h-2">
              <div className="bg-blue-600 h-2 rounded-full animate-pulse w-3/4" />
            </div>
          </div>
        </div>
      )}

      {/* Analysis Results */}
      {analysis && !isProcessing && (
        <>
          {/* Candidate Summary */}
          <div className="bg-white shadow rounded-lg p-6">
            <div className="flex justify-between items-start mb-4">
              <div>
                <h3 className="text-xl font-bold text-gray-900">
                  {analysis.candidate_name}
                </h3>
                <p className="text-sm text-gray-600">
                  {analysis.experience_years} years of experience
                </p>
              </div>

              <button
                onClick={handleReset}
                className="px-4 py-2 text-sm border border-gray-300 rounded-lg hover:bg-gray-50"
              >
                Analyze New Document
              </button>
            </div>

            {/* Extracted Skills */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 mb-3">
                Extracted Skills:
              </h4>
              <div className="flex flex-wrap gap-2">
                {analysis.extracted_skills.map((skill) => (
                  <span
                    key={skill}
                    className="px-3 py-1 bg-blue-100 text-blue-800 rounded-full text-sm font-medium"
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          </div>

          {/* Job Matches */}
          <div className="space-y-4">
            <h3 className="text-xl font-semibold text-gray-900">
              Top Job Matches ({analysis.job_matches.length})
            </h3>

            {analysis.job_matches.map((match) => (
              <div
                key={match.job_id}
                className="bg-white shadow rounded-lg p-6 hover:shadow-lg transition-shadow"
              >
                <div className="flex justify-between items-start mb-4">
                  <div>
                    <h4 className="text-lg font-semibold text-gray-900">
                      {match.job_title}
                    </h4>
                    <p className="text-sm text-gray-600">{match.company}</p>
                  </div>

                  <div className="text-right">
                    <div
                      className={`
                        text-3xl font-bold
                        ${match.match_score >= 90
                          ? 'text-green-600'
                          : match.match_score >= 80
                          ? 'text-blue-600'
                          : 'text-yellow-600'
                        }
                      `}
                    >
                      {match.match_score}%
                    </div>
                    <div className="text-xs text-gray-500">Match Score</div>
                  </div>
                </div>

                {/* Match Score Bar */}
                <div className="mb-4">
                  <div className="w-full bg-gray-200 rounded-full h-3">
                    <div
                      className={`
                        h-3 rounded-full transition-all
                        ${match.match_score >= 90
                          ? 'bg-green-600'
                          : match.match_score >= 80
                          ? 'bg-blue-600'
                          : 'bg-yellow-600'
                        }
                      `}
                      style={{ width: `${match.match_score}%` }}
                    />
                  </div>
                </div>

                {/* Key Skills */}
                <div className="mb-4">
                  <h5 className="text-sm font-medium text-gray-700 mb-2">
                    Key Skills Required:
                  </h5>
                  <div className="flex flex-wrap gap-2">
                    {match.key_skills.map((skill) => (
                      <span
                        key={skill}
                        className="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm"
                      >
                        {skill}
                      </span>
                    ))}
                  </div>
                </div>

                {/* Reasoning */}
                <div>
                  <h5 className="text-sm font-medium text-gray-700 mb-2">
                    Match Reasoning:
                  </h5>
                  <p className="text-sm text-gray-600">{match.reasoning}</p>
                </div>

                {/* Action Button */}
                <div className="mt-4 pt-4 border-t border-gray-200">
                  <button className="w-full px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700">
                    Apply to Position
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Error State */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4">
          <div className="flex">
            <span className="text-red-600 mr-3">✕</span>
            <div>
              <h3 className="text-sm font-medium text-red-800">Processing Error</h3>
              <p className="text-sm text-red-700 mt-1">{error}</p>
            </div>
          </div>
        </div>
      )}
    </div>
  );
});

DocumentProcessor.displayName = 'DocumentProcessor';

export default DocumentProcessor;
