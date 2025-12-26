/**
 * Context Compaction Module
 *
 * Summarizes conversation history when approaching Claude/Qwen context limits (170k tokens)
 * to maintain system performance and reduce costs.
 *
 * Features:
 * - Token estimation (chars/4 approximation)
 * - Smart summarization using DeepSeek V3.1 (text-only, cheapest)
 * - Preserves recent messages verbatim for accuracy
 * - Configurable compaction thresholds
 */

import OpenAI from 'openai';

// Types
export interface Message {
  role: 'system' | 'user' | 'assistant';
  content: string;
  timestamp?: string;
  metadata?: Record<string, unknown>;
}

export interface CompactionOptions {
  /**
   * Context limit in tokens (default: 170,000 for Claude Opus 4.5/Qwen VL)
   */
  contextLimit?: number;

  /**
   * Start compaction when reaching this percentage of limit (default: 0.75 = 75%)
   */
  compactionThreshold?: number;

  /**
   * Number of recent messages to keep verbatim (default: 10)
   * Preserves the most recent conversation context for accuracy
   */
  preserveRecentCount?: number;

  /**
   * Model to use for summarization (default: deepseek/deepseek-chat-v3.1)
   * Cost: $0.00027/1K tokens (cheapest text model)
   */
  summarizationModel?: string;

  /**
   * Target length for summaries in tokens (default: 500)
   */
  summaryTargetTokens?: number;

  /**
   * Site URL for OpenRouter referer header
   */
  siteUrl?: string;

  /**
   * Application title for OpenRouter
   */
  appTitle?: string;
}

export interface CompactionResult {
  /**
   * Compacted message array with summaries replacing old messages
   */
  compactedMessages: Message[];

  /**
   * Original token count before compaction
   */
  originalTokens: number;

  /**
   * Token count after compaction
   */
  compactedTokens: number;

  /**
   * Number of tokens saved
   */
  tokensSaved: number;

  /**
   * Whether compaction was performed
   */
  wasCompacted: boolean;

  /**
   * Number of messages summarized
   */
  messagesSummarized: number;
}

/**
 * Estimate token count using chars/4 approximation
 * This is a rough estimate - actual tokenization may vary
 *
 * @param text - Text to estimate
 * @returns Estimated token count
 */
export function estimateTokenCount(text: string): number {
  // Remove extra whitespace and normalize
  const normalized = text.trim().replace(/\s+/g, ' ');

  // Average: 1 token ≈ 4 characters for English text
  // This is conservative - real tokenization may differ
  return Math.ceil(normalized.length / 4);
}

/**
 * Estimate total token count for message array
 *
 * @param messages - Message array
 * @returns Total estimated tokens
 */
export function estimateMessagesTokenCount(messages: Message[]): number {
  return messages.reduce((total, msg) => {
    // Count content + role + small overhead for structure
    const contentTokens = estimateTokenCount(msg.content);
    const roleTokens = 2; // "role: user" etc
    const overhead = 3; // JSON structure, commas, etc

    return total + contentTokens + roleTokens + overhead;
  }, 0);
}

/**
 * Check if messages should be compacted based on token count
 *
 * @param messages - Message array to check
 * @param threshold - Compaction threshold (0-1, default 0.75)
 * @param contextLimit - Max context tokens (default 170,000)
 * @returns True if compaction needed
 */
export function shouldCompact(
  messages: Message[],
  threshold: number = 0.75,
  contextLimit: number = 170000
): boolean {
  const currentTokens = estimateMessagesTokenCount(messages);
  const thresholdTokens = contextLimit * threshold;

  console.log(`[ContextCompaction] Current tokens: ${currentTokens.toLocaleString()} / ${contextLimit.toLocaleString()} (${(currentTokens / contextLimit * 100).toFixed(1)}%)`);

  return currentTokens >= thresholdTokens;
}

/**
 * Summarize a batch of messages using DeepSeek V3.1
 *
 * @param messages - Messages to summarize
 * @param openrouterApiKey - OpenRouter API key
 * @param model - Model to use (default: deepseek/deepseek-chat-v3.1)
 * @param targetTokens - Target summary length in tokens
 * @param siteUrl - Site URL for referer header
 * @param appTitle - Application title
 * @returns Summarized text
 */
async function summarizeMessages(
  messages: Message[],
  openrouterApiKey: string,
  model: string = 'deepseek/deepseek-chat-v3.1',
  targetTokens: number = 500,
  siteUrl?: string,
  appTitle?: string
): Promise<string> {
  const openai = new OpenAI({
    baseURL: 'https://openrouter.ai/api/v1',
    apiKey: openrouterApiKey,
    defaultHeaders: {
      'HTTP-Referer': siteUrl || 'https://vlm-ai-core.dev',
      'X-Title': appTitle || 'VLM AI Core - Context Compaction',
    }
  });

  // Format messages as conversation for summarization
  const conversation = messages.map(msg =>
    `[${msg.role.toUpperCase()}]: ${msg.content}`
  ).join('\n\n');

  const summarizationPrompt = `You are a technical summarization assistant for an AI VLM analysis system.

Summarize the following conversation history concisely while preserving:
1. Key technical details (measurements, materials, equipment models)
2. Important decisions and conclusions
3. Context needed to understand subsequent messages

TARGET LENGTH: Approximately ${targetTokens} tokens (~${targetTokens * 4} characters)

CONVERSATION TO SUMMARIZE:
${conversation}

SUMMARY:`;

  try {
    const response = await openai.chat.completions.create({
      model,
      messages: [
        {
          role: 'system',
          content: 'You are a technical summarization expert. Create concise, accurate summaries that preserve critical technical details.'
        },
        {
          role: 'user',
          content: summarizationPrompt
        }
      ],
      temperature: 0.3, // Low temperature for consistency
      max_tokens: targetTokens + 100, // Allow some buffer
    });

    const summary = response.choices[0]?.message?.content || '';

    if (!summary) {
      throw new Error('Empty summary returned from model');
    }

    console.log(`[ContextCompaction] Summarized ${messages.length} messages into ${estimateTokenCount(summary)} tokens`);

    return summary;
  } catch (error) {
    console.error('[ContextCompaction] Summarization error:', error);

    // Fallback: Create a simple text summary if AI fails
    const fallback = `Summary of ${messages.length} messages: ` +
      messages.map(m => m.content.slice(0, 100)).join('; ').slice(0, targetTokens * 4);

    return fallback;
  }
}

