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
import MarkdownMessage from './MarkdownMessage';
import styles from './AlertAnalysisModal.module.css';

const AlertAnalysisModal = ({ alert, isOpen, onClose, onAlertFixed, aiEnabled = true, onNavigateToChat = () => {} }) => {
  const [activeTab, setActiveTab] = useState(0); // Start with Overview tab
  const [isFixing, setIsFixing] = useState(false);
  const [fixStatus, setFixStatus] = useState(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  // Parse and structure the RCA analysis text
  const parseRCAAnalysis = (analysisText) => {
    if (!analysisText) return null;

    const sections = [];
    const lines = analysisText.split('\n');
    let currentSection = null;
    let currentContent = [];

    // Patterns to skip (conversational/process lines)
    const skipPatterns = [
      /^(First|Let me|I'll|I'm|Now|Next|Analyzing|Checking|Searching)/i,
      /^(Using|Calling|Looking|Fetching|Retrieving)/i,
      /tool(s)? (for|to)/i,
      /available tool/i
    ];

    for (let line of lines) {
      const trimmed = line.trim();

      // Skip empty lines at the start
      if (!currentSection && !trimmed) continue;

      // Skip conversational/process lines
      if (skipPatterns.some(pattern => pattern.test(trimmed))) continue;

      // Check if this is a section header (uppercase words followed by colon or markdown header)
      const sectionMatch = trimmed.match(/^(#{1,3}\s*)?([A-Z][A-Z\s]+):?\s*$/);
      if (sectionMatch) {
        // Save previous section
        if (currentSection && currentContent.length > 0) {
          sections.push({
            title: currentSection,
            content: currentContent.join('\n').trim()
          });
        }
        // Start new section
        currentSection = sectionMatch[2].trim();
        currentContent = [];
        continue;
      }

      // Add content to current section
      if (currentSection) {
        currentContent.push(line);
      }
    }

    // Save last section
    if (currentSection && currentContent.length > 0) {
      sections.push({
        title: currentSection,
        content: currentContent.join('\n').trim()
      });
    }

    return sections;
  };

  // Render a structured section
  const renderSection = (section, index, totalSections) => {
    const sectionStyle = {
      marginBottom: '24px',
      paddingBottom: '16px',
      borderBottom: index < totalSections - 1 ? '1px solid var(--color-neutral-light2)' : 'none'
    };

    return (
      <div key={index} style={sectionStyle}>
        <H3 style={{
          fontSize: '16px',
          fontWeight: '600',
          marginBottom: '12px',
          color: 'var(--color-neutral-dark1)'
        }}>
          {section.title}
        </H3>
        <MarkdownMessage content={section.content} />
      </div>
    );
  };

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

          <Tab name="Agent Analysis">
            <div className={styles.tabContent}>
              {alert.rca_analysis && !alert.rca_analysis.error ? (
                <>
                  {/* Parse and render structured analysis */}
                  {(() => {
                    const parsedSections = parseRCAAnalysis(alert.rca_analysis.analysis);

                    return (
                      <>
                        {/* RCA Analysis Results */}
                        <Card className={styles.card}>
                          <H3 className={styles.sectionTitle}>Agent Analysis Results</H3>

                          {/* Structured Sections */}
                          {parsedSections && parsedSections.length > 0 ? (
                            <div>
                              {parsedSections.map((section, idx) =>
                                renderSection(section, idx, parsedSections.length)
                              )}
                            </div>
                          ) : (
                            <div style={{ marginBottom: '16px' }}>
                              <MarkdownMessage content={alert.rca_analysis.analysis || 'No analysis available.'} />
                            </div>
                          )}

                          {/* Tools Used */}
                          {alert.rca_analysis.tools_used && alert.rca_analysis.tools_used.length > 0 && (
                            <div style={{ marginTop: '24px', paddingTop: '16px', borderTop: '1px solid var(--color-neutral-light2)' }}>
                              <Body weight="medium" style={{ marginBottom: '8px' }}>Tools Used:</Body>
                              <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                                {alert.rca_analysis.tools_used.map((tool, idx) => (
                                  <Badge key={idx} variant="blue">{tool}</Badge>
                                ))}
                              </div>
                            </div>
                          )}

                          {/* Metadata */}
                          <div style={{ marginTop: '16px', paddingTop: '16px', borderTop: '1px solid var(--color-neutral-light2)' }}>
                            {alert.rca_analysis.timestamp && (
                              <Description style={{ marginBottom: '4px' }}>
                                Analysis completed: {new Date(alert.rca_analysis.timestamp).toLocaleString()}
                              </Description>
                            )}
                            {alert.rca_analysis.agent_model && (
                              <Description>
                                Model: {alert.rca_analysis.agent_model}
                              </Description>
                            )}
                          </div>
                        </Card>

                        {/* Ask Agent for Details Button */}
                        <Card className={styles.card}>
                          <H3 className={styles.sectionTitle}>Need More Information?</H3>
                          <Body style={{ marginBottom: '16px' }}>
                            Connect with the AI agent for a deeper interactive analysis and ask follow-up questions.
                          </Body>
                          <Button
                            variant="primary"
                            leftGlyph={<Icon glyph="Chat" />}
                            onClick={() => {
                              const query = `Please provide more detailed analysis about alert ${alert.alert_id} for equipment ${alert.equipment_id}.

Context:
- Alert Type: ${alert.alert_type}
- Equipment: ${alert.equipment_id}
- Wafer ID: ${metadata.wafer_id || 'N/A'}
- Lot ID: ${metadata.lot_id || 'N/A'}
- Timestamp: ${alert.timestamp}

The automatic RCA found: ${alert.rca_analysis.analysis.substring(0, 200)}...

Please investigate further using all available tools and provide additional insights.`;
                              onNavigateToChat(query);
                              onClose();
                            }}
                          >
                            Ask Agent for Details
                          </Button>
                        </Card>
                      </>
                    );
                  })()}
                </>
              ) : alert.rca_analysis && alert.rca_analysis.error ? (
                <Card className={styles.card}>
                  <H3 className={styles.sectionTitle}>Analysis Error</H3>
                  <Body style={{ color: 'var(--color-warning)' }}>
                    An error occurred during automatic analysis: {alert.rca_analysis.error}
                  </Body>
                </Card>
              ) : (
                <Card className={styles.card}>
                  <div style={{
                    display: 'flex',
                    flexDirection: 'column',
                    alignItems: 'center',
                    justifyContent: 'center',
                    padding: '40px 20px',
                    textAlign: 'center'
                  }}>
                    <div style={{
                      animation: 'spin 2s linear infinite',
                      marginBottom: '20px'
                    }}>
                      <Icon glyph="Refresh" size="xlarge" style={{ color: 'var(--color-neutral-dark1)' }} />
                    </div>
                    <H3 className={styles.sectionTitle} style={{ marginBottom: '12px' }}>
                      Analysis in Progress
                    </H3>
                    <Body style={{ color: 'var(--color-neutral-dark1)', maxWidth: '400px' }}>
                      The AI agent is analyzing this alert and performing root cause analysis. This may take a few moments.
                    </Body>
                  </div>
                  <style jsx>{`
                    @keyframes spin {
                      from {
                        transform: rotate(0deg);
                      }
                      to {
                        transform: rotate(360deg);
                      }
                    }
                  `}</style>
                </Card>
              )}
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