"use client";

import React, { useState, useEffect } from 'react';
import Modal from '@leafygreen-ui/modal';
import Button from '@leafygreen-ui/button';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { Tab, Tabs } from '@leafygreen-ui/tabs';
import Card from '@leafygreen-ui/card';
import { H2, H3, Body, Description } from '@leafygreen-ui/typography';
import Code from '@leafygreen-ui/code';
import { alertAPI } from '@/lib/api';
import styles from './AlertAnalysisModal.module.css';

const AlertAnalysisModal = ({ alert, isOpen, onClose, onAlertFixed, aiEnabled = true }) => {
  const [activeTab, setActiveTab] = useState(0); // Start with Overview tab
  const [isFixing, setIsFixing] = useState(false);
  const [fixStatus, setFixStatus] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  useEffect(() => {
    if (alert && isOpen && !alert.correlation_data?.analysis_timestamp) {
      // Trigger analysis if not already done
      analyzeAlert();
    }
  }, [alert, isOpen]);

  const analyzeAlert = async () => {
    if (!alert?.alert_id || isAnalyzing) return;

    setIsAnalyzing(true);
    try {
      await alertAPI.analyzeAlert(alert.alert_id);
      // Analysis triggered, data will be in alert object after refresh
    } catch (error) {
      console.error('Error analyzing alert:', error);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleFix = async () => {
    setIsFixing(true);
    setFixStatus(null);

    try {
      // Add timeout for the fix request (10 seconds)
      const controller = new AbortController();
      const timeoutId = setTimeout(() => controller.abort(), 10000);

      // Using direct fetch through proxy since alertAPI doesn't have fix method
      const response = await fetch(`/api/backend/alerts/${alert.alert_id}/fix`, {
        method: 'POST',
        signal: controller.signal
      });

      clearTimeout(timeoutId);

      if (response.ok) {
        const data = await response.json();
        setFixStatus({
          type: 'success',
          message: data.message || 'Equipment fixed successfully'
        });

        if (onAlertFixed) {
          onAlertFixed(alert.alert_id);
        }

        setTimeout(() => {
          onClose();
        }, 2000);
      } else {
        setFixStatus({
          type: 'error',
          message: 'Failed to fix equipment'
        });
      }
    } catch (error) {
      console.error('Error fixing equipment:', error);

      // Check if it was a timeout
      if (error.name === 'AbortError') {
        setFixStatus({
          type: 'warning',
          message: 'Fix request timed out - the fix may still be processing. Please refresh to check status.'
        });
      } else {
        setFixStatus({
          type: 'error',
          message: 'Error connecting to server'
        });
      }
    } finally {
      setIsFixing(false);
    }
  };

  if (!alert) return null;

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return 'var(--color-risk-critical)';
      case 'high': return 'var(--color-risk-high)';
      case 'medium': return 'var(--color-risk-medium)';
      case 'low': return 'var(--color-risk-low)';
      default: return 'var(--color-neutral-dark1)';
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    return new Date(timestamp).toLocaleString();
  };

  const formatMetricValue = (value, key) => {
    if (typeof value === 'number') {
      if (key.includes('temperature')) return `${value.toFixed(1)}°C`;
      if (key.includes('pressure')) return `${value.toFixed(1)} Torr`;
      if (key.includes('power')) return `${value.toFixed(0)}W`;
      if (key.includes('flow')) return `${value.toFixed(1)} sccm`;
      return value.toFixed(1);
    }
    return value;
  };

  // Extract data from the alert object
  const metrics = alert.source_data?.metrics || alert.metrics || {};
  const metadata = alert.source_data?.metadata || {};
  const correlationData = alert.correlation_data || alert.correlation_analysis || {};
  const rcaData = alert.rca_recommendations || [];
  const rcaHints = alert.rca_hints || alert.rca_analysis || {};

  // Get historical cases from rca_analysis/rca_hints
  // This field is populated immediately by AlertManager and later enhanced by RCA analysis
  const historicalCases = rcaHints.similar_historical_cases || [];

  // Get similar wafer defects from vector search
  const similarWaferDefects = rcaHints.similar_wafer_defects || [];

  // Get identified patterns with probable causes
  const identifiedPatterns = rcaHints.identified_patterns || [];

  // Unified Analysis Tab Data
  const overallConfidence = Math.max(
    rcaHints.confidence_score || 0,
    correlationData.confidence_score || 0
  );
  const insights = correlationData.insights || [];
  const problematicMaterials = correlationData.correlations?.process_context?.problematic_materials || [];
  const temporal = correlationData.correlations?.temporal || null;
  const equipment = correlationData.correlations?.equipment || null;
  const batch = correlationData.correlations?.batch || null;
  const recipe = correlationData.correlations?.recipe || null;
  const spatial = correlationData.correlations?.spatial || null;

  // Filter historical cases by relevance
  const highRelevanceCases = historicalCases.filter(c => c.relevance_score >= 0.7);
  const mediumRelevanceCases = historicalCases.filter(c => c.relevance_score >= 0.5 && c.relevance_score < 0.7);

  // Debug: Log historical cases
  if (historicalCases.length > 0 && isOpen) {
    console.log('[AlertAnalysisModal] Historical Cases:', historicalCases.map(c => ({
      title: c.title,
      relevance: c.relevance_score,
      type: c.document_type
    })));
    console.log('[AlertAnalysisModal] High relevance (≥0.7):', highRelevanceCases.length);
    console.log('[AlertAnalysisModal] Medium relevance (0.5-0.7):', mediumRelevanceCases.length);
  }

  return (
    <Modal
      open={isOpen}
      setOpen={onClose}
      size="large"
      className={styles.modal}
    >
      <div className={styles.modalContainer}>
        {/* Fixed Header */}
        <div className={styles.modalHeader}>
          <div className={styles.headerTop}>
            <H2 className={styles.modalTitle}>Alert Analysis</H2>
            <div className={styles.badgeGroup}>
              <Badge variant={alert.severity === 'critical' ? 'red' : alert.severity === 'high' ? 'yellow' : 'blue'}>
                {alert.severity?.toUpperCase()}
              </Badge>
              <Badge variant={alert.status === 'resolved' ? 'green' : 'lightgray'}>
                {alert.status?.toUpperCase()}
              </Badge>
            </div>
          </div>
          <Body weight="medium" className={styles.alertTitle}>{alert.title}</Body>
          <Description className={styles.alertId}>{alert.alert_id}</Description>
        </div>

        {/* Scrollable Content */}
        <div className={styles.modalContent}>
          <Tabs
            aria-label="Alert Analysis Tabs"
            selected={activeTab}
            setSelected={setActiveTab}
          >
          <Tab name="Overview">
            <div className={styles.tabContent}>
              {/* Basic Alert Information */}
              <Card className={styles.card}>
                <H3 className={styles.sectionTitle}>Alert Details</H3>
                <div className={styles.detailsGrid}>
                  <div className={styles.detailRow}>
                    <span className={styles.label}>Equipment:</span>
                    <span className={styles.value} style={{ fontWeight: '600' }}>{alert.equipment_id}</span>
                  </div>
                  <div className={styles.detailRow}>
                    <span className={styles.label}>Alert Type:</span>
                    <span className={styles.value}>{alert.alert_type}</span>
                  </div>
                  <div className={styles.detailRow}>
                    <span className={styles.label}>Timestamp:</span>
                    <span className={styles.value}>{formatTimestamp(alert.timestamp)}</span>
                  </div>
                  <div className={styles.detailRow}>
                    <span className={styles.label}>Description:</span>
                    <span className={styles.value}>{alert.description}</span>
                  </div>
                  {metadata.lot_id && (
                    <div className={styles.detailRow}>
                      <span className={styles.label}>Lot ID:</span>
                      <span className={styles.value}>{metadata.lot_id}</span>
                    </div>
                  )}
                  {metadata.wafer_id && (
                    <div className={styles.detailRow}>
                      <span className={styles.label}>Wafer ID:</span>
                      <span className={styles.value}>{metadata.wafer_id}</span>
                    </div>
                  )}
                  {metadata.recipe_id && (
                    <div className={styles.detailRow}>
                      <span className={styles.label}>Recipe:</span>
                      <span className={styles.value}>{metadata.recipe_id}</span>
                    </div>
                  )}
                  {alert.estimated_impact && (
                    <div className={styles.detailRow}>
                      <span className={styles.label}>Impact:</span>
                      <span className={styles.value} style={{ color: '#DC382D', fontWeight: '600' }}>
                        {alert.estimated_impact}
                      </span>
                    </div>
                  )}
                </div>
              </Card>

              {/* Current Sensor Metrics */}
              <Card style={{ marginBottom: '20px', padding: '20px' }}>
                <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Sensor Metrics</h3>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '15px' }}>
                  {Object.entries(metrics).map(([key, value]) => {
                    const isAnomaly =
                      (key === 'particle_count' && value > 1000) ||
                      (key === 'rf_power' && value > 1400) ||
                      (key === 'temperature' && value > 75);

                    return (
                      <div key={key} style={{
                        background: isAnomaly ? '#ffebee' : '#f7f9fb',
                        border: isAnomaly ? '1px solid #ef5350' : '1px solid #e0e4e7',
                        borderRadius: '8px',
                        padding: '12px',
                        textAlign: 'center'
                      }}>
                        <div style={{ fontSize: '11px', color: '#6b778c', marginBottom: '4px', textTransform: 'uppercase' }}>
                          {key.replace(/_/g, ' ')}
                        </div>
                        <div style={{
                          fontSize: '20px',
                          fontWeight: '600',
                          color: isAnomaly ? '#DC382D' : '#1e2d3d'
                        }}>
                          {formatMetricValue(value, key)}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </Card>

              {/* Process Context Metadata */}
              {metadata.slurry_batch && (
                <Card style={{ padding: '20px', marginBottom: '20px' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Process Context</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '10px' }}>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Slurry Batch: </span>
                      <span style={{ fontWeight: '600' }}>{metadata.slurry_batch}</span>
                    </div>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Operator: </span>
                      <span style={{ fontWeight: '600' }}>{metadata.operator_id || 'N/A'}</span>
                    </div>
                  </div>
                </Card>
              )}
            </div>
          </Tab>

          <Tab name="Actions">
            <div style={{ padding: '20px' }}>
              <h3 style={{ marginBottom: '20px', color: '#1e2d3d' }}>Available Actions</h3>

              {/* Fix Equipment Action */}
              <Card style={{ padding: '20px', marginBottom: '20px' }}>
                <h4 style={{ marginTop: 0, marginBottom: '15px' }}>Fix Equipment Issue</h4>
                <p style={{ color: '#5e6c84', marginBottom: '15px' }}>
                  This action will inject healthy sensor data into the system, simulating a maintenance fix.
                </p>

                <div style={{ background: '#e8f5e9', border: '1px solid #4caf50', borderRadius: '8px', padding: '15px', marginBottom: '20px' }}>
                  <h5 style={{ marginTop: 0, marginBottom: '10px', color: '#2e7d32' }}>What this will do:</h5>
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    <li>Set particle count to healthy level (450)</li>
                    <li>Normalize RF power to 1200W</li>
                    <li>Reset temperature to 65°C</li>
                    <li>Restore normal chamber pressure and flow rate</li>
                    <li>Mark this alert as resolved</li>
                  </ul>
                </div>

                {fixStatus && (
                  <div style={{
                    padding: '12px',
                    borderRadius: '6px',
                    marginBottom: '20px',
                    background: fixStatus.type === 'success' ? '#e8f5e9' : '#ffebee',
                    color: fixStatus.type === 'success' ? '#2e7d32' : '#c62828',
                    border: `1px solid ${fixStatus.type === 'success' ? '#4caf50' : '#ef5350'}`,
                    fontWeight: '500'
                  }}>
                    {fixStatus.message}
                  </div>
                )}

                <Button
                  variant="primary"
                  onClick={handleFix}
                  disabled={isFixing || alert.status === 'resolved'}
                  style={{
                    width: '100%',
                    padding: '12px',
                    fontSize: '16px'
                  }}
                >
                  {isFixing ? 'Fixing...' : alert.status === 'resolved' ? 'Already Resolved' : 'Fix Equipment'}
                </Button>
              </Card>

              {/* Other Actions */}
              <Card style={{ padding: '20px' }}>
                <h4 style={{ marginTop: 0, marginBottom: '15px' }}>Other Actions</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '12px' }}>
                  <Button
                    variant="default"
                    disabled={alert.status === 'acknowledged'}
                  >
                    Acknowledge Alert
                  </Button>
                  <Button
                    variant="default"
                    disabled={alert.status === 'resolved'}
                  >
                    Escalate to Manager
                  </Button>
                  <Button variant="default">
                    Generate Report
                  </Button>
                  <Button variant="default">
                    View Similar Issues
                  </Button>
                </div>
              </Card>
            </div>
          </Tab>
        </Tabs>
        </div>

        {/* Fixed Footer */}
        <div style={{ padding: '20px', borderTop: '1px solid #e0e4e7', textAlign: 'right', flexShrink: 0 }}>
          <Button variant="default" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default AlertAnalysisModal;