/**
 * Compact message context by summarizing old messages
 *
 * Strategy:
 * 1. Keep system message (index 0) unchanged
 * 2. Keep last N messages verbatim for accuracy
 * 3. Summarize everything in between
 *
 * @param messages - Original message array
 * @param options - Compaction options
 * @param openrouterApiKey - OpenRouter API key
 * @returns CompactionResult with compacted messages
 */
export async function compactContext(
  messages: Message[],
  options: CompactionOptions = {},
  openrouterApiKey?: string
): Promise<CompactionResult> {
  const {
    contextLimit = 170000,
    compactionThreshold = 0.75,
    preserveRecentCount = 10,
    summarizationModel = 'deepseek/deepseek-chat-v3.1',
    summaryTargetTokens = 500,
    siteUrl,
    appTitle
  } = options;

  const originalTokens = estimateMessagesTokenCount(messages);

  // Check if compaction needed
  if (!shouldCompact(messages, compactionThreshold, contextLimit)) {
    console.log('[ContextCompaction] No compaction needed');
    return {
      compactedMessages: messages,
      originalTokens,
      compactedTokens: originalTokens,
      tokensSaved: 0,
      wasCompacted: false,
      messagesSummarized: 0
    };
  }

  // Must have API key for summarization
  const apiKey = openrouterApiKey || process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    console.warn('[ContextCompaction] No API key - skipping compaction');
    return {
      compactedMessages: messages,
      originalTokens,
      compactedTokens: originalTokens,
      tokensSaved: 0,
      wasCompacted: false,
      messagesSummarized: 0
    };
  }

  console.log(`[ContextCompaction] Starting compaction (${messages.length} messages, ${originalTokens.toLocaleString()} tokens)`);

  // Strategy: Keep system message + summarize middle + keep recent
  const systemMessage = messages[0]?.role === 'system' ? messages[0] : null;
  const startIndex = systemMessage ? 1 : 0;
  const endIndex = Math.max(startIndex, messages.length - preserveRecentCount);

  // Messages to summarize
  const toSummarize = messages.slice(startIndex, endIndex);

  // Messages to keep verbatim
  const recentMessages = messages.slice(endIndex);

  if (toSummarize.length === 0) {
    // Nothing to summarize - all messages are recent
    console.log('[ContextCompaction] All messages are recent - no compaction needed');
    return {
      compactedMessages: messages,
      originalTokens,
      compactedTokens: originalTokens,
      tokensSaved: 0,
      wasCompacted: false,
      messagesSummarized: 0
    };
  }

  // Summarize old messages
  const summary = await summarizeMessages(
    toSummarize,
    apiKey,
    summarizationModel,
    summaryTargetTokens,
    siteUrl,
    appTitle
  );

  // Create summary message
  const summaryMessage: Message = {
    role: 'system',
    content: `[COMPACTED CONVERSATION HISTORY]\n\n${summary}\n\n[END COMPACTED HISTORY]\n\nThe following messages are the most recent conversation context:`,
    timestamp: new Date().toISOString(),
    metadata: {
      compacted: true,
      originalMessageCount: toSummarize.length,
      compactionTimestamp: new Date().toISOString()
    }
  };

  // Assemble compacted message array
  const compactedMessages: Message[] = [
    ...(systemMessage ? [systemMessage] : []),
    summaryMessage,
    ...recentMessages
  ];

  const compactedTokens = estimateMessagesTokenCount(compactedMessages);
  const tokensSaved = originalTokens - compactedTokens;

  console.log(`[ContextCompaction] Compaction complete:
  - Original: ${messages.length} messages, ${originalTokens.toLocaleString()} tokens
  - Compacted: ${compactedMessages.length} messages, ${compactedTokens.toLocaleString()} tokens
  - Saved: ${tokensSaved.toLocaleString()} tokens (${(tokensSaved / originalTokens * 100).toFixed(1)}%)
  - Summarized: ${toSummarize.length} messages into 1 summary`);

  return {
    compactedMessages,
    originalTokens,
    compactedTokens,
    tokensSaved,
    wasCompacted: true,
    messagesSummarized: toSummarize.length
  };
}

/**
 * Auto-compact context if needed before adding new message
 *
 * Usage pattern for VLM workflows:
 *
 * ```typescript
 * const { compactedMessages } = await autoCompactIfNeeded(
 *   conversationHistory,
 *   { preserveRecentCount: 5 }
 * );
 *
 * // Add new user message
 * const updatedHistory = [
 *   ...compactedMessages,
 *   { role: 'user', content: userPrompt }
 * ];
 * ```
 *
 * @param messages - Current message history
 * @param options - Compaction options
 * @param openrouterApiKey - OpenRouter API key
 * @returns CompactionResult
 */
export async function autoCompactIfNeeded(
  messages: Message[],
  options: CompactionOptions = {},
  openrouterApiKey?: string
): Promise<CompactionResult> {
  return compactContext(messages, options, openrouterApiKey);
}
