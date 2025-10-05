"use client";

import React, { useState } from 'react';
import ExpandableCard from '@leafygreen-ui/expandable-card';
import Code from '@leafygreen-ui/code';
import Badge from '@leafygreen-ui/badge';
import { Body, Description } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import styles from './QueryTransparencyCard.module.css';

/**
 * QueryTransparencyCard - Reusable component for displaying MongoDB queries
 * Showcases MongoDB operations with syntax highlighting and copy functionality
 *
 * @param {string} title - Card title
 * @param {object|array} query - MongoDB query object or aggregation pipeline
 * @param {string} queryType - Type of query (aggregation, find, update, etc.)
 * @param {number} executionTime - Query execution time in ms
 * @param {number} documentsScanned - Number of documents scanned
 * @param {string} indexUsed - Name of index used
 * @param {boolean} defaultOpen - Whether card is expanded by default
 */
const QueryTransparencyCard = ({
  title = "MongoDB Query",
  query = {},
  queryType = "aggregation",
  executionTime,
  documentsScanned,
  indexUsed,
  defaultOpen = false
}) => {
  const [isExpanded, setIsExpanded] = useState(defaultOpen);

  // Format query for display
  const formattedQuery = JSON.stringify(query, null, 2);

  // Get query type badge variant
  const getQueryTypeVariant = (type) => {
    switch (type.toLowerCase()) {
      case 'aggregation':
        return 'green';
      case 'vector':
        return 'purple';
      case 'search':
        return 'blue';
      case 'find':
        return 'lightgray';
      default:
        return 'darkgray';
    }
  };

  return (
    <div className={styles.container}>
      <ExpandableCard
        title={title}
        description={`MongoDB ${queryType} operation`}
        defaultOpen={defaultOpen}
        onClick={() => setIsExpanded(!isExpanded)}
        className={styles.card}
      >
        <div className={styles.content}>
          {/* Performance Metrics */}
          {(executionTime || documentsScanned || indexUsed) && (
            <div className={styles.metrics}>
              {executionTime && (
                <div className={styles.metric}>
                  <Icon glyph="Clock" size="small" />
                  <Description className={styles.metricLabel}>
                    <strong>{executionTime}ms</strong> execution time
                  </Description>
                </div>
              )}
              {documentsScanned !== undefined && (
                <div className={styles.metric}>
                  <Icon glyph="File" size="small" />
                  <Description className={styles.metricLabel}>
                    <strong>{documentsScanned.toLocaleString()}</strong> documents scanned
                  </Description>
                </div>
              )}
              {indexUsed && (
                <div className={styles.metric}>
                  <Icon glyph="InviteUser" size="small" />
                  <Description className={styles.metricLabel}>
                    Using index: <Badge variant="blue">{indexUsed}</Badge>
                  </Description>
                </div>
              )}
            </div>
          )}

          {/* Query Badge */}
          <div className={styles.queryHeader}>
            <Badge variant={getQueryTypeVariant(queryType)}>
              {queryType.toUpperCase()}
            </Badge>
            <Description className={styles.queryDescription}>
              Copy the query below to use in MongoDB Compass or Shell
            </Description>
          </div>

          {/* Code Block */}
          <div className={styles.codeContainer}>
            <Code
              language="javascript"
              copyable={true}
              darkMode={false}
            >
              {formattedQuery}
            </Code>
          </div>

          {/* MongoDB Feature Callout */}
          <div className={styles.featureCallout}>
            <Icon glyph="InfoWithCircle" size="small" fill="var(--color-blue-base)" />
            <Body className={styles.calloutText}>
              This query demonstrates MongoDB's {queryType === 'aggregation' ? 'powerful aggregation pipeline' :
              queryType === 'vector' ? 'vector search capabilities' :
              queryType === 'search' ? 'Atlas Search features' : 'flexible document model'}
            </Body>
          </div>
        </div>
      </ExpandableCard>
    </div>
  );
};

export default QueryTransparencyCard;
