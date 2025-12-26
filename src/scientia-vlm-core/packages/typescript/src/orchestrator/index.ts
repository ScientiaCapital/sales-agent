/**
 * Multi-Provider VLM Orchestrator
 *
 * The brain of our VLM stack. Routes requests to the optimal provider
 * based on project config, handles fallbacks, and tracks everything.
 *
 * @module @scientia/vlm-core/orchestrator
 * @version 1.0.0
 */

import type {
  VLMProvider,
  OrchestratorRequest,
  OrchestratorResponse,
  ProviderHealth,
} from './types';
import { getProjectConfig, getModelCost } from './project-configs';
import { vlmAnalytics, recordFromResponse } from './analytics';

/**
 * Provider client interface
 */
interface ProviderClient {
  analyze(
    image: string,
    imageType: 'base64' | 'url',
    mimeType: string,
    prompt: string,
    model: string,
  ): Promise<{
    data: Record<string, unknown>;
    inputTokens: number;
    outputTokens: number;
    latencyMs: number;
  }>;
}

/**
 * Provider clients registry
 */
const providerClients: Map<VLMProvider, ProviderClient> = new Map();

/**
 * Provider health tracking
 */
const providerHealth: Map<VLMProvider, ProviderHealth> = new Map();

/**
 * Initialize provider health
 */
function initializeHealth(): void {
  const providers: VLMProvider[] = ['openrouter', 'anthropic', 'google', 'deepseek'];
  providers.forEach(provider => {
    providerHealth.set(provider, {
      provider,
      status: 'healthy',
      lastCheck: new Date(),
      errorRate: 0,
      avgLatencyMs: 0,
    });
  });
}

initializeHealth();

/**
 * Register a provider client
 */
export function registerProvider(provider: VLMProvider, client: ProviderClient): void {
  providerClients.set(provider, client);
}

/**
 * Calculate confidence score from VLM response
 */
function calculateConfidence(data: Record<string, unknown>): number {
  // If model returned confidence, use it
  if (typeof data.confidence === 'number') {
    return data.confidence;
  }

  // Calculate based on completeness of fields
  const fields = Object.keys(data);
  const nonNullFields = fields.filter(f => data[f] !== null && data[f] !== undefined);
  const completeness = nonNullFields.length / Math.max(fields.length, 1);

  // Base confidence on completeness
  return Math.min(0.95, 0.5 + (completeness * 0.45));
}

/**
 * Update provider health after a call
 */
function updateHealth(
  provider: VLMProvider,
  success: boolean,
  latencyMs: number,
): void {
  const health = providerHealth.get(provider);
  if (!health) return;

  // Rolling average for error rate (last 100 calls approximation)
  const weight = 0.01;
  health.errorRate = health.errorRate * (1 - weight) + (success ? 0 : 1) * weight;

  // Rolling average for latency
  health.avgLatencyMs = health.avgLatencyMs * 0.9 + latencyMs * 0.1;

  // Update status
  if (health.errorRate > 0.5) {
    health.status = 'down';
  } else if (health.errorRate > 0.1) {
    health.status = 'degraded';
  } else {
    health.status = 'healthy';
  }

  health.lastCheck = new Date();
}

/**
 * Main orchestrator function
 *
 * Routes requests through the provider chain based on project config.
 */
export async function orchestrate(
  projectId: string,
  request: OrchestratorRequest,
): Promise<OrchestratorResponse> {
  const startTime = Date.now();

  // Get project config
  const config = request.overrides
    ? { ...getProjectConfig(projectId), ...request.overrides }
    : getProjectConfig(projectId);

  // Build provider chain: primary + fallbacks
  const providerChain = [
    { provider: config.primaryProvider, model: config.primaryModel, triggerOn: 'primary' as const },
    ...config.fallbackChain,
  ];

  let lastError: Error | null = null;
  let usedFallback = false;
  let fallbackReason: string | undefined;

  // Try each provider in chain
  for (let i = 0; i < providerChain.length; i++) {
    const { provider, model } = providerChain[i] as {
      provider: VLMProvider;
      model: string;
      triggerOn: string;
    };

    // Skip if provider is down
    const health = providerHealth.get(provider);
    if (health?.status === 'down' && i < providerChain.length - 1) {
      continue;
    }

    // Get provider client
    const client = providerClients.get(provider);
    if (!client) {
      console.warn(`No client registered for provider: ${provider}`);
      continue;
    }

    try {
      // Make the call
      const callStart = Date.now();
      const result = await client.analyze(
        request.image,
        request.imageType,
        request.mimeType,
        request.prompt,
        model,
      );
      const latencyMs = Date.now() - callStart;

      // Update health
      updateHealth(provider, true, latencyMs);

      // Calculate confidence
      const confidence = calculateConfidence(result.data);

      // Check if we should fallback due to low confidence
      const nextItem = providerChain[i + 1] as { triggerOn?: string } | undefined;
      if (
        confidence < 0.7 &&
        i < providerChain.length - 1 &&
        nextItem?.triggerOn === 'low_confidence'
      ) {
        usedFallback = true;
        fallbackReason = `Low confidence (${(confidence * 100).toFixed(1)}%) from ${model}`;
        continue;
      }

      // Calculate cost
      const modelCost = getModelCost(provider, model);
      const totalCost = modelCost; // Flat rate models

      // Build response
      const response: OrchestratorResponse = {
        data: result.data,
        provider,
        model,
        usedFallback,
        fallbackReason,
        confidence,
        cost: {
          inputTokens: result.inputTokens,
          outputTokens: result.outputTokens,
          totalCost,
        },
        latencyMs: Date.now() - startTime,
      };

      // Record for analytics
      recordFromResponse(response, projectId, request.mimeType);

      return response;
    } catch (error) {
      lastError = error as Error;
      updateHealth(provider, false, Date.now() - startTime);

      // If this was primary, mark that we're using fallback
      if (i === 0) {
        usedFallback = true;
        fallbackReason = `Error from ${model}: ${(error as Error).message}`;
      }

      console.error(`Provider ${provider}/${model} failed:`, error);
    }
  }

  // All providers failed
  throw new Error(
    `All providers failed for project ${projectId}. Last error: ${lastError?.message}`,
  );
}

/**
 * Quick analyze - uses project defaults
 */
export async function analyze(
  projectId: string,
  image: string,
  prompt: string,
  imageType: 'base64' | 'url' = 'base64',
  mimeType: 'image/png' | 'image/jpeg' | 'image/webp' = 'image/jpeg',
): Promise<OrchestratorResponse> {
  return orchestrate(projectId, {
    image,
    imageType,
    mimeType,
    prompt,
  });
}

/**
 * Get provider health status
 */
export function getProviderHealth(): Map<VLMProvider, ProviderHealth> {
  return new Map(providerHealth);
}

/**
 * Get analytics instance
 */
export function getAnalytics() {
  return vlmAnalytics;
}

/**
 * Export types
 */
export * from './types';
export * from './project-configs';
export * from './analytics';
