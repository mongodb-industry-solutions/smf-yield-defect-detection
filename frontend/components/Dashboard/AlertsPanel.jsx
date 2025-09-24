"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import { H3, Body, Description } from '@leafygreen-ui/typography';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import AlertAnalysisModal from './AlertAnalysisModal';
import styles from './AlertsPanel.module.css';

const AlertsPanel = () => {
  const { alerts: dataAlerts, refresh } = useDashboardData();
  const [alerts, setAlerts] = useState([]);
  const [expandedAlerts, setExpandedAlerts] = useState(new Set());
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [lastRefresh, setLastRefresh] = useState(new Date());
  const [selectedAlert, setSelectedAlert] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  useEffect(() => {
    if (dataAlerts) {
      // Transform backend alerts to display format with all details
      // Remove duplicates based on alert_id
      const uniqueAlerts = Array.from(
        new Map(dataAlerts.map(alert => [alert.alert_id || alert._id, alert])).values()
      );

      const formattedAlerts = uniqueAlerts.map(alert => ({
        id: alert._id || alert.alert_id,
        alert_id: alert.alert_id,
        title: alert.title || alert.description,
        description: alert.description,
        severity: alert.severity,
        equipment_id: alert.equipment_id,
        timestamp: alert.timestamp,
        status: alert.status || 'open',
        alert_type: alert.alert_type,
        lot_id: alert.lot_id,
        wafer_id: alert.wafer_id,
        // Extract key metrics from source_data
        metrics: alert.source_data?.metrics || alert.metrics || {},
        // Extract correlation insights
        correlations: alert.correlation_data?.correlations || {},
        problematic_materials: alert.correlation_data?.correlations?.process_context?.problematic_materials || [],
        // Preserve all data for modal
        impact: alert.impact,
        rca_recommendations: alert.rca_recommendations,
        historical_context: alert.historical_context,
        correlation_data: alert.correlation_data
      }));

      // Sort by timestamp (most recent first)
      formattedAlerts.sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));

      setAlerts(formattedAlerts);
      setLastRefresh(new Date());
    }
  }, [dataAlerts]);

  // Auto-refresh every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      refresh();
    }, 30000);

    return () => clearInterval(interval);
  }, [refresh]);

  // Format timestamp to readable format
  const formatTime = (timestamp) => {
    if (!timestamp) return 'Unknown';
    const date = new Date(timestamp);
    const now = new Date();
    const diffInMinutes = Math.floor((now - date) / 60000);

    if (diffInMinutes < 60) {
      return `${diffInMinutes} min ago`;
    } else if (diffInMinutes < 1440) {
      const hours = Math.floor(diffInMinutes / 60);
      return `${hours} hour${hours > 1 ? 's' : ''} ago`;
    } else {
      return date.toLocaleDateString();
    }
  };

  // Get severity color
  const getSeverityColor = (severity) => {
    switch(severity?.toLowerCase()) {
      case 'critical':
      case 'high':
        return '#DC382D'; // Red
      case 'warning':
      case 'medium':
        return '#FDB813'; // Yellow
      case 'info':
      case 'low':
        return '#0076FF'; // Blue
      default:
        return '#6B7280'; // Gray
    }
  };

  // Get severity badge variant
  const getSeverityVariant = (severity) => {
    switch(severity?.toLowerCase()) {
      case 'critical':
      case 'high':
        return 'red';
      case 'warning':
      case 'medium':
        return 'yellow';
      case 'info':
      case 'low':
        return 'blue';
      default:
        return 'gray';
    }
  };

  // Toggle alert expansion
  const toggleAlert = (alertId) => {
    setExpandedAlerts(prev => {
      const newSet = new Set(prev);
      if (newSet.has(alertId)) {
        newSet.delete(alertId);
      } else {
        newSet.add(alertId);
      }
      return newSet;
    });
  };

  // Open alert analysis modal
  const openAnalysisModal = (alert) => {
    setSelectedAlert(alert);
    setIsModalOpen(true);
  };

  // Close modal
  const closeModal = () => {
    setIsModalOpen(false);
    setSelectedAlert(null);
  };

  // Handle alert fixed callback
  const handleAlertFixed = (alertId) => {
    // Refresh alerts to show updated status
    refresh();
  };

  // Manual refresh
  const handleRefresh = async () => {
    setIsRefreshing(true);
    await refresh();
    setTimeout(() => setIsRefreshing(false), 500);
  };

  // Resolve all alerts
  const handleResolveAll = async () => {
    try {
      const response = await fetch('http://localhost:8000/alerts/resolve-all', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        }
      });

      if (response.ok) {
        const data = await response.json();
        console.log(`Resolved ${data.alerts_resolved} alerts`);
        // Refresh the alerts list after resolving
        await refresh();
      } else {
        console.error('Failed to resolve all alerts');
      }
    } catch (error) {
      console.error('Error resolving all alerts:', error);
    }
  };

  // Format last refresh time
  const formatLastRefresh = () => {
    const now = new Date();
    const diff = Math.floor((now - lastRefresh) / 1000);
    if (diff < 60) return 'Just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    return `${Math.floor(diff / 3600)}h ago`;
  };

  return (
    <div className={styles.panel}>
      <Card className={styles.header}>
        <div className={styles.headerContent}>
          <div className={styles.headerLeft}>
            <div className={styles.titleRow}>
              <H3>Active Alerts</H3>
              <div className={styles.liveIndicator} title="Auto-refresh enabled (30s)">
                <span className={styles.liveDot}></span>
                <span className={styles.liveText}>LIVE</span>
              </div>
            </div>
            <Description>{alerts.length} alert{alerts.length !== 1 ? 's' : ''} requiring attention</Description>
          </div>
          <div className={styles.headerRight}>
            <button
              className={styles.resolveButton}
              onClick={handleResolveAll}
              title="Resolve all alerts"
            >
              ✓
            </button>
            <button
              className={`${styles.refreshButton} ${isRefreshing ? styles.spinning : ''}`}
              onClick={handleRefresh}
              disabled={isRefreshing}
              title="Refresh alerts"
            >
              ↻
            </button>
            <Description className={styles.lastRefreshText}>
              {formatLastRefresh()}
            </Description>
          </div>
        </div>
      </Card>

      <div className={styles.alertsContainer}>
        {alerts.length === 0 ? (
          <Card className={styles.emptyState}>
            <div className={styles.emptyContent}>
              <Description>✅ All systems operating normally</Description>
            </div>
          </Card>
        ) : (
          <div className={styles.alertsList}>
            {alerts.map(alert => {
              const isExpanded = expandedAlerts.has(alert.id);
              return (
                <Card
                  key={alert.id}
                  className={`${styles.alertCard} ${isExpanded ? styles.expanded : ''}`}
                  onClick={() => toggleAlert(alert.id)}
                >
                  <div
                    className={styles.severityBar}
                    style={{ backgroundColor: getSeverityColor(alert.severity) }}
                  />

                  <div className={styles.alertInner}>
                    {/* Header with severity and time - Always visible */}
                    <div className={styles.alertHeader}>
                      <div className={styles.alertHeaderLeft}>
                        <div className={styles.alertBadgeGroup}>
                          <Badge variant={getSeverityVariant(alert.severity)}>
                            {alert.severity?.toUpperCase()}
                          </Badge>
                          {isExpanded && (
                            <Badge variant="lightgray">
                              {alert.alert_type?.toUpperCase()}
                            </Badge>
                          )}
                        </div>
                        <Body weight="medium" className={styles.alertTitleCompact}>
                          {alert.title}
                        </Body>
                      </div>
                      <div className={styles.alertHeaderRight}>
                        <Description className={styles.timestamp}>
                          {formatTime(alert.timestamp)}
                        </Description>
                        <span className={styles.expandIcon}>
                          {isExpanded ? '▼' : '▶'}
                        </span>
                      </div>
                    </div>

                    {/* Collapsible content */}
                    {isExpanded && (
                      <div className={styles.alertExpandedContent}>
                        {/* Description */}
                        {alert.description && alert.description !== alert.title && (
                          <Description className={styles.alertDescription}>
                            {alert.description}
                          </Description>
                        )}

                        {/* Key details */}
                        <div className={styles.alertMetadata}>
                          <div className={styles.metadataRow}>
                            <span className={styles.metadataLabel}>Equipment:</span>
                            <span className={styles.metadataValue}>{alert.equipment_id}</span>
                          </div>
                          {alert.lot_id && (
                            <div className={styles.metadataRow}>
                              <span className={styles.metadataLabel}>Lot ID:</span>
                              <span className={styles.metadataValue}>{alert.lot_id}</span>
                            </div>
                          )}
                          {alert.wafer_id && (
                            <div className={styles.metadataRow}>
                              <span className={styles.metadataLabel}>Wafer ID:</span>
                              <span className={styles.metadataValue}>{alert.wafer_id}</span>
                            </div>
                          )}
                        </div>

                        {/* Metrics if available */}
                        {alert.metrics && Object.keys(alert.metrics).length > 0 && (
                          <div className={styles.alertMetrics}>
                            <Description className={styles.metricsTitle}>Current Metrics:</Description>
                            <div className={styles.metricsGrid}>
                              {Object.entries(alert.metrics).slice(0, 6).map(([key, value]) => (
                                <div key={key} className={styles.metricItem}>
                                  <span className={styles.metricLabel}>
                                    {key.replace(/_/g, ' ')}
                                  </span>
                                  <span className={styles.metricValue}>
                                    {typeof value === 'number' ? value.toFixed(1) : value}
                                  </span>
                                </div>
                              ))}
                            </div>
                          </div>
                        )}

                        {/* Action buttons and Alert ID at bottom */}
                        <div className={styles.alertFooter}>
                          <Description className={styles.alertId}>ID: {alert.alert_id}</Description>
                          <button
                            className={styles.analyzeButton}
                            onClick={(e) => {
                              e.stopPropagation();
                              openAnalysisModal(alert);
                            }}
                          >
                            Analyze Alert →
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>

      {/* Alert Analysis Modal */}
      <AlertAnalysisModal
        alert={selectedAlert}
        isOpen={isModalOpen}
        onClose={closeModal}
        onAlertFixed={handleAlertFixed}
      />
    </div>
  );
};

export default AlertsPanel;