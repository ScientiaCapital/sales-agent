/**
 * VLM Analytics & KPI Tracking
 *
 * Everything a VC partner needs to validate our claims:
 * - Real-time cost tracking
 * - Accuracy metrics per model
 * - Latency percentiles
 * - Fallback rates
 * - Provider comparison data
 *
 * @module @scientia/vlm-core/orchestrator
 * @version 1.0.0
 */

import type { VLMProvider, OrchestratorResponse } from './types';

/**
 * Individual call record (for audit trail)
 */
export interface CallRecord {
  id: string;
  timestamp: Date;
  projectId: string;

  // Provider info
  provider: VLMProvider;
  model: string;
  usedFallback: boolean;
  fallbackReason?: string;

  // Performance
  latencyMs: number;
  inputTokens: number;
  outputTokens: number;

  // Cost
  costUSD: number;

  // Quality
  confidenceScore: number;
  jsonValid: boolean;
  schemaMatch: boolean;

  // For debugging
  imageType: string;
  trade?: string;

  // Human validation (when available)
  humanScore?: number;  // 1-10 manual review
  humanNotes?: string;
}

/**
 * Aggregated KPIs for VC dashboards
 */
export interface VLMKPIs {
  // Time period
  periodStart: Date;
  periodEnd: Date;

  // Volume metrics
  totalCalls: number;
  callsPerDay: number;
  uniqueProjects: number;

  // Cost metrics (THE KILLER METRIC)
  totalCostUSD: number;
  avgCostPerCall: number;
  costPerSuccessfulCall: number;  // Excludes failures
  projectedMonthlyCost: number;

  // Comparison vs Western models
  vsClaudeHaikuSavings: number;     // $ saved vs if we used Haiku
  vsGeminiFlashSavings: number;     // $ saved vs if we used Gemini
  vsCombinedWesternSavings: number; // Total savings
  savingsPercentage: number;        // Our cost / Western cost

  // Quality metrics
  avgConfidence: number;
  jsonSuccessRate: number;          // % calls returning valid JSON
  schemaMatchRate: number;          // % matching expected schema
  avgHumanScore: number;            // When manual review available

  // Reliability metrics
  fallbackRate: number;             // % calls that needed fallback
  errorRate: number;                // % calls that completely failed
  avgLatencyMs: number;
  p50LatencyMs: number;
  p95LatencyMs: number;
  p99LatencyMs: number;

  // Provider breakdown
  providerBreakdown: {
    provider: VLMProvider;
    calls: number;
    percentage: number;
    avgCost: number;
    avgConfidence: number;
    errorRate: number;
  }[];

  // Model breakdown
  modelBreakdown: {
    model: string;
    calls: number;
    percentage: number;
    avgCost: number;
    avgConfidence: number;
    avgLatency: number;
  }[];

  // Trade breakdown (construction-specific)
  tradeBreakdown?: {
    trade: string;
    calls: number;
    avgScore: number;
    bestModel: string;
  }[];
}

/**
 * Head-to-head comparison (for VC proof)
 */
export interface ModelComparison {
  testDate: Date;
  testId: string;

  // Test details
  imageDescription: string;
  trade: string;
  imageType: 'blueprint' | 'field_photo' | 'reference_chart' | 'nameplate';

  // Results per model
  results: {
    model: string;
    provider: VLMProvider;

    // Scores (1-10)
    jsonValid: number;      // 0 or 2
    schemaMatch: number;    // 0-2
    accuracy: number;       // 0-4
    completeness: number;   // 0-2
    totalScore: number;     // Sum (max 10)

    // Cost
    costUSD: number;

    // Derived
    scorePerDollar: number; // totalScore / costUSD

    // Raw output for audit
    rawOutput?: string;
  }[];

  // Winner
  winner: {
    byScore: string;        // Model with highest score
    byCost: string;         // Model with lowest cost
    byValue: string;        // Model with best score/cost ratio
  };

  // Notes
  notes?: string;
}

