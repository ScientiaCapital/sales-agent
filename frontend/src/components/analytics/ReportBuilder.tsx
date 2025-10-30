import React, { useState, useEffect } from 'react';
import type {
  ReportTemplate,
  QueryConfig,
  FilterClause,
  Aggregation,
  OrderClause,
  VisualizationConfig,
  ReportGenerateRequest,
  ExportRequest
} from '../../types';

/**
 * Report Builder - 4-Step Wizard
 *
 * Professional report creation interface with:
 * - Step 1: Template selection or custom report
 * - Step 2: Query configuration (table, columns, filters)
 * - Step 3: Visualization settings
 * - Step 4: Preview and export
 */

interface ReportBuilderProps {
  onComplete?: (templateId: string) => void;
  initialTemplate?: ReportTemplate;
}

export const ReportBuilder: React.FC<ReportBuilderProps> = ({
  onComplete,
  initialTemplate
}) => {
  // Wizard state
  const [currentStep, setCurrentStep] = useState(1);
  const [templates, setTemplates] = useState<ReportTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [reportName, setReportName] = useState('');
  const [reportDescription, setReportDescription] = useState('');
  const [reportType, setReportType] = useState<string>('custom');
  const [selectedTemplate, setSelectedTemplate] = useState<ReportTemplate | null>(initialTemplate || null);

  // Query configuration state
  const [selectedTable, setSelectedTable] = useState<string>('leads');
  const [selectedColumns, setSelectedColumns] = useState<string[]>([]);
  const [filters, setFilters] = useState<FilterClause[]>([]);
  const [aggregations, setAggregations] = useState<Aggregation[]>([]);
  const [groupBy, setGroupBy] = useState<string[]>([]);
  const [orderBy, setOrderBy] = useState<OrderClause[]>([]);
  const [limit, setLimit] = useState<number>(100);

  // Visualization state
  const [chartType, setChartType] = useState<string>('table');
  const [xAxis, setXAxis] = useState<string>('');
  const [yAxis, setYAxis] = useState<string>('');
  const [series, setSeries] = useState<string[]>([]);

  // Preview state
  const [previewData, setPreviewData] = useState<any[]>([]);
  const [previewColumns, setPreviewColumns] = useState<string[]>([]);

  // Available tables and columns (hardcoded for now, could be fetched from API)
  const availableTables = [
    { value: 'leads', label: 'Leads', columns: ['id', 'company_name', 'email', 'qualification_score', 'status', 'created_at'] },
    { value: 'analytics_campaign_metrics', label: 'Campaign Metrics', columns: ['campaign_id', 'metric_date', 'messages_sent', 'responses_received', 'response_rate', 'conversions'] },
    { value: 'analytics_cost_tracking', label: 'Cost Tracking', columns: ['provider', 'operation_type', 'cost_usd', 'tokens_used', 'created_at'] },
    { value: 'analytics_ab_tests', label: 'A/B Tests', columns: ['test_id', 'test_name', 'status', 'conversion_rate_a', 'conversion_rate_b', 'winner'] }
  ];

  const operators = [
    { value: '=', label: 'Equals' },
    { value: '!=', label: 'Not Equals' },
    { value: '>', label: 'Greater Than' },
    { value: '>=', label: 'Greater or Equal' },
    { value: '<', label: 'Less Than' },
    { value: '<=', label: 'Less or Equal' },
    { value: 'in', label: 'In List' },
    { value: 'like', label: 'Contains' }
  ];

  const aggregationFunctions = [
    { value: 'count', label: 'Count' },
    { value: 'sum', label: 'Sum' },
    { value: 'avg', label: 'Average' },
    { value: 'min', label: 'Minimum' },
    { value: 'max', label: 'Maximum' }
  ];

  const chartTypes = [
    { value: 'table', label: 'Table', icon: '📊' },
    { value: 'bar', label: 'Bar Chart', icon: '📊' },
    { value: 'line', label: 'Line Chart', icon: '📈' },
    { value: 'pie', label: 'Pie Chart', icon: '🥧' },
    { value: 'doughnut', label: 'Doughnut Chart', icon: '🍩' }
  ];

  // Load templates on mount
  useEffect(() => {
    fetchTemplates();
  }, []);

  // Initialize from selected template
  useEffect(() => {
    if (selectedTemplate) {
      setReportName(selectedTemplate.name);
      setReportDescription(selectedTemplate.description || '');
      setReportType(selectedTemplate.report_type);

      const config = selectedTemplate.query_config;
      setSelectedTable(config.table);
      setSelectedColumns(config.columns || []);
      setFilters(config.filters || []);
      setAggregations(config.aggregations || []);
      setGroupBy(config.group_by || []);
      setOrderBy(config.order_by || []);
      setLimit(config.limit || 100);

      if (selectedTemplate.visualization_config) {
        const vizConfig = selectedTemplate.visualization_config;
        setChartType(vizConfig.chart_type);
        setXAxis(vizConfig.x_axis || '');
        setYAxis(vizConfig.y_axis || '');
        setSeries(vizConfig.series || []);
      }
    }
  }, [selectedTemplate]);

  const fetchTemplates = async () => {
    try {
      const response = await fetch('/api/v1/report-templates');
      const data = await response.json();
      setTemplates(data);
    } catch (err) {
      console.error('Failed to fetch templates:', err);
      setError('Failed to load templates');
    }
  };

  const getCurrentTableColumns = (): string[] => {
    const table = availableTables.find(t => t.value === selectedTable);
    return table?.columns || [];
  };

  const handleNext = () => {
    if (currentStep < 4) {
      setCurrentStep(currentStep + 1);
    }
  };

  const handleBack = () => {
    if (currentStep > 1) {
      setCurrentStep(currentStep - 1);
    }
  };

  const handlePreview = async () => {
    setLoading(true);
    setError(null);

    try {
      const queryConfig: QueryConfig = {
        table: selectedTable,
        columns: selectedColumns,
        filters,
        aggregations,
        group_by: groupBy,
        order_by: orderBy,
        limit: Math.min(limit, 50) // Preview limit
      };

      const response = await fetch('/api/v1/report-templates/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_config: queryConfig
        })
      });

      if (!response.ok) {
        throw new Error('Failed to generate preview');
      }

      const result = await response.json();
      setPreviewData(result.data);
      setPreviewColumns(result.columns);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Preview generation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveTemplate = async () => {
    setLoading(true);
    setError(null);

    try {
      const queryConfig: QueryConfig = {
        table: selectedTable,
        columns: selectedColumns,
        filters,
        aggregations,
        group_by: groupBy,
        order_by: orderBy,
        limit
      };

      const visualizationConfig: VisualizationConfig = {
        chart_type: chartType as any,
        x_axis: xAxis || undefined,
        y_axis: yAxis || undefined,
        series: series.length > 0 ? series : undefined
      };

      const response = await fetch('/api/v1/report-templates', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name: reportName,
          description: reportDescription,
          report_type: reportType,
          query_config: queryConfig,
          visualization_config: visualizationConfig
        })
      });

      if (!response.ok) {
        throw new Error('Failed to save template');
      }

      const template = await response.json();

      if (onComplete) {
        onComplete(template.template_id);
      }

      alert('Report template saved successfully!');
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to save template');
    } finally {
      setLoading(false);
    }
  };

  const handleExport = async (format: 'csv' | 'pdf' | 'xlsx') => {
    setLoading(true);
    setError(null);

    try {
      const queryConfig: QueryConfig = {
        table: selectedTable,
        columns: selectedColumns,
        filters,
        aggregations,
        group_by: groupBy,
        order_by: orderBy,
        limit
      };

      const response = await fetch('/api/v1/exports/report', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query_config: queryConfig,
          format,
          title: reportName || 'Custom Report',
          include_summary: true
        })
      });

      if (!response.ok) {
        throw new Error('Export failed');
      }

      // Download file
      const blob = await response.blob();
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.download = `${reportName.replace(/\s+/g, '_')}_${new Date().toISOString().split('T')[0]}.${format}`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Export failed');
    } finally {
      setLoading(false);
    }
  };

  const addFilter = () => {
    setFilters([...filters, { column: '', operator: '=', value: '' }]);
  };

  const removeFilter = (index: number) => {
    setFilters(filters.filter((_, i) => i !== index));
  };

  const updateFilter = (index: number, field: keyof FilterClause, value: any) => {
    const updated = [...filters];
    updated[index] = { ...updated[index], [field]: value };
    setFilters(updated);
  };

  const addAggregation = () => {
    setAggregations([...aggregations, { function: 'count', column: '', alias: '' }]);
  };

  const removeAggregation = (index: number) => {
    setAggregations(aggregations.filter((_, i) => i !== index));
  };

  const updateAggregation = (index: number, field: keyof Aggregation, value: any) => {
    const updated = [...aggregations];
    updated[index] = { ...updated[index], [field]: value };
    setAggregations(updated);
  };

  return (
    <div className="max-w-6xl mx-auto p-6">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 mb-2">Report Builder</h1>
        <p className="text-gray-600">Create custom analytics reports with a flexible query builder</p>
      </div>

      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex items-center justify-between">
          {[1, 2, 3, 4].map((step) => (
            <div key={step} className="flex items-center flex-1">
              <div className={`flex items-center justify-center w-10 h-10 rounded-full ${
                currentStep >= step
                  ? 'bg-blue-600 text-white'
                  : 'bg-gray-200 text-gray-600'
              }`}>
                {step}
              </div>
              <div className="ml-3 flex-1">
                <p className={`text-sm font-medium ${
                  currentStep >= step ? 'text-blue-600' : 'text-gray-500'
                }`}>
                  {step === 1 && 'Template'}
                  {step === 2 && 'Query'}
                  {step === 3 && 'Visualization'}
                  {step === 4 && 'Preview'}
                </p>
              </div>
              {step < 4 && (
                <div className={`h-0.5 flex-1 mx-2 ${
                  currentStep > step ? 'bg-blue-600' : 'bg-gray-200'
                }`} />
              )}
            </div>
          ))}
        </div>
      </div>

      {/* Error Display */}
      {error && (
        <div className="mb-4 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded">
          {error}
        </div>
      )}

      {/* Step Content */}
      <div className="bg-white rounded-lg shadow p-6">
        {/* Step 1: Template Selection */}
        {currentStep === 1 && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Step 1: Template Selection</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Report Name *
              </label>
              <input
                type="text"
                value={reportName}
                onChange={(e) => setReportName(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2"
                placeholder="My Custom Report"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Description
              </label>
              <textarea
                value={reportDescription}
                onChange={(e) => setReportDescription(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2"
                rows={3}
                placeholder="Describe what this report will show..."
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Report Type
              </label>
              <select
                value={reportType}
                onChange={(e) => setReportType(e.target.value)}
                className="w-full border border-gray-300 rounded-lg px-4 py-2"
              >
                <option value="custom">Custom Report</option>
                <option value="lead_analysis">Lead Analysis</option>
                <option value="campaign_performance">Campaign Performance</option>
                <option value="cost_summary">Cost Summary</option>
                <option value="ab_test_results">A/B Test Results</option>
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Start from Template (Optional)
              </label>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {templates.filter(t => t.is_system_template).map((template) => (
                  <div
                    key={template.id}
                    onClick={() => setSelectedTemplate(template)}
                    className={`p-4 border-2 rounded-lg cursor-pointer transition ${
                      selectedTemplate?.id === template.id
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <h3 className="font-semibold text-gray-900">{template.name}</h3>
                    <p className="text-sm text-gray-600 mt-1">{template.description}</p>
                    <span className="inline-block mt-2 text-xs bg-gray-100 px-2 py-1 rounded">
                      {template.report_type}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Step 2: Query Configuration */}
        {currentStep === 2 && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Step 2: Query Configuration</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Data Source *
              </label>
              <select
                value={selectedTable}
                onChange={(e) => {
                  setSelectedTable(e.target.value);
                  setSelectedColumns([]);
                }}
                className="w-full border border-gray-300 rounded-lg px-4 py-2"
              >
                {availableTables.map((table) => (
                  <option key={table.value} value={table.value}>
                    {table.label}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Columns to Include *
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-2">
                {getCurrentTableColumns().map((column) => (
                  <label key={column} className="flex items-center space-x-2">
                    <input
                      type="checkbox"
                      checked={selectedColumns.includes(column)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setSelectedColumns([...selectedColumns, column]);
                        } else {
                          setSelectedColumns(selectedColumns.filter(c => c !== column));
                        }
                      }}
                      className="rounded"
                    />
                    <span className="text-sm">{column}</span>
                  </label>
                ))}
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Filters
              </label>
              {filters.map((filter, index) => (
                <div key={index} className="flex gap-2 mb-2">
                  <select
                    value={filter.column}
                    onChange={(e) => updateFilter(index, 'column', e.target.value)}
                    className="border border-gray-300 rounded px-3 py-2 flex-1"
                  >
                    <option value="">Select column...</option>
                    {getCurrentTableColumns().map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                  <select
                    value={filter.operator}
                    onChange={(e) => updateFilter(index, 'operator', e.target.value)}
                    className="border border-gray-300 rounded px-3 py-2"
                  >
                    {operators.map(op => (
                      <option key={op.value} value={op.value}>{op.label}</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={filter.value as string}
                    onChange={(e) => updateFilter(index, 'value', e.target.value)}
                    className="border border-gray-300 rounded px-3 py-2 flex-1"
                    placeholder="Value"
                  />
                  <button
                    onClick={() => removeFilter(index)}
                    className="px-3 py-2 text-red-600 hover:bg-red-50 rounded"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                onClick={addFilter}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                + Add Filter
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Aggregations
              </label>
              {aggregations.map((agg, index) => (
                <div key={index} className="flex gap-2 mb-2">
                  <select
                    value={agg.function}
                    onChange={(e) => updateAggregation(index, 'function', e.target.value)}
                    className="border border-gray-300 rounded px-3 py-2"
                  >
                    {aggregationFunctions.map(fn => (
                      <option key={fn.value} value={fn.value}>{fn.label}</option>
                    ))}
                  </select>
                  <select
                    value={agg.column}
                    onChange={(e) => updateAggregation(index, 'column', e.target.value)}
                    className="border border-gray-300 rounded px-3 py-2 flex-1"
                  >
                    <option value="">Select column...</option>
                    {getCurrentTableColumns().map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                  <input
                    type="text"
                    value={agg.alias || ''}
                    onChange={(e) => updateAggregation(index, 'alias', e.target.value)}
                    className="border border-gray-300 rounded px-3 py-2 flex-1"
                    placeholder="Alias (optional)"
                  />
                  <button
                    onClick={() => removeAggregation(index)}
                    className="px-3 py-2 text-red-600 hover:bg-red-50 rounded"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                onClick={addAggregation}
                className="text-blue-600 hover:text-blue-700 text-sm font-medium"
              >
                + Add Aggregation
              </button>
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                Limit
              </label>
              <input
                type="number"
                value={limit}
                onChange={(e) => setLimit(parseInt(e.target.value) || 100)}
                className="w-40 border border-gray-300 rounded-lg px-4 py-2"
                min={1}
                max={10000}
              />
            </div>
          </div>
        )}

        {/* Step 3: Visualization */}
        {currentStep === 3 && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Step 3: Visualization Settings</h2>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-3">
                Chart Type
              </label>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4">
                {chartTypes.map((type) => (
                  <div
                    key={type.value}
                    onClick={() => setChartType(type.value)}
                    className={`p-4 border-2 rounded-lg cursor-pointer transition ${
                      chartType === type.value
                        ? 'border-blue-600 bg-blue-50'
                        : 'border-gray-200 hover:border-blue-300'
                    }`}
                  >
                    <div className="text-3xl mb-2">{type.icon}</div>
                    <p className="font-medium">{type.label}</p>
                  </div>
                ))}
              </div>
            </div>

            {chartType !== 'table' && (
              <>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    X-Axis Column
                  </label>
                  <select
                    value={xAxis}
                    onChange={(e) => setXAxis(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-4 py-2"
                  >
                    <option value="">Select column...</option>
                    {selectedColumns.map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    Y-Axis Column
                  </label>
                  <select
                    value={yAxis}
                    onChange={(e) => setYAxis(e.target.value)}
                    className="w-full border border-gray-300 rounded-lg px-4 py-2"
                  >
                    <option value="">Select column...</option>
                    {selectedColumns.map(col => (
                      <option key={col} value={col}>{col}</option>
                    ))}
                  </select>
                </div>
              </>
            )}
          </div>
        )}

        {/* Step 4: Preview & Generate */}
        {currentStep === 4 && (
          <div className="space-y-6">
            <h2 className="text-xl font-semibold">Step 4: Preview & Generate</h2>

            <div className="bg-gray-50 p-4 rounded-lg">
              <h3 className="font-semibold mb-2">Report Summary</h3>
              <dl className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-gray-600">Name:</dt>
                  <dd className="font-medium">{reportName || 'Untitled Report'}</dd>
                </div>
                <div>
                  <dt className="text-gray-600">Type:</dt>
                  <dd className="font-medium">{reportType}</dd>
                </div>
                <div>
                  <dt className="text-gray-600">Data Source:</dt>
                  <dd className="font-medium">{selectedTable}</dd>
                </div>
                <div>
                  <dt className="text-gray-600">Columns:</dt>
                  <dd className="font-medium">{selectedColumns.length}</dd>
                </div>
                <div>
                  <dt className="text-gray-600">Filters:</dt>
                  <dd className="font-medium">{filters.length}</dd>
                </div>
                <div>
                  <dt className="text-gray-600">Chart Type:</dt>
                  <dd className="font-medium">{chartType}</dd>
                </div>
              </dl>
            </div>

            <div>
              <button
                onClick={handlePreview}
                disabled={loading || selectedColumns.length === 0}
                className="bg-blue-600 text-white px-6 py-2 rounded-lg hover:bg-blue-700 disabled:opacity-50"
              >
                {loading ? 'Loading Preview...' : 'Generate Preview'}
              </button>
            </div>

            {previewData.length > 0 && (
              <div className="border rounded-lg overflow-hidden">
                <div className="bg-gray-50 px-4 py-2 border-b">
                  <p className="text-sm font-medium">Preview Results ({previewData.length} rows)</p>
                </div>
                <div className="overflow-x-auto">
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        {previewColumns.map((col) => (
                          <th key={col} className="px-4 py-2 text-left text-xs font-medium text-gray-700 uppercase">
                            {col}
                          </th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {previewData.slice(0, 10).map((row, idx) => (
                        <tr key={idx}>
                          {previewColumns.map((col) => (
                            <td key={col} className="px-4 py-2 text-sm text-gray-900">
                              {String(row[col] || '')}
                            </td>
                          ))}
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            <div className="border-t pt-6 mt-6">
              <h3 className="font-semibold mb-4">Actions</h3>
              <div className="flex gap-4">
                <button
                  onClick={handleSaveTemplate}
                  disabled={loading || !reportName || selectedColumns.length === 0}
                  className="bg-green-600 text-white px-6 py-2 rounded-lg hover:bg-green-700 disabled:opacity-50"
                >
                  Save Template
                </button>
                <button
                  onClick={() => handleExport('csv')}
                  disabled={loading || selectedColumns.length === 0}
                  className="bg-gray-600 text-white px-6 py-2 rounded-lg hover:bg-gray-700 disabled:opacity-50"
                >
                  Export CSV
                </button>
                <button
                  onClick={() => handleExport('xlsx')}
                  disabled={loading || selectedColumns.length === 0}
                  className="bg-gray-600 text-white px-6 py-2 rounded-lg hover:bg-gray-700 disabled:opacity-50"
                >
                  Export Excel
                </button>
                <button
                  onClick={() => handleExport('pdf')}
                  disabled={loading || selectedColumns.length === 0}
                  className="bg-gray-600 text-white px-6 py-2 rounded-lg hover:bg-gray-700 disabled:opacity-50"
                >
                  Export PDF
                </button>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Navigation */}
      <div className="flex justify-between mt-6">
        <button
          onClick={handleBack}
          disabled={currentStep === 1}
          className="px-6 py-2 border border-gray-300 rounded-lg hover:bg-gray-50 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          Back
        </button>
        <button
          onClick={handleNext}
          disabled={currentStep === 4 || (currentStep === 1 && !reportName) || (currentStep === 2 && selectedColumns.length === 0)}
          className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {currentStep === 4 ? 'Complete' : 'Next'}
        </button>
      </div>
    </div>
  );
};

export default ReportBuilder;
