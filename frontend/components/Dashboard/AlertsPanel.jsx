"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Icon from '@leafygreen-ui/icon';
import Badge from '@leafygreen-ui/badge';
import IconButton from '@leafygreen-ui/icon-button';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { appPalette } from '@/lib/palette';
import { useWebSocket } from '@/lib/websocket';
import styles from './AlertsPanel.module.css';

const AlertsPanel = () => {
  const { alerts: wsAlerts, isConnected } = useWebSocket();
  const [alerts, setAlerts] = useState([]);
  const [filter, setFilter] = useState('all'); // all, critical, warning
  
  // Initialize with demo alerts if no WebSocket data
  useEffect(() => {
    if (wsAlerts && wsAlerts.length > 0) {
      setAlerts(wsAlerts);
    } else {
      // Use demo alerts
      const demoAlerts = [
        {
          id: 'alert-001',
          timestamp: new Date(Date.now() - 5 * 60000).toISOString(),
          type: 'particle_excursion',
          severity: 'critical',
          equipment: 'CMP-01',
          metric: 'particle_count',
          value: 1250,
          threshold: 1000,
          message: 'Particle count exceeded threshold on CMP-01',
          acknowledged: false
        },
        {
          id: 'alert-002',
          timestamp: new Date(Date.now() - 15 * 60000).toISOString(),
          type: 'equipment_drift',
          severity: 'warning',
          equipment: 'ETCH-03',
          metric: 'rf_power',
          value: 105,
          threshold: 100,
          message: 'RF Power drift detected on ETCH-03',
          acknowledged: false
        },
        {
          id: 'alert-003',
          timestamp: new Date(Date.now() - 30 * 60000).toISOString(),
          type: 'temperature_variation',
          severity: 'warning',
          equipment: 'LITHO-02',
          metric: 'temperature',
          value: 22.5,
          threshold: 20,
          message: 'Temperature variation on LITHO-02',
          acknowledged: true
        }
      ];
      setAlerts(demoAlerts);
    }
  }, [wsAlerts]);
  
  const acknowledgeAlert = (alertId) => {
    setAlerts(prev => prev.map(alert => 
      alert.id === alertId 
        ? { ...alert, acknowledged: true }
        : alert
    ));
  };
  
  const deleteAlert = (alertId) => {
    setAlerts(prev => prev.filter(alert => alert.id !== alertId));
  };
  
  const filteredAlerts = alerts.filter(alert => {
    if (filter === 'all') return true;
    return alert.severity === filter;
  });
  
  const criticalCount = alerts.filter(a => a.severity === 'critical' && !a.acknowledged).length;
  const warningCount = alerts.filter(a => a.severity === 'warning' && !a.acknowledged).length;
  
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diff = Math.floor((now - date) / 1000); // seconds
    
    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)} min ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)} hours ago`;
    return date.toLocaleDateString();
  };
  
  const getSeverityColor = (severity) => {
    return severity === 'critical' ? appPalette.status.critical : appPalette.status.warning;
  };
  
  const getSeverityIcon = (severity) => {
    return severity === 'critical' ? 'X' : 'Warning';
  };

  return (
    <Card className={styles.panel}>
      <div className={styles.header}>
        <div className={styles.titleSection}>
          <Icon 
            glyph="Bell" 
            size="large" 
            fill={criticalCount > 0 ? appPalette.status.critical : appPalette.status.warning}
          />
          <H3 className={styles.title}>Active Alerts</H3>
          {isConnected && (
            <div className={styles.liveIndicator}>
              <div className={styles.liveDot} />
              <Description>Live</Description>
            </div>
          )}
        </div>
        
        <div className={styles.filterButtons}>
          <button 
            className={`${styles.filterBtn} ${filter === 'all' ? styles.active : ''}`}
            onClick={() => setFilter('all')}
          >
            All ({alerts.length})
          </button>
          <button 
            className={`${styles.filterBtn} ${filter === 'critical' ? styles.active : ''}`}
            onClick={() => setFilter('critical')}
          >
            Critical ({criticalCount})
          </button>
          <button 
            className={`${styles.filterBtn} ${filter === 'warning' ? styles.active : ''}`}
            onClick={() => setFilter('warning')}
          >
            Warning ({warningCount})
          </button>
        </div>
      </div>
      
      <div className={styles.alertsList}>
        {filteredAlerts.length === 0 ? (
          <div className={styles.noAlerts}>
            <Icon glyph="Checkmark" size="large" fill={appPalette.status.success} />
            <Body>No {filter === 'all' ? '' : filter} alerts</Body>
          </div>
        ) : (
          filteredAlerts.map(alert => (
            <div 
              key={alert.id} 
              className={`${styles.alert} ${alert.acknowledged ? styles.acknowledged : ''}`}
            >
              <div className={styles.alertIcon}>
                <Icon 
                  glyph={getSeverityIcon(alert.severity)}
                  size="small"
                  fill={getSeverityColor(alert.severity)}
                />
              </div>
              
              <div className={styles.alertContent}>
                <div className={styles.alertHeader}>
                  <Body weight="medium" className={styles.alertMessage}>
                    {alert.message}
                  </Body>
                  <Badge 
                    variant={alert.severity === 'critical' ? 'red' : 'yellow'}
                    size="small"
                  >
                    {alert.severity.toUpperCase()}
                  </Badge>
                </div>
                
                <div className={styles.alertDetails}>
                  <div className={styles.alertMeta}>
                    <Icon glyph="Settings" size="xsmall" fill={appPalette.text.secondary} />
                    <Description>{alert.equipment}</Description>
                  </div>
                  <div className={styles.alertMeta}>
                    <Icon glyph="Clock" size="xsmall" fill={appPalette.text.secondary} />
                    <Description>{formatTime(alert.timestamp)}</Description>
                  </div>
                  {alert.value && (
                    <div className={styles.alertMeta}>
                      <Icon glyph="Charts" size="xsmall" fill={appPalette.text.secondary} />
                      <Description>
                        {alert.value} / {alert.threshold} (threshold)
                      </Description>
                    </div>
                  )}
                </div>
              </div>
              
              <div className={styles.alertActions}>
                {!alert.acknowledged && (
                  <IconButton
                    onClick={() => acknowledgeAlert(alert.id)}
                    aria-label="Acknowledge"
                    size="small"
                  >
                    <Icon glyph="Checkmark" />
                  </IconButton>
                )}
                <IconButton
                  onClick={() => deleteAlert(alert.id)}
                  aria-label="Dismiss"
                  size="small"
                >
                  <Icon glyph="X" />
                </IconButton>
              </div>
            </div>
          ))
        )}
      </div>
      
      {filteredAlerts.length > 0 && (
        <div className={styles.footer}>
          <Description>
            Showing {filteredAlerts.length} of {alerts.length} alerts
          </Description>
          {criticalCount > 0 && (
            <Body className={styles.criticalWarning}>
              ⚠️ {criticalCount} critical alert{criticalCount > 1 ? 's' : ''} require immediate attention
            </Body>
          )}
        </div>
      )}
    </Card>
  );
};

export default AlertsPanel;