# VLM AI Core

**PRIVATE REPOSITORY - Scientia Capital Proprietary IP**

Shared Vision Language Model (VLM) stack for all Scientia Capital projects.

## Installation

```bash
# Authenticate with GitHub Packages
npm login --registry=https://npm.pkg.github.com --scope=@scientia

# Install the package
npm install @scientia/vlm-core --registry=https://npm.pkg.github.com
```

## Quick Start

```typescript
import {
  OpenRouterClient,
  CircuitBreaker,
  withRetry,
  calculateConfidence
} from '@scientia/vlm-core';

// Initialize client
const client = new OpenRouterClient(process.env.OPENROUTER_API_KEY);
const breaker = new CircuitBreaker({ serviceName: 'vlm' });

// Analyze with resilience
const result = await breaker.execute(() =>
  withRetry(() => client.analyze(imageBase64, {
    analysisType: 'equipment',
    model: 'qwen/qwen2.5-vl-72b-instruct'
  }))
);

// Check confidence
const confidence = calculateConfidence([
  { type: 'vlm', score: result.confidence, weight: 1.0 }
]);
```

## Features

- **Circuit Breaker** - Fail-fast when services are down
- **Exponential Retry** - With jitter to prevent thundering herd
- **Confidence Scoring** - Multi-signal aggregation
- **Cost Tracking** - Per-analysis cost estimation
- **Context Compaction** - Token management for long contexts

## Consumer Projects

- FieldVault (source)
- NetZero Calculator
- NetZeroExpert-OS
- netzero-bot
- solarappraisal-ai

## Models Supported

| Model | Use Case | Cost |
|-------|----------|------|
| qwen/qwen2.5-vl-72b-instruct | Blueprints, field photos | $0.40/1M tokens |
| deepseek/deepseek-chat-v3.1 | Text normalization | $0.00027/1K tokens |
| qwen/qwen3-embedding-8b | Embeddings | $0.01/1M tokens |

## License

UNLICENSED - Proprietary to Scientia Capital
