"use client";

import React from 'react';
import { Body, Description } from '@leafygreen-ui/typography';
import Icon from '@leafygreen-ui/icon';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './FabPulseBar.module.css';

const PulseMetric = ({ label, value, unit, trend, severity, prefix = '', suffix = '' }) => {
  const getTrendIcon = () => {
    if (!trend) return null;
    return trend === 'up' ? 'ArrowUp' : 'ArrowDown';
  };

  const getTrendColor = () => {
    if (!trend) return styles.neutral;
    if (label === 'Active Excursions') {
      return trend === 'down' ? styles.positive : styles.negative;
    }
    return trend === 'up' ? styles.positive : styles.negative;
  };

  const getSeverityClass = () => {
    if (!severity) return '';
    switch(severity) {
      case 'critical': return styles.critical;
      case 'warning': return styles.warning;
      case 'good': return styles.good;
      default: return '';
    }
  };

  return (
    <div className={`${styles.pulseMetric} ${getSeverityClass()}`}>
      <Description className={styles.metricLabel}>{label}</Description>
      <div className={styles.metricValue}>
        <Body weight="bold" className={styles.value}>
          {prefix}{value}{unit}{suffix}
        </Body>
        {trend && (
          <Icon 
            glyph={getTrendIcon()} 
            size="small" 
            className={`${styles.trendIcon} ${getTrendColor()}`}
          />
        )}
      </div>
    </div>
  );
};

const FabPulseBar = ({ fabMetrics }) => {
  const { kpi: kpiData, isLoading } = useDashboardData();
  
  // Use real data if available, otherwise fall back to defaults
  const oee = kpiData ? {
    value: kpiData.equipment_utilization || 87.3,
    unit: '%',
    trend: kpiData.equipment_utilization > 85 ? 'up' : 'down'
  } : { value: 87.3, unit: '%', trend: 'up' };
  
  const excursions = kpiData ? {
    value: kpiData.active_alerts || 0,
    severity: kpiData.active_alerts > 5 ? 'critical' : kpiData.active_alerts > 2 ? 'warning' : 'good',
    trend: kpiData.active_alerts < 3 ? 'down' : 'up'
  } : { value: 2, severity: 'warning', trend: 'down' };
  
  const toolsOnline = kpiData && kpiData.equipment_status ? {
    value: `${kpiData.equipment_status.online}/${kpiData.equipment_status.total}`,
    trend: kpiData.equipment_status.online >= kpiData.equipment_status.total * 0.8 ? 'stable' : 'down'
  } : { value: '12/15', trend: 'stable' };
  
  const currentYield = kpiData ? {
    value: kpiData.current_yield ? parseFloat(kpiData.current_yield).toFixed(1) : 94.2,
    unit: '%',
    trend: kpiData.current_yield > 92 ? 'up' : 'down'
  } : { value: 94.2, unit: '%', trend: 'up' };
  
  const wip = { value: 423, unit: ' wafers', trend: 'up' }; // WIP not in current backend

  return (
    <div className={styles.fabPulseBar}>
      <div className={styles.pulseContainer}>
        <div className={styles.statusIndicator}>
          <div className={styles.statusDot} />
          <Description className={styles.statusText}>LIVE</Description>
        </div>
        
        <PulseMetric 
          label="Overall Equipment Effectiveness"
          value={oee.value}
          unit={oee.unit}
          trend={oee.trend}
        />
        
        <PulseMetric 
          label="Active Excursions"
          value={excursions.value}
          severity={excursions.severity}
          trend={excursions.trend}
        />
        
        <PulseMetric 
          label="Tools Online"
          value={toolsOnline.value}
          trend={toolsOnline.trend}
        />
        
        <PulseMetric 
          label="Current Yield"
          value={currentYield.value}
          unit={currentYield.unit}
          trend={currentYield.trend}
        />
        
        <PulseMetric 
          label="Work in Progress"
          value={wip.value}
          unit={wip.unit}
          trend={wip.trend}
        />
      </div>
    </div>
  );
};

export default FabPulseBar;