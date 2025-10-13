"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Label, Description } from '@leafygreen-ui/typography';
import styles from './AgentDetailPanel.module.css';
import { alertAPI } from '@/lib/api';

const AGENT_DETAILS = {
  1: {
    name: "Monitoring Agent",
    icon: "ActivityFeed",
    purpose: "Statistical false positive filtering using real-time sensor data",
    mongoFeatures: [
      { name: "Time Series Collections", type: "timeseries", icon: "Charts" },
      { name: "Aggregation Pipeline", type: "aggregation", icon: "Folder" }
    ],
    collections: ["process_sensor_ts"],
    metrics: [
      { label: "Query Speed", value: "10-50ms", icon: "Clock" },
      { label: "Analysis Window", value: "Last 1 hour", icon: "Calendar" },
      { label: "Noise Reduction", value: "60-70%", icon: "Checkmark" }
    ],
    dataFlow: [
      "process_sensor_ts → Statistical Aggregation ($avg, $stdDev)",
      "Calculate deviation: Current vs. Historical",
      "LLM Decision: Create Alert or Filter (>2.5σ threshold)",
      "Output: Alert decision + confidence score"
    ],
    value: "Time Series collections enable 10-50ms statistical analysis on streaming sensor data, filtering false positives before they become alerts"
  },
  2: {
    name: "Investigation Agent",
    icon: "Connect",
    purpose: "Cross-collection correlation analysis to identify root causes",
    mongoFeatures: [
      { name: "Multi-Collection Queries", type: "query", icon: "Database" },
      { name: "$lookup Joins", type: "aggregation", icon: "Folder" }
    ],
    collections: ["wafer_defects", "process_context", "alerts", "process_sensor_ts"],
    metrics: [
      { label: "Collections Joined", value: "4", icon: "Connect" },
      { label: "Correlation Types", value: "Temporal, Batch, Spatial", icon: "Diagram3" },
      { label: "Wafer Analysis", value: "1000s in seconds", icon: "Speedometer" }
    ],
    dataFlow: [
      "Multi-collection query: wafer_defects + process_context + alerts",
      "Correlation Engine: Temporal, Batch, Spatial analysis",
      "Statistical correlation scoring",
      "LLM Interpretation: Convert data → Key findings"
    ],
    value: "MongoDB's flexible document model and $lookup enable complex correlations across diverse data types without rigid schemas"
  },
  3: {
    name: "RCA Agent",
    icon: "MagnifyingGlass",
    purpose: "Semantic search of historical knowledge for validated solutions",
    mongoFeatures: [
      { name: "Vector Search", type: "vector", icon: "Sparkle" },
      { name: "Similarity Matching", type: "vector", icon: "Sparkle" }
    ],
    collections: ["historical_knowledge"],
    metrics: [
      { label: "Search Speed", value: "<100ms", icon: "Clock" },
      { label: "Relevance Threshold", value: "70%+", icon: "Target" },
      { label: "Knowledge Base", value: "1000s RCA reports", icon: "University" }
    ],
    dataFlow: [
      "Generate embedding for current issue description",
      "Vector Search: $vectorSearch on historical_knowledge",
      "Retrieve top similar past incidents (cosine similarity)",
      "LLM Validation: Align recommendations with current context"
    ],
    value: "Atlas Vector Search finds semantically similar historical incidents in <100ms, enabling AI to learn from past resolutions"
  },
  4: {
    name: "Supervisor Agent",
    icon: "Beaker",
    purpose: "Synthesize all agent outputs into actionable recommendations",
    mongoFeatures: [
      { name: "Flexible Document Model", type: "document", icon: "Code" },
      { name: "Nested Data Storage", type: "document", icon: "Folder" }
    ],
    collections: ["alerts"],
    metrics: [
      { label: "Agents Synthesized", value: "3", icon: "Cloud" },
      { label: "Output Format", value: "Executive Summary", icon: "File" },
      { label: "Action Items", value: "Prioritized", icon: "SortAscending" }
    ],
    dataFlow: [
      "Aggregate outputs from 3 worker agents",
      "LLM Synthesis: Generate executive summary",
      "Prioritize action items for yield improvement",
      "Store complete analysis chain in alerts.correlation_data"
    ],
    value: "MongoDB's flexible schema allows storing the complete multi-agent analysis chain without predefined structure constraints"
  }
};

const FEATURE_COLORS = {
  timeseries: "#0498EC",
  aggregation: "#FF6E3C",
  query: "#13AA52",
  vector: "#6554C0",
  document: "#00684A"
};

