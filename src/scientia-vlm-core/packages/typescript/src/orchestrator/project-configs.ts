/**
 * Project-Specific VLM Configurations
 *
 * Each Scientia Capital project can have its own provider strategy.
 * This allows us to:
 * - Use Chinese VLMs where cost matters most
 * - Use Anthropic/Google where reliability is critical
 * - Mix providers based on task type
 *
 * @module @scientia/vlm-core/orchestrator
 * @version 1.0.0
 */

import type { ProjectConfig, VLMProvider } from './types';

/**
 * FieldVault.ai - Construction Document Extraction
 *
 * Strategy: Chinese VLMs primary (cost), Anthropic fallback (reliability)
 * Use case: High volume blueprint/photo analysis
 */
export const FIELDVAULT_CONFIG: ProjectConfig = {
  projectId: 'fieldvault-ai',
  name: 'FieldVault.ai',
  primaryProvider: 'openrouter',
  primaryModel: 'qwen/qwen3-vl-30b-a3b-instruct',
  fallbackChain: [
    {
      provider: 'openrouter',
      model: 'qwen/qwen-vl-max',
      triggerOn: 'low_confidence',
    },
    {
      provider: 'openrouter',
      model: 'z-ai/glm-4.6v',
      triggerOn: 'low_confidence',  // For charts/legends
    },
    {
      provider: 'anthropic',
      model: 'claude-3-5-haiku-20241022',
      triggerOn: 'error',  // Emergency fallback
    },
  ],
  budget: {
    maxCostPerCall: 0.05,  // Cap at 5 cents
    maxMonthlyCost: 500,
  },
  features: {
    usePreprocessing: true,
    useROIDetection: true,
    useConfidenceScoring: true,
  },
};

/**
 * NetZero Projects - Sustainability Analysis
 *
 * Strategy: Chinese VLMs for document extraction, DeepSeek for text
 * Use case: Emissions reports, sustainability documents
 */
export const NETZERO_CONFIG: ProjectConfig = {
  projectId: 'netzero-expert',
  name: 'NetZero Expert',
  primaryProvider: 'openrouter',
  primaryModel: 'qwen/qwen3-vl-30b-a3b-instruct',
  fallbackChain: [
    {
      provider: 'openrouter',
      model: 'qwen/qwen-vl-max',
      triggerOn: 'low_confidence',
    },
    {
      provider: 'google',
      model: 'gemini-2.5-flash',
      triggerOn: 'error',  // Google as backup
    },
  ],
  budget: {
    maxCostPerCall: 0.02,
    maxMonthlyCost: 200,
  },
  features: {
    usePreprocessing: true,
    useROIDetection: false,
    useConfidenceScoring: true,
  },
};

/**
 * SolarAppraisal.ai - Solar Panel Analysis
 *
 * Strategy: Chinese VLMs primary, specialized for solar imagery
 * Use case: Panel detection, shade analysis, defect identification
 */
export const SOLARAPPRAISAL_CONFIG: ProjectConfig = {
  projectId: 'solarappraisal-ai',
  name: 'SolarAppraisal.ai',
  primaryProvider: 'openrouter',
  primaryModel: 'qwen/qwen3-vl-30b-a3b-instruct',
  fallbackChain: [
    {
      provider: 'openrouter',
      model: 'qwen/qwen-vl-max',
      triggerOn: 'low_confidence',
    },
    {
      provider: 'anthropic',
      model: 'claude-3-5-haiku-20241022',
      triggerOn: 'error',
    },
  ],
  budget: {
    maxCostPerCall: 0.03,
    maxMonthlyCost: 300,
  },
  features: {
    usePreprocessing: true,
    useROIDetection: true,  // Important for panel detection
    useConfidenceScoring: true,
  },
};

/**
 * Sales Agent - B2B Outreach
 *
 * Strategy: Text-focused, DeepSeek primary for reasoning
 * Use case: Email generation, company research
 */
export const SALES_AGENT_CONFIG: ProjectConfig = {
  projectId: 'sales-agent',
  name: 'Sales Agent',
  primaryProvider: 'deepseek',
  primaryModel: 'deepseek-chat-v3.1',
  fallbackChain: [
    {
      provider: 'anthropic',
      model: 'claude-3-5-haiku-20241022',
      triggerOn: 'error',
    },
  ],
  budget: {
    maxCostPerCall: 0.01,
    maxMonthlyCost: 100,
  },
  features: {
    usePreprocessing: false,  // No images
    useROIDetection: false,
    useConfidenceScoring: false,
  },
};

/**
 * Premium Project Template
 *
 * For projects that need highest reliability (e.g., enterprise clients)
 * Strategy: Anthropic primary, Google fallback
 */
