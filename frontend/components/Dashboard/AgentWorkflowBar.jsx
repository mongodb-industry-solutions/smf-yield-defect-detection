"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { Select, Option } from '@leafygreen-ui/select';
import { Body, Label } from '@leafygreen-ui/typography';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
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

const AgentWorkflowBar = ({ selectedAgent, onAgentSelect, selectedAlertId, onAlertSelect }) => {
  // Use alerts from DashboardDataProvider instead of polling separately
  const { alerts } = useDashboardData();

  // Auto-select the first (newest) alert if no alert is selected
  useEffect(() => {
    if (alerts.length > 0 && !selectedAlertId) {
      const newAlertId = alerts[0]._id || alerts[0].id;
      onAlertSelect(newAlertId);
    }
  }, [alerts, selectedAlertId, onAlertSelect]);

  return (
    <Card className={styles.container}>
      <div className={styles.header}>
        <div className={styles.headerLeft}>
          <Label className={styles.title}>AI Workflow Pipeline</Label>
          <Badge variant="blue">4 Agents</Badge>
        </div>
        <div className={styles.alertSelector}>
          <Select
            label="Select Alert (applies to all agents)"
            description="Auto-updates with new alerts"
            value={selectedAlertId || ''}
            onChange={(value) => onAlertSelect(value)}
            disabled={alerts.length === 0}
            size="small"
          >
            {alerts.map((alert, index) => {
              const isLatest = index === 0;
              const timestamp = new Date(alert.timestamp);
              const timeStr = timestamp.toLocaleTimeString();
              const severityEmoji = alert.severity === 'critical' ? '🔴' : alert.severity === 'high' ? '🟠' : '🟡';

              return (
                <Option key={alert._id || alert.id} value={alert._id || alert.id}>
                  {isLatest ? '⭐ ' : ''}{severityEmoji} {alert.equipment_id} - {alert.alert_type} ({timeStr})
                </Option>
              );
            })}
          </Select>
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
