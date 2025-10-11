"use client";

import React, { useState, useEffect } from 'react';
import Card from '@leafygreen-ui/card';
import Badge from '@leafygreen-ui/badge';
import Icon from '@leafygreen-ui/icon';
import FabPulseBar from './FabPulseBar';
import ProcessHealthMatrix from './ProcessHealthMatrix';
import AlertsPanel from './AlertsPanel';
import DemoControlPanel from './DemoControlPanel';
import DashboardModeToggle from './DashboardModeToggle';
import AgenticWorkflowView from './AgenticWorkflowView';
import AgentWorkflowBar from './AgentWorkflowBar';
import AgentDetailPanel from './AgentDetailPanel';
import LiveParticleMonitor from './LiveParticleMonitor';
import LiveTemperatureMonitor from './LiveTemperatureMonitor';
import LiveRFPowerMonitor from './LiveRFPowerMonitor';
import LiveWaferImageMapCompact from './LiveWaferImageMapCompact';
import EquipmentMetricsChart from './EquipmentMetricsChart';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import { aiAgentAPI } from '@/lib/api';
import styles from './Dashboard.module.css';

// Agent-Collection mapping
const AGENT_COLLECTION_MAP = {
  1: ['process_sensor_ts'], // Monitoring Agent
  2: ['wafer_defects', 'process_context', 'alerts'], // Investigation Agent
  3: ['historical_knowledge'], // RCA Agent
  4: ['wafer_defects', 'historical_knowledge', 'process_context'] // Supervisor Agent
};

const Dashboard = () => {
  const { refresh } = useDashboardData();
  const [dashboardMode, setDashboardMode] = useState('normal'); // 'normal' or 'agentic'
  const [aiEnabled, setAiEnabled] = useState(true);
  const [isMatrixCollapsed, setIsMatrixCollapsed] = useState(false);
  const [isAlertsCollapsed, setIsAlertsCollapsed] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState(null);
  const [clickedCollection, setClickedCollection] = useState(null);

  // Find agents that use a specific collection
  const getAgentsUsingCollection = (collectionName) => {
    return Object.entries(AGENT_COLLECTION_MAP)
      .filter(([agent, collections]) => collections.includes(collectionName))
      .map(([agent]) => parseInt(agent));
  };

  // Fetch AI agent status on mount and poll periodically
  useEffect(() => {
    const fetchAIStatus = async () => {
      try {
        const data = await aiAgentAPI.getStatus();
        setAiEnabled(data.enabled);
      } catch (err) {
        console.error('Error fetching AI status:', err);
      }
    };

    fetchAIStatus();
    const interval = setInterval(fetchAIStatus, 5000); // Poll every 5 seconds
    return () => clearInterval(interval);
  }, []);

  return (
    <div className={styles.dashboard}>
      <FabPulseBar />
      <div className={styles.dashboardBody}>
        <div className={`${styles.leftPanel} ${isMatrixCollapsed ? styles.leftPanelCollapsed : ''}`}>
          <ProcessHealthMatrix
            isCollapsed={isMatrixCollapsed}
            onToggle={() => setIsMatrixCollapsed(!isMatrixCollapsed)}
          />
        </div>
        <div className={styles.centerPanel}>
          {/* Dashboard Mode Toggle - Replaces MongoDBConsolePanel */}
          <DashboardModeToggle
            mode={dashboardMode}
            onModeChange={setDashboardMode}
          />

          {/* Demo Control Panel */}
          <DemoControlPanel />

          {/* Conditional Content Based on Mode */}
          {dashboardMode === 'normal' ? (
            <>
              {/* Normal Mode: 5 Charts */}
              <div className={styles.chartsRowThree}>
                <LiveParticleMonitor />
                <LiveTemperatureMonitor />
                <LiveRFPowerMonitor />
              </div>

              <div className={styles.chartsRowTwo}>
                <LiveWaferImageMapCompact />
                <EquipmentMetricsChart />
              </div>
            </>
          ) : (
            <>
              {/* Agentic Mode: AI Workflow Pipeline */}
              <AgentWorkflowBar
                selectedAgent={selectedAgent}
                onAgentSelect={setSelectedAgent}
              />

              <AgentDetailPanel
                selectedAgent={selectedAgent}
              />

              {clickedCollection && (
                <Card className={styles.collectionInfo}>
                  <Icon glyph="InfoWithCircle" size="small" />
                  <Badge variant="blue">
                    Used by Agents: {getAgentsUsingCollection(clickedCollection).join(', ')}
                  </Badge>
                </Card>
              )}

              <AgenticWorkflowView
                highlightedCollections={selectedAgent ? AGENT_COLLECTION_MAP[selectedAgent] : []}
                onCollectionClick={setClickedCollection}
              />
            </>
          )}
        </div>
        <div className={`${styles.rightPanel} ${isAlertsCollapsed ? styles.rightPanelCollapsed : ''}`}>
          <AlertsPanel
            dashboardMode={dashboardMode}
            aiEnabled={aiEnabled}
            isCollapsed={isAlertsCollapsed}
            onToggle={() => setIsAlertsCollapsed(!isAlertsCollapsed)}
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;