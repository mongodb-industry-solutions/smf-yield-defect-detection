import React, { useState } from 'react';
import Card from '@leafygreen-ui/card';
import Code from '@leafygreen-ui/code';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import Button from '@leafygreen-ui/button';
import { Description, Body, Label } from '@leafygreen-ui/typography';
import { semanticColors } from '@/utils/semanticColors';
import MongoDBBadge from './MongoDBBadge';
import styles from './QueryDisplay.module.css';

const QueryDisplay = ({
  query,
  title = "MongoDB Query",
  description = "View the aggregation pipeline for this visualization",
  metrics = {},
  feature = null,
  collapsedByDefault = true,
  showCopyButton = true,
  showExecuteButton = false,
  onExecute = null,
  language = 'javascript',
  className = ''
}) => {
  const [expanded, setExpanded] = useState(!collapsedByDefault);
  const [copied, setCopied] = useState(false);
  const [executing, setExecuting] = useState(false);

  // Format the query for display
  const formatQuery = (q) => {
    if (typeof q === 'string') return q;
    try {
      return JSON.stringify(q, null, 2);
    } catch {
      return String(q);
    }
  };

  const handleCopy = async () => {
    const queryText = formatQuery(query);
    await navigator.clipboard.writeText(queryText);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleExecute = async () => {
    if (!onExecute) return;
    setExecuting(true);
    try {
      await onExecute(query);
    } finally {
      setExecuting(false);
    }
  };

  // Get feature color if specified
  const featureColor = feature ? semanticColors.mongodb[feature] : null;

  return (
    <Card className={`${styles.queryDisplay} ${className}`}>
      <div className={styles.queryHeader}>
        <div className={styles.queryTitleSection}>
          <div className={styles.queryTitle}>
            <Icon
              glyph="Code"
              fill={featureColor || semanticColors.mongodb.aggregation}
            />
            <span className={styles.titleText}>{title}</span>
            {feature && (
              <MongoDBBadge
                feature={feature}
                size="small"
                active={executing}
              />
            )}
          </div>
          <Description className={styles.queryDescription}>{description}</Description>
        </div>
        <Button
          size="xsmall"
          onClick={() => setExpanded(!expanded)}
          aria-label={expanded ? "Collapse" : "Expand"}
          className={styles.expandButton}
          leftGlyph={<Icon glyph={expanded ? "ChevronUp" : "ChevronDown"} />}
        />
      </div>

      {expanded && (
        <div className={styles.queryContent}>
          {/* Query Code Block */}
          <div className={styles.codeWrapper}>
            <Code
              language={language}
              copyable={false}
              showLineNumbers
              showWindowChrome
              chromeTitle="MongoDB Query"
              className={styles.codeBlock}
            >
              {formatQuery(query)}
            </Code>
          </div>

          {/* Query Metrics */}
          {Object.keys(metrics).length > 0 && (
            <div className={styles.queryMetrics}>
              {metrics.executionTime !== undefined && (
                <Badge variant="blue" className={styles.metricBadge}>
                  <Icon glyph="Clock" size="xsmall" />
                  Execution: {metrics.executionTime}ms
                </Badge>
              )}
              {metrics.docsScanned !== undefined && (
                <Badge variant="green" className={styles.metricBadge}>
                  <Icon glyph="Database" size="xsmall" />
                  Documents: {metrics.docsScanned.toLocaleString()}
                </Badge>
              )}
              {metrics.indexUsed && (
                <Badge variant="yellow" className={styles.metricBadge}>
                  <Icon glyph="Charts" size="xsmall" />
                  Index: {metrics.indexUsed}
                </Badge>
              )}
              {metrics.stages && (
                <Badge variant="lightgray" className={styles.metricBadge}>
                  <Icon glyph="Code" size="xsmall" />
                  Stages: {metrics.stages}
                </Badge>
              )}
            </div>
          )}

          {/* Action Buttons */}
          <div className={styles.actions}>
            {showCopyButton && (
              <Button
                size="small"
                variant="baseGreen"
                leftGlyph={<Icon glyph={copied ? 'Checkmark' : 'Copy'} />}
                onClick={handleCopy}
                disabled={copied}
                className={styles.actionButton}
              >
                {copied ? 'Copied!' : 'Copy Query'}
              </Button>
            )}
            {showExecuteButton && onExecute && (
              <Button
                size="small"
                variant="primary"
                leftGlyph={<Icon glyph="Play" />}
                onClick={handleExecute}
                disabled={executing}
                className={styles.actionButton}
              >
                {executing ? 'Executing...' : 'Execute Query'}
              </Button>
            )}
          </div>

          {/* Performance Tip */}
          {metrics.indexHitRate !== undefined && metrics.indexHitRate < 100 && (
            <div className={styles.performanceTip}>
              <Icon glyph="InfoWithCircle" fill={semanticColors.mongodb.timeSeries} />
              <Description>
                <strong>Performance Tip:</strong> Consider adding an index to improve query performance.
                Current index hit rate: {metrics.indexHitRate}%
              </Description>
            </div>
          )}
        </div>
      )}
    </Card>
  );
};

// Export preset query displays for common MongoDB operations
export const TimeSeriesQueryDisplay = (props) => (
  <QueryDisplay
    feature="timeSeries"
    title="Time-Series Aggregation"
    description="MongoDB's native time-series collections optimize storage and queries for time-stamped data"
    {...props}
  />
);

export const VectorSearchQueryDisplay = (props) => (
  <QueryDisplay
    feature="vectorSearch"
    title="Vector Search Query"
    description="MongoDB Vector Search for semantic similarity using embeddings"
    {...props}
  />
);

export const ChangeStreamsQueryDisplay = (props) => (
  <QueryDisplay
    feature="changeStreams"
    title="Change Streams Pipeline"
    description="Real-time data capture with MongoDB Change Streams"
    {...props}
  />
);

export const AggregationQueryDisplay = (props) => (
  <QueryDisplay
    feature="aggregation"
    title="Aggregation Pipeline"
    description="MongoDB's powerful aggregation framework for data transformation"
    {...props}
  />
);

export default QueryDisplay;