/**
 * Authentication utilities for the BDR Cockpit dashboard
 *
 * Handles Supabase token retrieval for WebSocket and API authentication.
 * Supabase stores auth tokens with dynamic key names based on project ID.
 */

/**
 * Get the current authentication token from Supabase storage
 *
 * Supabase stores tokens in localStorage with keys like:
 * - sb-{project-ref}-auth-token (newer format)
 * - supabase.auth.token (older format)
 *
 * @returns The access token string or null if not authenticated
 */
export function getAuthToken(): string | null {
  if (typeof window === "undefined") {
    return null; // SSR - no localStorage available
  }

  try {
    // Method 1: Look for Supabase's default key pattern (sb-{project}-auth-token)
    const supabaseKey = Object.keys(localStorage).find(
      (key) => key.startsWith("sb-") && key.endsWith("-auth-token")
    );

    if (supabaseKey) {
      const data = localStorage.getItem(supabaseKey);
      if (data) {
        const parsed = JSON.parse(data);
        // Supabase stores { access_token, refresh_token, ... } or nested in currentSession
        if (parsed.access_token) {
          return parsed.access_token;
        }
        if (parsed.currentSession?.access_token) {
          return parsed.currentSession.access_token;
        }
      }
    }

    // Method 2: Check for older supabase.auth.token format
    const legacyToken = localStorage.getItem("supabase.auth.token");
    if (legacyToken) {
      const parsed = JSON.parse(legacyToken);
      if (parsed.currentSession?.access_token) {
        return parsed.currentSession.access_token;
      }
    }

    // Method 3: Check sessionStorage as fallback
    const sessionKey = Object.keys(sessionStorage).find(
      (key) => key.startsWith("sb-") && key.endsWith("-auth-token")
    );

    if (sessionKey) {
      const data = sessionStorage.getItem(sessionKey);
      if (data) {
        const parsed = JSON.parse(data);
        if (parsed.access_token) {
          return parsed.access_token;
        }
      }
    }

    return null;
  } catch (error) {
    console.error("Failed to retrieve auth token:", error);
    return null;
  }
}

/**
 * Check if the user is currently authenticated
 *
 * @returns True if a valid token exists
 */
export function isAuthenticated(): boolean {
  return getAuthToken() !== null;
}

/**
 * Get the WebSocket URL with authentication token
 *
 * @param endpoint The WebSocket endpoint path (e.g., "/api/v1/ws/cockpit")
 * @returns Full WebSocket URL with token query param, or null if not authenticated
 */
export function getAuthenticatedWebSocketUrl(endpoint: string): string | null {
  const token = getAuthToken();
  if (!token) {
    console.warn("Cannot create authenticated WebSocket: no auth token");
    return null;
  }

  const wsBaseUrl =
    import.meta.env.VITE_WS_URL ||
    (typeof window !== "undefined" && window.location.hostname === "localhost"
      ? "ws://localhost:8001"
      : `wss://${typeof window !== "undefined" ? window.location.host : ""}`);

  return `${wsBaseUrl}${endpoint}?token=${encodeURIComponent(token)}`;
}
