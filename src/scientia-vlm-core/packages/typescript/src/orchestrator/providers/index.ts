/**
 * VLM Provider Implementations
 *
 * All provider clients for the multi-provider orchestrator.
 *
 * @module @scientia/vlm-core/orchestrator/providers
 */

export * from './openrouter';
export * from './anthropic';
export * from './google';

// Re-export create functions for convenience
import { createOpenRouterClient, OpenRouterClient } from './openrouter';
import { createAnthropicClient, AnthropicClient } from './anthropic';
import { createGoogleClient, GoogleClient } from './google';

/**
 * Create all provider clients from environment variables
 */
export function createAllClients(): {
  openrouter?: OpenRouterClient;
  anthropic?: AnthropicClient;
  google?: GoogleClient;
} {
  const clients: {
    openrouter?: OpenRouterClient;
    anthropic?: AnthropicClient;
    google?: GoogleClient;
  } = {};

  // OpenRouter (Chinese VLMs)
  if (process.env.OPENROUTER_API_KEY) {
    clients.openrouter = createOpenRouterClient();
  }

  // Anthropic Direct (Claude)
  if (process.env.ANTHROPIC_API_KEY) {
    clients.anthropic = createAnthropicClient();
  }

  // Google (Gemini)
  if (process.env.GOOGLE_API_KEY) {
    clients.google = createGoogleClient();
  }

  return clients;
}

/**
 * Provider cost comparison (per typical VLM call)
 *
 * This is what VCs see when they ask "why Chinese VLMs?"
 */
export const PROVIDER_COST_COMPARISON = {
  // Our stack (Chinese VLMs via OpenRouter)
  fieldvault: {
    primary: { model: 'qwen/qwen3-vl-30b-a3b-instruct', costPerCall: 0.00022 },
    fallback: { model: 'qwen/qwen-vl-max', costPerCall: 0.00073 },
    specialist: { model: 'z-ai/glm-4.6v', costPerCall: 0.00110 },
    emergency: { model: 'claude-3-5-haiku-20241022', costPerCall: 0.0037 },
    blendedAverage: 0.00024,  // Based on 97% primary, 2.5% fallback, 0.5% emergency
  },

  // Western alternatives (what competitors would use)
  western: {
    anthropicHaiku: { model: 'claude-3-5-haiku-20241022', costPerCall: 0.0037 },
    anthropicSonnet: { model: 'claude-sonnet-4-5-20250514', costPerCall: 0.0111 },
    anthropicOpus: { model: 'claude-opus-4-5-20250514', costPerCall: 0.0185 },
    geminiFlash: { model: 'gemini-2.5-flash', costPerCall: 0.0006 },
    geminiPro: { model: 'gemini-2.5-pro', costPerCall: 0.0100 },
  },

  // Cost multipliers (how many times more expensive vs our primary)
  multipliers: {
    vsHaiku: 16.8,      // Claude Haiku is 16.8x more expensive
    vsSonnet: 50.5,     // Claude Sonnet is 50.5x more expensive
    vsOpus: 84.1,       // Claude Opus is 84.1x more expensive
    vsGeminiFlash: 2.7, // Gemini Flash is 2.7x more expensive
    vsGeminiPro: 45.5,  // Gemini Pro is 45.5x more expensive
  },

  // Margin analysis (if we price at competitor parity)
  margins: {
    atHaikuParity: 0.935,   // 93.5% gross margin at Haiku pricing
    atGeminiParity: 0.633,  // 63.3% gross margin at Gemini pricing
    competitorMargin: 0.30, // Competitors running Haiku/Sonnet have ~30% margins
  },
} as const;

/**
 * Provider selection guidance
 */
export const PROVIDER_SELECTION = {
  // High volume, cost-sensitive
  budget: {
    description: 'High volume extraction where cost matters most',
    recommended: ['openrouter:qwen/qwen3-vl-30b-a3b-instruct'],
    useCase: 'FieldVault blueprints, NetZero documents',
  },

  // Balanced
  balanced: {
    description: 'Good balance of cost and reliability',
    recommended: ['openrouter:qwen/qwen-vl-max', 'google:gemini-2.5-flash'],
    useCase: 'Medium volume, mixed document types',
  },

  // Premium/Enterprise
  premium: {
    description: 'Maximum reliability for enterprise clients',
    recommended: ['anthropic:claude-sonnet-4-5-20250514', 'google:gemini-2.5-pro'],
    useCase: 'High-stakes analysis, regulatory compliance',
  },

  // Specialist tasks
  specialist: {
    description: 'Specific model strengths',
    chartAnalysis: 'openrouter:z-ai/glm-4.6v',      // GLM excels at charts
    complexReasoning: 'anthropic:claude-opus-4-5',  // Opus for complex tasks
    fastIteration: 'google:gemini-2.5-flash',       // Gemini for speed
  },
} as const;
