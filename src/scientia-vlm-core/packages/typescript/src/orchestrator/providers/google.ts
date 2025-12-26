/**
 * Google Gemini Provider
 *
 * Uses Google's Generative AI API for Gemini models.
 * Good balance of cost and quality - 2.7x our primary but 15x less than Haiku.
 *
 * @module @scientia/vlm-core/orchestrator/providers
 */

/**
 * Google client configuration
 */
export interface GoogleConfig {
  apiKey: string;
  baseUrl?: string;
}

/**
 * Gemini response format
 */
interface GeminiResponse {
  candidates: Array<{
    content: {
      parts: Array<{
        text?: string;
      }>;
      role: string;
    };
    finishReason: string;
  }>;
  usageMetadata: {
    promptTokenCount: number;
    candidatesTokenCount: number;
    totalTokenCount: number;
  };
}

/**
 * Gemini model pricing (per 1M tokens)
 */
export const GEMINI_PRICING = {
  'gemini-2.5-flash': { input: 0.15, output: 0.60 },
  'gemini-2.5-pro': { input: 2.00, output: 12.00 },
  'gemini-2.0-flash-lite': { input: 0.075, output: 0.30 },
  'gemini-1.5-flash': { input: 0.075, output: 0.30 },
  'gemini-1.5-pro': { input: 1.25, output: 5.00 },
} as const;

/**
 * Google Gemini API Client
 *
 * Direct connection to Google's Generative AI API.
 */
export class GoogleClient {
  private apiKey: string;
  private baseUrl: string;

  constructor(config: GoogleConfig) {
    this.apiKey = config.apiKey;
    this.baseUrl = config.baseUrl || 'https://generativelanguage.googleapis.com/v1beta';
  }

  /**
   * Analyze an image with Gemini
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
    let imageData: string;
    let imageMimeType: string;

    if (imageType === 'base64') {
      imageData = image;
      imageMimeType = mimeType;
    } else {
      // URL type - fetch and convert to base64
      const imageResponse = await fetch(image);
      const imageBuffer = await imageResponse.arrayBuffer();
      imageData = Buffer.from(imageBuffer).toString('base64');
      imageMimeType = imageResponse.headers.get('content-type') || mimeType;
    }

    // Build request body (Gemini format)
    const requestBody = {
      contents: [
        {
          parts: [
            {
              inline_data: {
                mime_type: imageMimeType,
                data: imageData,
              },
            },
            {
              text: prompt,
            },
          ],
        },
      ],
      generationConfig: {
        temperature: 0.1,
        maxOutputTokens: 4096,
      },
    };

    // Make request
    const url = `${this.baseUrl}/models/${model}:generateContent?key=${this.apiKey}`;
    const response = await fetch(url, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(requestBody),
    });

    if (!response.ok) {
      const error = await response.text();
      throw new Error(`Google API error (${response.status}): ${error}`);
    }

    const result = await response.json() as GeminiResponse;
    const latencyMs = Date.now() - startTime;

    // Extract text content
    const content = result.candidates?.[0]?.content?.parts?.[0]?.text || '';

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
      inputTokens: result.usageMetadata?.promptTokenCount || 0,
      outputTokens: result.usageMetadata?.candidatesTokenCount || 0,
      latencyMs,
    };
  }

  /**
   * Calculate cost for a Gemini call
   */
  static calculateCost(
    model: string,
    inputTokens: number,
    outputTokens: number,
  ): number {
    const pricing = GEMINI_PRICING[model as keyof typeof GEMINI_PRICING];
    if (!pricing) {
      return 0.001; // Default fallback
    }

    const inputCost = (inputTokens / 1_000_000) * pricing.input;
    const outputCost = (outputTokens / 1_000_000) * pricing.output;
    return inputCost + outputCost;
  }

  /**
   * List available Gemini vision models
   */
  static getVisionModels(): string[] {
    return [
      'gemini-2.5-flash',
      'gemini-2.5-pro',
      'gemini-2.0-flash-lite',
      'gemini-1.5-flash',
      'gemini-1.5-pro',
    ];
  }
}

/**
 * Create a pre-configured Google client from environment
 */
export function createGoogleClient(): GoogleClient {
  const apiKey = process.env.GOOGLE_API_KEY;
  if (!apiKey) {
    throw new Error('GOOGLE_API_KEY environment variable is required');
  }

  return new GoogleClient({ apiKey });
}
