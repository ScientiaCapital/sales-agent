/**
 * Context Compaction Tests
 */

import { describe, it, expect } from 'vitest';
import {
  estimateTokenCount,
  estimateMessagesTokenCount,
  shouldCompact,
  type Message,
} from './context-compaction';

describe('Context Compaction', () => {
  describe('estimateTokenCount', () => {
    it('should estimate token count using chars/4 approximation', () => {
      const text = 'Hello, world!'; // 13 chars
      const tokens = estimateTokenCount(text);
      expect(tokens).toBe(Math.ceil(13 / 4)); // 4 tokens
    });

    it('should normalize whitespace', () => {
      const text = 'Hello,    world!   '; // Extra spaces
      const normalized = 'Hello, world!'; // 13 chars
      const tokens = estimateTokenCount(text);
      expect(tokens).toBe(Math.ceil(normalized.length / 4));
    });

    it('should handle empty string', () => {
      const tokens = estimateTokenCount('');
      expect(tokens).toBe(0);
    });

    it('should handle long text', () => {
      const text = 'a'.repeat(1000); // 1000 chars
      const tokens = estimateTokenCount(text);
      expect(tokens).toBe(250); // 1000 / 4
    });
  });

  describe('estimateMessagesTokenCount', () => {
    it('should count tokens for message array', () => {
      const messages: Message[] = [
        { role: 'system', content: 'You are helpful.' }, // ~4 content + 2 role + 3 overhead = 9
        { role: 'user', content: 'Hello!' }, // ~2 content + 2 role + 3 overhead = 7
      ];

      const tokens = estimateMessagesTokenCount(messages);
      expect(tokens).toBeGreaterThan(0);
      expect(tokens).toBeLessThan(50); // Sanity check
    });

    it('should handle empty message array', () => {
      const tokens = estimateMessagesTokenCount([]);
      expect(tokens).toBe(0);
    });

    it('should account for role and overhead', () => {
      const message: Message = { role: 'user', content: '' };
      const tokens = estimateMessagesTokenCount([message]);
      // Should be at least 5 (2 role + 3 overhead)
      expect(tokens).toBeGreaterThanOrEqual(5);
    });
  });

  describe('shouldCompact', () => {
    it('should return false when below threshold', () => {
      const messages: Message[] = [
        { role: 'user', content: 'Short message' },
      ];

      const result = shouldCompact(messages, 0.75, 170000);
      expect(result).toBe(false);
    });

    it('should return true when above threshold', () => {
      // Create many large messages to exceed threshold
      const messages: Message[] = Array(1000).fill(null).map(() => ({
        role: 'user',
        content: 'a'.repeat(1000), // 250 tokens each
      }));

      const result = shouldCompact(messages, 0.01, 1000); // Very low threshold
      expect(result).toBe(true);
    });

    it('should use custom threshold', () => {
      const messages: Message[] = [
        { role: 'user', content: 'a'.repeat(4000) }, // ~1000 tokens
      ];

      // Threshold 0.5 of 1000 = 500 tokens
      const result = shouldCompact(messages, 0.5, 1000);
      expect(result).toBe(true);
    });

    it('should use custom context limit', () => {
      const messages: Message[] = [
        { role: 'user', content: 'a'.repeat(400) }, // ~100 tokens
      ];

      // Threshold 0.75 of 100 = 75 tokens
      const result = shouldCompact(messages, 0.75, 100);
      expect(result).toBe(true);
    });
  });

  describe('Message type', () => {
    it('should accept valid message roles', () => {
      const messages: Message[] = [
        { role: 'system', content: 'System message' },
        { role: 'user', content: 'User message' },
        { role: 'assistant', content: 'Assistant message' },
      ];

      expect(messages).toHaveLength(3);
    });

    it('should support optional timestamp', () => {
      const message: Message = {
        role: 'user',
        content: 'Hello',
        timestamp: new Date().toISOString(),
      };

      expect(message.timestamp).toBeDefined();
    });

    it('should support optional metadata', () => {
      const message: Message = {
        role: 'user',
        content: 'Hello',
        metadata: { source: 'test', confidence: 0.95 },
      };

      expect(message.metadata).toBeDefined();
      expect(message.metadata?.source).toBe('test');
    });
  });
});