const AgentDetailPanel = ({ selectedAgent, selectedAlertId }) => {
  const [agentData, setAgentData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch real agent data when alert is selected
  useEffect(() => {
    console.log('[AgentDetailPanel] useEffect triggered - selectedAlertId:', selectedAlertId, 'selectedAgent:', selectedAgent);

    if (!selectedAlertId || !selectedAgent) {
      console.log('[AgentDetailPanel] Missing selectedAlertId or selectedAgent, clearing agentData');
      setAgentData(null);
      return;
    }

    const fetchAgentData = async () => {
      setLoading(true);
      setError(null);
      console.log('[AgentDetailPanel] Fetching agent data for alert:', selectedAlertId, 'agent:', selectedAgent);

      try {
        const response = await alertAPI.getAgentDetails(selectedAlertId);
        console.log('[AgentDetailPanel] API response:', response);

        const agent = response.agents?.find(a => a.id === selectedAgent);
        console.log('[AgentDetailPanel] Found agent data:', agent);

        setAgentData(agent);
      } catch (err) {
        console.error('[AgentDetailPanel] Error fetching agent data:', err);
        setError('Failed to load agent execution data');
      } finally {
        setLoading(false);
      }
    };

    fetchAgentData();
  }, [selectedAlertId, selectedAgent]);

  if (!selectedAgent) {
    return (
      <Card className={styles.emptyState}>
        <Icon glyph="InfoWithCircle" size="xlarge" className={styles.emptyIcon} />
        <Body className={styles.emptyText}>
          Select an agent above to view MongoDB features
        </Body>
      </Card>
    );
  }

  const agent = AGENT_DETAILS[selectedAgent];

  return (
    <Card className={styles.container}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <Icon glyph={agent.icon} size="xlarge" className={styles.headerIcon} />
          <div>
            <H3 className={styles.title}>{agent.name}</H3>
            <Description className={styles.purpose}>{agent.purpose}</Description>
          </div>
        </div>
      </div>

      {/* MongoDB Features */}
      <div className={styles.section}>
        <Label className={styles.sectionTitle}>
          <Icon glyph="Sparkle" size="small" /> MongoDB Features
        </Label>
        <div className={styles.features}>
          {agent.mongoFeatures.map((feature, idx) => (
            <Badge
              key={idx}
              variant="lightgray"
              className={styles.featureBadge}
              style={{
                backgroundColor: FEATURE_COLORS[feature.type] + '15',
                color: FEATURE_COLORS[feature.type],
                border: `1.5px solid ${FEATURE_COLORS[feature.type] + '40'}`
              }}
            >
              <Icon glyph={feature.icon} size="small" /> {feature.name}
            </Badge>
          ))}
        </div>
      </div>

      {/* Collections Used */}
      <div className={styles.section}>
        <Label className={styles.sectionTitle}>
          <Icon glyph="Database" size="small" /> Collections Accessed
        </Label>
        <div className={styles.collections}>
          {agent.collections.map((coll, idx) => (
            <div key={idx} className={styles.collectionChip}>
              <Icon glyph="CurlyBraces" size="small" />
              <code>{coll}</code>
            </div>
          ))}
        </div>
      </div>

      {/* Data Flow */}
      <div className={styles.section}>
        <Label className={styles.sectionTitle}>
          <Icon glyph="Diagram3" size="small" /> Data Flow
        </Label>
        <div className={styles.dataFlow}>
          {agent.dataFlow.map((step, idx) => (
            <div key={idx} className={styles.flowStep}>
              <div className={styles.stepNumber}>{idx + 1}</div>
              <Body className={styles.stepText}>{step}</Body>
            </div>
          ))}
        </div>
      </div>

      {/* Real-Time Agent Execution Data (All Agents) */}
      {selectedAgent && (
        <div className={styles.section}>
          <Label className={styles.sectionTitle}>
            <Icon glyph="ActivityFeed" size="small" /> Live Agent Output
          </Label>

          {loading && <Body className={styles.loadingText}>Loading agent data...</Body>}
          {error && <Body className={styles.errorText}>{error}</Body>}
          {!loading && !error && !agentData && selectedAlertId && (
            <Body className={styles.errorText}>
              ⚠️ No {AGENT_DETAILS[selectedAgent]?.name} data for this alert. The agent may have failed during execution. Try selecting a different alert or inject a new excursion pattern.
            </Body>
          )}

          {/* MONITORING AGENT OUTPUT */}
          {agentData && selectedAgent === 1 && (
            <div className={styles.agentOutput}>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Decision:</Label>
                <Badge variant={agentData.output.decision === 'CREATE ALERT' ? 'red' : 'green'}>
                  {agentData.output.decision}
                </Badge>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Confidence:</Label>
                <Body>{(agentData.output.confidence * 100).toFixed(0)}%</Body>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Pattern Detected:</Label>
                <Badge variant="blue">{agentData.output.pattern}</Badge>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Reasoning:</Label>
                <Body className={styles.reasoningText}>{agentData.output.reasoning}</Body>
              </div>
              {agentData.output.statistical_context && (
                <>
                  <div className={styles.outputRow}>
                    <Label className={styles.outputLabel}>Deviation:</Label>
                    <Body>{agentData.output.statistical_context.deviation_sigma?.toFixed(1)}σ ({agentData.output.statistical_context.deviation_pct > 0 ? '+' : ''}{agentData.output.statistical_context.deviation_pct?.toFixed(1)}%)</Body>
                  </div>
                  <div className={styles.outputRow}>
                    <Label className={styles.outputLabel}>Historical Context:</Label>
                    <Body>Avg: {agentData.output.statistical_context.avg_particles?.toFixed(0)}, Min: {agentData.output.statistical_context.min_particles}, Max: {agentData.output.statistical_context.max_particles} ({agentData.output.statistical_context.readings_count} readings)</Body>
                  </div>
                </>
              )}
            </div>
          )}

          {/* INVESTIGATION AGENT OUTPUT */}
          {agentData && selectedAgent === 2 && (
            <div className={styles.agentOutput}>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Correlation Confidence:</Label>
                <Body>{(agentData.output.correlation_confidence * 100).toFixed(0)}%</Body>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Affected Wafers:</Label>
                <Body>{agentData.output.affected_wafers}</Body>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Key Findings:</Label>
                <div className={styles.findingsList}>
                  {agentData.output.key_findings?.map((finding, idx) => (
                    <Body key={idx} className={styles.findingItem}>• {finding}</Body>
                  ))}
                </div>
              </div>
              {agentData.output.summary && (
                <div className={styles.outputRow}>
                  <Label className={styles.outputLabel}>Summary:</Label>
                  <Body className={styles.reasoningText}>{agentData.output.summary}</Body>
                </div>
              )}
            </div>
          )}

          {/* RCA AGENT OUTPUT */}
          {agentData && selectedAgent === 3 && (
            <div className={styles.agentOutput}>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Confidence:</Label>
                <Body>{(agentData.output.confidence * 100).toFixed(0)}%</Body>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Validated Root Causes:</Label>
                <div className={styles.findingsList}>
                  {agentData.output.validated_causes?.map((cause, idx) => (
                    <Body key={idx} className={styles.findingItem}>• {cause}</Body>
                  ))}
                </div>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Recommendations:</Label>
                <div className={styles.recommendationsList}>
                  {agentData.output.recommendations?.map((rec, idx) => (
                    <div key={idx} className={styles.recommendationItem}>
                      <Badge variant={rec.priority === 'urgent' ? 'red' : rec.priority === 'high' ? 'yellow' : 'blue'}>
                        {rec.confidence ? `${(rec.confidence * 100).toFixed(0)}%` : 'N/A'}
                      </Badge>
                      <Body className={styles.recTitle}>{rec.title}</Body>
                      {rec.actions && (
                        <div className={styles.actionsList}>
                          {rec.actions.map((action, aidx) => (
                            <Body key={aidx} className={styles.actionItem}>→ {action}</Body>
                          ))}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
              {agentData.output.validation && (
                <div className={styles.outputRow}>
                  <Label className={styles.outputLabel}>Validation:</Label>
                  <Body className={styles.reasoningText}>{agentData.output.validation}</Body>
                </div>
              )}
            </div>
          )}

          {/* SUPERVISOR AGENT OUTPUT */}
          {agentData && selectedAgent === 4 && (
            <div className={styles.agentOutput}>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Risk Level:</Label>
                <Badge variant={
                  agentData.output.risk_level === 'Critical' ? 'red' :
                  agentData.output.risk_level === 'High' ? 'yellow' :
                  agentData.output.risk_level === 'Medium' ? 'blue' : 'green'
                }>
                  {agentData.output.risk_level}
                </Badge>
              </div>
              <div className={styles.outputRow}>
                <Label className={styles.outputLabel}>Overall Confidence:</Label>
                <Body>{(agentData.output.overall_confidence * 100).toFixed(0)}%</Body>
              </div>
              {agentData.output.synthesis && (
                <div className={styles.outputRow}>
                  <Label className={styles.outputLabel}>Executive Summary:</Label>
                  <Body className={styles.reasoningText} style={{ whiteSpace: 'pre-wrap' }}>{agentData.output.synthesis}</Body>
                </div>
              )}
              {agentData.output.agent_summary && (
                <div className={styles.outputRow}>
                  <Label className={styles.outputLabel}>Agent Summary:</Label>
                  <div className={styles.findingsList}>
                    {agentData.output.agent_summary.monitoring && (
                      <Body className={styles.findingItem}>
                        🔵 Monitoring: {agentData.output.agent_summary.monitoring.pattern} ({(agentData.output.agent_summary.monitoring.confidence * 100).toFixed(0)}%)
                      </Body>
                    )}
                    {agentData.output.agent_summary.investigation && (
                      <Body className={styles.findingItem}>
                        🟠 Investigation: {agentData.output.agent_summary.investigation.affected_wafers} wafers, {agentData.output.agent_summary.investigation.key_findings_count} findings
                      </Body>
                    )}
                    {agentData.output.agent_summary.rca && (
                      <Body className={styles.findingItem}>
                        🟣 RCA: {agentData.output.agent_summary.rca.validated_causes_count} causes, {agentData.output.agent_summary.rca.recommendations_count} recommendations
                      </Body>
                    )}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Value Prop */}
      <div className={styles.valueBox}>
        <Icon glyph="Sparkle" className={styles.valueIcon} />
        <div>
          <Label className={styles.valueLabel}>MongoDB Value</Label>
          <Body className={styles.valueText}>{agent.value}</Body>
        </div>
      </div>
    </Card>
  );
};

export default AgentDetailPanel;
