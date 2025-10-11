"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Label, Description } from '@leafygreen-ui/typography';
import styles from './AgentDetailPanel.module.css';

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

const AgentDetailPanel = ({ selectedAgent }) => {
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

      {/* Key Metrics */}
      <div className={styles.section}>
        <Label className={styles.sectionTitle}>
          <Icon glyph="Charts" size="small" /> Performance Metrics
        </Label>
        <div className={styles.metrics}>
          {agent.metrics.map((metric, idx) => (
            <div key={idx} className={styles.metric}>
              <Icon glyph={metric.icon} className={styles.metricIcon} />
              <div className={styles.metricContent}>
                <Label className={styles.metricLabel}>{metric.label}</Label>
                <Body className={styles.metricValue}>{metric.value}</Body>
              </div>
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

      {/* Value Prop */}
      <div className={styles.valueBox}>
        <Icon glyph="Lightbulb" className={styles.valueIcon} />
        <div>
          <Label className={styles.valueLabel}>MongoDB Value</Label>
          <Body className={styles.valueText}>{agent.value}</Body>
        </div>
      </div>
    </Card>
  );
};

export default AgentDetailPanel;
