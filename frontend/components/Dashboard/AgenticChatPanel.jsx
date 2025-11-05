"use client";

import React, { useState, useRef, useEffect } from 'react';
import TextInput from '@leafygreen-ui/text-input';
import Button from '@leafygreen-ui/button';
import { Body, H3 } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import styles from './AgenticChatPanel.module.css';
import { useChatStream } from '../../hooks/useChatStream';
import { chatAPI } from '../../lib/api';
import WaferVisualization from './WaferVisualization';
import MarkdownMessage from './MarkdownMessage';

// Example queries to showcase all 4 tools + multi-tool RCA
const EXAMPLE_QUERIES = [
  // Tool 1: query_alerts
  {
    text: "Show me recent alerts",
    icon: "Megaphone",
    description: "Query recent alerts (Tool 1)"
  },
  {
    text: "Show high severity alerts",
    icon: "Warning",
    description: "Filter alerts by severity (Tool 1)"
  },
  {
    text: "Show particle excursion alerts",
    icon: "ImportantWithCircle",
    description: "Filter by excursion type (Tool 1)"
  },

  // Tool 2: query_wafer_info
  {
    text: "Show me recent wafer defects",
    icon: "Folder",
    description: "Get recent wafer defect information (Tool 2)"
  },

  // Tool 3: query_time_series_data
  {
    text: "Show sensor data for CMP equipment",
    icon: "Charts",
    description: "Query sensor statistics for CMP tools (Tool 3)"
  },
  {
    text: "Show temperature trends for ETCH tools",
    icon: "ActivityFeed",
    description: "Query temperature sensor data (Tool 3)"
  },

  // Tool 4: vector_search_knowledge_base
  {
    text: "Search for particle defect solutions",
    icon: "University",
    description: "Search historical RCA reports (Tool 4)"
  },
  {
    text: "Find CMP RCA Reports",
    icon: "InviteUser",
    description: "Search technical manuals (Tool 4)"
  },

  // Multi-Tool RCA (LLM orchestration)
  {
    text: "What's causing recent particle excursions?",
    icon: "Bulb",
    description: "LLM-driven RCA using multiple tools"
  },
  {
    text: "Analyze root cause of latest defects",
    icon: "Beaker",
    description: "Multi-tool analysis with evidence"
  }
];

