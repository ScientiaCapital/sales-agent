/**
 * OpenRouter Provider
 *
 * Handles Chinese VLMs (Qwen, GLM) via OpenRouter API.
 * Primary provider for cost-optimized extraction.
 *
 * @module @scientia/vlm-core/orchestrator/providers
 */

/**
 * OpenRouter client configuration
 */
export interface OpenRouterConfig {
  apiKey: string;
  baseUrl?: string;
  defaultHeaders?: Record<string, string>;
  zeroDataRetention?: boolean;  // ZDR mode for privacy
}

/**
 * OpenRouter response format
 */
interface OpenRouterResponse {
  id: string;
  choices: Array<{
    message: {
      content: string;
      role: string;
    };
    finish_reason: string;
  }>;
  usage: {
    prompt_tokens: number;
    completion_tokens: number;
    total_tokens: number;
  };
}

/**
 * OpenRouter VLM Client
 *
 * Supports all Chinese VLMs through OpenRouter's unified API.
 */
export class OpenRouterClient {
  private apiKey: string;
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;

  constructor(config: OpenRouterConfig) {
    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl || 'https://openrouter.ai/api/v1';
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${this.apiKey}`,
      'HTTP-Referer': 'https://fieldvault.ai',
      'X-Title': 'FieldVault VLM Core',
      ...(config.zeroDataRetention ? { 'X-ZDR': 'true' } : {}),
      ...(config.defaultHeaders || {}),
    };
  }

  /**
   * Analyze an image with a VLM
   */
  async analyze(
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
  }> {
    const startTime = Date.now();

    // Build image content
    const imageContent = imageType === 'base64'
      ? { type: 'image_url' as const, image_url: { url: `data:${mimeType};base64,${image}` } }
      : { type: 'image_url' as const, image_url: { url: image } };

    // Build request
    const requestBody = {
      model,
      messages: [
        {
          role: 'user',
          content: [
            imageContent,
            { type: 'text', text: prompt },
          ],
        },
      ],
      temperature: 0.1,  // Low temp for structured extraction
      max_tokens: 4096,
    };

    // Make request
    const response = await fetch(`${this.baseUrl}/chat/completions`, {
      method: 'POST',
      headers: this.defaultHeaders,
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`OpenRouter API error (${response.status}): ${error}`);
    }

    const result = await response.json() as OpenRouterResponse;
    const latencyMs = Date.now() - startTime;

    // Parse response
    const content = result.choices[0]?.message?.content || '';

    // Try to parse as JSON
    let data: Record<string, unknown>;
    try {
      // Handle markdown code blocks
      const jsonMatch = content.match(/```(?:json)?\s*([\s\S]*?)\s*```/);
      const jsonStr = jsonMatch ? jsonMatch[1] : content;
      data = JSON.parse(jsonStr.trim());
    } catch {
      // Return raw content if not JSON
      data = { raw: content, jsonParseError: true };
    }

    return {
      data,
      inputTokens: result.usage?.prompt_tokens || 0,
      outputTokens: result.usage?.completion_tokens || 0,
      latencyMs,
    };
  }

  /**
   * List available models
   */
  async listModels(): Promise<string[]> {
    const response = await fetch(`${this.baseUrl}/models`, {
      headers: this.defaultHeaders,
    });

    if (!response.ok) {
      throw new Error(`Failed to list models: ${response.status}`);
    }

    const result = await response.json() as { data: Array<{ id: string }> };
    return result.data.map(m => m.id);
  }

  /**
   * Check if a model supports vision
   */
  static isVisionModel(model: string): boolean {
    const visionModels = [
      'qwen/qwen3-vl-30b-a3b-instruct',
      'qwen/qwen3-vl-8b-a3b-instruct',
      'qwen/qwen-vl-max',
      'qwen/qwen2.5-vl-72b-instruct',
      'z-ai/glm-4.6v',
    ];
    return visionModels.includes(model);
  }
}

/**
 * Create a pre-configured OpenRouter client from environment
 */
export function createOpenRouterClient(): OpenRouterClient {
  const apiKey = process.env.OPENROUTER_API_KEY;
  if (!apiKey) {
    throw new Error('OPENROUTER_API_KEY environment variable is required');
  }

  return new OpenRouterClient({
    apiKey,
    zeroDataRetention: true,  // Always use ZDR for privacy
  });
}
