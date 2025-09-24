import React from 'react';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { Description, Body } from '@leafygreen-ui/typography';
import { semanticColors } from '@/utils/semanticColors';
import MongoDBBadge from './MongoDBBadge';
import styles from './PerformanceIndicator.module.css';

const PerformanceIndicator = ({
  executionTime,
  documentsScanned,
  indexUsed,
  throughput,
  indexHitRate,
  activeConnections,
  mongoFeature = null,
  showPoweredBy = true,
  className = '',
  variant = 'inline' // 'inline' | 'expanded' | 'minimal'
}) => {
  // Determine performance status based on metrics
  const getPerformanceStatus = () => {
    if (indexHitRate && indexHitRate < 50) return 'critical';
    if (executionTime && executionTime > 1000) return 'warning';
    if (indexHitRate && indexHitRate < 80) return 'warning';
    return 'good';
  };

  const status = getPerformanceStatus();
  const statusColor = {
    good: semanticColors.mongodb.changeStreams,
    warning: semanticColors.mongodb.timeSeries,
    critical: semanticColors.severity.high
  }[status];

  // Render minimal variant
  if (variant === 'minimal') {
    return (
      <div className={`${styles.minimal} ${className}`}>
        {executionTime !== undefined && (
          <span className={styles.minimalMetric}>
            <Icon glyph="Clock" size="xsmall" fill={statusColor} />
            {executionTime}ms
          </span>
        )}
        {documentsScanned !== undefined && (
          <span className={styles.minimalMetric}>
            {documentsScanned.toLocaleString()} docs
          </span>
        )}
      </div>
    );
  }

  // Render expanded variant
  if (variant === 'expanded') {
    return (
      <div className={`${styles.expanded} ${className}`}>
        <div className={styles.expandedHeader}>
          <Icon glyph="Charts" fill={statusColor} />
          <Description className={styles.expandedTitle}>Performance Metrics</Description>
          {mongoFeature && (
            <MongoDBBadge feature={mongoFeature} size="small" />
          )}
        </div>

        <div className={styles.metricsGrid}>
          {executionTime !== undefined && (
            <div className={styles.gridMetric}>
              <div className={styles.gridIcon}>
                <Icon glyph="Clock" size="small" fill={statusColor} />
              </div>
              <div className={styles.gridContent}>
                <Description className={styles.gridLabel}>Execution</Description>
                <Body className={styles.gridValue}>{executionTime}ms</Body>
              </div>
            </div>
          )}

          {documentsScanned !== undefined && (
            <div className={styles.gridMetric}>
              <div className={styles.gridIcon}>
                <Icon glyph="Database" size="small" fill={semanticColors.mongodb.aggregation} />
              </div>
              <div className={styles.gridContent}>
                <Description className={styles.gridLabel}>Documents</Description>
                <Body className={styles.gridValue}>{documentsScanned.toLocaleString()}</Body>
              </div>
            </div>
          )}

          {indexHitRate !== undefined && (
            <div className={styles.gridMetric}>
              <div className={styles.gridIcon}>
                <Icon glyph="Charts" size="small" fill={
                  indexHitRate > 80 ? semanticColors.mongodb.changeStreams : semanticColors.mongodb.timeSeries
                } />
              </div>
              <div className={styles.gridContent}>
                <Description className={styles.gridLabel}>Index Hit</Description>
                <Body className={styles.gridValue}>{indexHitRate}%</Body>
              </div>
            </div>
          )}

          {throughput !== undefined && (
            <div className={styles.gridMetric}>
              <div className={styles.gridIcon}>
                <Icon glyph="Activity" size="small" fill={semanticColors.mongodb.vectorSearch} />
              </div>
              <div className={styles.gridContent}>
                <Description className={styles.gridLabel}>Throughput</Description>
                <Body className={styles.gridValue}>{throughput}/sec</Body>
              </div>
            </div>
          )}
        </div>

        {indexUsed && (
          <div className={styles.indexInfo}>
            <Icon glyph="Diagram" size="small" />
            <Description>Index: {indexUsed}</Description>
          </div>
        )}
      </div>
    );
  }

  // Default inline variant
  return (
    <div className={`${styles.performanceBar} ${className}`}>
      <div className={styles.metrics}>
        {executionTime !== undefined && (
          <div className={styles.metric}>
            <Icon glyph="Clock" size="small" fill={statusColor} />
            <Description className={styles.metricValue}>{executionTime}ms</Description>
          </div>
        )}

        {documentsScanned !== undefined && (
          <div className={styles.metric}>
            <Icon glyph="Database" size="small" fill={semanticColors.text.secondary} />
            <Description className={styles.metricValue}>
              {documentsScanned.toLocaleString()} docs
            </Description>
          </div>
        )}

        {indexUsed && (
          <div className={styles.metric}>
            <Icon glyph="Charts" size="small" fill={semanticColors.text.secondary} />
            <Description className={styles.metricValue}>{indexUsed}</Description>
          </div>
        )}

        {throughput !== undefined && (
          <div className={styles.metric}>
            <Icon glyph="Activity" size="small" fill={semanticColors.text.secondary} />
            <Description className={styles.metricValue}>{throughput}/sec</Description>
          </div>
        )}

        {indexHitRate !== undefined && (
          <div className={styles.metric}>
            <Icon
              glyph="Charts"
              size="small"
              fill={indexHitRate > 80 ? semanticColors.mongodb.changeStreams : semanticColors.mongodb.timeSeries}
            />
            <Description className={styles.metricValue}>{indexHitRate}% hit rate</Description>
          </div>
        )}

        {activeConnections !== undefined && (
          <div className={styles.metric}>
            <Icon glyph="Connect" size="small" fill={semanticColors.text.secondary} />
            <Description className={styles.metricValue}>{activeConnections} connections</Description>
          </div>
        )}
      </div>

      {showPoweredBy && (
        <div className={styles.poweredBy}>
          <Icon glyph="Sparkle" size="small" fill={semanticColors.mongodb.changeStreams} />
          <Description className={styles.poweredByText}>Powered by MongoDB</Description>
        </div>
      )}

      {/* Performance warning if needed */}
      {status === 'warning' && indexHitRate !== undefined && indexHitRate < 80 && (
        <div className={styles.warning}>
          <Icon glyph="InfoWithCircle" size="small" fill={semanticColors.mongodb.timeSeries} />
          <Description className={styles.warningText}>
            Consider adding an index to improve performance
          </Description>
        </div>
      )}
    </div>
  );
};

// Export preset performance indicators
export const QueryPerformanceIndicator = (props) => (
  <PerformanceIndicator {...props} variant="inline" />
);

export const DetailedPerformanceIndicator = (props) => (
  <PerformanceIndicator {...props} variant="expanded" />
);

export const CompactPerformanceIndicator = (props) => (
  <PerformanceIndicator {...props} variant="minimal" showPoweredBy={false} />
);

export default PerformanceIndicator;