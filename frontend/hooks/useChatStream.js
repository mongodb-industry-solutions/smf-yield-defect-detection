import { useState, useCallback } from 'react';
import { chatAPI } from '../lib/api';

export function useChatStream({ sessionId, onToken, onToolCall, onToolResultData, onComplete, onError }) {
  const [isConnected, setIsConnected] = useState(false);

  const sendMessage = useCallback(async (message) => {
    console.log('🔵 useChatStream: sendMessage called with:', message, 'sessionId:', sessionId);
    setIsConnected(true);

    try {
      console.log('🔵 Calling chatAPI.streamChat...');
      const response = await chatAPI.streamChat(message, sessionId);
      console.log('🔵 Got response:', response);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      console.log('🔵 Starting to read stream...');
      while (true) {
        const { done, value } = await reader.read();
        if (done) {
          console.log('🔵 Stream done');
          break;
        }

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.trim() || line.startsWith(':')) continue;

          if (line.startsWith('data: ')) {
            const data = line.slice(6);
            console.log('🔵 Received SSE data:', data.substring(0, 100));

            if (data === '[DONE]') {
              console.log('🔵 Received [DONE] signal');
              onComplete?.();
              setIsConnected(false);
              return;
            }

            try {
              const event = JSON.parse(data);
              console.log('🔵 Parsed event:', event.type);

              if (event.type === 'token' && event.content) {
                console.log('🔵 Token received, calling onToken');
                onToken?.(event.content);
              } else if (event.type === 'tool_call') {
                console.log('🔵 Tool call received');
                onToolCall?.(event.tool_name, event.tool_args);
              } else if (event.type === 'tool_result') {
                console.log('🔵 Tool result received');
                onToolCall?.(event.content, {});
              } else if (event.type === 'tool_result_data') {
                console.log('🔵 Tool result data received:', event.tool_name);
                onToolResultData?.(event.tool_name, event.data);
              } else if (event.type === 'done') {
                console.log('🔵 Done event received');
                onComplete?.();
                setIsConnected(false);
                return;
              } else if (event.type === 'error') {
                console.log('🔵 Error event received');
                onError?.(event.content || event.error);
                setIsConnected(false);
              }
            } catch (parseError) {
              console.error('❌ Failed to parse SSE event:', parseError);
            }
          }
        }
      }

      console.log('🔵 Stream completed normally');
      onComplete?.();
      setIsConnected(false);
    } catch (error) {
      console.error('❌ Stream error:', error);
      onError?.(error.message || 'Connection failed');
      setIsConnected(false);
    }
  }, [sessionId, onToken, onToolCall, onToolResultData, onComplete, onError]);

  return {
    sendMessage,
    isConnected,
    error: null
  };
}
