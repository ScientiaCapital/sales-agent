/**
 * useWebSocket Hook
 * 
 * Manages WebSocket connections with automatic cleanup
 * Following React 19 best practices for WebSocket lifecycle management
 */

import { useEffect, useRef, useState, useCallback } from 'react';
import type { StreamMessage } from '../types';

interface UseWebSocketOptions {
  onMessage?: (message: StreamMessage) => void;
  onOpen?: () => void;
  onClose?: () => void;
  onError?: (error: Event) => void;
  reconnectAttempts?: number;
  reconnectDelay?: number;
}

interface UseWebSocketReturn {
  isConnected: boolean;
  lastMessage: StreamMessage | null;
  error: string | null;
  sendMessage: (message: string) => void;
  disconnect: () => void;
}

/**
 * Hook for managing WebSocket connections with automatic cleanup
 * 
 * @example
 * ```tsx
 * const { isConnected, lastMessage } = useWebSocket(wsUrl, {
 *   onMessage: (msg) => console.log('Received:', msg),
 *   onError: (err) => console.error('Error:', err)
 * });
 * ```
 */
export function useWebSocket(
  url: string | null,
  options: UseWebSocketOptions = {}
): UseWebSocketReturn {
  const {
    onMessage,
    onOpen,
    onClose,
    onError,
    reconnectAttempts = 3,
    reconnectDelay = 1000,
  } = options;

  const [isConnected, setIsConnected] = useState(false);
  const [lastMessage, setLastMessage] = useState<StreamMessage | null>(null);
  const [error, setError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectCountRef = useRef(0);
  const shouldConnectRef = useRef(true);

  /**
   * Send message through WebSocket
   */
  const sendMessage = useCallback((message: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(message);
    } else {
      console.warn('WebSocket not connected, cannot send message');
    }
  }, []);

  /**
   * Manual disconnect
   */
  const disconnect = useCallback(() => {
    shouldConnectRef.current = false;
    
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  /**
   * Connect to WebSocket with retry logic
   */
  const connect = useCallback(() => {
    if (!url || !shouldConnectRef.current) return;

    try {
      const ws = new WebSocket(url);
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('WebSocket connected:', url);
        setIsConnected(true);
        setError(null);
        reconnectCountRef.current = 0;
        onOpen?.();
      };

      ws.onmessage = (event) => {
        try {
          const message: StreamMessage = JSON.parse(event.data);
          setLastMessage(message);
          onMessage?.(message);
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };

      ws.onerror = (event) => {
        console.error('WebSocket error:', event);
        setError('WebSocket connection error');
        onError?.(event);
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setIsConnected(false);
        wsRef.current = null;
        onClose?.();

        // Attempt reconnection if allowed
        if (
          shouldConnectRef.current &&
          reconnectCountRef.current < reconnectAttempts
        ) {
          reconnectCountRef.current++;
          console.log(
            `Reconnecting... (${reconnectCountRef.current}/${reconnectAttempts})`
          );

          setTimeout(() => {
            if (shouldConnectRef.current) {
              connect();
            }
          }, reconnectDelay);
        }
      };
    } catch (err) {
      console.error('Failed to create WebSocket:', err);
      setError(err instanceof Error ? err.message : 'Connection failed');
    }
  }, [url, onMessage, onOpen, onClose, onError, reconnectAttempts, reconnectDelay]);

  /**
   * Effect to manage WebSocket lifecycle
   * Following React 19 cleanup patterns
   */
  useEffect(() => {
    shouldConnectRef.current = true;
    
    if (url) {
      connect();
    }

    // Cleanup function - called when component unmounts or URL changes
    return () => {
      shouldConnectRef.current = false;
      
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      setIsConnected(false);
    };
  }, [url, connect]);

  return {
    isConnected,
    lastMessage,
    error,
    sendMessage,
    disconnect,
  };
}

export default useWebSocket;