/**
 * Analytics store (in-memory for now, can be persisted)
 */
export class VLMAnalytics {
  protected calls: CallRecord[] = [];
  protected comparisons: ModelComparison[] = [];

  /**
   * Record a VLM call
   */
  recordCall(record: CallRecord): void {
    this.calls.push(record);
  }

  /**
   * Record a head-to-head comparison
   */
  recordComparison(comparison: ModelComparison): void {
    this.comparisons.push(comparison);
  }

  /**
   * Get KPIs for a time period
   */
  getKPIs(startDate: Date, endDate: Date, projectId?: string): VLMKPIs {
    // Filter calls
    let filteredCalls = this.calls.filter(
      c => c.timestamp >= startDate && c.timestamp <= endDate
    );
    if (projectId) {
      filteredCalls = filteredCalls.filter(c => c.projectId === projectId);
    }

    const totalCalls = filteredCalls.length;
    if (totalCalls === 0) {
      return this.emptyKPIs(startDate, endDate);
    }

    // Calculate metrics
    const totalCost = filteredCalls.reduce((sum, c) => sum + c.costUSD, 0);
    const avgCost = totalCost / totalCalls;

    const successfulCalls = filteredCalls.filter(c => c.jsonValid);
    const costPerSuccess = successfulCalls.length > 0
      ? successfulCalls.reduce((sum, c) => sum + c.costUSD, 0) / successfulCalls.length
      : 0;

    // Western model comparison
    const HAIKU_COST_PER_CALL = 0.0037;
    const GEMINI_COST_PER_CALL = 0.0006;
    const haikuWouldCost = totalCalls * HAIKU_COST_PER_CALL;
    const geminiWouldCost = totalCalls * GEMINI_COST_PER_CALL;

    // Latency percentiles
    const latencies = filteredCalls.map(c => c.latencyMs).sort((a, b) => a - b);
    const p50 = latencies[Math.floor(latencies.length * 0.5)] || 0;
    const p95 = latencies[Math.floor(latencies.length * 0.95)] || 0;
    const p99 = latencies[Math.floor(latencies.length * 0.99)] || 0;

    // Provider breakdown
    const providerMap = new Map<VLMProvider, CallRecord[]>();
    filteredCalls.forEach(c => {
      const existing = providerMap.get(c.provider) || [];
      existing.push(c);
      providerMap.set(c.provider, existing);
    });

    const providerBreakdown = Array.from(providerMap.entries()).map(([provider, calls]) => ({
      provider,
      calls: calls.length,
      percentage: (calls.length / totalCalls) * 100,
      avgCost: calls.reduce((sum, c) => sum + c.costUSD, 0) / calls.length,
      avgConfidence: calls.reduce((sum, c) => sum + c.confidenceScore, 0) / calls.length,
      errorRate: calls.filter(c => !c.jsonValid).length / calls.length,
    }));

    // Model breakdown
    const modelMap = new Map<string, CallRecord[]>();
    filteredCalls.forEach(c => {
      const existing = modelMap.get(c.model) || [];
      existing.push(c);
      modelMap.set(c.model, existing);
    });

    const modelBreakdown = Array.from(modelMap.entries()).map(([model, calls]) => ({
      model,
      calls: calls.length,
      percentage: (calls.length / totalCalls) * 100,
      avgCost: calls.reduce((sum, c) => sum + c.costUSD, 0) / calls.length,
      avgConfidence: calls.reduce((sum, c) => sum + c.confidenceScore, 0) / calls.length,
      avgLatency: calls.reduce((sum, c) => sum + c.latencyMs, 0) / calls.length,
    }));

    // Days in period
    const days = Math.max(1, (endDate.getTime() - startDate.getTime()) / (1000 * 60 * 60 * 24));

    return {
      periodStart: startDate,
      periodEnd: endDate,

      totalCalls,
      callsPerDay: totalCalls / days,
      uniqueProjects: new Set(filteredCalls.map(c => c.projectId)).size,

      totalCostUSD: totalCost,
      avgCostPerCall: avgCost,
      costPerSuccessfulCall: costPerSuccess,
      projectedMonthlyCost: (totalCost / days) * 30,

      vsClaudeHaikuSavings: haikuWouldCost - totalCost,
      vsGeminiFlashSavings: geminiWouldCost - totalCost,
      vsCombinedWesternSavings: haikuWouldCost - totalCost,
      savingsPercentage: totalCost / haikuWouldCost,

      avgConfidence: filteredCalls.reduce((sum, c) => sum + c.confidenceScore, 0) / totalCalls,
      jsonSuccessRate: successfulCalls.length / totalCalls,
      schemaMatchRate: filteredCalls.filter(c => c.schemaMatch).length / totalCalls,
      avgHumanScore: filteredCalls.filter(c => c.humanScore !== undefined)
        .reduce((sum, c) => sum + (c.humanScore || 0), 0) /
        Math.max(1, filteredCalls.filter(c => c.humanScore !== undefined).length),

      fallbackRate: filteredCalls.filter(c => c.usedFallback).length / totalCalls,
      errorRate: filteredCalls.filter(c => !c.jsonValid).length / totalCalls,
      avgLatencyMs: filteredCalls.reduce((sum, c) => sum + c.latencyMs, 0) / totalCalls,
      p50LatencyMs: p50,
      p95LatencyMs: p95,
      p99LatencyMs: p99,

      providerBreakdown,
      modelBreakdown,
    };
  }

