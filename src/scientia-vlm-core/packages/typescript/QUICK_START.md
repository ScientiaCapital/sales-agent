# Quick Start - @scientia/vlm-core

## Installation

```bash
npm install @scientia/vlm-core
```

## Context Compaction

### Basic Usage

```typescript
import { autoCompactIfNeeded } from '@scientia/vlm-core';

// Your conversation history
const messages = [
  { role: 'system', content: 'You are a helpful assistant.' },
  { role: 'user', content: 'What is the capital of France?' },
  { role: 'assistant', content: 'The capital of France is Paris.' },
  // ... many more messages
];

// Auto-compact if needed
const { compactedMessages } = await autoCompactIfNeeded(
  messages,
  {},
  process.env.OPENROUTER_API_KEY
);

// Use compacted messages
const response = await vlm.chat({ messages: compactedMessages });
```

### Advanced Usage

```typescript
import {
  compactContext,
  shouldCompact,
  estimateMessagesTokenCount
} from '@scientia/vlm-core';

// Check if compaction needed
const currentTokens = estimateMessagesTokenCount(messages);
console.log(`Current tokens: ${currentTokens.toLocaleString()}`);

if (shouldCompact(messages, 0.75, 170000)) {
  const result = await compactContext(
    messages,
    {
      contextLimit: 170000,
      compactionThreshold: 0.75,
      preserveRecentCount: 10,
      summarizationModel: 'deepseek/deepseek-chat-v3.1',
      summaryTargetTokens: 500,
      siteUrl: 'https://yourapp.com',
      appTitle: 'Your App',
    },
    process.env.OPENROUTER_API_KEY
  );

  console.log(`
    Compacted: ${result.wasCompacted}
    Original: ${result.originalTokens.toLocaleString()} tokens
    Compacted: ${result.compactedTokens.toLocaleString()} tokens
    Saved: ${result.tokensSaved.toLocaleString()} tokens
    Messages summarized: ${result.messagesSummarized}
  `);
}
```

## Circuit Breaker

```typescript
import { CircuitBreaker, CircuitBreakerOpenError } from '@scientia/vlm-core';

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
    console.log('Service down, using fallback');
    // Use fallback logic
  }
}
```

## Confidence Scoring

```typescript
import {
  calculateConfidence,
  createVLMSignal,
  createCompletenessSignal,
} from '@scientia/vlm-core';

const signals = [
  createVLMSignal(0.85, 'High confidence VLM extraction'),
  createCompletenessSignal(0.9, {
    requiredFields: 10,
    filledFields: 9,
  }),
];

const result = calculateConfidence(signals);

console.log(`
  Confidence: ${(result.confidence * 100).toFixed(1)}%
  Meets threshold: ${result.meetsThreshold}
  Description: ${result.description}
`);
```

## Complete Example - Multi-Turn VLM Conversation

```typescript
import {
  autoCompactIfNeeded,
  CircuitBreaker,
  calculateConfidence,
  createVLMSignal,
  type Message,
} from '@scientia/vlm-core';

// Initialize circuit breaker
const breaker = new CircuitBreaker({
  serviceName: 'qwen-vl',
  failureThreshold: 3,
  resetTimeout: 30000,
});

// Conversation state
let messages: Message[] = [
  {
    role: 'system',
    content: 'You are a VLM construction analysis assistant.',
  },
];

async function analyzeImage(imageUrl: string, prompt: string) {
  // Add user message
  messages.push({
    role: 'user',
    content: `${prompt}\n\nImage: ${imageUrl}`,
  });

  // Auto-compact if needed
  const { compactedMessages, wasCompacted, tokensSaved } =
    await autoCompactIfNeeded(
      messages,
      {
        preserveRecentCount: 5,
        summaryTargetTokens: 300,
      },
      process.env.OPENROUTER_API_KEY
    );

  if (wasCompacted) {
    console.log(`Saved ${tokensSaved.toLocaleString()} tokens`);
    messages = compactedMessages;
  }

  // Call VLM with circuit breaker protection
  const response = await breaker.execute(async () => {
    const result = await fetch('https://openrouter.ai/api/v1/chat/completions', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${process.env.OPENROUTER_API_KEY}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        model: 'qwen/qwen2.5-vl-72b-instruct',
        messages: compactedMessages,
      }),
    });

    return result.json();
  });

  // Calculate confidence
  const confidence = calculateConfidence([
    createVLMSignal(0.85, 'VLM extraction'),
  ]);

  // Add assistant response
  messages.push({
    role: 'assistant',
    content: response.choices[0].message.content,
    metadata: { confidence: confidence.confidence },
  });

  return {
    content: response.choices[0].message.content,
    confidence: confidence.confidence,
  };
}

// Use it
const result = await analyzeImage(
  'https://example.com/blueprint.jpg',
  'Extract dimensions from this blueprint'
);

console.log(result);
```

## Environment Variables

```bash
# Required for context compaction
OPENROUTER_API_KEY=sk-or-v1-...
```

## TypeScript Support

All exports are fully typed:

```typescript
import type {
  Message,
  CompactionOptions,
  CompactionResult,
  CircuitBreakerConfig,
  ConfidenceSignal,
  ConfidenceResult,
} from '@scientia/vlm-core';
```

## Cost Optimization

**DeepSeek V3.1 Summarization:**
- Input: $0.00027/1K tokens
- Output: $0.00055/1K tokens

**Example:**
- 100 messages (50K tokens) → 500 token summary
- Cost: ~$0.014
- Token reduction: 99%

## Best Practices

1. **Set appropriate thresholds** - Start with 0.75 (75%)
2. **Preserve recent messages** - Keep 10+ for accuracy
3. **Monitor compaction events** - Log when compaction occurs
4. **Use circuit breaker** - Always wrap external API calls
5. **Check confidence scores** - Validate VLM outputs

## License

UNLICENSED - Proprietary Scientia Capital IP
