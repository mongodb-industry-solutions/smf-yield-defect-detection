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
import styles from './AlertAnalysisModal.module.css';

const AlertAnalysisModal = ({ alert, isOpen, onClose, onAlertFixed }) => {
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
      const response = await fetch(`http://localhost:8000/alerts/${alert.alert_id}/analyze`, {
        method: 'POST'
      });
      if (response.ok) {
        // Analysis triggered, data will be in alert object after refresh
      }
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

      const response = await fetch(`http://localhost:8000/alerts/${alert.alert_id}/fix`, {
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

              {/* Alert Lifecycle Timeline */}
              <Card style={{ padding: '20px' }}>
                <H3 style={{ marginTop: 0, marginBottom: '15px' }}>Alert Timeline</H3>
                <div style={{ position: 'relative', paddingLeft: '30px' }}>
                  {/* Created */}
                  <div style={{ marginBottom: '16px', position: 'relative' }}>
                    <div style={{ position: 'absolute', left: '-30px', top: '4px', width: '20px', height: '20px', borderRadius: '50%', backgroundColor: '#00A35C', border: '3px solid white', boxShadow: '0 0 0 2px #00A35C' }} />
                    <Body weight="medium" style={{ fontSize: '12px' }}>Created</Body>
                    <Description style={{ fontSize: '11px' }}>{formatTimestamp(alert.timestamp)}</Description>
                  </div>

                  {/* RCA Generated */}
                  {alert.rca_analysis?.generated_at && (
                    <div style={{ marginBottom: '16px', position: 'relative' }}>
                      <div style={{ position: 'absolute', left: '-30px', top: '4px', width: '20px', height: '20px', borderRadius: '50%', backgroundColor: '#00A35C', border: '3px solid white', boxShadow: '0 0 0 2px #00A35C' }} />
                      <Body weight="medium" style={{ fontSize: '12px' }}>RCA Analysis Completed</Body>
                      <Description style={{ fontSize: '11px' }}>{formatTimestamp(alert.rca_analysis.generated_at)}</Description>
                    </div>
                  )}

                  {/* Correlation Analysis */}
                  {(alert.correlation_data?.analysis_timestamp || alert.correlation_analysis?.analysis_timestamp) && (
                    <div style={{ marginBottom: '16px', position: 'relative' }}>
                      <div style={{ position: 'absolute', left: '-30px', top: '4px', width: '20px', height: '20px', borderRadius: '50%', backgroundColor: '#00A35C', border: '3px solid white', boxShadow: '0 0 0 2px #00A35C' }} />
                      <Body weight="medium" style={{ fontSize: '12px' }}>Correlation Analysis Completed</Body>
                      <Description style={{ fontSize: '11px' }}>{formatTimestamp(alert.correlation_data?.analysis_timestamp || alert.correlation_analysis?.analysis_timestamp)}</Description>
                    </div>
                  )}

                  {/* Acknowledged */}
                  {alert.acknowledged_at && (
                    <div style={{ marginBottom: '16px', position: 'relative' }}>
                      <div style={{ position: 'absolute', left: '-30px', top: '4px', width: '20px', height: '20px', borderRadius: '50%', backgroundColor: '#FFB000', border: '3px solid white', boxShadow: '0 0 0 2px #FFB000' }} />
                      <Body weight="medium" style={{ fontSize: '12px' }}>Acknowledged</Body>
                      <Description style={{ fontSize: '11px' }}>{formatTimestamp(alert.acknowledged_at)}</Description>
                    </div>
                  )}

                  {/* Resolved */}
                  {alert.resolved_at ? (
                    <div style={{ position: 'relative' }}>
                      <div style={{ position: 'absolute', left: '-30px', top: '4px', width: '20px', height: '20px', borderRadius: '50%', backgroundColor: '#00A35C', border: '3px solid white', boxShadow: '0 0 0 2px #00A35C' }} />
                      <Body weight="medium" style={{ fontSize: '12px' }}>Resolved</Body>
                      <Description style={{ fontSize: '11px' }}>{formatTimestamp(alert.resolved_at)}</Description>
                    </div>
                  ) : (
                    <div style={{ position: 'relative' }}>
                      <div style={{ position: 'absolute', left: '-30px', top: '4px', width: '20px', height: '20px', borderRadius: '50%', backgroundColor: '#E0E4E7', border: '3px solid white', boxShadow: '0 0 0 2px #E0E4E7' }} />
                      <Body weight="medium" style={{ fontSize: '12px', color: '#6b778c' }}>Awaiting Resolution</Body>
                    </div>
                  )}
                </div>
              </Card>
            </div>
          </Tab>

          <Tab name="Analysis">
            <div className={styles.tabContent}>
              {/* NEW: Excursion Trigger Section */}
              {alert.source_data?.excursion_type && (
                <Card style={{ marginBottom: '20px', padding: '20px', backgroundColor: '#FFF4E6', borderLeft: '4px solid #FF991F' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Icon glyph="Warning" size="large" fill="#FF991F" />
                    <div style={{ flex: 1 }}>
                      <H3 style={{ margin: 0, marginBottom: '4px' }}>Excursion Detected</H3>
                      <Body weight="medium" style={{ fontSize: '16px' }}>
                        {alert.source_data.excursion_type.replace(/_/g, ' ').toUpperCase()}
                      </Body>
                      {alert.source_data.excursion_type === 'temperature_drift' && alert.source_data.metrics?.temp_drift && (
                        <Description style={{ marginTop: '4px' }}>
                          Drift: {alert.source_data.metrics.temp_drift}°C (Current: {alert.source_data.metrics?.temperature}°C, Threshold: 65°C)
                        </Description>
                      )}
                      {alert.source_data.excursion_type === 'particle_excursion' && alert.source_data.metrics?.particle_count > 1000 && (
                        <Description style={{ marginTop: '4px' }}>
                          Particle Count: {alert.source_data.metrics.particle_count}/cm³ (Threshold: 1000/cm³)
                        </Description>
                      )}
                      {alert.source_data.excursion_type === 'rf_power_drift' && alert.source_data.metrics?.rf_power && (
                        <Description style={{ marginTop: '4px' }}>
                          RF Power: {alert.source_data.metrics.rf_power}W (Threshold: 1400W)
                        </Description>
                      )}
                    </div>
                    <Badge variant="red" style={{ fontSize: '14px' }}>
                      {alert.rca_analysis?.suggested_priority?.toUpperCase() || 'URGENT'}
                    </Badge>
                  </div>
                </Card>
              )}

              {/* Section 1: Analysis Summary */}
              {(overallConfidence > 0 || insights.length > 0) && (
                <Card style={{ marginBottom: '20px', padding: '20px', backgroundColor: '#f9fbfa' }}>
                  <H3 style={{ margin: 0, marginBottom: '16px' }}>Analysis Summary</H3>

                  {overallConfidence > 0 && (
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: insights.length > 0 ? '16px' : '0' }}>
                      <div>
                        <Body weight="medium">Overall Confidence</Body>
                        <Description style={{ fontSize: '12px' }}>Combined confidence from correlation and RCA analysis</Description>
                      </div>
                      <Badge variant={overallConfidence > 0.8 ? 'green' : overallConfidence > 0.6 ? 'yellow' : 'lightgray'} style={{ fontSize: '16px', padding: '8px 16px' }}>
                        {Math.round(overallConfidence * 100)}%
                      </Badge>
                    </div>
                  )}

                  {insights.length > 0 && (
                    <div>
                      {overallConfidence > 0 && <div style={{ borderTop: '1px solid #e0e4e7', margin: '16px 0' }} />}
                      <Body weight="medium" style={{ marginBottom: '12px' }}>Key Insights</Body>
                      <ul style={{ margin: 0, paddingLeft: '20px' }}>
                        {insights.map((insight, index) => (
                          <li key={index} style={{ marginBottom: '8px', lineHeight: '1.5' }}>
                            <Body style={{ fontSize: '13px' }}>{insight}</Body>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </Card>
              )}

              {/* Section 2: Root Cause Identification */}
              {(identifiedPatterns.length > 0 || problematicMaterials.length > 0 || rcaData.length > 0) && (
                <Card style={{ marginBottom: '20px', padding: '20px', borderLeft: '4px solid #C84018' }}>
                  <H3 style={{ margin: 0, marginBottom: '16px', color: '#C84018' }}>Root Cause Identification</H3>

                  {/* NEW: Identified Patterns with Probable Causes */}
                  {identifiedPatterns.length > 0 && (
                    <div style={{ marginBottom: (problematicMaterials.length > 0 || rcaData.length > 0) ? '24px' : '0' }}>
                      <Body weight="medium" style={{ marginBottom: '12px' }}>Identified Patterns</Body>
                      <Description style={{ marginBottom: '12px', fontSize: '12px' }}>
                        Pattern-based analysis with probable root causes
                      </Description>
                      {identifiedPatterns.map((pattern, idx) => (
                        <Card key={idx} style={{ padding: '15px', marginBottom: '12px', backgroundColor: '#FFF9F5', border: '1px solid #FFE4B3' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginBottom: '12px' }}>
                            <div style={{ flex: 1 }}>
                              <Badge variant="yellow" style={{ marginBottom: '8px' }}>
                                {pattern.pattern_type?.replace(/_/g, ' ').toUpperCase()}
                              </Badge>
                              <Body style={{ fontSize: '13px' }}>{pattern.trigger}</Body>
                            </div>
                          </div>

                          {pattern.probable_causes && pattern.probable_causes.length > 0 && (
                            <>
                              <Body weight="medium" style={{ fontSize: '12px', marginTop: '12px', marginBottom: '8px' }}>
                                Probable Causes:
                              </Body>
                              {pattern.probable_causes.map((cause, causeIdx) => (
                                <div key={causeIdx} style={{ padding: '10px', backgroundColor: 'white', borderRadius: '6px', marginBottom: '8px', border: '1px solid #FFE4B3' }}>
                                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                                    <Body weight="medium" style={{ fontSize: '13px' }}>{cause.cause}</Body>
                                    <Badge variant={cause.confidence > 0.7 ? 'green' : 'yellow'}>
                                      {Math.round(cause.confidence * 100)}%
                                    </Badge>
                                  </div>
                                  {cause.actions && cause.actions.length > 0 && (
                                    <ol style={{ margin: '8px 0 0 0', paddingLeft: '20px', fontSize: '12px' }}>
                                      {cause.actions.map((action, actionIdx) => (
                                        <li key={actionIdx} style={{ marginBottom: '4px', lineHeight: '1.5' }}>
                                          <Body style={{ fontSize: '12px' }}>{action}</Body>
                                        </li>
                                      ))}
                                    </ol>
                                  )}
                                  {cause.supporting_evidence !== undefined && cause.supporting_evidence > 0 && (
                                    <Description style={{ fontSize: '11px', marginTop: '6px' }}>
                                      {cause.supporting_evidence} supporting case{cause.supporting_evidence !== 1 ? 's' : ''} found
                                    </Description>
                                  )}
                                </div>
                              ))}
                            </>
                          )}
                        </Card>
                      ))}
                    </div>
                  )}

                  {/* Problematic Materials */}
                  {problematicMaterials.length > 0 && (
                    <div style={{ marginBottom: rcaData.length > 0 ? '24px' : '0' }}>
                      <Body weight="medium" style={{ marginBottom: '12px' }}>Known Problematic Materials</Body>
                      <Description style={{ marginBottom: '12px', fontSize: '12px' }}>
                        Materials identified as problematic in the process context database
                      </Description>
                      <div style={{ display: 'grid', gap: '12px' }}>
                        {problematicMaterials.map((material, idx) => (
                      <div key={idx} style={{ padding: '12px', backgroundColor: '#FFF4E6', borderRadius: '6px', border: '1px solid #FFE4B3' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
                          <Badge variant="red">
                            {material.type === 'slurry_batch' && 'Slurry Batch'}
                            {material.type === 'recipe' && 'Recipe'}
                            {material.type === 'reticle' && 'Reticle'}
                          </Badge>
                          <Body weight="medium">{material.id}</Body>
                        </div>

                        {material.issues && material.issues.length > 0 && (
                          <div style={{ marginTop: '8px' }}>
                            {material.issues.map((issue, issueIdx) => (
                              <div key={issueIdx} style={{ display: 'flex', alignItems: 'flex-start', gap: '6px', marginBottom: '4px' }}>
                                <Badge variant={issue.severity === 'high' ? 'red' : issue.severity === 'medium' ? 'yellow' : 'lightgray'} style={{ fontSize: '10px' }}>
                                  {issue.severity?.toUpperCase()}
                                </Badge>
                                <Body style={{ fontSize: '12px', flex: 1 }}>{issue.description}</Body>
                              </div>
                            ))}
                          </div>
                        )}

                        {material.details && (
                          <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #FFE4B3' }}>
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '8px', fontSize: '11px' }}>
                              {material.type === 'slurry_batch' && (
                                <>
                                  {material.details.qc_status && (
                                    <div>
                                      <span style={{ color: '#6b778c' }}>QC Status: </span>
                                      <Badge variant={material.details.qc_status === 'failed' ? 'red' : 'green'} style={{ fontSize: '10px' }}>
                                        {material.details.qc_status}
                                      </Badge>
                                    </div>
                                  )}
                                  {material.details.large_particle_count && (
                                    <div>
                                      <span style={{ color: '#6b778c' }}>Particle Count: </span>
                                      <span style={{ fontWeight: '600' }}>{material.details.large_particle_count}</span>
                                    </div>
                                  )}
                                  {material.details.manufacturer && (
                                    <div>
                                      <span style={{ color: '#6b778c' }}>Manufacturer: </span>
                                      <span>{material.details.manufacturer}</span>
                                    </div>
                                  )}
                                </>
                              )}
                              {material.type === 'reticle' && (
                                <>
                                  {material.details.total_exposures && (
                                    <div>
                                      <span style={{ color: '#6b778c' }}>Total Exposures: </span>
                                      <span style={{ fontWeight: '600' }}>{material.details.total_exposures}</span>
                                    </div>
                                  )}
                                  {material.details.condition && (
                                    <div>
                                      <span style={{ color: '#6b778c' }}>Condition: </span>
                                      <span>{material.details.condition}</span>
                                    </div>
                                  )}
                                </>
                              )}
                            </div>
                          </div>
                        )}
                        </div>
                      ))}
                      </div>
                    </div>
                  )}

                  {/* RCA Recommendations */}
                  {rcaData.length > 0 && (
                    <div>
                      {problematicMaterials.length > 0 && <div style={{ borderTop: '1px solid #FFE4B3', margin: '20px 0' }} />}
                      <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '12px' }}>
                        <Body weight="medium">Recommended Actions</Body>
                        <Badge variant="purple">
                          <Icon glyph="Bulb" size="small" /> Vector Search
                        </Badge>
                      </div>
                      <Description style={{ marginBottom: '16px', fontSize: '12px' }}>
                        AI-generated recommendations based on similar historical cases
                      </Description>

                      <div style={{ display: 'grid', gap: '12px' }}>
                        {rcaData.map((rec, index) => (
                          <div key={index} style={{ padding: '12px', backgroundColor: '#f9fbfa', borderRadius: '6px', border: '1px solid #e0e4e7' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                              <Body weight="medium" style={{ fontSize: '14px' }}>
                                {rec.title || `Recommendation ${index + 1}`}
                              </Body>
                              {rec.confidence && (
                                <Badge variant={rec.confidence > 0.8 ? 'green' : rec.confidence > 0.5 ? 'yellow' : 'lightgray'}>
                                  {Math.round(rec.confidence * 100)}%
                                </Badge>
                              )}
                            </div>

                            {rec.actions && rec.actions.length > 0 && (
                              <ol style={{ margin: '8px 0 0 0', paddingLeft: '20px' }}>
                                {rec.actions.map((action, actionIndex) => (
                                  <li key={actionIndex} style={{ marginBottom: '4px', lineHeight: '1.5' }}>
                                    <Body style={{ fontSize: '12px' }}>{action}</Body>
                                  </li>
                                ))}
                              </ol>
                            )}

                            {rec.pattern && (
                              <div style={{ marginTop: '8px' }}>
                                <Badge variant="lightgray" style={{ fontSize: '10px' }}>Pattern: {rec.pattern}</Badge>
                              </div>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {/* Section 3: Correlation Evidence */}
              {(temporal || equipment || batch || recipe || spatial) && (
                <Card style={{ marginBottom: '20px', padding: '20px' }}>
                  <H3 style={{ margin: 0, marginBottom: '16px' }}>Correlation Evidence</H3>
                  <Description style={{ marginBottom: '16px', fontSize: '12px' }}>
                    Supporting data from correlation analysis across multiple dimensions
                  </Description>

                  {/* Check if we have any actual data to display */}
                  {!(temporal && (temporal.correlation_strength > 0 || temporal.yield_impact !== 0 || temporal.defect_rate_change !== 0)) &&
                   !equipment &&
                   !(batch?.suspect_batches?.length > 0) &&
                   !recipe?.worst_recipe &&
                   !(spatial?.dominant_patterns?.length > 0) ? (
                    <div style={{ padding: '20px', textAlign: 'center', backgroundColor: '#f9fbfa', borderRadius: '6px' }}>
                      <Description>No wafers processed yet. Correlation evidence will appear once wafers are inspected.</Description>
                    </div>
                  ) : (
                  <div style={{ display: 'grid', gap: '16px' }}>
                    {/* Temporal Impact - Only show if there's actual data (not all zeros) */}
                    {temporal && (temporal.correlation_strength > 0 || temporal.yield_impact !== 0 || temporal.defect_rate_change !== 0) && (
                      <div style={{ padding: '12px', backgroundColor: '#f9fbfa', borderRadius: '6px' }}>
                        <Body weight="medium" style={{ marginBottom: '8px', fontSize: '13px' }}>Temporal Impact</Body>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', fontSize: '12px' }}>
                          {temporal.correlation_strength > 0 && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Correlation Strength</Description>
                              <Body weight="medium">{(temporal.correlation_strength * 100).toFixed(0)}%</Body>
                            </div>
                          )}
                          {temporal.yield_impact !== 0 && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Yield Impact</Description>
                              <Body weight="medium" style={{ color: temporal.yield_impact < 0 ? '#C84018' : '#00684A' }}>
                                {temporal.yield_impact > 0 ? '+' : ''}{temporal.yield_impact}%
                              </Body>
                            </div>
                          )}
                          {temporal.defect_rate_change !== 0 && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Defect Rate Change</Description>
                              <Body weight="medium" style={{ color: temporal.defect_rate_change > 0 ? '#C84018' : '#00684A' }}>
                                {temporal.defect_rate_change > 0 ? '+' : ''}{temporal.defect_rate_change}%
                              </Body>
                            </div>
                          )}
                          {temporal.time_lag_hours && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Time Lag</Description>
                              <Body weight="medium">{temporal.time_lag_hours}h</Body>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Equipment Health */}
                    {equipment && (
                      <div style={{ padding: '12px', backgroundColor: '#f9fbfa', borderRadius: '6px' }}>
                        <Body weight="medium" style={{ marginBottom: '8px', fontSize: '13px' }}>Equipment Health</Body>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '12px', fontSize: '12px' }}>
                          {equipment.equipment_health_score !== undefined && equipment.equipment_health_score > 0 && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Health Score</Description>
                              <Body weight="medium" style={{ color: equipment.equipment_health_score > 0.8 ? '#00684A' : equipment.equipment_health_score > 0.6 ? '#FFB000' : '#C84018' }}>
                                {(equipment.equipment_health_score * 100).toFixed(0)}%
                              </Body>
                            </div>
                          )}
                          {equipment.utilization_rate !== undefined && equipment.utilization_rate > 0 && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Utilization</Description>
                              <Body weight="medium">{equipment.utilization_rate}%</Body>
                            </div>
                          )}
                          {equipment.recent_anomalies !== undefined && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Recent Anomalies</Description>
                              <Body weight="medium" style={{ color: equipment.recent_anomalies > 0 ? '#C84018' : '#00684A' }}>
                                {equipment.recent_anomalies}
                              </Body>
                            </div>
                          )}
                          {equipment.maintenance_due !== undefined && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Maintenance Due</Description>
                              <Badge variant={equipment.maintenance_due ? 'red' : 'green'} style={{ fontSize: '10px' }}>
                                {equipment.maintenance_due ? 'Yes' : 'No'}
                              </Badge>
                            </div>
                          )}
                        </div>
                        {equipment.metric_trends && Object.keys(equipment.metric_trends).length > 0 && (
                          <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #e0e4e7' }}>
                            <Description style={{ fontSize: '11px', marginBottom: '4px' }}>Metric Trends</Description>
                            {Object.entries(equipment.metric_trends).map(([metric, trend]) => (
                              <div key={metric} style={{ fontSize: '11px', marginBottom: '2px' }}>
                                <Body style={{ fontSize: '11px' }}>
                                  {metric.replace(/_/g, ' ')}: {trend.trend}
                                  {trend.rate_of_change && ` (${trend.rate_of_change > 0 ? '+' : ''}${trend.rate_of_change}/hr)`}
                                </Body>
                              </div>
                            ))}
                          </div>
                        )}
                      </div>
                    )}

                    {/* Material Analysis */}
                    {(batch || recipe) && (
                      <div style={{ padding: '12px', backgroundColor: '#f9fbfa', borderRadius: '6px' }}>
                        <Body weight="medium" style={{ marginBottom: '8px', fontSize: '13px' }}>Material Analysis</Body>
                        <div style={{ display: 'grid', gap: '8px', fontSize: '12px' }}>
                          {batch?.suspect_batches && batch.suspect_batches.length > 0 && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Suspect Batches</Description>
                              {batch.suspect_batches.slice(0, 3).map((b, idx) => (
                                <Body key={idx} style={{ fontSize: '11px' }}>
                                  {b.batch_id}: {b.yield}% yield ({b.wafer_count} wafers)
                                </Body>
                              ))}
                            </div>
                          )}
                          {recipe?.worst_recipe && (
                            <div>
                              <Description style={{ fontSize: '11px' }}>Worst Recipe</Description>
                              <Body style={{ fontSize: '11px' }}>
                                {recipe.worst_recipe.recipe_id}: {recipe.worst_recipe.avg_yield}% yield
                              </Body>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Spatial Patterns */}
                    {spatial?.dominant_patterns && spatial.dominant_patterns.length > 0 && (
                      <div style={{ padding: '12px', backgroundColor: '#f9fbfa', borderRadius: '6px' }}>
                        <Body weight="medium" style={{ marginBottom: '8px', fontSize: '13px' }}>Spatial Patterns</Body>
                        <div style={{ display: 'grid', gap: '4px', fontSize: '12px' }}>
                          {spatial.dominant_patterns.slice(0, 3).map((pattern, idx) => (
                            <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              <Body style={{ fontSize: '11px' }}>
                                {pattern.pattern.charAt(0).toUpperCase() + pattern.pattern.slice(1)}
                              </Body>
                              <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                                <Description style={{ fontSize: '10px' }}>{pattern.percentage.toFixed(1)}%</Description>
                                <Description style={{ fontSize: '10px' }}>({pattern.frequency} wafers)</Description>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                  )}
                </Card>
              )}

              {/* NEW: Similar Defect Fingerprints */}
              {similarWaferDefects.length > 0 && (
                <Card style={{ marginBottom: '20px', padding: '20px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                    <H3 style={{ margin: 0 }}>Similar Defect Fingerprints</H3>
                    <Badge variant="purple">
                      <Icon glyph="Bulb" size="small" /> Multimodal Search
                    </Badge>
                  </div>
                  <Description style={{ marginBottom: '16px', fontSize: '12px' }}>
                    Visually similar wafer defect patterns from voyage-multimodal-3 embeddings
                  </Description>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '15px' }}>
                    {similarWaferDefects.map((defect, idx) => (
                      <Card key={idx} style={{ padding: '12px' }}>
                        {defect.thumbnail_base64 && (
                          <img
                            src={`data:image/png;base64,${defect.thumbnail_base64}`}
                            alt="Wafer defect"
                            style={{ width: '100%', borderRadius: '4px', marginBottom: '8px' }}
                          />
                        )}
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
                          <Body weight="medium" style={{ fontSize: '12px' }}>{defect.wafer_id}</Body>
                          <Badge variant={defect.similarity_score > 0.8 ? 'green' : 'yellow'}>
                            {Math.round(defect.similarity_score * 100)}%
                          </Badge>
                        </div>
                        <Description style={{ fontSize: '11px' }}>
                          {defect.pattern} • Yield: {defect.yield}%
                        </Description>
                      </Card>
                    ))}
                  </div>
                </Card>
              )}

              {/* Section 4: Historical Context */}
              {(highRelevanceCases.length > 0 || mediumRelevanceCases.length > 0) && (
                <Card style={{ padding: '20px' }}>
                  {highRelevanceCases.length > 0 ? (
                    <>
                      <H3 style={{ margin: 0, marginBottom: '16px' }}>
                        Historical Context ({highRelevanceCases.length} high-confidence match{highRelevanceCases.length !== 1 ? 'es' : ''})
                      </H3>
                      <Description style={{ marginBottom: '16px', fontSize: '12px' }}>
                        Similar cases from historical RCA reports and troubleshooting guides (≥70% relevance)
                      </Description>
                    </>
                  ) : (
                    <>
                      <H3 style={{ margin: 0, marginBottom: '16px' }}>
                        Historical Context ({mediumRelevanceCases.length} medium-confidence match{mediumRelevanceCases.length !== 1 ? 'es' : ''})
                      </H3>
                      <Description style={{ marginBottom: '16px', fontSize: '12px' }}>
                        Similar cases from historical RCA reports and troubleshooting guides (50-70% relevance)
                      </Description>
                    </>
                  )}
                  <div style={{ display: 'grid', gap: '15px' }}>
                    {/* Remove duplicates by title - show high relevance if available, otherwise medium */}
                    {Array.from(new Map((highRelevanceCases.length > 0 ? highRelevanceCases : mediumRelevanceCases).map(c => [c.title, c])).values()).map((case_, index) => (
                      <Card key={index} style={{ padding: '15px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '10px' }}>
                          <div style={{ flex: 1 }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px' }}>
                              {/* Document Type Badge */}
                              {case_.document_type === 'troubleshooting_guide' && (
                                <Badge variant="blue">Troubleshooting Guide</Badge>
                              )}
                              {case_.document_type === 'rca_report' && (
                                <Badge variant="green">RCA Report</Badge>
                              )}
                              {case_.document_type === 'best_practice' && (
                                <Badge variant="purple">Best Practice</Badge>
                              )}
                              {case_.semantic_match && (
                                <Badge variant="lightgray">Vector Search</Badge>
                              )}
                            </div>
                            <h5 style={{ margin: 0, color: '#1e2d3d' }}>{case_.title}</h5>
                          </div>
                          <Badge variant={case_.relevance_score > 0.8 ? 'green' : case_.relevance_score > 0.6 ? 'yellow' : 'lightgray'}>
                            {Math.round((case_.relevance_score || 0) * 100)}% Match
                          </Badge>
                        </div>

                        {/* Show content with more details */}
                        <div style={{ marginTop: '8px' }}>
                          {/* Always show resolution time and defect type if available */}
                          {(case_.resolution_time !== undefined && case_.resolution_time > 0) || case_.defect_type || case_.root_cause ? (
                            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(150px, 1fr))', gap: '10px', fontSize: '12px', marginBottom: '8px', padding: '8px', backgroundColor: '#f9fbfa', borderRadius: '4px' }}>
                              {case_.resolution_time !== undefined && case_.resolution_time > 0 && (
                                <div>
                                  <Description style={{ fontSize: '10px', marginBottom: '2px' }}>Resolution Time</Description>
                                  <Body weight="medium" style={{ fontSize: '12px' }}>{case_.resolution_time}h</Body>
                                </div>
                              )}
                              {case_.defect_type && (
                                <div>
                                  <Description style={{ fontSize: '10px', marginBottom: '2px' }}>Defect Type</Description>
                                  <Body style={{ fontSize: '12px' }}>{case_.defect_type?.replace(/_/g, ' ')}</Body>
                                </div>
                              )}
                              {case_.process_area && (
                                <div>
                                  <Description style={{ fontSize: '10px', marginBottom: '2px' }}>Process Area</Description>
                                  <Body style={{ fontSize: '12px' }}>{case_.process_area}</Body>
                                </div>
                              )}
                            </div>
                          ) : null}

                          {/* Root cause (if available) */}
                          {case_.root_cause && case_.root_cause !== 'Root cause not specified' && (
                            <div style={{ padding: '8px', backgroundColor: '#e8f5e9', borderRadius: '4px', border: '1px solid #c8e6c9', marginBottom: '8px' }}>
                              <Description style={{ fontSize: '10px', marginBottom: '4px', color: '#2e7d32' }}>Root Cause</Description>
                              <Body style={{ fontSize: '12px', color: '#1e2d3d' }}>{case_.root_cause}</Body>
                            </div>
                          )}

                          {/* Troubleshooting guide content */}
                          {case_.document_type === 'troubleshooting_guide' && case_.content && (
                            <div style={{ padding: '12px', backgroundColor: '#e3f2fd', borderRadius: '4px', border: '1px solid #90caf9', marginBottom: '8px' }}>
                              <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '8px' }}>
                                <Icon glyph="InfoWithCircle" size="small" fill="#1565c0" />
                                <Body weight="medium" style={{ fontSize: '12px', color: '#1565c0' }}>
                                  Troubleshooting Steps
                                </Body>
                              </div>
                              <div style={{ fontSize: '11px', color: '#1e2d3d', whiteSpace: 'pre-wrap', lineHeight: '1.6', maxHeight: '300px', overflowY: 'auto' }}>
                                {case_.content}
                              </div>
                              {case_.metadata?.estimated_mttr_hours && (
                                <div style={{ marginTop: '8px', paddingTop: '8px', borderTop: '1px solid #90caf9' }}>
                                  <Description style={{ fontSize: '10px', marginBottom: '2px' }}>Estimated MTTR</Description>
                                  <Body style={{ fontSize: '12px', color: '#1565c0' }}>{case_.metadata.estimated_mttr_hours} hours</Body>
                                </div>
                              )}
                            </div>
                          )}

                          {/* Show if no meaningful data is available */}
                          {!case_.resolution_time && !case_.defect_type && !case_.root_cause && case_.document_type === 'rca_report' && (
                            <div style={{ padding: '8px', backgroundColor: '#f9fbfa', borderRadius: '4px' }}>
                              <Description style={{ fontSize: '11px' }}>Limited details available for this case</Description>
                            </div>
                          )}
                        </div>
                      </Card>
                    ))}
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