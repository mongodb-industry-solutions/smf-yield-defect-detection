"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import { Body, Label } from '@leafygreen-ui/typography';
import { appPalette, getKPIVariant, getTrendColor } from '@/lib/palette';
import styles from './KPICard.module.css';

const KPICard = ({ 
  label, 
  value, 
  unit = '', 
  prefix = '',
  trend = null, 
  trendValue = null,
  trendLabel = '%',
  icon = 'Charts',
  thresholds = null,
  period = null,
  mongoMetrics = null // { queryTime: 12, docsScanned: 5764 }
}) => {
  // Determine the variant based on thresholds
  const variant = getKPIVariant(value, thresholds);
  const colors = appPalette.kpi[variant];
  const trendColor = getTrendColor(trend);
  
  // Format the display value
  const displayValue = `${prefix}${value}${unit}`;
  
  // Get trend icon
  const getTrendIcon = () => {
    switch(trend) {
      case 'up': return 'ArrowUp';
      case 'down': return 'ArrowDown';
      case 'stable': return 'Dash';
      default: return null;
    }
  };

  return (
    <Card className={styles.card}>
      <div 
        className={styles.header}
        style={{ 
          backgroundColor: colors.bg,
          borderLeft: `4px solid ${colors.border}`
        }}
      >
        <Icon 
          glyph={icon} 
          size="large" 
          fill={colors.text}
        />
      </div>
      
      <div className={styles.content}>
        <Label className={styles.label}>{label}</Label>
        
        <div className={styles.valueContainer}>
          <span 
            className={styles.value}
            style={{ color: colors.text }}
          >
            {displayValue}
          </span>
          
          {trend && (
            <div className={styles.trend}>
              <Icon 
                glyph={getTrendIcon()} 
                size="small" 
                fill={trendColor}
              />
              {trendValue && (
                <span 
                  className={styles.trendValue}
                  style={{ color: trendColor }}
                >
                  {Math.abs(trendValue)}{trendLabel}
                </span>
              )}
            </div>
          )}
        </div>
        
        {period && (
          <Body className={styles.period}>{period}</Body>
        )}
        
        {mongoMetrics && (
          <div className={styles.mongoMetrics}>
            <Icon 
              glyph="Database" 
              size="xsmall" 
              fill={appPalette.text.secondary}
            />
            <span className={styles.mongoText}>
              {mongoMetrics.queryTime}ms | {mongoMetrics.docsScanned.toLocaleString()} docs
            </span>
          </div>
        )}
      </div>
    </Card>
  );
};

export default KPICard;