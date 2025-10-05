"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import { H2, Body, Description } from '@leafygreen-ui/typography';
import { getSeverityColor, getSeverityVariant } from '@/lib/design-tokens';
import styles from './RiskScoreCard.module.css';

/**
 * RiskScoreCard - Display risk/yield score with visual indicators
 * Professional score card with MongoDB branding
 *
 * @param {number} score - Score value (0-100)
 * @param {string} label - Score label (e.g., "Yield", "Quality Score")
 * @param {string} level - Risk level (critical, high, medium, low)
 * @param {number} trend - Trend value (+/- percentage)
 * @param {string} trendDirection - up or down
 * @param {array} breakdown - Array of {label, value, color} for contributing factors
 */
const RiskScoreCard = ({
  score = 0,
  label = "Score",
  level = "low",
  trend = 0,
  trendDirection = "up",
  breakdown = []
}) => {
  // Get colors based on level
  const scoreColor = getSeverityColor(level);
  const badgeVariant = getSeverityVariant(level);

  // Calculate gradient colors for background
  const getGradientColors = () => {
    switch (level.toLowerCase()) {
      case 'critical':
        return ['#8B0000', '#DC382D'];
      case 'high':
        return ['#C3190C', '#FF7968'];
      case 'medium':
      case 'warning':
        return ['#D59700', '#FFC555'];
      case 'low':
        return ['#00684A', '#83FFCD'];
      default:
        return ['#89979B', '#C1C7C6'];
    }
  };

  const [gradientStart, gradientEnd] = getGradientColors();

  // Format score for display
  const formattedScore = typeof score === 'number' ? score.toFixed(1) : '--';

  return (
    <Card className={styles.card}>
      <div className={styles.container}>
        {/* Score Display */}
        <div
          className={styles.scoreDisplay}
          style={{
            background: `linear-gradient(135deg, ${gradientStart}, ${gradientEnd})`
          }}
        >
          <H2 className={styles.scoreValue} style={{ color: '#fff' }}>
            {formattedScore}
            <span className={styles.scoreUnit}>%</span>
          </H2>
          <Description className={styles.scoreLabel} style={{ color: 'rgba(255,255,255,0.9)' }}>
            {label}
          </Description>
        </div>

        {/* Level Badge & Trend */}
        <div className={styles.metadata}>
          <Badge variant={badgeVariant} className={styles.levelBadge}>
            {level.toUpperCase()} {level === 'low' || level === 'good' ? '' : 'RISK'}
          </Badge>

          {trend !== 0 && (
            <div className={`${styles.trend} ${trendDirection === 'up' ? styles.trendUp : styles.trendDown}`}>
              <span className={styles.trendIcon}>
                {trendDirection === 'up' ? '↑' : '↓'}
              </span>
              <span className={styles.trendValue}>
                {Math.abs(trend).toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Breakdown of Contributing Factors */}
        {breakdown && breakdown.length > 0 && (
          <div className={styles.breakdown}>
            <Description className={styles.breakdownTitle}>
              Contributing Factors
            </Description>
            <div className={styles.breakdownList}>
              {breakdown.map((factor, index) => (
                <div key={index} className={styles.breakdownItem}>
                  <div className={styles.breakdownLabel}>
                    <span
                      className={styles.breakdownDot}
                      style={{ backgroundColor: factor.color || 'var(--color-neutral-base)' }}
                    ></span>
                    <Body className={styles.breakdownText}>{factor.label}</Body>
                  </div>
                  <Body className={styles.breakdownValue}>
                    {factor.value}
                    {factor.unit || ''}
                  </Body>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* MongoDB Branding */}
        <div className={styles.branding}>
          <Description className={styles.brandingText}>
            Powered by MongoDB Atlas
          </Description>
        </div>
      </div>
    </Card>
  );
};

export default RiskScoreCard;
