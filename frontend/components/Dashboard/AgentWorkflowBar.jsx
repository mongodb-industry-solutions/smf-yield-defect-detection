"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { Body, Label } from '@leafygreen-ui/typography';
import { alertAPI } from '@/lib/api';
import styles from './AgentWorkflowBar.module.css';

const AGENTS = [
  {
    id: 1,
    name: "Monitor",
    icon: "ActivityFeed",
    fullName: "Monitoring Agent",
    color: "#0498EC" // LeafyGreen Blue
  },
  {
    id: 2,
    name: "Investigate",
    icon: "Connect",
    fullName: "Investigation Agent",
    color: "#FF6E3C" // LeafyGreen Orange
  },
  {
    id: 3,
    name: "RCA",
    icon: "MagnifyingGlass",
    fullName: "RCA Agent",
    color: "#6554C0" // LeafyGreen Purple
  },
  {
    id: 4,
    name: "Synthesize",
    icon: "Beaker",
    fullName: "Supervisor Agent",
    color: "#00684A" // MongoDB Green
  }
];

const AgentWorkflowBar = ({ selectedAgent, onAgentSelect, selectedAlertId }) => {
  const [alertInfo, setAlertInfo] = useState(null);
  const [loading, setLoading] = useState(false);

  // Fetch alert details when selectedAlertId changes
  useEffect(() => {
    if (!selectedAlertId) {
      setAlertInfo(null);
      return;
    }

    const fetchAlertInfo = async () => {
      setLoading(true);
      try {
        const alert = await alertAPI.getById(selectedAlertId);
        setAlertInfo(alert);
      } catch (error) {
        console.error('Error fetching alert info:', error);
        setAlertInfo(null);
      } finally {
        setLoading(false);
      }
    };

    fetchAlertInfo();
  }, [selectedAlertId]);

  // Helper to get severity badge variant
  const getSeverityBadgeVariant = (severity) => {
    switch (severity) {
      case 'critical': return 'red';
      case 'high': return 'yellow';
      case 'medium': return 'blue';
      default: return 'lightgray';
    }
  };

  return (
    <Card className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Label className={styles.title}>AI Workflow Pipeline</Label>
          <Badge variant="blue">4 Agents</Badge>
        </div>

        {/* Alert Info Display */}
        <div className={styles.alertInfo}>
          {loading && (
            <Body className={styles.loadingText}>Loading alert...</Body>
          )}

          {!loading && !alertInfo && (
            <Body className={styles.noAlertText}>No analysis running</Body>
          )}

          {!loading && alertInfo && (
            <div className={styles.alertDetails}>
              <Badge variant={getSeverityBadgeVariant(alertInfo.severity)}>
                {alertInfo.severity.toUpperCase()}
              </Badge>
              <span className={styles.alertEquipment}>{alertInfo.equipment_id}</span>
              <span className={styles.alertSeparator}>•</span>
              <span className={styles.alertType}>{alertInfo.alert_type}</span>
              <span className={styles.alertSeparator}>•</span>
              <span className={styles.alertTime}>
                {new Date(alertInfo.timestamp).toLocaleTimeString()}
              </span>
            </div>
          )}
        </div>
      </div>

      <div className={styles.stepsContainer}>
        {AGENTS.map((agent, index) => (
          <React.Fragment key={agent.id}>
            <button
              className={`${styles.stepButton} ${selectedAgent === agent.id ? styles.active : ''}`}
              onClick={() => onAgentSelect(agent.id)}
              style={{
                borderColor: selectedAgent === agent.id ? agent.color : 'var(--gray-light-2)'
              }}
            >
              <div className={styles.stepNumber} style={{
                backgroundColor: selectedAgent === agent.id ? agent.color : 'var(--gray-light-2)',
                color: selectedAgent === agent.id ? 'white' : 'var(--gray-dark-2)'
              }}>
                {agent.id}
              </div>
              <div className={styles.stepInfo}>
                <Icon
                  glyph={agent.icon}
                  size="large"
                  className={styles.stepIcon}
                  style={{ color: selectedAgent === agent.id ? agent.color : 'var(--gray-base)' }}
                />
                <Label className={styles.stepName}>{agent.name}</Label>
              </div>
            </button>

            {index < AGENTS.length - 1 && (
              <Icon glyph="ArrowRight" className={styles.arrow} size="large" />
            )}
          </React.Fragment>
        ))}
      </div>

      <Body className={styles.subtitle}>
        Data sourced from unified collections above
      </Body>
    </Card>
  );
};

export default AgentWorkflowBar;
