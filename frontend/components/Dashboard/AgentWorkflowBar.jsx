"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import { Body, Label } from '@leafygreen-ui/typography';
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

const AgentWorkflowBar = ({ selectedAgent, onAgentSelect }) => {
  return (
    <Card className={styles.container}>
      <div className={styles.header}>
        <Label className={styles.title}>
          AI Workflow Pipeline
        </Label>
        <Badge variant="blue">4 Agents</Badge>
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
