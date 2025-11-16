# Verified OpenRouter Model IDs

**Generated**: verify_openrouter_models.py
**Date**: 2025-11-16 08:25:15

This document contains verified model identifiers from OpenRouter API for use in our sales-agent system.

---

## 🎯 Recommended Models for Implementation

### EnrichmentAgent

```python
"deepseek/deepseek-r1-distill-qwen-32b"
```

- **Cost**: $0.270000/1M input, $0.270000/1M output
- **Context**: 131,072 tokens
- **Description**: DeepSeek R1 Distill Qwen 32B is a distilled large language model based on [Qwen 2.5 32B](https://hug

### GrowthAgent

```python
"qwen/qwq-32b"
```

- **Cost**: $0.150000/1M input, $0.400000/1M output
- **Context**: 32,768 tokens
- **Description**: QwQ is the reasoning model of the Qwen series. Compared with conventional instruction-tuned models, 

### ConversationAgent 🆓

```python
"google/gemini-2.0-flash-exp:free"
```

- **Cost**: $0.000000/1M input, $0.000000/1M output
- **Context**: 1,048,576 tokens
- **Description**: Gemini Flash 2.0 offers a significantly faster time to first token (TTFT) compared to [Gemini Flash 

### Tier 1 Leads 🆓

```python
"moonshotai/kimi-k2:free"
```

- **Cost**: $0.000000/1M input, $0.000000/1M output
- **Context**: 32,768 tokens
- **Description**: Kimi K2 Instruct is a large-scale Mixture-of-Experts (MoE) language model developed by Moonshot AI, 

---

## 📋 Complete Verified Models

### Moonshot Kimi

#### MoonshotAI: Kimi K2 0711 (free) 🆓 FREE

**Model ID**:
```python
"moonshotai/kimi-k2:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 32,768 tokens |
| Description | Kimi K2 Instruct is a large-scale Mixture-of-Experts (MoE) language model developed by Moonshot AI,  |

#### MoonshotAI: Kimi K2 0905

**Model ID**:
```python
"moonshotai/kimi-k2-0905"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.390000/1M tokens |
| Output Cost | $1.900000/1M tokens |
| Context Window | 262,144 tokens |
| Description | Kimi K2 0905 is the September update of [Kimi K2 0711](moonshotai/kimi-k2). It is a large-scale Mixt |

#### MoonshotAI: Kimi K2 0711

**Model ID**:
```python
"moonshotai/kimi-k2"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.500000/1M tokens |
| Output Cost | $2.400000/1M tokens |
| Context Window | 131,072 tokens |
| Description | Kimi K2 Instruct is a large-scale Mixture-of-Experts (MoE) language model developed by Moonshot AI,  |

#### MoonshotAI: Kimi K2 Thinking

**Model ID**:
```python
"moonshotai/kimi-k2-thinking"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.550000/1M tokens |
| Output Cost | $2.250000/1M tokens |
| Context Window | 262,144 tokens |
| Description | Kimi K2 Thinking is Moonshot AI’s most advanced open reasoning model to date, extending the K2 serie |

#### MoonshotAI: Kimi K2 0905 (exacto)

**Model ID**:
```python
"moonshotai/kimi-k2-0905:exacto"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.600000/1M tokens |
| Output Cost | $2.500000/1M tokens |
| Context Window | 262,144 tokens |
| Description | Kimi K2 0905 is the September update of [Kimi K2 0711](moonshotai/kimi-k2). It is a large-scale Mixt |

### Gemini Flash

#### Google: Gemini 2.0 Flash Experimental (free) 🆓 FREE

**Model ID**:
```python
"google/gemini-2.0-flash-exp:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini Flash 2.0 offers a significantly faster time to first token (TTFT) compared to [Gemini Flash  |

#### Google: Gemini 2.0 Flash Lite

**Model ID**:
```python
"google/gemini-2.0-flash-lite-001"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.075000/1M tokens |
| Output Cost | $0.300000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini 2.0 Flash Lite offers a significantly faster time to first token (TTFT) compared to [Gemini F |

#### Google: Gemini 2.5 Flash Lite Preview 09-2025

**Model ID**:
```python
"google/gemini-2.5-flash-lite-preview-09-2025"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.100000/1M tokens |
| Output Cost | $0.400000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini 2.5 Flash-Lite is a lightweight reasoning model in the Gemini 2.5 family, optimized for ultra |

#### Google: Gemini 2.5 Flash Lite

**Model ID**:
```python
"google/gemini-2.5-flash-lite"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.100000/1M tokens |
| Output Cost | $0.400000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini 2.5 Flash-Lite is a lightweight reasoning model in the Gemini 2.5 family, optimized for ultra |

#### Google: Gemini 2.5 Flash Lite Preview 06-17

**Model ID**:
```python
"google/gemini-2.5-flash-lite-preview-06-17"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.100000/1M tokens |
| Output Cost | $0.400000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini 2.5 Flash-Lite is a lightweight reasoning model in the Gemini 2.5 family, optimized for ultra |

#### Google: Gemini 2.0 Flash

**Model ID**:
```python
"google/gemini-2.0-flash-001"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.100000/1M tokens |
| Output Cost | $0.400000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini Flash 2.0 offers a significantly faster time to first token (TTFT) compared to [Gemini Flash  |

#### Google: Gemini 2.5 Flash Image (Nano Banana)

**Model ID**:
```python
"google/gemini-2.5-flash-image"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $2.500000/1M tokens |
| Context Window | 32,768 tokens |
| Description | Gemini 2.5 Flash Image, a.k.a. "Nano Banana," is now generally available. It is a state of the art i |

#### Google: Gemini 2.5 Flash Preview 09-2025

**Model ID**:
```python
"google/gemini-2.5-flash-preview-09-2025"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $2.500000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini 2.5 Flash Preview September 2025 Checkpoint is Google's state-of-the-art workhorse model, spe |

#### Google: Gemini 2.5 Flash Image Preview (Nano Banana)

**Model ID**:
```python
"google/gemini-2.5-flash-image-preview"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $2.500000/1M tokens |
| Context Window | 32,768 tokens |
| Description | Gemini 2.5 Flash Image Preview, a.k.a. "Nano Banana," is a state of the art image generation model w |

#### Google: Gemini 2.5 Flash

**Model ID**:
```python
"google/gemini-2.5-flash"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $2.500000/1M tokens |
| Context Window | 1,048,576 tokens |
| Description | Gemini 2.5 Flash is Google's state-of-the-art workhorse model, specifically designed for advanced re |

### Deepseek V3

#### DeepSeek: DeepSeek V3.1 (free) 🆓 FREE

**Model ID**:
```python
"deepseek/deepseek-chat-v3.1:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 163,800 tokens |
| Description | DeepSeek-V3.1 is a large hybrid reasoning model (671B parameters, 37B active) that supports both thi |

#### DeepSeek: DeepSeek V3 0324 (free) 🆓 FREE

**Model ID**:
```python
"deepseek/deepseek-chat-v3-0324:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek V3, a 685B-parameter, mixture-of-experts model, is the latest iteration of the flagship cha |

#### DeepSeek: DeepSeek V3.1

**Model ID**:
```python
"deepseek/deepseek-chat-v3.1"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.200000/1M tokens |
| Output Cost | $0.800000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek-V3.1 is a large hybrid reasoning model (671B parameters, 37B active) that supports both thi |

#### DeepSeek: DeepSeek V3 0324

**Model ID**:
```python
"deepseek/deepseek-chat-v3-0324"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.240000/1M tokens |
| Output Cost | $0.840000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek V3, a 685B-parameter, mixture-of-experts model, is the latest iteration of the flagship cha |

#### DeepSeek: DeepSeek V3

**Model ID**:
```python
"deepseek/deepseek-chat"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $1.200000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek-V3 is the latest model from the DeepSeek team, building upon the instruction following and  |

### Deepseek R1

#### TNG: DeepSeek R1T2 Chimera (free) 🆓 FREE

**Model ID**:
```python
"tngtech/deepseek-r1t2-chimera:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek-TNG-R1T2-Chimera is the second-generation Chimera model from TNG Tech. It is a 671 B-parame |

#### DeepSeek: DeepSeek R1 0528 Qwen3 8B (free) 🆓 FREE

**Model ID**:
```python
"deepseek/deepseek-r1-0528-qwen3-8b:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 131,072 tokens |
| Description | DeepSeek-R1-0528 is a lightly upgraded release of DeepSeek R1 that taps more compute and smarter pos |

#### DeepSeek: R1 0528 (free) 🆓 FREE

**Model ID**:
```python
"deepseek/deepseek-r1-0528:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 163,840 tokens |
| Description | May 28th update to the [original DeepSeek R1](/deepseek/deepseek-r1) Performance on par with [OpenAI |

#### TNG: DeepSeek R1T Chimera (free) 🆓 FREE

**Model ID**:
```python
"tngtech/deepseek-r1t-chimera:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek-R1T-Chimera is created by merging DeepSeek-R1 and DeepSeek-V3 (0324), combining the reasoni |

#### DeepSeek: R1 Distill Llama 70B (free) 🆓 FREE

**Model ID**:
```python
"deepseek/deepseek-r1-distill-llama-70b:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 8,192 tokens |
| Description | DeepSeek R1 Distill Llama 70B is a distilled large language model based on [Llama-3.3-70B-Instruct]( |

#### DeepSeek: R1 (free) 🆓 FREE

**Model ID**:
```python
"deepseek/deepseek-r1:free"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.000000/1M tokens |
| Output Cost | $0.000000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek R1 is here: Performance on par with [OpenAI o1](/openai/o1), but open-sourced and with full |

#### DeepSeek: DeepSeek R1 0528 Qwen3 8B

**Model ID**:
```python
"deepseek/deepseek-r1-0528-qwen3-8b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.020000/1M tokens |
| Output Cost | $0.100000/1M tokens |
| Context Window | 32,768 tokens |
| Description | DeepSeek-R1-0528 is a lightly upgraded release of DeepSeek R1 that taps more compute and smarter pos |

#### DeepSeek: R1 Distill Llama 70B

**Model ID**:
```python
"deepseek/deepseek-r1-distill-llama-70b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.030000/1M tokens |
| Output Cost | $0.130000/1M tokens |
| Context Window | 131,072 tokens |
| Description | DeepSeek R1 Distill Llama 70B is a distilled large language model based on [Llama-3.3-70B-Instruct]( |

#### DeepSeek: R1 Distill Qwen 14B

**Model ID**:
```python
"deepseek/deepseek-r1-distill-qwen-14b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.150000/1M tokens |
| Output Cost | $0.150000/1M tokens |
| Context Window | 32,768 tokens |
| Description | DeepSeek R1 Distill Qwen 14B is a distilled large language model based on [Qwen 2.5 14B](https://hug |

#### DeepSeek: R1 Distill Qwen 32B

**Model ID**:
```python
"deepseek/deepseek-r1-distill-qwen-32b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.270000/1M tokens |
| Output Cost | $0.270000/1M tokens |
| Context Window | 131,072 tokens |
| Description | DeepSeek R1 Distill Qwen 32B is a distilled large language model based on [Qwen 2.5 32B](https://hug |

#### TNG: DeepSeek R1T2 Chimera

**Model ID**:
```python
"tngtech/deepseek-r1t2-chimera"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $1.200000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek-TNG-R1T2-Chimera is the second-generation Chimera model from TNG Tech. It is a 671 B-parame |

#### TNG: DeepSeek R1T Chimera

**Model ID**:
```python
"tngtech/deepseek-r1t-chimera"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $1.200000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek-R1T-Chimera is created by merging DeepSeek-R1 and DeepSeek-V3 (0324), combining the reasoni |

#### DeepSeek: R1

**Model ID**:
```python
"deepseek/deepseek-r1"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.300000/1M tokens |
| Output Cost | $1.200000/1M tokens |
| Context Window | 163,840 tokens |
| Description | DeepSeek R1 is here: Performance on par with [OpenAI o1](/openai/o1), but open-sourced and with full |

#### DeepSeek: R1 0528

**Model ID**:
```python
"deepseek/deepseek-r1-0528"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.400000/1M tokens |
| Output Cost | $1.750000/1M tokens |
| Context Window | 163,840 tokens |
| Description | May 28th update to the [original DeepSeek R1](/deepseek/deepseek-r1) Performance on par with [OpenAI |

### Qwen Qwq

#### Qwen: QwQ 32B

**Model ID**:
```python
"qwen/qwq-32b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.150000/1M tokens |
| Output Cost | $0.400000/1M tokens |
| Context Window | 32,768 tokens |
| Description | QwQ is the reasoning model of the Qwen series. Compared with conventional instruction-tuned models,  |

### Deepseek R1 Distill

#### DeepSeek: R1 Distill Qwen 14B

**Model ID**:
```python
"deepseek/deepseek-r1-distill-qwen-14b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.150000/1M tokens |
| Output Cost | $0.150000/1M tokens |
| Context Window | 32,768 tokens |
| Description | DeepSeek R1 Distill Qwen 14B is a distilled large language model based on [Qwen 2.5 14B](https://hug |

#### DeepSeek: R1 Distill Qwen 32B

**Model ID**:
```python
"deepseek/deepseek-r1-distill-qwen-32b"
```

| Property | Value |
|----------|-------|
| Input Cost | $0.270000/1M tokens |
| Output Cost | $0.270000/1M tokens |
| Context Window | 131,072 tokens |
| Description | DeepSeek R1 Distill Qwen 32B is a distilled large language model based on [Qwen 2.5 32B](https://hug |

---

## 💡 Implementation Notes

1. **FREE models** (`:free` suffix): 20 req/min, 200 req/day limit
2. **Paid models**: No rate limits (subject to OpenRouter account limits)
3. **Model format**: `provider/model-name` (e.g., `deepseek/deepseek-r1-distill-qwen-32b`)
4. **Testing**: Always test with small batch before full rollout

