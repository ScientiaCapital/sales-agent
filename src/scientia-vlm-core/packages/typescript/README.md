# @scientia/vlm-core

Scientia Capital VLM Stack - Vision Language Model integration with circuit breaker, retry, confidence scoring, and context compaction.

## Features

### Circuit Breaker
Fault-tolerant execution wrapper that prevents cascading failures when VLM services are down.

### Confidence Scoring
Multi-signal confidence aggregation for VLM extractions with configurable thresholds.

### Context Compaction
Proprietary token management system for handling 170K+ token contexts using DeepSeek V3.1 summarization.

## Installation

```bash
npm install @scientia/vlm-core
```

## Usage

### Context Compaction

Automatically manage large conversation contexts by summarizing old messages while preserving recent context:

```typescript
import { autoCompactIfNeeded, type Message } from '@scientia/vlm-core';

// Your conversation history
const messages: Message[] = [
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: 'What is the square root of 144?' },
  { role: 'assistant', content: '12' },
  // ... many more messages
];

// Auto-compact if approaching token limit
const { compactedMessages, wasCompacted, tokensSaved } = await autoCompactIfNeeded(
  messages,
  {
    contextLimit: 170000,           // Claude Opus 4.5 / Qwen VL limit
    compactionThreshold: 0.75,       // Compact at 75% of limit
    preserveRecentCount: 10,         // Keep last 10 messages verbatim
    summarizationModel: 'deepseek/deepseek-chat-v3.1',
    summaryTargetTokens: 500,
  },
  process.env.OPENROUTER_API_KEY
);

if (wasCompacted) {
  console.log(`Saved ${tokensSaved.toLocaleString()} tokens through compaction`);
}

// Use compacted messages for next VLM call
const response = await vlm.chat({
  messages: compactedMessages,
  // ...
});
```

### Circuit Breaker

```typescript
import { CircuitBreaker } from '@scientia/vlm-core';

const breaker = new CircuitBreaker({
  serviceName: 'openrouter',
  failureThreshold: 5,
  resetTimeout: 30000,
});

try {
  const result = await breaker.execute(
    () => callVLMAPI(),
    { serviceName: 'openrouter' }
  );
} catch (error) {
  if (error instanceof CircuitBreakerOpenError) {
    // Use fallback
  }
}
```

### Confidence Scoring

```typescript
import {
  calculateConfidence,
  createVLMSignal,
  createCompletenessSignal
} from '@scientia/vlm-core';

const signals = [
  createVLMSignal(0.85, 'High confidence extraction'),
  createCompletenessSignal(0.9, { requiredFields: 10, filledFields: 9 }),
];

const result = calculateConfidence(signals);

console.log(result.confidence); // 0.875
console.log(result.meetsThreshold); // true (default: 0.7)
console.log(result.description); // "High confidence"
```

## Token Management Strategy

Context compaction uses a three-tier preservation strategy:

1. **System Message**: Always preserved unchanged
2. **Middle Messages**: Summarized using DeepSeek V3.1 ($0.00027/1K tokens)
3. **Recent Messages**: Last N messages kept verbatim for accuracy

This ensures:
- Technical details are preserved
- Recent context is accurate
- Token costs are minimized
- 170K token limit is respected

## License

UNLICENSED - Proprietary Scientia Capital IP
