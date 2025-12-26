/**
 * Anthropic Provider (Direct API)
 *
 * Uses Anthropic's direct API for Claude models.
 * Better rate limits than OpenRouter for Claude.
 * Used as emergency fallback for reliability.
 *
 * @module @scientia/vlm-core/orchestrator/providers
 */

/**
 * Anthropic client configuration
 */
export interface AnthropicConfig {
  apiKey: string;
  baseUrl?: string;
  defaultHeaders?: Record<string, string>;
}

/**
 * Anthropic message response format
 */
interface AnthropicResponse {
  id: string;
  type: string;
  role: string;
  content: Array<{
    type: string;
    text?: string;
  }>;
  model: string;
  stop_reason: string;
  stop_sequence: string | null;
  usage: {
    input_tokens: number;
    output_tokens: number;
  };
}

/**
 * Claude 4.5 model pricing (per 1M tokens)
 */
export const CLAUDE_PRICING = {
  'claude-3-5-haiku-20241022': { input: 1.00, output: 5.00 },
  'claude-sonnet-4-5-20250514': { input: 3.00, output: 15.00 },
  'claude-opus-4-5-20250514': { input: 5.00, output: 25.00 },
} as const;

/**
 * Anthropic Direct API Client
 *
 * Connects directly to Anthropic API for Claude models.
 * Better rate limits and reliability than proxied access.
 */
export class AnthropicClient {
  private apiKey: string;
  private baseUrl: string;
  private defaultHeaders: Record<string, string>;

  constructor(config: AnthropicConfig) {
    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl || 'https://api.anthropic.com/v1';
    this.defaultHeaders = {
      'Content-Type': 'application/json',
      'x-api-key': this.apiKey,
      'anthropic-version': '2023-06-01',
      ...(config.defaultHeaders || {}),
    };
  }

  /**
   * Analyze an image with Claude
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
    // Anthropic uses a different format than OpenAI
    let imageContent: {
      type: 'image';
      source: {
        type: 'base64' | 'url';
        media_type?: string;
        data?: string;
        url?: string;
      };
    };

    if (imageType === 'base64') {
      imageContent = {
        type: 'image',
        source: {
          type: 'base64',
          media_type: mimeType,
          data: image,
        },
      };
    } else {
      // URL type - fetch and convert to base64
      // Anthropic doesn't support URL directly, so we need to fetch
      const imageResponse = await fetch(image);
      const imageBuffer = await imageResponse.arrayBuffer();
      const base64Image = Buffer.from(imageBuffer).toString('base64');
      const contentType = imageResponse.headers.get('content-type') || mimeType;

      imageContent = {
        type: 'image',
        source: {
          type: 'base64',
          media_type: contentType,
          data: base64Image,
        },
      };
    }

    // Build request body
    const requestBody = {
      model,
      max_tokens: 4096,
      messages: [
        {
          role: 'user',
          content: [
            imageContent,
            { type: 'text', text: prompt },
          ],
        },
      ],
    };

    // Make request
    const response = await fetch(`${this.baseUrl}/messages`, {
      method: 'POST',
      headers: this.defaultHeaders,
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Anthropic API error (${response.status}): ${error}`);
    }

    const result = await response.json() as AnthropicResponse;
    const latencyMs = Date.now() - startTime;

    // Extract text content
    const textContent = result.content.find(c => c.type === 'text');
    const content = textContent?.text || '';

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
      inputTokens: result.usage?.input_tokens || 0,
      outputTokens: result.usage?.output_tokens || 0,
      latencyMs,
    };
  }

  /**
   * Calculate cost for a Claude call
   */
  static calculateCost(
    model: string,
    inputTokens: number,
    outputTokens: number,
  ): number {
    const pricing = CLAUDE_PRICING[model as keyof typeof CLAUDE_PRICING];
    if (!pricing) {
      return 0.01; // Default fallback
    }

    const inputCost = (inputTokens / 1_000_000) * pricing.input;
    const outputCost = (outputTokens / 1_000_000) * pricing.output;
    return inputCost + outputCost;
  }

  /**
   * List available Claude vision models
   */
  static getVisionModels(): string[] {
    return [
      'claude-3-5-haiku-20241022',
      'claude-sonnet-4-5-20250514',
      'claude-opus-4-5-20250514',
    ];
  }
}

/**
 * Create a pre-configured Anthropic client from environment
 */
export function createAnthropicClient(): AnthropicClient {
  const apiKey = process.env.ANTHROPIC_API_KEY;
  if (!apiKey) {
    throw new Error('ANTHROPIC_API_KEY environment variable is required');
  }

  return new AnthropicClient({ apiKey });
}