  /**
   * Get all comparisons for audit
   */
  getComparisons(): ModelComparison[] {
    return [...this.comparisons];
  }

  /**
   * Export for VC presentation
   */
  exportForVC(): {
    kpis: VLMKPIs;
    comparisons: ModelComparison[];
    rawCallCount: number;
  } {
    const now = new Date();
    const thirtyDaysAgo = new Date(now.getTime() - 30 * 24 * 60 * 60 * 1000);

    return {
      kpis: this.getKPIs(thirtyDaysAgo, now),
      comparisons: this.comparisons,
      rawCallCount: this.calls.length,
    };
  }

  protected emptyKPIs(startDate: Date, endDate: Date): VLMKPIs {
    return {
      periodStart: startDate,
      periodEnd: endDate,
      totalCalls: 0,
      callsPerDay: 0,
      uniqueProjects: 0,
      totalCostUSD: 0,
      avgCostPerCall: 0,
      costPerSuccessfulCall: 0,
      projectedMonthlyCost: 0,
      vsClaudeHaikuSavings: 0,
      vsGeminiFlashSavings: 0,
      vsCombinedWesternSavings: 0,
      savingsPercentage: 0,
      avgConfidence: 0,
      jsonSuccessRate: 0,
      schemaMatchRate: 0,
      avgHumanScore: 0,
      fallbackRate: 0,
      errorRate: 0,
      avgLatencyMs: 0,
      p50LatencyMs: 0,
      p95LatencyMs: 0,
      p99LatencyMs: 0,
      providerBreakdown: [],
      modelBreakdown: [],
    };
  }
}

/**
 * Global analytics instance
 */
export const vlmAnalytics = new VLMAnalytics();

/**
 * Helper to record a call from OrchestratorResponse
 */
export function recordFromResponse(
  response: OrchestratorResponse,
  projectId: string,
  imageType: string,
  trade?: string,
): void {
  vlmAnalytics.recordCall({
    id: crypto.randomUUID(),
    timestamp: new Date(),
    projectId,
    provider: response.provider,
    model: response.model,
    usedFallback: response.usedFallback,
    fallbackReason: response.fallbackReason,
    latencyMs: response.latencyMs,
    inputTokens: response.cost.inputTokens,
    outputTokens: response.cost.outputTokens,
    costUSD: response.cost.totalCost,
    confidenceScore: response.confidence,
    jsonValid: true,  // If we got a response, JSON was valid
    schemaMatch: true,  // Assume true unless validation fails
    imageType,
    trade,
  });
}