export default function AgenticChatPanel({ pendingQuery = null, onQueryProcessed = () => {} }) {
  // Session management - persist across page refreshes
  const [sessionId, setSessionId] = useState(() => {
    if (typeof window !== 'undefined') {
      const stored = localStorage.getItem('chat_session_id');
      if (stored) {
        try {
          const data = JSON.parse(stored);
          // Reuse session if less than 24 hours old
          const age = new Date() - new Date(data.created);
          if (age < 24 * 60 * 60 * 1000) {
            console.log('✅ Reusing existing session:', data.id);
            return data.id;
          } else {
            console.log('⏰ Session expired, creating new one');
          }
        } catch (e) {
          console.error('Failed to parse stored session:', e);
        }
      }
    }
    
    // Create new session
    const newId = typeof crypto !== 'undefined' && crypto.randomUUID 
      ? crypto.randomUUID() 
      : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    
    if (typeof window !== 'undefined') {
      localStorage.setItem('chat_session_id', JSON.stringify({
        id: newId,
        created: new Date().toISOString()
      }));
    }
    
    console.log('✅ Created new session:', newId);
    return newId;
  });

  const [messages, setMessages] = useState([]);
  const [inputValue, setInputValue] = useState('');
  const [isStreaming, setIsStreaming] = useState(false);
  const [waferData, setWaferData] = useState(null);
  const [isLoadingHistory, setIsLoadingHistory] = useState(true);
  const messagesEndRef = useRef(null);

  const { sendMessage, error } = useChatStream({
    sessionId,  // Pass session ID to hook
    onToken: (token) => {
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant' && !lastMsg.isComplete) {
          return [...prev.slice(0, -1), { ...lastMsg, content: lastMsg.content + token }];
        }
        return [...prev, { role: 'assistant', content: token, isComplete: false }];
      });
    },
    onToolCall: (toolName, toolArgs) => {
      setMessages(prev => [...prev, {
        role: 'tool',
        toolName,
        toolArgs,
        timestamp: new Date()
      }]);
    },
    onToolResultData: (toolName, data) => {
      console.log('📊 Tool result data received:', toolName, data);
      if (toolName === 'query_wafer_info') {
        setWaferData(data);
        // Add a message to show wafer visualization
        setMessages(prev => [...prev, {
          role: 'wafer_viz',
          data,
          timestamp: new Date()
        }]);
      }
    },
    onComplete: () => {
      setIsStreaming(false);
      setMessages(prev => {
        const lastMsg = prev[prev.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          return [...prev.slice(0, -1), { ...lastMsg, isComplete: true }];
        }
        return prev;
      });
    },
    onError: (err) => {
      setIsStreaming(false);
      console.error('Chat error:', err);
    }
  });

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  // Load conversation history on mount
  useEffect(() => {
    const loadHistory = async () => {
      try {
        console.log('📜 Loading conversation history for session:', sessionId);
        const history = await chatAPI.getChatHistory(sessionId);
        
        if (history.messages && history.messages.length > 0) {
          console.log('📜 Found', history.messages.length, 'messages in history');
          
          // Convert backend message format to frontend format
          const historicalMessages = history.messages.map(msg => {
            if (msg.type === 'HumanMessage') {
              return { 
                role: 'user', 
                content: msg.content 
              };
            } else if (msg.type === 'AIMessage') {
              return { 
                role: 'assistant', 
                content: msg.content, 
                isComplete: true 
              };
            } else if (msg.type === 'ToolMessage') {
              return { 
                role: 'tool', 
                toolName: msg.name || 'unknown', 
                toolArgs: {} 
              };
            }
            return null;
          }).filter(Boolean);
          
          setMessages(historicalMessages);
          console.log('✅ Loaded', historicalMessages.length, 'messages from history');
        } else {
          console.log('📜 No history found, starting fresh');
        }
      } catch (error) {
        console.error('Failed to load conversation history:', error);
        // Don't fail - just start with empty messages
      } finally {
        setIsLoadingHistory(false);
      }
    };
    
    loadHistory();
  }, [sessionId]);

  // Handle pending query from alert modal navigation
  useEffect(() => {
    if (pendingQuery && !isStreaming && !isLoadingHistory) {
      console.log('Received pending query from alert modal:', pendingQuery);
      setInputValue(pendingQuery);

      // Auto-send after a brief delay to allow UI to update
      setTimeout(() => {
        if (pendingQuery.trim()) {
          setMessages(prev => [...prev, { role: 'user', content: pendingQuery }]);
          setIsStreaming(true);

          sendMessage(pendingQuery)
            .then(() => {
              console.log('Pending query sent successfully');
            })
            .catch((err) => {
              console.error('Failed to send pending query:', err);
              setIsStreaming(false);
            });

          // Clear the pending query
          onQueryProcessed();
        }
      }, 300);
    }
  }, [pendingQuery, isStreaming, isLoadingHistory]);

  // Clear conversation and start new session
  const handleClearConversation = async () => {
    if (isStreaming) {
      console.log('⚠️ Cannot clear while streaming');
      return;
    }

    try {
      console.log('🔄 Clearing conversation for session:', sessionId);
      
      // Call backend to clear checkpoints
      const apiBase = process.env.NEXT_PUBLIC_API_URL || '/api/backend';
      await fetch(`${apiBase}/chat/clear/${sessionId}`, {
        method: 'DELETE'
      });
      
      // Create new session
      const newId = typeof crypto !== 'undefined' && crypto.randomUUID 
        ? crypto.randomUUID() 
        : `session-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      
      if (typeof window !== 'undefined') {
        localStorage.setItem('chat_session_id', JSON.stringify({
          id: newId,
          created: new Date().toISOString()
        }));
      }
      
      // Reset state
      setSessionId(newId);
      setMessages([]);
      setWaferData(null);
      setInputValue('');
      
      console.log('✅ Conversation cleared, new session:', newId);
    } catch (error) {
      console.error('Failed to clear conversation:', error);
      alert('Failed to clear conversation. Please try again.');
    }
  };

  const handleSend = async () => {
    console.log('🚀 handleSend called, inputValue:', inputValue, 'isStreaming:', isStreaming);
    if (!inputValue.trim() || isStreaming) {
      console.log('❌ Returning early - empty or already streaming');
      return;
    }

    const userMessage = inputValue.trim();
    console.log('✅ Sending message:', userMessage);
    setInputValue('');
    setMessages(prev => [...prev, { role: 'user', content: userMessage }]);
    setIsStreaming(true);

    try {
      console.log('📡 Calling sendMessage...');
      await sendMessage(userMessage);
      console.log('✅ sendMessage completed');
    } catch (err) {
      console.error('❌ Failed to send message:', err);
      setIsStreaming(false);
    }
  };

  const handleKeyPress = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleExampleClick = (query) => {
    if (isStreaming) return;

    // Set input value so user can see and modify if needed
    setInputValue(query.text);

    // Optionally: auto-send immediately
    // Uncomment if you want instant send without "Send" button click:
    // setTimeout(() => handleSend(), 100);
  };

  return (
    <div className={styles.chatContainer}>
      <div className={styles.chatHeader}>
        <H3>Agentic Analytics</H3>
        <Body className={styles.headerSubtitle}>
          Ask questions about open alerts, wafer defects, and process anomalies
        </Body>
      </div>

      {/* Session controls */}
      <div className={styles.sessionControls}>
        <div className={styles.sessionInfo}>
          <Icon glyph="Folder" size="small" />
          <Body className={styles.sessionText}>
            Session: {sessionId.slice(0, 8)}...
          </Body>
          {isLoadingHistory && (
            <Body className={styles.loadingText}>(Loading history...)</Body>
          )}
        </div>
        <Button
          onClick={handleClearConversation}
          variant="default"
          size="small"
          disabled={isStreaming}
          leftGlyph={<Icon glyph="Refresh" />}
        >
          New Conversation
        </Button>
      </div>

      <div className={styles.messagesContainer}>
        {messages.length === 0 && (
          <div className={styles.emptyState}>
            <Icon glyph="Megaphone" size={48} />
            <Body>Start a conversation to analyze yield defects</Body>
            <Body className={styles.suggestions}>
              Try: "Show me open alerts" or "What defects occurred in the last 24 hours?"
            </Body>
          </div>
        )}

        {messages.map((msg, idx) => (
          <React.Fragment key={idx}>
            {msg.role === 'user' && (
              <div className={styles.userMessage}>
                <Body weight="medium">You</Body>
                <Body>{msg.content}</Body>
              </div>
            )}

            {msg.role === 'assistant' && (
              <div className={styles.assistantMessage}>
                <Body weight="medium">AI Assistant</Body>
                <MarkdownMessage content={msg.content} />
              </div>
            )}

            {msg.role === 'tool' && (
              <div className={styles.toolMessage}>
                <Icon glyph="Wrench" size="small" />
                <Body className={styles.toolText}>
                  Calling tool: <code>{msg.toolName}</code>
                </Body>
              </div>
            )}

            {msg.role === 'wafer_viz' && (
              <WaferVisualization data={msg.data} />
            )}
          </React.Fragment>
        ))}

        {isStreaming && (
          <div className={styles.typingIndicator}>
            <Icon glyph="Clock" size="small" />
            <Body>AI is typing...</Body>
          </div>
        )}

        {error && (
          <div className={styles.errorMessage}>
            <Icon glyph="Warning" size="small" />
            <Body>{error}</Body>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div className={styles.inputContainer}>
        <TextInput
          className={styles.textInput}
          placeholder="Type your message..."
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyPress={handleKeyPress}
          disabled={isStreaming}
        />
        <Button
          onClick={handleSend}
          disabled={!inputValue.trim() || isStreaming}
          variant="primary"
        >
          Send
        </Button>
      </div>

      {/* Example Queries Section */}
      <div className={styles.exampleQueriesContainer}>
        <Body className={styles.exampleQueriesLabel}>Try these examples:</Body>
        <div className={styles.exampleQueriesGrid}>
          {EXAMPLE_QUERIES.map((query, idx) => (
            <button
              key={idx}
              onClick={() => handleExampleClick(query)}
              disabled={isStreaming}
              className={styles.exampleQueryChip}
              title={query.description}
            >
              <Icon glyph={query.icon} size="small" />
              <span>{query.text}</span>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
