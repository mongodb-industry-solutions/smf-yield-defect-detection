"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import styles from './MongoDBInsightsPanel.module.css';

/**
 * MongoDBInsightsPanel - Shows active MongoDB operations
 * Highlights MongoDB features being used in real-time
 *
 * @param {array} operations - Array of MongoDB operations
 *   Each operation: {
 *     type: string (e.g., '$graphLookup', '$rankFusion', 'vectorSearch'),
 *     status: 'running'|'complete'|'error',
 *     executionTime: number (ms),
 *     description: string
 *   }
 * @param {object} stats - Database statistics
 *   {
 *     totalQueries: number,
 *     avgQueryTime: number,
 *     indexHits: number,
 *     cacheHitRate: number
 *   }
 */
const MongoDBInsightsPanel = ({
  operations = [],
  stats = {}
}) => {
  // Get status color
  const getStatusColor = (status) => {
    switch (status) {
      case 'running':
        return 'var(--color-blue-base)';
      case 'complete':
        return 'var(--color-status-good)';
      case 'error':
        return 'var(--color-status-critical)';
      default:
        return 'var(--color-neutral-base)';
    }
  };

  // Get status variant for badge
  const getStatusVariant = (status) => {
    switch (status) {
      case 'running':
        return 'blue';
      case 'complete':
        return 'green';
      case 'error':
        return 'red';
      default:
        return 'lightgray';
    }
  };

  // Get MongoDB feature color
  const getFeatureColor = (type) => {
    if (type.includes('vector') || type.includes('Vector')) {
      return 'var(--color-purple-base)';
    }
    if (type.includes('search') || type.includes('Search')) {
      return 'var(--color-blue-base)';
    }
    if (type.includes('graph') || type.includes('Graph')) {
      return 'var(--color-blue-dark1)';
    }
    return 'var(--color-primary-dark2)';
  };

  return (
    <Card className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <Icon glyph="Diagram3" fill="var(--color-primary-dark2)" />
          <H3 className={styles.title}>MongoDB Operations</H3>
        </div>
        <Description className={styles.subtitle}>
          Live database operations and performance metrics
        </Description>
      </div>

      {/* Active Operations */}
      {operations.length > 0 && (
        <div className={styles.section}>
          <Description className={styles.sectionTitle}>
            Active Operations
          </Description>
          <div className={styles.operationsList}>
            {operations.map((op, index) => (
              <div key={index} className={styles.operation}>
                <div className={styles.operationHeader}>
                  <div className={styles.operationTitle}>
                    <span
                      className={styles.operationDot}
                      style={{ backgroundColor: getFeatureColor(op.type) }}
                    ></span>
                    <Body className={styles.operationType}>{op.type}</Body>
                  </div>
                  <Badge variant={getStatusVariant(op.status)}>
                    {op.status.toUpperCase()}
                  </Badge>
                </div>

                {op.description && (
                  <Description className={styles.operationDescription}>
                    {op.description}
                  </Description>
                )}

                {op.executionTime && (
                  <div className={styles.operationTime}>
                    <Icon glyph="Clock" size="small" fill="var(--color-neutral-dark1)" />
                    <Description className={styles.timeText}>
                      {op.executionTime}ms
                    </Description>
                  </div>
                )}

                {/* Progress bar for running operations */}
                {op.status === 'running' && (
                  <div className={styles.progressBar}>
                    <div className={styles.progressFill}></div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Database Statistics */}
      {stats && Object.keys(stats).length > 0 && (
        <div className={styles.section}>
          <Description className={styles.sectionTitle}>
            Performance Metrics
          </Description>
          <div className={styles.statsGrid}>
            {stats.totalQueries !== undefined && (
              <div className={styles.stat}>
                <Icon glyph="Database" size="small" fill="var(--color-primary-dark2)" />
                <div className={styles.statContent}>
                  <Body className={styles.statValue}>
                    {stats.totalQueries.toLocaleString()}
                  </Body>
                  <Description className={styles.statLabel}>
                    Total Queries
                  </Description>
                </div>
              </div>
            )}

            {stats.avgQueryTime !== undefined && (
              <div className={styles.stat}>
                <Icon glyph="Clock" size="small" fill="var(--color-blue-base)" />
                <div className={styles.statContent}>
                  <Body className={styles.statValue}>
                    {stats.avgQueryTime}ms
                  </Body>
                  <Description className={styles.statLabel}>
                    Avg Query Time
                  </Description>
                </div>
              </div>
            )}

            {stats.indexHits !== undefined && (
              <div className={styles.stat}>
                <Icon glyph="Checkmark" size="small" fill="var(--color-status-good)" />
                <div className={styles.statContent}>
                  <Body className={styles.statValue}>
                    {stats.indexHits.toLocaleString()}
                  </Body>
                  <Description className={styles.statLabel}>
                    Index Hits
                  </Description>
                </div>
              </div>
            )}

            {stats.cacheHitRate !== undefined && (
              <div className={styles.stat}>
                <Icon glyph="InviteUser" size="small" fill="var(--color-purple-base)" />
                <div className={styles.statContent}>
                  <Body className={styles.statValue}>
                    {stats.cacheHitRate}%
                  </Body>
                  <Description className={styles.statLabel}>
                    Cache Hit Rate
                  </Description>
                </div>
              </div>
            )}
          </div>
        </div>
      )}

      {/* MongoDB Branding Footer */}
      <div className={styles.footer}>
        <Icon glyph="Logo" size="small" fill="var(--color-primary-dark2)" />
        <Description className={styles.footerText}>
          Powered by MongoDB Atlas
        </Description>
      </div>
    </Card>
  );
};

export default MongoDBInsightsPanel;
