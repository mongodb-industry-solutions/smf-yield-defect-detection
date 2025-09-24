"use client";

import React, { useState, useEffect } from 'react';
import Modal from '@leafygreen-ui/modal';
import Button from '@leafygreen-ui/button';
import Badge from '@leafygreen-ui/badge';
import { Tab, Tabs } from '@leafygreen-ui/tabs';
import Card from '@leafygreen-ui/card';
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
      const response = await fetch(`http://localhost:8000/alerts/${alert.alert_id}/fix`, {
        method: 'POST'
      });

      if (response.ok) {
        const data = await response.json();
        setFixStatus({
          type: 'success',
          message: data.message
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
      setFixStatus({
        type: 'error',
        message: 'Error connecting to server'
      });
    } finally {
      setIsFixing(false);
    }
  };

  if (!alert) return null;

  const getSeverityColor = (severity) => {
    switch (severity) {
      case 'critical': return '#DC382D';
      case 'high': return '#FDB813';
      case 'medium': return '#FFE169';
      case 'low': return '#13AA52';
      default: return '#6b778c';
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
  const rcaHints = alert.rca_hints || {};
  const historicalCases = rcaHints.similar_historical_cases || [];

  return (
    <Modal
      open={isOpen}
      setOpen={onClose}
      size="large"
    >
      <div style={{ padding: '20px', maxHeight: '80vh', overflowY: 'auto' }}>
        <div style={{ marginBottom: '20px', borderBottom: '1px solid #e0e4e7', paddingBottom: '15px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
            <h2 style={{ margin: 0, fontSize: '24px', color: '#1e2d3d' }}>Alert Analysis</h2>
            <div style={{ display: 'flex', gap: '8px' }}>
              <Badge variant={alert.severity === 'critical' ? 'red' : alert.severity === 'high' ? 'yellow' : 'blue'}>
                {alert.severity?.toUpperCase()}
              </Badge>
              <Badge variant={alert.status === 'resolved' ? 'green' : 'lightgray'}>
                {alert.status?.toUpperCase()}
              </Badge>
            </div>
          </div>
          <p style={{ margin: '5px 0', fontSize: '14px', fontWeight: '600', color: '#1e2d3d' }}>{alert.title}</p>
          <p style={{ margin: 0, fontSize: '12px', color: '#6b778c', fontFamily: 'monospace' }}>{alert.alert_id}</p>
        </div>

        <Tabs
          aria-label="Alert Analysis Tabs"
          selected={activeTab}
          setSelected={setActiveTab}
        >
          <Tab name="Overview">
            <div style={{ padding: '20px' }}>
              {/* Basic Alert Information */}
              <Card style={{ marginBottom: '20px', padding: '20px' }}>
                <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Alert Details</h3>
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
                <Card style={{ padding: '20px' }}>
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

          <Tab name="Root Cause Analysis">
            <div style={{ padding: '20px' }}>
              {/* RCA Recommendations */}
              {rcaData.length > 0 ? (
                <div>
                  <h3 style={{ marginTop: 0, marginBottom: '20px', color: '#1e2d3d' }}>
                    Root Cause Analysis & Recommendations
                  </h3>
                  {rcaData.map((rec, index) => (
                    <Card key={index} style={{ marginBottom: '15px', padding: '20px' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '15px' }}>
                        <h4 style={{ margin: 0, color: '#1e2d3d' }}>
                          {rec.title || `Recommendation ${index + 1}`}
                        </h4>
                        {rec.confidence && (
                          <Badge variant={rec.confidence > 0.8 ? 'green' : rec.confidence > 0.5 ? 'yellow' : 'lightgray'}>
                            {Math.round(rec.confidence * 100)}% Confidence
                          </Badge>
                        )}
                      </div>

                      {rec.actions && rec.actions.length > 0 && (
                        <div style={{ marginTop: '15px' }}>
                          <h5 style={{ marginBottom: '10px', color: '#5e6c84' }}>Recommended Actions:</h5>
                          <ol style={{ margin: 0, paddingLeft: '20px' }}>
                            {rec.actions.map((action, actionIndex) => (
                              <li key={actionIndex} style={{ marginBottom: '5px', lineHeight: '1.5' }}>
                                {action}
                              </li>
                            ))}
                          </ol>
                        </div>
                      )}

                      {rec.pattern && (
                        <div style={{ marginTop: '10px' }}>
                          <Badge variant="lightgray">Pattern: {rec.pattern}</Badge>
                        </div>
                      )}
                    </Card>
                  ))}
                </div>
              ) : (
                <Card style={{ padding: '40px', textAlign: 'center' }}>
                  <p style={{ color: '#6b778c', margin: 0 }}>
                    {isAnalyzing ? 'Analyzing alert...' : 'No RCA recommendations available yet'}
                  </p>
                </Card>
              )}

              {/* Historical Similar Cases */}
              {historicalCases.length > 0 && (
                <div style={{ marginTop: '30px' }}>
                  <h3 style={{ marginBottom: '20px', color: '#1e2d3d' }}>Similar Historical Cases</h3>
                  <div style={{ display: 'grid', gap: '15px' }}>
                    {historicalCases.map((case_, index) => (
                      <Card key={index} style={{ padding: '15px' }}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '10px' }}>
                          <h5 style={{ margin: 0, color: '#1e2d3d' }}>{case_.title}</h5>
                          <Badge variant="lightgray">
                            {Math.round((case_.relevance_score || 0) * 100)}% Match
                          </Badge>
                        </div>
                        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '10px', fontSize: '12px' }}>
                          <div>
                            <span style={{ color: '#6b778c' }}>Resolution Time: </span>
                            <span style={{ fontWeight: '600' }}>{case_.resolution_time}h</span>
                          </div>
                          <div>
                            <span style={{ color: '#6b778c' }}>Defect Type: </span>
                            <span>{case_.defect_type?.replace(/_/g, ' ')}</span>
                          </div>
                          {case_.root_cause && (
                            <div>
                              <span style={{ color: '#6b778c' }}>Root Cause: </span>
                              <span>{case_.root_cause}</span>
                            </div>
                          )}
                        </div>
                      </Card>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </Tab>

          <Tab name="Correlation Analysis">
            <div style={{ padding: '20px' }}>
              {/* Process Context Correlation */}
              {correlationData.correlations?.process_context && (
                <Card style={{ marginBottom: '20px', padding: '20px' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Process Context Analysis</h3>

                  {correlationData.correlations.process_context.problematic_materials?.length > 0 && (
                    <div style={{ marginBottom: '20px' }}>
                      <h4 style={{ color: '#DC382D', marginBottom: '10px' }}>⚠️ Problematic Materials Detected</h4>
                      {correlationData.correlations.process_context.problematic_materials.map((material, index) => (
                        <div key={index} style={{
                          background: '#ffebee',
                          border: '1px solid #ef5350',
                          borderRadius: '8px',
                          padding: '15px',
                          marginBottom: '10px'
                        }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
                            <span style={{ fontWeight: '600' }}>
                              {material.type?.replace(/_/g, ' ').toUpperCase()}: {material.id}
                            </span>
                            <Badge variant="red">PROBLEMATIC</Badge>
                          </div>

                          {material.issues?.map((issue, issueIndex) => (
                            <div key={issueIndex} style={{ marginBottom: '5px' }}>
                              <div style={{ color: '#c62828', fontWeight: '500' }}>
                                {issue.description}
                              </div>
                              <div style={{ fontSize: '12px', color: '#6b778c' }}>
                                Severity: {issue.severity} | Date: {new Date(issue.date).toLocaleDateString()}
                              </div>
                            </div>
                          ))}

                          {material.details && (
                            <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid #ffcdd2' }}>
                              <div style={{ fontSize: '12px' }}>
                                <strong>QC Status:</strong> {material.details.qc_status} |
                                <strong> Large Particle Count:</strong> {material.details.large_particle_count} |
                                <strong> Manufacturer:</strong> {material.details.manufacturer}
                              </div>
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {correlationData.correlations.process_context.correlation_found && (
                    <div style={{ background: '#e8f5e9', border: '1px solid #4caf50', borderRadius: '8px', padding: '15px' }}>
                      <div style={{ fontWeight: '600', marginBottom: '5px' }}>
                        Correlation Found with Confidence: {Math.round((correlationData.correlations.process_context.confidence || 0) * 100)}%
                      </div>
                    </div>
                  )}
                </Card>
              )}

              {/* Equipment Correlation */}
              {correlationData.correlations?.equipment && (
                <Card style={{ marginBottom: '20px', padding: '20px' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Equipment Analysis</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '15px' }}>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Utilization Rate: </span>
                      <span style={{ fontWeight: '600' }}>{correlationData.correlations.equipment.utilization_rate}%</span>
                    </div>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Recent Anomalies: </span>
                      <span style={{ fontWeight: '600', color: correlationData.correlations.equipment.recent_anomalies > 0 ? '#DC382D' : '#00684a' }}>
                        {correlationData.correlations.equipment.recent_anomalies}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Maintenance Due: </span>
                      <span style={{ fontWeight: '600', color: correlationData.correlations.equipment.maintenance_due ? '#DC382D' : '#00684a' }}>
                        {correlationData.correlations.equipment.maintenance_due ? 'Yes' : 'No'}
                      </span>
                    </div>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Data Points Analyzed: </span>
                      <span style={{ fontWeight: '600' }}>{correlationData.correlations.equipment.data_points}</span>
                    </div>
                  </div>
                </Card>
              )}

              {/* Temporal Correlation */}
              {correlationData.correlations?.temporal && (
                <Card style={{ marginBottom: '20px', padding: '20px' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Temporal Analysis</h3>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '15px' }}>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Correlation Strength: </span>
                      <span style={{ fontWeight: '600' }}>{(correlationData.correlations.temporal.correlation_strength || 0).toFixed(2)}</span>
                    </div>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Yield Impact: </span>
                      <span style={{ fontWeight: '600' }}>{correlationData.correlations.temporal.yield_impact}%</span>
                    </div>
                    <div>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Defect Rate Change: </span>
                      <span style={{ fontWeight: '600' }}>{correlationData.correlations.temporal.defect_rate_change}%</span>
                    </div>
                    {correlationData.correlations.temporal.time_lag_hours && (
                      <div>
                        <span style={{ color: '#6b778c', fontSize: '12px' }}>Time Lag: </span>
                        <span style={{ fontWeight: '600' }}>{correlationData.correlations.temporal.time_lag_hours}h</span>
                      </div>
                    )}
                  </div>
                </Card>
              )}

              {/* Insights */}
              {correlationData.insights && correlationData.insights.length > 0 && (
                <Card style={{ padding: '20px' }}>
                  <h3 style={{ marginTop: 0, marginBottom: '15px', color: '#1e2d3d' }}>Key Insights</h3>
                  <ul style={{ margin: 0, paddingLeft: '20px' }}>
                    {correlationData.insights.map((insight, index) => (
                      <li key={index} style={{ marginBottom: '8px', lineHeight: '1.5' }}>
                        {insight}
                      </li>
                    ))}
                  </ul>
                  {correlationData.confidence_score && (
                    <div style={{ marginTop: '15px', paddingTop: '15px', borderTop: '1px solid #e0e4e7' }}>
                      <span style={{ color: '#6b778c', fontSize: '12px' }}>Overall Confidence Score: </span>
                      <Badge variant={correlationData.confidence_score > 0.5 ? 'green' : 'yellow'}>
                        {Math.round(correlationData.confidence_score * 100)}%
                      </Badge>
                    </div>
                  )}
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

        <div style={{ marginTop: '20px', paddingTop: '20px', borderTop: '1px solid #e0e4e7', textAlign: 'right' }}>
          <Button variant="default" onClick={onClose}>
            Close
          </Button>
        </div>
      </div>
    </Modal>
  );
};

export default AlertAnalysisModal;