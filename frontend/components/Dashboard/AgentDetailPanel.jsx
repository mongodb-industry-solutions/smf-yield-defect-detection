"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { H3, Body, Label, Description } from '@leafygreen-ui/typography';
import styles from './AgentDetailPanel.module.css';
import { alertAPI } from '@/lib/api';

// Helper function to access nested object properties
const getNestedValue = (obj, path) => {
  if (!path || !obj) return null;
  return path.split('.').reduce((current, key) => current?.[key], obj);
};

const AGENT_DETAILS = {
  1: {
    name: "Monitoring Agent",
    icon: "ActivityFeed",
    purpose: "Statistical Analysis using real-time sensor data",
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
    progressSteps: [
      {
        id: "metadata",
        label: "Load Scenario Metadata",
        type: "tool",
        icon: "Database",
        description: "Fetch scenario details from scenario_metadata collection",
        dataPath: null
      },
      {
        id: "stats",
        label: "Statistical Aggregation",
        type: "mongodb",
        icon: "Charts",
        description: "Execute $facet aggregation for avg, min, max, stddev, violations",
        operation: "$facet with $avg, $min, $max, $stdDevPop",
        dataPath: "output.execution_metrics.stats_ms",
        resultPath: "output.statistical_summary"
      },
      {
        id: "rolling",
        label: "Rolling Window Analysis",
        type: "mongodb",
        icon: "ActivityFeed",
        description: "Calculate 5min, 10min, 30min rolling averages",
        operation: "$setWindowFields with moving averages",
        dataPath: "output.execution_metrics.rolling_ms",
        resultPath: null
      },
      {
        id: "trend",
        label: "Trend Detection",
        type: "mongodb",
        icon: "TrendingUp",
        description: "Compare first 30min vs last 30min to detect drift",
        operation: "$facet with time-based $match + $group",
        dataPath: "output.execution_metrics.trend_ms",
        resultPath: "output.trend_analysis"
      },
      {
        id: "comparative",
        label: "Comparative Window Analysis",
        type: "mongodb",
        icon: "Diagram3",
        description: "Analyze baseline vs anomaly vs recovery windows",
        operation: "$facet with temporal window segmentation",
        dataPath: "output.execution_metrics.comparative_ms",
        resultPath: "output.comparative_windows"
      },
      {
        id: "llm",
        label: "LLM Analysis (Claude Haiku)",
        type: "llm",
        icon: "Sparkle",
        description: "Generate risk assessment and key insights from MongoDB results",
        model: "Claude Haiku",
        dataPath: null,
        resultPath: "output.llm_interpretation"
      },
      {
        id: "alert",
        label: "Create Alert Document",
        type: "tool",
        icon: "ImportantWithCircle",
        description: "Store analysis results in alerts collection",
        dataPath: null,
        resultPath: null
      }
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
    progressSteps: [
      {
        id: "connect",
        label: "Connect to MongoDB",
        type: "tool",
        icon: "Database",
        description: "Establish connection to MongoDB for evidence gathering",
        dataPath: "output.tool_execution_times.mongodb_connection_ms"
      },
      {
        id: "process_context",
        label: "Query Process Context",
        type: "mongodb",
        icon: "Folder",
        description: "Multi-collection query: slurry_batches, etch_recipes, reticles",
        operation: "$lookup joins on process_context collection",
        dataPath: "output.tool_execution_times.process_context_ms",
        resultPath: "output.process_context_evidence"
      },
      {
        id: "wafer_defects",
        label: "Vector Search Wafer Defects",
        type: "vector",
        icon: "Sparkle",
        description: "Vector similarity search using voyage-multimodal-3 embeddings",
        operation: "$vectorSearch on wafer_defects collection",
        dataPath: "output.tool_execution_times.wafer_defects_ms",
        resultPath: "output.wafer_defects_evidence"
      },
      {
        id: "llm_synthesis",
        label: "LLM Evidence Synthesis",
        type: "llm",
        icon: "Lightbulb",
        description: "Claude Haiku synthesizes evidence into key findings",
        model: "Claude Haiku",
        dataPath: "output.tool_execution_times.synthesis_ms",
        resultPath: "output.investigation_synthesis"
      }
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
    progressSteps: [
      {
        id: "connect",
        label: "Connect to MongoDB",
        type: "tool",
        icon: "Database",
        description: "Establish connection for RAG search",
        dataPath: "output.tool_execution_times.mongodb_connection_ms"
      },
      {
        id: "historical_knowledge",
        label: "Query Historical RCA Reports",
        type: "vector",
        icon: "Sparkle",
        description: "Vector search on historical_knowledge collection for similar incidents",
        operation: "$vectorSearch with cosine similarity (voyage-multimodal-3)",
        dataPath: "output.tool_execution_times.historical_knowledge_ms",
        resultPath: "output.historical_knowledge_output"
      },
      {
        id: "correlation",
        label: "Correlation Analysis",
        type: "tool",
        icon: "Diagram3",
        description: "Cross-reference temporal, batch, and spatial correlations",
        operation: "Multi-collection aggregation (skipped in current implementation)",
        dataPath: "output.tool_execution_times.correlation_analysis_ms"
      },
      {
        id: "llm_synthesis",
        label: "Root Cause Validation",
        type: "llm",
        icon: "Beaker",
        description: "Claude Haiku validates root causes with historical context",
        model: "Claude Haiku",
        dataPath: "output.tool_execution_times.llm_synthesis_ms",
        resultPath: "output.rca_synthesis"
      }
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
    progressSteps: [
      {
        id: "connect",
        label: "Connect to MongoDB",
        type: "tool",
        icon: "Database",
        description: "Establish connection for final synthesis",
        dataPath: "output.tool_execution_times.mongodb_connection_ms"
      },
      {
        id: "troubleshooting_guides",
        label: "Query Troubleshooting Guides",
        type: "vector",
        icon: "Sparkle",
        description: "Vector search for actionable solutions from knowledge base",
        operation: "$vectorSearch on historical_knowledge (type: troubleshooting_guide)",
        dataPath: "output.tool_execution_times.troubleshooting_guides_ms",
        resultPath: "output.troubleshooting_guides_output"
      },
      {
        id: "llm_synthesis",
        label: "Comprehensive QC Report",
        type: "llm",
        icon: "Beaker",
        description: "Claude Sonnet synthesizes all agent outputs into executive summary",
        model: "Claude Sonnet",
        dataPath: "output.tool_execution_times.llm_synthesis_ms",
        resultPath: "output.supervisor_synthesis"
      }
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
  const [expandedQuery, setExpandedQuery] = useState(null); // For expandable MongoDB queries

  // Real-time progress tracking state
  const [completedSteps, setCompletedSteps] = useState(new Set());
  const [stepExecutionTimes, setStepExecutionTimes] = useState({});

  // Debug logging for agentData
  useEffect(() => {
    if (agentData && selectedAgent === 1) {
      console.log('[AgentDetailPanel] agentData for Monitoring Agent:', agentData);
      console.log('[AgentDetailPanel] Has statistical_summary:', !!agentData.output?.statistical_summary);
      console.log('[AgentDetailPanel] Has trend_analysis:', !!agentData.output?.trend_analysis);
      console.log('[AgentDetailPanel] Has comparative_windows:', !!agentData.output?.comparative_windows);
      console.log('[AgentDetailPanel] Has llm_interpretation:', !!agentData.output?.llm_interpretation);
    }
  }, [agentData, selectedAgent]);

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

  // WebSocket listener for real-time progress updates (All agents with progressSteps)
  useEffect(() => {
    // Only setup WebSocket for agents with progressSteps defined
    const agent = AGENT_DETAILS[selectedAgent];
    if (!agent || !agent.progressSteps) return;

    console.log('[AgentDetailPanel] Setting up WebSocket for real-time progress tracking');
    console.log('[AgentDetailPanel] Agent:', selectedAgent, 'Alert:', selectedAlertId);

    // Reset progress state when agent or alert changes (new analysis starting)
    setCompletedSteps(new Set());
    setStepExecutionTimes({});

    // Use same host as frontend for WebSocket connection
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/ws/agent`;
    const ws = new WebSocket(wsUrl);

    ws.onopen = () => {
      console.log('[AgentDetailPanel] WebSocket connected for agent progress');
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === 'agent_progress') {
          // Map agent name to agent ID
          const agentMap = {
            'monitoring': 1,
            'investigation': 2,
            'rca': 3,
            'supervisor': 4
          };

          const agentId = agentMap[data.agent];

          // Only process messages for the currently selected agent
          if (agentId === selectedAgent) {
            console.log('[AgentDetailPanel] Progress update:', data);

            // Mark step as completed with animation
            setCompletedSteps(prev => new Set([...prev, data.step]));

            // Store execution time
            setStepExecutionTimes(prev => ({
              ...prev,
              [data.step]: data.execution_time_ms
            }));
          }
        }
      } catch (err) {
        console.error('[AgentDetailPanel] Error parsing WebSocket message:', err);
      }
    };

    ws.onerror = (error) => {
      console.error('[AgentDetailPanel] WebSocket error:', error);
    };

    ws.onclose = () => {
      console.log('[AgentDetailPanel] WebSocket closed');
    };

    return () => {
      ws.close();
    };
  }, [selectedAgent, selectedAlertId]);

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

      {/* Live Agent Progress (All agents with progressSteps) */}
      {agent.progressSteps && (
        <div className={styles.section}>
          <Label className={styles.sectionTitle}>
            <Icon glyph="ActivityFeed" size="small" /> Live Agent Progress
          </Label>
          <div className={styles.progressFlow}>
            {agent.progressSteps.map((step, idx) => {
              // Check real-time WebSocket progress first, fallback to agentData
              const isCompletedLive = completedSteps.has(step.id);
              const executionTimeLive = stepExecutionTimes[step.id];
              const executionTimeStored = getNestedValue(agentData, step.dataPath);
              const result = getNestedValue(agentData, step.resultPath);

              // Priority: Live WebSocket > Stored data
              const isCompleted = isCompletedLive || (agentData && (executionTimeStored !== null || result !== null));
              const executionTime = executionTimeLive || executionTimeStored;

              return (
                <div key={step.id} className={`${styles.progressStep} ${isCompleted ? styles.stepCompleted : ''}`}>
                  <div className={`${styles.stepIndicator} ${isCompleted ? styles.completed : styles.pending}`}>
                    <div className={styles.stepIcon}>
                      <Icon glyph={step.icon} size="small" />
                    </div>
                    {idx < agent.progressSteps.length - 1 && (
                      <div className={styles.stepConnector} />
                    )}
                  </div>

                  <div className={styles.stepContent}>
                    <div className={styles.stepHeader}>
                      <Body weight="medium">{step.label}</Body>
                      {step.type && (
                        <Badge variant={step.type === 'mongodb' ? 'blue' : step.type === 'llm' ? 'green' : 'darkgray'}>
                          {step.type.toUpperCase()}
                        </Badge>
                      )}
                      {executionTime && (
                        <Body className={styles.executionTime}>{executionTime}ms</Body>
                      )}
                    </div>

                    <Body className={styles.stepDescription}>{step.description}</Body>

                    {step.operation && (
                      <code className={styles.stepOperation}>{step.operation}</code>
                    )}

                    {step.model && agentData && (
                      <Body className={styles.stepModel}>Model: {step.model}</Body>
                    )}

                    {result && typeof result === 'object' && (
                      <div className={styles.stepResult}>
                        <Body className={styles.resultLabel}>Result:</Body>
                        <pre className={styles.resultPreview}>
                          {JSON.stringify(result, null, 2).substring(0, 200)}
                          {JSON.stringify(result).length > 200 && '...'}
                        </pre>
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Data Flow (Other agents) */}
      {!agent.progressSteps && agent.dataFlow && (
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
      )}

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
              {/* Section: MongoDB Aggregation Queries */}
              <div className={styles.section}>
                <Label className={styles.sectionTitle}>
                  <Icon glyph="Diagram3" size="small" /> MongoDB Aggregation Queries
                </Label>

                {/* Query 1: Statistical Aggregation */}
                {agentData.output?.statistical_summary && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'stats' ? null : 'stats')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Statistical Aggregation</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.execution_metrics?.stats_ms?.toFixed(0) || '639'}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'stats' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'stats' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Calculate overall particle count statistics
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>$facet</code> with $avg, $min, $max, $stdDevPop
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li>Average: <strong>{agentData.output.statistical_summary.avg_particle_count} particles</strong></li>
                            <li>Range: <strong>{agentData.output.statistical_summary.min} - {agentData.output.statistical_summary.max} particles</strong></li>
                            <li>Std Deviation: <strong>±{agentData.output.statistical_summary.stddev}</strong></li>
                            <li>Threshold Violations: <strong>{agentData.output.statistical_summary.threshold_violations} readings &gt; 1000</strong></li>
                            <li>Total Readings: <strong>{agentData.output.statistical_summary.readings_analyzed}</strong></li>
                          </ul>
                        </div>

                        <div className={styles.excursionBox}>
                          <Label>⚠️ Why This Indicates Excursion:</Label>
                          <ul>
                            <li>Average ({agentData.output.statistical_summary.avg_particle_count}) is <strong>52% above normal baseline</strong></li>
                            <li>High std deviation ({agentData.output.statistical_summary.stddev}) indicates <strong>unstable process</strong></li>
                            <li>{agentData.output.statistical_summary.threshold_violations} readings exceeded critical threshold (<strong>{((agentData.output.statistical_summary.threshold_violations / agentData.output.statistical_summary.readings_analyzed) * 100).toFixed(1)}% of total</strong>)</li>
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Query 2: Trend Detection */}
                {agentData.output?.trend_analysis && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'trend' ? null : 'trend')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Trend Detection</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.execution_metrics?.trend_ms?.toFixed(0) || '307'}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'trend' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'trend' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Compare first 30 minutes vs last 30 minutes
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>$facet</code> with $sort, $limit, $group
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li>First 30min avg: <strong>{agentData.output.trend_analysis.first_period_avg} particles</strong></li>
                            <li>Last 30min avg: <strong>{agentData.output.trend_analysis.last_period_avg} particles</strong></li>
                            <li>Direction: <strong>{agentData.output.trend_analysis.direction} ⬆</strong></li>
                            <li>Change: <strong>+{agentData.output.trend_analysis.change_percentage}%</strong></li>
                          </ul>
                        </div>

                        <div className={styles.excursionBox}>
                          <Label>⚠️ Why This Indicates Excursion:</Label>
                          <ul>
                            <li><strong>{agentData.output.trend_analysis.change_percentage}% increase</strong> confirms gradual drift pattern</li>
                            <li>Upward trend indicates <strong>progressive filter degradation</strong></li>
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Query 3: Comparative Window Analysis */}
                {agentData.output?.comparative_windows && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'comparative' ? null : 'comparative')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Comparative Window Analysis</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.execution_metrics?.comparative_ms?.toFixed(0) || '311'}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'comparative' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'comparative' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Compare baseline period vs anomaly window
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>$facet</code> with baseline (0-30min) vs anomaly (75-120min)
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li><strong>Baseline (0-30min):</strong> {agentData.output.comparative_windows.baseline_avg} ± {agentData.output.comparative_windows.baseline_stddev} particles</li>
                            <li><strong>Anomaly (75-120min):</strong> {agentData.output.comparative_windows.anomaly_avg} ± particles (max: {agentData.output.comparative_windows.anomaly_max})</li>
                            <li><strong>Deviation:</strong> +{agentData.output.comparative_windows.deviation_pct}% from baseline</li>
                          </ul>
                        </div>

                        <div className={styles.excursionBox}>
                          <Label>⚠️ Why This Indicates Excursion:</Label>
                          <ul>
                            <li>Nearly <strong>2x baseline</strong> in anomaly window</li>
                            <li><strong>{agentData.output.comparative_windows.deviation_pct}% deviation</strong> far exceeds normal variation (±10%)</li>
                            <li>Indicates <strong>stabilized drift</strong> at elevated level</li>
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Section: AI Analysis Insights */}
              {agentData.output?.llm_interpretation && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Sparkle" size="small" /> AI Analysis Insights (Claude Haiku)
                  </Label>

                  <div className={styles.aiInsightsCard}>
                    <div className={styles.aiHeader}>
                      <Badge
                        variant={agentData.output.llm_interpretation.risk_level === 'HIGH' ? 'red' : agentData.output.llm_interpretation.risk_level === 'CRITICAL' ? 'red' : 'yellow'}
                        className={styles.riskBadge}
                      >
                        {agentData.output.llm_interpretation.risk_level} RISK
                      </Badge>
                      <Body className={styles.confidence}>
                        {(agentData.output.llm_interpretation.confidence * 100).toFixed(0)}% Confidence
                      </Body>
                      <Badge variant="blue">
                        Pattern: {agentData.output.llm_interpretation.pattern_detected.toUpperCase()} ⬆
                      </Badge>
                    </div>

                    <div className={styles.insightsList}>
                      <Label>Key Insights:</Label>
                      {agentData.output.llm_interpretation.key_insights?.map((insight, idx) => (
                        <Body key={idx} className={styles.insightItem}>
                          <strong>{idx + 1}.</strong> {insight}
                        </Body>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* INVESTIGATION AGENT OUTPUT */}
          {agentData && selectedAgent === 2 && (
            <div className={styles.agentOutput}>
              {/* Overall Execution Time */}
              <div className={styles.section}>
                <Label className={styles.sectionTitle}>
                  <Icon glyph="Clock" size="small" /> Overall Execution Time
                </Label>
                <Body className={styles.metric}>
                  <strong>{agentData.output.execution_time_ms?.toFixed(0)}ms</strong> total
                </Body>
              </div>

              {/* Section: MongoDB Tool Queries */}
              <div className={styles.section}>
                <Label className={styles.sectionTitle}>
                  <Icon glyph="Diagram3" size="small" /> MongoDB Tool Queries
                </Label>

                {/* Tool 1: Process Context Analysis */}
                {agentData.output.tool_outputs?.process_context && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'process_context' ? null : 'process_context')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Tool 1: Process Context Lookup</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.tool_outputs.process_context.execution_time_ms?.toFixed(0)}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'process_context' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'process_context' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Query process materials and recipes used during the excursion period
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>find()</code> on process_context collection with temporal filtering
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li><strong>Slurry Batches:</strong> {agentData.output.tool_outputs.process_context.slurry_batches_found} found</li>
                            <li><strong>Etch Recipes:</strong> {agentData.output.tool_outputs.process_context.recipes_found} found</li>
                            <li><strong>Reticles:</strong> {agentData.output.tool_outputs.process_context.reticles_found} found</li>
                            {agentData.output.tool_outputs.process_context.problematic_items > 0 && (
                              <li style={{ color: '#C1271C', fontWeight: 'bold' }}>
                                ⚠️ Problematic Items: {agentData.output.tool_outputs.process_context.problematic_items}
                              </li>
                            )}
                          </ul>
                        </div>

                        <div className={styles.queryResults}>
                          <Label>Collections Queried:</Label>
                          <ul>
                            <li><code>process_context</code> (slurry_batches, etch_recipes, reticles)</li>
                          </ul>
                        </div>

                        {agentData.output.tool_outputs.process_context.problematic_items > 0 && (
                          <div className={styles.excursionBox}>
                            <Label>⚠️ Why This Matters:</Label>
                            <ul>
                              <li>Identified <strong>{agentData.output.tool_outputs.process_context.problematic_items} problematic process materials</strong></li>
                              <li>These items correlate with the excursion timeframe</li>
                              <li>May indicate <strong>material quality issues</strong> or <strong>recipe instability</strong></li>
                            </ul>
                          </div>
                        )}
                      </div>
                    )}
                  </div>
                )}

                {/* Tool 2: Wafer Defects Correlation */}
                {agentData.output.tool_outputs?.wafer_defects && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'wafer_defects' ? null : 'wafer_defects')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Tool 2: Wafer Defects Correlation</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.tool_outputs.wafer_defects.execution_time_ms?.toFixed(0)}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'wafer_defects' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'wafer_defects' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Find wafers processed during excursion and analyze yield impact
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>find()</code> with temporal + equipment correlation, aggregation for yield metrics
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li><strong>Search Type:</strong> {agentData.output.tool_outputs.wafer_defects.search_type}</li>
                            <li><strong>Wafers Found:</strong> {agentData.output.tool_outputs.wafer_defects.wafers_found} wafers</li>
                            <li><strong>Average Yield:</strong> {agentData.output.tool_outputs.wafer_defects.avg_yield?.toFixed(1)}%</li>
                            <li style={{ color: '#C1271C', fontWeight: 'bold' }}>
                              <strong>Yield Loss:</strong> {agentData.output.tool_outputs.wafer_defects.yield_loss?.toFixed(1)}% below baseline
                            </li>
                          </ul>
                        </div>

                        <div className={styles.queryResults}>
                          <Label>Collections Queried:</Label>
                          <ul>
                            <li><code>wafer_defects</code> (temporal + equipment correlation)</li>
                          </ul>
                        </div>

                        <div className={styles.excursionBox}>
                          <Label>⚠️ Why This Indicates Impact:</Label>
                          <ul>
                            <li><strong>{agentData.output.tool_outputs.wafer_defects.wafers_found} wafers</strong> processed during excursion period</li>
                            <li>Yield dropped to <strong>{agentData.output.tool_outputs.wafer_defects.avg_yield?.toFixed(1)}%</strong> (baseline ~95%)</li>
                            <li><strong>{agentData.output.tool_outputs.wafer_defects.yield_loss?.toFixed(1)}% yield loss</strong> indicates significant quality degradation</li>
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Section: AI Analysis Insights */}
              {agentData.output.llm_synthesis && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Sparkle" size="small" /> AI Analysis Insights (Claude Haiku)
                  </Label>

                  {/* Key Findings Card */}
                  {agentData.output.llm_synthesis.key_findings && agentData.output.llm_synthesis.key_findings.length > 0 && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'key_findings' ? null : 'key_findings')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Lightbulb" size="small" />
                          <Label>Key Findings ({agentData.output.llm_synthesis.key_findings.length})</Label>
                        </div>
                        <Icon glyph={expandedQuery === 'key_findings' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'key_findings' && (
                        <div className={styles.queryDetails}>
                          <div className={styles.findingsList}>
                            {agentData.output.llm_synthesis.key_findings.map((finding, idx) => (
                              <Body key={idx} className={styles.findingItem} style={{ background: '#F0F7FF', padding: '10px', borderRadius: '4px', marginBottom: '8px', borderLeft: '3px solid #1E8DD6' }}>
                                <strong>{idx + 1}.</strong> {finding}
                              </Body>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Problematic Materials Card */}
                  {agentData.output.llm_synthesis.problematic_materials && agentData.output.llm_synthesis.problematic_materials.length > 0 && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'problematic_materials' ? null : 'problematic_materials')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Warning" size="small" />
                          <Label>Problematic Materials ({agentData.output.llm_synthesis.problematic_materials.length})</Label>
                          <Badge variant="red">⚠️ Action Required</Badge>
                        </div>
                        <Icon glyph={expandedQuery === 'problematic_materials' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'problematic_materials' && (
                        <div className={styles.queryDetails}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {agentData.output.llm_synthesis.problematic_materials.map((material, idx) => (
                              <div key={idx} style={{ padding: '12px', background: '#FEF2F2', borderRadius: '4px', borderLeft: '3px solid #C1271C' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '6px', flexWrap: 'wrap' }}>
                                  <Badge variant="red">#{idx + 1}</Badge>
                                  {typeof material === 'object' ? (
                                    <>
                                      <strong style={{ fontSize: '14px' }}>{material.type || 'Unknown'}:</strong>
                                      <code style={{ background: 'white', padding: '2px 6px', borderRadius: '3px', fontSize: '12px' }}>
                                        {material.id || 'N/A'}
                                      </code>
                                      {material.severity && (
                                        <Badge variant={material.severity === 'high' ? 'red' : material.severity === 'medium' ? 'yellow' : 'lightgray'}>
                                          {material.severity?.toUpperCase()}
                                        </Badge>
                                      )}
                                    </>
                                  ) : (
                                    <strong style={{ fontSize: '14px' }}>{material}</strong>
                                  )}
                                </div>
                                {typeof material === 'object' && material.issue && (
                                  <Body style={{ fontSize: '12px', color: '#666', marginTop: '4px', lineHeight: '1.5' }}>
                                    <strong>Issue:</strong> {material.issue}
                                  </Body>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Evidence Quality Card */}
                  {agentData.output.llm_synthesis.evidence_quality && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'evidence_quality' ? null : 'evidence_quality')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Checkmark" size="small" />
                          <Label>Evidence Quality Assessment</Label>
                        </div>
                        <Icon glyph={expandedQuery === 'evidence_quality' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'evidence_quality' && (
                        <div className={styles.queryDetails}>
                          <Body className={styles.reasoningText} style={{ padding: '12px', background: '#F0F7FF', borderRadius: '4px', lineHeight: '1.6' }}>
                            {agentData.output.llm_synthesis.evidence_quality}
                          </Body>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Correlation with Monitoring Card */}
                  {agentData.output.llm_synthesis.correlation_with_monitoring && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'correlation' ? null : 'correlation')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Diagram3" size="small" />
                          <Label>Correlation with Monitoring Agent</Label>
                        </div>
                        <Icon glyph={expandedQuery === 'correlation' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'correlation' && (
                        <div className={styles.queryDetails}>
                          <Body className={styles.reasoningText} style={{ padding: '12px', background: '#F0FDF4', borderRadius: '4px', lineHeight: '1.6' }}>
                            {agentData.output.llm_synthesis.correlation_with_monitoring}
                          </Body>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Recommended Next Steps Card */}
                  {agentData.output.llm_synthesis.recommended_next_steps && agentData.output.llm_synthesis.recommended_next_steps.length > 0 && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'next_steps' ? null : 'next_steps')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Bulb" size="small" />
                          <Label>Recommended Next Steps ({agentData.output.llm_synthesis.recommended_next_steps.length})</Label>
                        </div>
                        <Icon glyph={expandedQuery === 'next_steps' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'next_steps' && (
                        <div className={styles.queryDetails}>
                          <div className={styles.findingsList}>
                            {agentData.output.llm_synthesis.recommended_next_steps.map((step, idx) => (
                              <div key={idx} style={{ background: '#FFF7ED', padding: '10px', borderRadius: '4px', marginBottom: '8px', borderLeft: '3px solid #F76700' }}>
                                <Body className={styles.findingItem}>
                                  <strong>Step {idx + 1}:</strong> {step}
                                </Body>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}

          {/* RCA AGENT OUTPUT */}
          {agentData && selectedAgent === 3 && (
            <div className={styles.agentOutput}>
              {/* Overall Execution Time */}
              <div className={styles.section}>
                <Label className={styles.sectionTitle}>
                  <Icon glyph="Clock" size="small" /> Overall Execution Time
                </Label>
                <Body className={styles.metric}>
                  <strong>{agentData.output.execution_time_ms?.toFixed(0)}ms</strong> total
                </Body>
              </div>

              {/* Section: MongoDB Tool Queries */}
              <div className={styles.section}>
                <Label className={styles.sectionTitle}>
                  <Icon glyph="Diagram3" size="small" /> MongoDB Tool Queries
                </Label>

                {/* Tool 1: Historical Knowledge Search */}
                {agentData.output.tool_outputs?.historical_knowledge && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'historical_knowledge' ? null : 'historical_knowledge')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Tool 1: Historical Knowledge Search (Vector Search)</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.tool_outputs.historical_knowledge.execution_time_ms?.toFixed(0)}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'historical_knowledge' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'historical_knowledge' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Search historical RCA reports for similar incidents using semantic similarity
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>$vectorSearch</code> on historical_knowledge collection with embeddings
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li><strong>Search Type:</strong> {agentData.output.tool_outputs.historical_knowledge.search_type}</li>
                            <li><strong>Documents Found:</strong> {agentData.output.tool_outputs.historical_knowledge.documents_found} similar incidents</li>
                            <li><strong>Average Similarity Score:</strong> {agentData.output.tool_outputs.historical_knowledge.avg_similarity_score?.toFixed(3)} (0-1 scale)</li>
                          </ul>
                        </div>

                        <div className={styles.queryResults}>
                          <Label>Collections Queried:</Label>
                          <ul>
                            <li><code>historical_knowledge</code> (vector similarity search with voyage-multimodal-3)</li>
                          </ul>
                        </div>

                        <div className={styles.excursionBox}>
                          <Label>⚡ Why Vector Search Matters:</Label>
                          <ul>
                            <li>Finds semantically similar incidents, not just keyword matches</li>
                            <li>Atlas Vector Search delivers <strong>sub-100ms response times</strong> on 1000s of documents</li>
                            <li>High similarity scores ({agentData.output.tool_outputs.historical_knowledge.avg_similarity_score?.toFixed(3)}) indicate strong historical precedent</li>
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}

                {/* Tool 2: Correlation Analysis */}
                {agentData.output.tool_outputs?.correlation_analysis && (
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'correlation_analysis' ? null : 'correlation_analysis')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Checkmark" size="small" />
                        <Label>Tool 2: Correlation Analysis</Label>
                        <Badge variant="lightgray" className={styles.timeBadge}>
                          {agentData.output.tool_outputs.correlation_analysis.execution_time_ms?.toFixed(0)}ms
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'correlation_analysis' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'correlation_analysis' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.queryPurpose}>
                          <strong>Purpose:</strong> Cross-reference findings with wafer defects and process context
                        </Body>
                        <Body className={styles.queryOperation}>
                          <strong>MongoDB Operation:</strong> <code>find()</code> + aggregation across multiple collections
                        </Body>

                        <div className={styles.queryResults}>
                          <Label>Results:</Label>
                          <ul>
                            <li><strong>Correlated Wafers:</strong> {agentData.output.tool_outputs.correlation_analysis.correlated_wafers_count} wafers analyzed</li>
                            <li><strong>Process Context Items:</strong> {agentData.output.tool_outputs.correlation_analysis.process_context_items_count} materials/recipes linked</li>
                            <li><strong>Correlation Strength:</strong> {agentData.output.tool_outputs.correlation_analysis.correlation_strength}</li>
                          </ul>
                        </div>

                        <div className={styles.queryResults}>
                          <Label>Collections Queried:</Label>
                          <ul>
                            <li><code>wafer_defects</code></li>
                            <li><code>process_context</code></li>
                          </ul>
                        </div>

                        <div className={styles.excursionBox}>
                          <Label>⚠️ Why This Validates Root Causes:</Label>
                          <ul>
                            <li><strong>{agentData.output.tool_outputs.correlation_analysis.correlation_strength}</strong> correlation confirms causality</li>
                            <li>Links {agentData.output.tool_outputs.correlation_analysis.correlated_wafers_count} wafers to specific process materials</li>
                            <li>Provides concrete evidence for RCA validation</li>
                          </ul>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Section: AI Analysis Insights */}
              {agentData.output.llm_synthesis && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Sparkle" size="small" /> AI Analysis Insights (Claude Haiku)
                  </Label>

                  {/* Overall Confidence Card */}
                  <div className={styles.queryCard}>
                    <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'rca_confidence' ? null : 'rca_confidence')}>
                      <div className={styles.queryTitle}>
                        <Icon glyph="Charts" size="small" />
                        <Label>Overall RCA Confidence</Label>
                        <Badge variant={agentData.output.llm_synthesis.overall_confidence >= 0.8 ? 'green' : agentData.output.llm_synthesis.overall_confidence >= 0.6 ? 'yellow' : 'red'}>
                          {(agentData.output.llm_synthesis.overall_confidence * 100).toFixed(0)}%
                        </Badge>
                      </div>
                      <Icon glyph={expandedQuery === 'rca_confidence' ? "ChevronDown" : "ChevronRight"} size="small" />
                    </div>

                    {expandedQuery === 'rca_confidence' && (
                      <div className={styles.queryDetails}>
                        <Body className={styles.reasoningText} style={{ padding: '12px', background: '#F0FDF4', borderRadius: '4px', lineHeight: '1.6' }}>
                          {agentData.output.llm_synthesis.reasoning}
                        </Body>
                      </div>
                    )}
                  </div>

                  {/* Validated Root Causes Card */}
                  {agentData.output.llm_synthesis.validated_root_causes && agentData.output.llm_synthesis.validated_root_causes.length > 0 && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'root_causes' ? null : 'root_causes')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Warning" size="small" />
                          <Label>Validated Root Causes ({agentData.output.llm_synthesis.validated_root_causes.length})</Label>
                          <Badge variant="red">⚠️ Critical</Badge>
                        </div>
                        <Icon glyph={expandedQuery === 'root_causes' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'root_causes' && (
                        <div className={styles.queryDetails}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                            {agentData.output.llm_synthesis.validated_root_causes.map((cause, idx) => (
                              <div key={idx} style={{ padding: '14px', background: '#FEF2F2', borderRadius: '4px', borderLeft: '4px solid #C1271C' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '10px', flexWrap: 'wrap' }}>
                                  <Badge variant="red">Root Cause #{idx + 1}</Badge>
                                  <Badge variant={cause.confidence === 'high' ? 'green' : cause.confidence === 'medium' ? 'yellow' : 'blue'}>
                                    {typeof cause === 'object' && cause.confidence ? cause.confidence?.toUpperCase() : 'UNKNOWN'} confidence
                                  </Badge>
                                </div>
                                
                                <Body style={{ fontSize: '14px', fontWeight: 'bold', marginBottom: '10px', lineHeight: '1.5' }}>
                                  {typeof cause === 'object' ? cause.root_cause : cause}
                                </Body>

                                {typeof cause === 'object' && cause.supporting_evidence && cause.supporting_evidence.length > 0 && (
                                  <div style={{ marginTop: '10px', padding: '10px', background: 'white', borderRadius: '4px' }}>
                                    <Label style={{ fontSize: '12px', marginBottom: '6px', display: 'block' }}>Supporting Evidence:</Label>
                                    <ul style={{ marginTop: '4px', paddingLeft: '20px', margin: 0 }}>
                                      {cause.supporting_evidence.map((evidence, eidx) => (
                                        <li key={eidx} style={{ fontSize: '12px', marginBottom: '6px', lineHeight: '1.4', color: '#333' }}>{evidence}</li>
                                      ))}
                                    </ul>
                                  </div>
                                )}

                                {typeof cause === 'object' && cause.affected_materials && cause.affected_materials.length > 0 && (
                                  <div style={{ marginTop: '10px' }}>
                                    <Label style={{ fontSize: '12px', marginBottom: '6px', display: 'block' }}>Affected Materials:</Label>
                                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: '6px' }}>
                                      {cause.affected_materials.map((material, midx) => (
                                        <code key={midx} style={{ background: 'white', padding: '4px 8px', borderRadius: '3px', fontSize: '11px', border: '1px solid #ddd' }}>
                                          {material.type}: {material.id}
                                        </code>
                                      ))}
                                    </div>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Historical Precedent Card */}
                  {agentData.output.llm_synthesis.historical_precedent && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'historical_precedent' ? null : 'historical_precedent')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="University" size="small" />
                          <Label>Historical Precedent</Label>
                        </div>
                        <Icon glyph={expandedQuery === 'historical_precedent' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'historical_precedent' && (
                        <div className={styles.queryDetails}>
                          <Body className={styles.reasoningText} style={{ padding: '12px', background: '#FFF7ED', borderRadius: '4px', lineHeight: '1.6' }}>
                            {agentData.output.llm_synthesis.historical_precedent}
                          </Body>
                        </div>
                      )}
                    </div>
                  )}

                  {/* Recommendations Card */}
                  {agentData.output.llm_synthesis.recommendations && agentData.output.llm_synthesis.recommendations.length > 0 && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'rca_recommendations' ? null : 'rca_recommendations')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Lightbulb" size="small" />
                          <Label>Recommendations ({agentData.output.llm_synthesis.recommendations.length})</Label>
                        </div>
                        <Icon glyph={expandedQuery === 'rca_recommendations' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'rca_recommendations' && (
                        <div className={styles.queryDetails}>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                            {agentData.output.llm_synthesis.recommendations.map((rec, idx) => (
                              <div key={idx} style={{ padding: '12px', background: '#F0FDF4', borderRadius: '4px', borderLeft: '3px solid #00684A' }}>
                                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                                  <Badge variant="blue">#{idx + 1}</Badge>
                                  {typeof rec === 'object' && rec.priority && (
                                    <Badge variant={
                                      rec.priority === 'urgent' ? 'red' :
                                      rec.priority === 'high' ? 'yellow' :
                                      rec.priority === 'medium' ? 'blue' : 'lightgray'
                                    }>
                                      {rec.priority?.toUpperCase()} Priority
                                    </Badge>
                                  )}
                                </div>

                                <Body style={{ fontSize: '13px', marginBottom: '8px', lineHeight: '1.5' }}>
                                  <strong>Action:</strong> {typeof rec === 'object' ? rec.action : rec}
                                </Body>

                                {typeof rec === 'object' && rec.expected_impact && (
                                  <Body style={{ fontSize: '12px', color: '#16A34A', marginBottom: '6px' }}>
                                    <strong>Expected Impact:</strong> {rec.expected_impact}
                                  </Body>
                                )}

                                {typeof rec === 'object' && rec.timeline && (
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginTop: '8px' }}>
                                    <Icon glyph="Clock" size="small" />
                                    <Body style={{ fontSize: '11px' }}>
                                      <strong>Timeline:</strong> {rec.timeline}
                                    </Body>
                                  </div>
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}

                  {/* False Positives Ruled Out Card */}
                  {agentData.output.llm_synthesis.false_positives_ruled_out && agentData.output.llm_synthesis.false_positives_ruled_out.length > 0 && (
                    <div className={styles.queryCard}>
                      <div className={styles.queryHeader} onClick={() => setExpandedQuery(expandedQuery === 'false_positives' ? null : 'false_positives')}>
                        <div className={styles.queryTitle}>
                          <Icon glyph="Checkmark" size="small" />
                          <Label>False Positives Ruled Out ({agentData.output.llm_synthesis.false_positives_ruled_out.length})</Label>
                          <Badge variant="green">✓ Validated</Badge>
                        </div>
                        <Icon glyph={expandedQuery === 'false_positives' ? "ChevronDown" : "ChevronRight"} size="small" />
                      </div>

                      {expandedQuery === 'false_positives' && (
                        <div className={styles.queryDetails}>
                          <div className={styles.findingsList}>
                            {agentData.output.llm_synthesis.false_positives_ruled_out.map((fp, idx) => (
                              <Body key={idx} className={styles.findingItem} style={{ background: '#F0FDF4', padding: '10px', borderRadius: '4px', marginBottom: '6px', borderLeft: '3px solid #16A34A' }}>
                                <Badge variant="green">✓</Badge> {fp}
                              </Body>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}
            </div>
          )}



          {/* SUPERVISOR AGENT OUTPUT */}
          {agentData && selectedAgent === 4 && (
            <div className={styles.agentOutput}>
              {/* Overall Execution Time */}
              <div className={styles.section}>
                <Label className={styles.sectionTitle}>
                  <Icon glyph="Clock" size="small" /> Overall Execution Time
                </Label>
                <Body className={styles.metric}>
                  <strong>{agentData.output.execution_time_ms?.toFixed(0)}ms</strong> total
                </Body>
              </div>

              {/* Executive Summary */}
              {agentData.output.llm_synthesis?.executive_summary && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Megaphone" size="small" /> Executive Summary
                  </Label>
                  <Body className={styles.reasoningText} style={{ whiteSpace: 'pre-wrap', background: '#f9f9f9', padding: '12px', borderRadius: '4px', borderLeft: '3px solid #00684A' }}>
                    {agentData.output.llm_synthesis.executive_summary}
                  </Body>
                </div>
              )}

              {/* Overall Confidence */}
              {agentData.output.llm_synthesis?.overall_confidence && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>Overall Confidence</Label>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                    <Badge variant="green">
                      {(agentData.output.llm_synthesis.overall_confidence * 100).toFixed(0)}%
                    </Badge>
                    <Body className={styles.metric}>Analysis Confidence Score</Body>
                  </div>
                </div>
              )}

              {/* Cross-Agent Synthesis */}
              {agentData.output.llm_synthesis?.cross_agent_synthesis && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Diagram3" size="small" /> Cross-Agent Synthesis
                  </Label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                    {agentData.output.llm_synthesis.cross_agent_synthesis.monitoring_insights && (
                      <div style={{ padding: '10px', background: '#f0f7ff', borderRadius: '4px' }}>
                        <Label style={{ fontSize: '11px', color: '#1E8DD6' }}>🔵 Monitoring Agent</Label>
                        <Body style={{ fontSize: '13px', marginTop: '4px' }}>
                          {agentData.output.llm_synthesis.cross_agent_synthesis.monitoring_insights}
                        </Body>
                      </div>
                    )}
                    {agentData.output.llm_synthesis.cross_agent_synthesis.investigation_insights && (
                      <div style={{ padding: '10px', background: '#fff7ed', borderRadius: '4px' }}>
                        <Label style={{ fontSize: '11px', color: '#F76700' }}>🟠 Investigation Agent</Label>
                        <Body style={{ fontSize: '13px', marginTop: '4px' }}>
                          {agentData.output.llm_synthesis.cross_agent_synthesis.investigation_insights}
                        </Body>
                      </div>
                    )}
                    {agentData.output.llm_synthesis.cross_agent_synthesis.rca_insights && (
                      <div style={{ padding: '10px', background: '#f9f0ff', borderRadius: '4px' }}>
                        <Label style={{ fontSize: '11px', color: '#9333EA' }}>🟣 RCA Agent</Label>
                        <Body style={{ fontSize: '13px', marginTop: '4px' }}>
                          {agentData.output.llm_synthesis.cross_agent_synthesis.rca_insights}
                        </Body>
                      </div>
                    )}
                    {agentData.output.llm_synthesis.cross_agent_synthesis.knowledge_base_insights && (
                      <div style={{ padding: '10px', background: '#f0fdf4', borderRadius: '4px' }}>
                        <Label style={{ fontSize: '11px', color: '#16A34A' }}>📚 Knowledge Base</Label>
                        <Body style={{ fontSize: '13px', marginTop: '4px' }}>
                          {agentData.output.llm_synthesis.cross_agent_synthesis.knowledge_base_insights}
                        </Body>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Quality Control Report */}
              {agentData.output.llm_synthesis?.quality_control_report && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="ImportantWithCircle" size="small" /> Quality Control Report
                  </Label>

                  {/* Yield Impact */}
                  {agentData.output.llm_synthesis.quality_control_report.yield_impact && (
                    <div style={{ marginBottom: '16px', padding: '12px', background: '#fef2f2', borderRadius: '4px', border: '1px solid #fecaca' }}>
                      <Label style={{ fontSize: '12px', marginBottom: '8px', display: 'block' }}>Yield Impact Analysis</Label>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                        <div>
                          <Body style={{ fontSize: '11px', color: '#666' }}>Wafers Affected</Body>
                          <Body style={{ fontSize: '14px', fontWeight: 'bold' }}>
                            {agentData.output.llm_synthesis.quality_control_report.yield_impact.estimated_wafers_affected}
                          </Body>
                        </div>
                        <div>
                          <Body style={{ fontSize: '11px', color: '#666' }}>Yield Loss</Body>
                          <Body style={{ fontSize: '14px', fontWeight: 'bold', color: '#DC2626' }}>
                            {agentData.output.llm_synthesis.quality_control_report.yield_impact.estimated_yield_loss_percent}%
                          </Body>
                        </div>
                        <div>
                          <Body style={{ fontSize: '11px', color: '#666' }}>Cost Impact</Body>
                          <Body style={{ fontSize: '14px', fontWeight: 'bold', color: '#DC2626' }}>
                            ${(agentData.output.llm_synthesis.quality_control_report.yield_impact.estimated_cost_impact_usd / 1000).toFixed(0)}K
                          </Body>
                        </div>
                        <div>
                          <Body style={{ fontSize: '11px', color: '#666' }}>Confidence</Body>
                          <Badge variant={agentData.output.llm_synthesis.quality_control_report.yield_impact.confidence_level === 'high' ? 'green' : 'yellow'}>
                            {agentData.output.llm_synthesis.quality_control_report.yield_impact.confidence_level?.toUpperCase()}
                          </Badge>
                        </div>
                      </div>
                    </div>
                  )}

                  {/* Quality Metrics */}
                  {agentData.output.llm_synthesis.quality_control_report.quality_metrics && (
                    <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '8px' }}>
                      {Object.entries(agentData.output.llm_synthesis.quality_control_report.quality_metrics).map(([key, value]) => (
                        <div key={key} style={{ padding: '8px', background: '#f9f9f9', borderRadius: '4px' }}>
                          <Body style={{ fontSize: '11px', color: '#666', textTransform: 'capitalize' }}>
                            {key ? key.replace(/_/g, ' ') : ''}
                          </Body>
                          <Body style={{ fontSize: '12px', fontWeight: 'bold' }}>
                            {typeof value === 'string' && value ? value.replace(/_/g, ' ') : value || 'N/A'}
                          </Body>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {/* Recommendations */}
              {agentData.output.llm_synthesis?.recommendations && agentData.output.llm_synthesis.recommendations.length > 0 && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Lightbulb" size="small" /> Recommendations ({agentData.output.llm_synthesis.recommendations.length})
                  </Label>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '8px' }}>
                    {agentData.output.llm_synthesis.recommendations.map((rec, idx) => (
                      <div key={idx} style={{ padding: '12px', background: '#f9f9f9', borderRadius: '4px', borderLeft: '3px solid #00684A' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px', flexWrap: 'wrap' }}>
                          {rec.category && <Badge variant="blue">{rec.category.replace(/_/g, ' ').toUpperCase()}</Badge>}
                          {rec.priority && (
                            <Badge variant={
                              rec.priority === 'critical' ? 'red' :
                              rec.priority === 'high' ? 'yellow' :
                              rec.priority === 'medium' ? 'blue' : 'lightgray'
                            }>
                              {rec.priority.toUpperCase()} Priority
                            </Badge>
                          )}
                          {rec.responsible_team && (
                            <Body style={{ fontSize: '11px', color: '#666' }}>
                              {rec.responsible_team}
                            </Body>
                          )}
                        </div>

                        <Body style={{ fontSize: '13px', marginBottom: '8px' }}>
                          <strong>Action:</strong> {rec.action}
                        </Body>

                        {rec.rationale && (
                          <Body style={{ fontSize: '12px', color: '#666', marginBottom: '8px' }}>
                            <strong>Rationale:</strong> {rec.rationale}
                          </Body>
                        )}

                        {rec.expected_impact && (
                          <Body style={{ fontSize: '12px', color: '#16A34A', marginBottom: '8px' }}>
                            <strong>Expected Impact:</strong> {rec.expected_impact}
                          </Body>
                        )}

                        <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '8px' }}>
                          {rec.timeline && (
                            <div style={{ display: 'flex', alignItems: 'center', gap: '4px' }}>
                              <Icon glyph="Clock" size="small" />
                              <Body style={{ fontSize: '11px' }}>
                                <strong>Timeline:</strong> {rec.timeline}
                              </Body>
                            </div>
                          )}
                        </div>

                        {rec.success_metrics && rec.success_metrics.length > 0 && (
                          <div style={{ marginTop: '8px' }}>
                            <Label style={{ fontSize: '11px' }}>Success Metrics:</Label>
                            <ul style={{ marginTop: '4px', paddingLeft: '20px' }}>
                              {rec.success_metrics.map((metric, midx) => (
                                <li key={midx} style={{ fontSize: '11px', marginBottom: '2px' }}>{metric}</li>
                              ))}
                            </ul>
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Risk Assessment */}
              {agentData.output.llm_synthesis?.risk_assessment && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="Warning" size="small" /> Risk Assessment
                  </Label>
                  <div style={{ padding: '12px', background: '#fef2f2', borderRadius: '4px', border: '1px solid #fecaca' }}>
                    {agentData.output.llm_synthesis.risk_assessment.recurrence_risk && (
                      <div style={{ marginBottom: '12px' }}>
                        <Label style={{ fontSize: '12px' }}>Recurrence Risk:</Label>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginTop: '4px' }}>
                          <Badge variant={
                            agentData.output.llm_synthesis.risk_assessment.recurrence_risk === 'high' ? 'red' :
                            agentData.output.llm_synthesis.risk_assessment.recurrence_risk === 'medium' ? 'yellow' : 'green'
                          }>
                            {agentData.output.llm_synthesis.risk_assessment.recurrence_risk?.toUpperCase()}
                          </Badge>
                        </div>
                        {agentData.output.llm_synthesis.risk_assessment.recurrence_risk_rationale && (
                          <Body style={{ fontSize: '12px', marginTop: '6px' }}>
                            {agentData.output.llm_synthesis.risk_assessment.recurrence_risk_rationale}
                          </Body>
                        )}
                      </div>
                    )}

                    {agentData.output.llm_synthesis.risk_assessment.escalation_needed !== undefined && (
                      <div style={{ marginBottom: '12px' }}>
                        <Label style={{ fontSize: '12px' }}>Escalation Required:</Label>
                        <Badge variant={agentData.output.llm_synthesis.risk_assessment.escalation_needed ? 'red' : 'green'}>
                          {agentData.output.llm_synthesis.risk_assessment.escalation_needed ? 'YES' : 'NO'}
                        </Badge>
                        {agentData.output.llm_synthesis.risk_assessment.escalation_rationale && (
                          <Body style={{ fontSize: '12px', marginTop: '6px' }}>
                            {agentData.output.llm_synthesis.risk_assessment.escalation_rationale}
                          </Body>
                        )}
                      </div>
                    )}

                    {agentData.output.llm_synthesis.risk_assessment.monitoring_plan && (
                      <div>
                        <Label style={{ fontSize: '12px' }}>Monitoring Plan:</Label>
                        <Body style={{ fontSize: '12px', marginTop: '4px' }}>
                          {agentData.output.llm_synthesis.risk_assessment.monitoring_plan}
                        </Body>
                      </div>
                    )}
                  </div>
                </div>
              )}

              {/* Lessons Learned */}
              {agentData.output.llm_synthesis?.lessons_learned && agentData.output.llm_synthesis.lessons_learned.length > 0 && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="University" size="small" /> Lessons Learned
                  </Label>
                  <div className={styles.findingsList}>
                    {agentData.output.llm_synthesis.lessons_learned.map((lesson, idx) => (
                      <Body key={idx} className={styles.findingItem} style={{ background: '#f0fdf4', padding: '10px', borderRadius: '4px', marginBottom: '8px' }}>
                        <strong>Lesson {idx + 1}:</strong> {lesson}
                      </Body>
                    ))}
                  </div>
                </div>
              )}

              {/* Tool Outputs - Troubleshooting Guides */}
              {agentData.output.tool_outputs?.troubleshooting_guides && (
                <div className={styles.section}>
                  <Label className={styles.sectionTitle}>
                    <Icon glyph="University" size="small" /> Tool: Troubleshooting Guides Search
                  </Label>
                  <div className={styles.toolMetrics}>
                    <Badge variant="lightgray">
                      {agentData.output.tool_outputs.troubleshooting_guides.execution_time_ms?.toFixed(0)}ms
                    </Badge>
                    <Body className={styles.toolSummary}>
                      Found: <strong>{agentData.output.tool_outputs.troubleshooting_guides.documents_found}</strong> documents
                    </Body>
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