export const PREMIUM_CONFIG: ProjectConfig = {
  projectId: 'premium-template',
  name: 'Premium Template',
  primaryProvider: 'anthropic',
  primaryModel: 'claude-sonnet-4-5-20250514',
  fallbackChain: [
    {
      provider: 'google',
      model: 'gemini-2.5-pro',
      triggerOn: 'error',
    },
    {
      provider: 'anthropic',
      model: 'claude-opus-4-5-20250514',
      triggerOn: 'low_confidence',  // Premium fallback for complex tasks
    },
  ],
  budget: {
    maxCostPerCall: 0.50,  // Higher budget for premium
    maxMonthlyCost: 2000,
  },
  features: {
    usePreprocessing: true,
    useROIDetection: true,
    useConfidenceScoring: true,
  },
};

/**
 * Budget Project Template
 *
 * For high-volume, cost-sensitive projects
 * Strategy: Cheapest Chinese VLMs only
 */
export const BUDGET_CONFIG: ProjectConfig = {
  projectId: 'budget-template',
  name: 'Budget Template',
  primaryProvider: 'openrouter',
  primaryModel: 'qwen/qwen2.5-vl-72b-instruct',  // Cheapest
  fallbackChain: [
    {
      provider: 'openrouter',
      model: 'qwen/qwen3-vl-30b-a3b-instruct',
      triggerOn: 'low_confidence',
    },
    {
      provider: 'google',
      model: 'gemini-2.0-flash-lite',
      triggerOn: 'error',  // Cheapest Western fallback
    },
  ],
  budget: {
    maxCostPerCall: 0.005,  // Very tight budget
    maxMonthlyCost: 50,
  },
  features: {
    usePreprocessing: false,  // Save on compute
    useROIDetection: false,
    useConfidenceScoring: true,
  },
};

/**
 * All project configurations
 */
export const PROJECT_CONFIGS: Record<string, ProjectConfig> = {
  'fieldvault-ai': FIELDVAULT_CONFIG,
  'netzero-expert': NETZERO_CONFIG,
  'netzero-calculator': { ...NETZERO_CONFIG, projectId: 'netzero-calculator', name: 'NetZero Calculator' },
  'netzero-bot': { ...NETZERO_CONFIG, projectId: 'netzero-bot', name: 'NetZero Bot' },
  'solarappraisal-ai': SOLARAPPRAISAL_CONFIG,
  'sales-agent': SALES_AGENT_CONFIG,
  'premium': PREMIUM_CONFIG,
  'budget': BUDGET_CONFIG,
};

/**
 * Get config for a project
 */
export function getProjectConfig(projectId: string): ProjectConfig {
  return PROJECT_CONFIGS[projectId] || BUDGET_CONFIG;
}

/**
 * Provider pricing reference (updated Dec 2025)
 *
 * This data powers cost calculations and budget enforcement.
 */
export const PROVIDER_PRICING = {
  openrouter: {
    'qwen/qwen3-vl-30b-a3b-instruct': { input: 0.00022, output: 0, perCall: 0.00022 },
    'qwen/qwen-vl-max': { input: 0.00073, output: 0, perCall: 0.00073 },
    'z-ai/glm-4.6v': { input: 0.00110, output: 0, perCall: 0.00110 },
    'qwen/qwen2.5-vl-72b-instruct': { input: 0.00012, output: 0, perCall: 0.00012 },
  },
  anthropic: {
    'claude-3-5-haiku-20241022': { input: 1.00, output: 5.00, perCall: 0.0037 },
    'claude-sonnet-4-5-20250514': { input: 3.00, output: 15.00, perCall: 0.0111 },
    'claude-opus-4-5-20250514': { input: 5.00, output: 25.00, perCall: 0.0185 },
  },
  google: {
    'gemini-2.5-flash': { input: 0.15, output: 0.60, perCall: 0.0006 },
    'gemini-2.5-pro': { input: 2.00, output: 12.00, perCall: 0.0100 },
    'gemini-2.0-flash-lite': { input: 0.075, output: 0.30, perCall: 0.0003 },
  },
  deepseek: {
    'deepseek-chat-v3.1': { input: 0.14, output: 0.28, perCall: 0.0003 },
    'deepseek-reasoner': { input: 0.55, output: 2.19, perCall: 0.0015 },
  },
} as const;

/**
 * Get estimated cost for a model
 */
export function getModelCost(provider: VLMProvider, model: string): number {
  const providerPricing = PROVIDER_PRICING[provider] as Record<string, { perCall: number }>;
  return providerPricing?.[model]?.perCall || 0.01;  // Default to 1 cent if unknown
}
