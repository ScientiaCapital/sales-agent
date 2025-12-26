/**
 * Utility functions for VLM AI Core
 *
 * @module utils
 */

// Context Compaction - Token management for large contexts
export {
  compactContext,
  autoCompactIfNeeded,
  estimateTokenCount,
  estimateMessagesTokenCount,
  shouldCompact,
  type Message,
  type CompactionOptions,
  type CompactionResult
} from './context-compaction';
