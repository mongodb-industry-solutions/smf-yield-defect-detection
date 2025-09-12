"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { H3, Body } from '@leafygreen-ui/typography';
import { kpiData } from '@/lib/mockData';
import { appPalette } from '@/lib/palette';
import styles from './KPIPanel.module.css';

const KPIPanel = () => {
  const getTrendIcon = (trend) => {
    switch(trend) {
      case 'up': return 'ArrowUp';
      case 'down': return 'ArrowDown';
      default: return 'Dash';
    }
  };
  
  const getTrendColor = (trend) => {
    return trend === 'up' ? appPalette.status.success : 
           trend === 'down' ? appPalette.status.critical : 
           appPalette.text.secondary;
  };

  return (
    <Card className={styles.panel}>
      <div className={styles.header}>
        <Icon glyph="Charts" size="large" fill={appPalette.status.info} />
        <H3 className={styles.title}>Key Metrics</H3>
      </div>
      
      <div className={styles.kpiList}>
        {/* Current Yield */}
        <div className={styles.kpiItem}>
          <div className={styles.kpiHeader}>
            <div className={styles.kpiLabel}>
              <Icon glyph="Charts" size="small" fill={appPalette.status.success} />
              <Body weight="medium">Current Yield</Body>
            </div>
            <Badge variant="green" size="small">GOOD</Badge>
          </div>
          
          <div className={styles.kpiValue}>
            <span className={styles.mainValue}>{kpiData.yield.value}%</span>
            <div className={styles.trend}>
              <Icon 
                glyph={getTrendIcon(kpiData.yield.trend)} 
                size="small" 
                fill={getTrendColor(kpiData.yield.trend)}
              />
              <span style={{ color: getTrendColor(kpiData.yield.trend) }}>
                {kpiData.yield.trendValue}%
              </span>
            </div>
          </div>
        </div>
        
        {/* Active Alerts */}
        <div className={styles.kpiItem}>
          <div className={styles.kpiHeader}>
            <div className={styles.kpiLabel}>
              <Icon glyph="Warning" size="small" fill={appPalette.status.warning} />
              <Body weight="medium">Active Alerts</Body>
            </div>
            <Badge variant="yellow" size="small">WARNING</Badge>
          </div>
          
          <div className={styles.kpiValue}>
            <span className={styles.mainValue}>{kpiData.alerts.value}</span>
            <div className={styles.trend}>
              <Icon 
                glyph={getTrendIcon(kpiData.alerts.trend)} 
                size="small" 
                fill={getTrendColor(kpiData.alerts.trend)}
              />
              <span style={{ color: getTrendColor(kpiData.alerts.trend) }}>
                {Math.abs(kpiData.alerts.trendValue)}
              </span>
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
};

export default KPIPanel;