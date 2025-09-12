"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import { Body, Description } from '@leafygreen-ui/typography';
import styles from './IntelligentAlertsPanel.module.css';

const SmartAlert = ({ alert }) => {
  const getSeverityIcon = (severity) => {
    switch(severity) {
      case 'critical': return 'Warning';
      case 'warning': return 'ImportantWithCircle';
      case 'predictive': return 'Sparkle';
      case 'info': return 'InfoWithCircle';
      default: return 'Bell';
    }
  };
  
  const getSeverityColor = (severity) => {
    switch(severity) {
      case 'critical': return '#e11900';
      case 'warning': return '#fbb13c';
      case 'predictive': return '#0884dc';
      case 'info': return '#00684a';
      default: return '#6b778c';
    }
  };
  
  const getSeverityBadge = (severity) => {
    switch(severity) {
      case 'critical': return 'red';
      case 'warning': return 'yellow';
      case 'predictive': return 'blue';
      case 'info': return 'green';
      default: return 'gray';
    }
  };
  
  const formatTimeAgo = (timestamp) => {
    const now = new Date();
    const alertTime = new Date(timestamp);
    const diffMs = now - alertTime;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} min${diffMins > 1 ? 's' : ''} ago`;
    const diffHours = Math.floor(diffMins / 60);
    return `${diffHours} hour${diffHours > 1 ? 's' : ''} ago`;
  };
  
  return (
    <div className={`${styles.alertCard} ${styles[alert.severity]}`}>
      <div className={styles.alertHeader}>
        <div className={styles.alertIcon}>
          <Icon 
            glyph={getSeverityIcon(alert.severity)} 
            size="small" 
            fill={getSeverityColor(alert.severity)}
          />
        </div>
        <div className={styles.alertContent}>
          <div className={styles.alertTitle}>
            <Body weight="medium">{alert.title}</Body>
            <Badge variant={getSeverityBadge(alert.severity)} size="small">
              {alert.severity.toUpperCase()}
            </Badge>
          </div>
          
          <Description className={styles.alertMessage}>
            {alert.message}
          </Description>
          
          {alert.correlation && (
            <div className={styles.correlation}>
              <Icon glyph="Link" size="xsmall" />
              <Description>{alert.correlation}</Description>
            </div>
          )}
          
          {alert.recommendation && (
            <div className={styles.recommendation}>
              <Icon glyph="Bulb" size="xsmall" />
              <Body weight="medium">{alert.recommendation}</Body>
            </div>
          )}
          
          {alert.impact && (
            <div className={styles.impact}>
              <Description>Impact: {alert.impact}</Description>
            </div>
          )}
        </div>
        <div className={styles.alertTime}>
          <Description>{formatTimeAgo(alert.timestamp)}</Description>
        </div>
      </div>
    </div>
  );
};

const IntelligentAlertsPanel = () => {
  // Enhanced alert data with intelligent correlations
  const intelligentAlerts = [
    {
      id: 'ia-001',
      severity: 'critical',
      title: 'CMP-01 Particle Excursion',
      message: 'Particle count reached 1,247 (threshold: 1,000)',
      correlation: 'Correlates with Slurry Batch SB-050. 2 other tools using same batch showing early signs.',
      recommendation: 'Pause SB-050 usage immediately. Switch to backup batch SB-051.',
      impact: '3 lots at risk (~75 wafers)',
      timestamp: new Date(Date.now() - 3 * 60000).toISOString()
    },
    {
      id: 'ia-002',
      severity: 'predictive',
      title: 'ETCH-02 Pressure Drift Predicted',
      message: 'Chamber pressure trending upward, excursion expected in ~15 mins',
      correlation: 'Similar pattern detected before previous maintenance event',
      recommendation: 'Schedule preventive recalibration during next idle window',
      impact: 'Potential yield loss of 2-3% if not addressed',
      timestamp: new Date(Date.now() - 8 * 60000).toISOString()
    },
    {
      id: 'ia-003',
      severity: 'warning',
      title: 'Multi-Tool Temperature Deviation',
      message: 'LITHO-02, DEP-01 showing correlated temperature rise',
      correlation: 'Facility HVAC Zone 3 showing reduced cooling capacity',
      recommendation: 'Check HVAC system, adjust zone 3 cooling setpoint',
      impact: 'Process uniformity at risk across 2 tools',
      timestamp: new Date(Date.now() - 15 * 60000).toISOString()
    },
    {
      id: 'ia-004',
      severity: 'info',
      title: 'Maintenance Window Approaching',
      message: 'ETCH-03 scheduled maintenance in 24h',
      correlation: 'Current utilization at 96%, 8 lots queued',
      recommendation: 'Consider rerouting non-critical lots to ETCH-01',
      impact: 'Minimal - preventive action available',
      timestamp: new Date(Date.now() - 30 * 60000).toISOString()
    }
  ];
  
  return (
    <div className={styles.alertsPanel}>
      <div className={styles.alertsList}>
        {intelligentAlerts.map(alert => (
          <SmartAlert key={alert.id} alert={alert} />
        ))}
      </div>
      
      {intelligentAlerts.length === 0 && (
        <div className={styles.noAlerts}>
          <Icon glyph="Checkmark" size="large" fill="#00ed64" />
          <Body>All systems operating normally</Body>
          <Description>No active alerts or predictions</Description>
        </div>
      )}
    </div>
  );
};

export default IntelligentAlertsPanel;