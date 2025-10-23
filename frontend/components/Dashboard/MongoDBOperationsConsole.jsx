"use client";

import React, { useState, useEffect, useRef } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import IconButton from '@leafygreen-ui/icon-button';
import styles from './MongoDBOperationsConsole.module.css';

const MongoDBOperationsConsole = ({
  maxEvents = 20,
  autoScroll = true,
  pauseOnHover = true,
  defaultExpanded = false
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultExpanded);
  const [operations, setOperations] = useState([]);
  const [isPaused, setIsPaused] = useState(false);
  const [expandedEvents, setExpandedEvents] = useState(new Set()); // Track which events are expanded
  const consoleBodyRef = useRef(null);
  const wsRef = useRef(null);
  const recentEventsRef = useRef(new Map()); // Track recent events for deduplication

  // WebSocket connection for MongoDB operations
  useEffect(() => {
    const connectWebSocket = () => {
      const ws = new WebSocket('ws://localhost:8000/ws/alerts');
      wsRef.current = ws;

      ws.onopen = () => {
        console.log('MongoDB Operations Console: WebSocket connected');
      };

      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          // Filter for mongodb_operation messages
          if (data.type === 'mongodb_operation') {
            // DEDUPLICATION: Create unique key from operation_type + collection
            const dedupeKey = `${data.operation_type}:${data.collection}`;
            const now = Date.now();

            // Check if we've seen this exact operation type recently (within 500ms)
            const recentEvent = recentEventsRef.current.get(dedupeKey);
            if (recentEvent && (now - recentEvent.timestamp) < 500) {
              // Skip duplicate - already seen this operation recently
              console.log(`Deduped: ${dedupeKey} (seen ${now - recentEvent.timestamp}ms ago)`);
              return;
            }

            // Record this event for deduplication
            recentEventsRef.current.set(dedupeKey, {
              timestamp: now,
              data: data
            });

            // Clean up old entries (older than 1 second)
            for (const [key, value] of recentEventsRef.current.entries()) {
              if (now - value.timestamp > 1000) {
                recentEventsRef.current.delete(key);
              }
            }

            setOperations(prev => {
              const newOps = [...prev, data];
              // Keep only last maxEvents
              if (newOps.length > maxEvents) {
                return newOps.slice(-maxEvents);
              }
              return newOps;
            });
          }
        } catch (error) {
          console.error('MongoDB Console: Error parsing WebSocket message:', error);
        }
      };

      ws.onerror = (error) => {
        console.error('MongoDB Console: WebSocket error:', error);
      };

      ws.onclose = () => {
        console.log('MongoDB Console: WebSocket closed, reconnecting in 3s...');
        setTimeout(connectWebSocket, 3000);
      };
    };

    connectWebSocket();

    return () => {
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [maxEvents]);

  // Auto-scroll to bottom when new operations arrive
  useEffect(() => {
    if (autoScroll && !isPaused && consoleBodyRef.current && isExpanded) {
      consoleBodyRef.current.scrollTop = consoleBodyRef.current.scrollHeight;
    }
  }, [operations, autoScroll, isPaused, isExpanded]);

  // Format timestamp
  const formatTimestamp = (isoString) => {
    const date = new Date(isoString);
    return date.toLocaleTimeString('en-US', {
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      fractionalSecondDigits: 3
    });
  };

  // Get badge variant for operation type
  const getBadgeVariant = (operationType) => {
    const variants = {
      'change_stream': 'green',
      'insert': 'blue',
      'update': 'yellow',
      'vector_search': 'purple',
      'aggregation': 'darkgray'
    };
    return variants[operationType] || 'lightgray';
  };

  // Format operation label
  const formatOperationType = (type) => {
    const labels = {
      'change_stream': 'CHANGE STREAM',
      'insert': 'INSERT',
      'update': 'UPDATE',
      'vector_search': 'VECTOR SEARCH',
      'aggregation': 'AGGREGATION'
    };
    return labels[type] || type.toUpperCase();
  };

  // Format JSON for display with syntax highlighting
  const formatJSON = (obj, indent = 2) => {
    return JSON.stringify(obj, null, indent);
  };

  // Render collapsed summary
  const renderCollapsedSummary = () => {
    const recentOps = operations.slice(-3);
    if (recentOps.length === 0) {
      return <span className={styles.summaryText}>Waiting for MongoDB operations...</span>;
    }

    return (
      <div className={styles.summaryContainer}>
        {recentOps.map((op, idx) => (
          <span key={idx} className={styles.summaryItem}>
            {formatOperationType(op.operation_type)}: {op.collection}
          </span>
        ))}
      </div>
    );
  };

  // Toggle event expansion
  const toggleEventExpansion = (index) => {
    setExpandedEvents(prev => {
      const newSet = new Set(prev);
      if (newSet.has(index)) {
        newSet.delete(index);
      } else {
        newSet.add(index);
      }
      return newSet;
    });
  };

  // Render operation entry
  const renderOperation = (operation, index) => {
    const { timestamp, operation_type, collection, operation: opCommand, document, metadata } = operation;
    const isEventExpanded = expandedEvents.has(index);

    return (
      <div key={index} className={styles.operation}>
        <div
          className={styles.operationHeader}
          onClick={() => toggleEventExpansion(index)}
        >
          <div className={styles.operationHeaderLeft}>
            <IconButton
              aria-label={isEventExpanded ? "Collapse event" : "Expand event"}
              className={styles.expandButton}
              onClick={(e) => {
                e.stopPropagation();
                toggleEventExpansion(index);
              }}
            >
              <Icon glyph={isEventExpanded ? "ChevronDown" : "ChevronRight"} size="small" />
            </IconButton>
            <span className={styles.operationTimestamp}>
              [{formatTimestamp(timestamp)}]
            </span>
            <Badge variant={getBadgeVariant(operation_type)} className={styles.operationBadge}>
              {formatOperationType(operation_type)}
            </Badge>
            <span className={styles.operationCollectionName}>
              {collection}
            </span>
          </div>
        </div>

        {isEventExpanded && (
          <div className={styles.operationContent}>
            <div className={styles.operationCommand}>
              {operation_type === 'change_stream' && (
                <>
                  <span className={styles.label}>Watch:</span> {collection} (timeseries)
                </>
              )}
              {operation_type === 'insert' && (
                <>
                  <span className={styles.label}>db.{collection}.insertOne()</span>
                </>
              )}
              {operation_type === 'update' && (
                <>
                  <span className={styles.label}>db.{collection}.updateOne()</span>
                </>
              )}
              {operation_type === 'vector_search' && (
                <>
                  <span className={styles.label}>db.{collection}.aggregate([{'{'}$vectorSearch: ...{'}'}])</span>
                </>
              )}
              {operation_type === 'aggregation' && (
                <>
                  <span className={styles.label}>db.{collection}.aggregate([...])</span>
                </>
              )}
            </div>

            {document && (
              <pre className={styles.jsonBlock}>
                <code className={styles.jsonSyntax}>
                  {formatJSON(document)}
                </code>
              </pre>
            )}

            {metadata && Object.keys(metadata).length > 0 && (
              <div className={styles.metadata}>
                {metadata.index_used && (
                  <span className={styles.metadataItem}>
                    Index: <span className={styles.metadataValue}>{metadata.index_used}</span>
                  </span>
                )}
                {metadata.execution_time_ms && (
                  <span className={styles.metadataItem}>
                    Execution: <span className={styles.metadataValue}>{metadata.execution_time_ms}ms</span>
                  </span>
                )}
                {metadata.docs_processed && (
                  <span className={styles.metadataItem}>
                    Docs: <span className={styles.metadataValue}>{metadata.docs_processed}</span>
                  </span>
                )}
                {metadata.similarity_score && (
                  <span className={styles.metadataItem}>
                    Similarity: <span className={styles.metadataValue}>{metadata.similarity_score.toFixed(2)}</span>
                  </span>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    );
  };

  return (
    <Card className={`${styles.console} ${isExpanded ? styles.consoleExpanded : styles.consoleCollapsed}`}>
      <div
        className={styles.consoleHeader}
        onClick={() => setIsExpanded(!isExpanded)}
      >
        <div className={styles.headerLeft}>
          <Icon glyph="Database" size="small" className={styles.headerIcon} />
          <h4 className={styles.headerTitle}>
            MongoDB Operations
            {operations.length > 0 && (
              <span className={styles.eventCount}>({operations.length} events)</span>
            )}
          </h4>
        </div>
        <div className={styles.headerRight}>
          {!isExpanded && renderCollapsedSummary()}
          <IconButton
            aria-label={isExpanded ? "Collapse console" : "Expand console"}
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            <Icon glyph={isExpanded ? "ChevronUp" : "ChevronDown"} />
          </IconButton>
        </div>
      </div>

      {isExpanded && (
        <div
          className={styles.consoleBody}
          ref={consoleBodyRef}
          onMouseEnter={() => pauseOnHover && setIsPaused(true)}
          onMouseLeave={() => pauseOnHover && setIsPaused(false)}
        >
          {operations.length === 0 ? (
            <div className={styles.emptyState}>
              <Icon glyph="Clock" size="large" className={styles.emptyIcon} />
              <p className={styles.emptyText}>Waiting for MongoDB operations...</p>
              <p className={styles.emptySubtext}>
                Change streams, inserts, vector searches, and aggregations will appear here
              </p>
            </div>
          ) : (
            <div className={styles.operationsList}>
              {operations.map((op, idx) => renderOperation(op, idx))}
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

export default MongoDBOperationsConsole;
