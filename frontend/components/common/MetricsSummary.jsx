"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { getMetricColor } from '@/lib/design-tokens';
import styles from './MetricsSummary.module.css';

/**
 * MetricsSummary - Grid layout for KPI metrics
 * Professional metrics display with thresholds and trends
 *
 * @param {array} metrics - Array of metric objects
 *   Each metric: {
 *     label: string,
 *     value: number|string,
 *     unit: string,
 *     icon: string (LeafyGreen icon name),
 *     trend: 'up'|'down'|'neutral',
 *     trendValue: number,
 *     thresholds: {good: number, warning: number} (optional)
 *   }
 * @param {number} columns - Number of columns (1-4)
 */
const MetricsSummary = ({
  metrics = [],
  columns = 4
}) => {
  // Get trend icon
  const getTrendIcon = (trend) => {
    switch (trend) {
      case 'up': return '↑';
      case 'down': return '↓';
      default: return '−';
    }
  };

  // Get trend color
  const getTrendColor = (trend, isPositiveGood = true) => {
    if (trend === 'neutral') return 'var(--color-neutral-base)';
    if (isPositiveGood) {
      return trend === 'up' ? 'var(--color-status-good)' : 'var(--color-status-critical)';
    } else {
      return trend === 'up' ? 'var(--color-status-critical)' : 'var(--color-status-good)';
    }
  };

  return (
    <div
      className={styles.grid}
      style={{ gridTemplateColumns: `repeat(${columns}, 1fr)` }}
    >
      {metrics.map((metric, index) => {
        // Calculate metric color based on thresholds
        const valueColor = metric.thresholds
          ? getMetricColor(metric.value, metric.thresholds)
          : 'var(--color-neutral-dark3)';

        // Determine if higher is better for trend coloring
        const isPositiveGood = metric.isPositiveGood !== false;

        return (
          <Card key={index} className={styles.metricCard}>
            <div className={styles.metricContent}>
              {/* Icon */}
              {metric.icon && (
                <div className={styles.iconContainer}>
                  <Icon
                    glyph={metric.icon}
                    size="large"
                    fill="var(--color-primary-dark2)"
                  />
                </div>
              )}

              {/* Label */}
              <Description className={styles.label}>
                {metric.label}
              </Description>

              {/* Value */}
              <div className={styles.valueContainer}>
                <H3
                  className={styles.value}
                  style={{ color: valueColor }}
                >
                  {typeof metric.value === 'number'
                    ? metric.value.toLocaleString()
                    : metric.value}
                  {metric.unit && (
                    <span className={styles.unit}>{metric.unit}</span>
                  )}
                </H3>

                {/* Trend Indicator */}
                {metric.trend && metric.trendValue !== undefined && (
                  <div
                    className={styles.trend}
                    style={{ color: getTrendColor(metric.trend, isPositiveGood) }}
                  >
                    <span className={styles.trendIcon}>
                      {getTrendIcon(metric.trend)}
                    </span>
                    <span className={styles.trendValue}>
                      {Math.abs(metric.trendValue).toFixed(1)}%
                    </span>
                  </div>
                )}
              </div>

              {/* Additional Info */}
              {metric.subtitle && (
                <Description className={styles.subtitle}>
                  {metric.subtitle}
                </Description>
              )}
            </div>
          </Card>
        );
      })}
    </div>
  );
};

export default MetricsSummary;
