"use client";

import React, { useState, useEffect } from 'react';
import FabPulseBar from './FabPulseBar';
import ProcessHealthMatrix from './ProcessHealthMatrix';
import AlertsPanel from './AlertsPanel';
import DemoControlPanel from './DemoControlPanel';
import DashboardModeToggle from './DashboardModeToggle';
import ChartLayoutToggle from './ChartLayoutToggle';
import UnifiedSearchPanel from './UnifiedSearchPanel';
import AgenticChatPanel from './AgenticChatPanel';
import LiveParticleMonitor from './LiveParticleMonitor';
import LiveTemperatureMonitor from './LiveTemperatureMonitor';
import LiveRFPowerMonitor from './LiveRFPowerMonitor';
import LiveWaferImageMapCompact from './LiveWaferImageMapCompact';
import EquipmentMetricsChart from './EquipmentMetricsChart';
import MongoDBOperationsConsole from './MongoDBOperationsConsole';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import { demoAPI } from '@/lib/api';
import styles from './Dashboard.module.css';

const Dashboard = ({ onModeChange }) => {
  const { refresh } = useDashboardData();
  const [dashboardMode, setDashboardMode] = useState('normal'); // 'normal' or 'search'
  const [chartLayout, setChartLayout] = useState('grid'); // 'grid' or 'vertical'
  const [pendingChatQuery, setPendingChatQuery] = useState(null);

  // Propagate mode changes to parent
  const handleModeChange = (newMode) => {
    setDashboardMode(newMode);
    if (onModeChange) {
      onModeChange(newMode);
    }
  };

  // Handle navigation from alert modal to chat with pre-populated query
  const handleNavigateToChat = (query) => {
    setPendingChatQuery(query);
    handleModeChange('agentic');
  };

  // Clear pending query after it's been processed
  const clearPendingQuery = () => {
    setPendingChatQuery(null);
  };
  
  // Handle layout changes
  const handleLayoutChange = (newLayout) => {
    setChartLayout(newLayout);
  };
  
  const [isMatrixCollapsed, setIsMatrixCollapsed] = useState(false);
  const [isAlertsCollapsed, setIsAlertsCollapsed] = useState(false);

  // Heartbeat to keep demo alive (prevents auto-stop)
  useEffect(() => {
    // Send heartbeat every 30 seconds while dashboard is mounted
    const heartbeatInterval = setInterval(() => {
      demoAPI.sendHeartbeat().catch(err => {
        console.warn('Heartbeat failed:', err);
        // Non-fatal - just log and continue
      });
    }, 30000); // 30 seconds

    // Cleanup on unmount
    return () => clearInterval(heartbeatInterval);
  }, []); // Run once on mount

  return (
    <div className={styles.dashboard}>
      <FabPulseBar dashboardMode={dashboardMode} />
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
            onModeChange={handleModeChange}
          />

          {/* Demo Control Panel - Hide in search and agentic modes */}
          {dashboardMode !== 'search' && dashboardMode !== 'agentic' && (
            <DemoControlPanel
              dashboardMode={dashboardMode}
            />
          )}

          {/* Conditional Content Based on Mode */}
          {dashboardMode === 'search' ? (
            <>
              {/* Search Mode: Unified Search Panel */}
              <UnifiedSearchPanel />
            </>
          ) : dashboardMode === 'agentic' ? (
            <>
              {/* Agentic AI Mode: Chat Interface */}
              <div className={styles.agenticContainer}>
                <AgenticChatPanel
                  pendingQuery={pendingChatQuery}
                  onQueryProcessed={clearPendingQuery}
                />
              </div>
            </>
          ) : (
            <>
              {/* Normal Mode: 5 Charts */}
              {/* Chart Layout Toggle - Only show in normal mode */}
              <ChartLayoutToggle 
                layout={chartLayout} 
                onLayoutChange={handleLayoutChange}
              />
              
              <div className={chartLayout === 'grid' ? styles.chartsRowThree : styles.chartsRowThreeVertical}>
                <LiveParticleMonitor />
                <LiveTemperatureMonitor />
                <LiveRFPowerMonitor />
              </div>

              <div className={chartLayout === 'grid' ? styles.chartsRowTwo : styles.chartsRowTwoVertical}>
                <LiveWaferImageMapCompact />
                <EquipmentMetricsChart />
              </div>
            </>
          )}

          {/* MongoDB Operations Console - Bottom of centerPanel (hide in search mode) */}
          {dashboardMode === 'normal' && (
            <MongoDBOperationsConsole
              maxEvents={20}
              autoScroll={true}
              pauseOnHover={true}
              defaultExpanded={false}
            />
          )}
        </div>
        <div className={`${styles.rightPanel} ${isAlertsCollapsed ? styles.rightPanelCollapsed : ''}`}>
          <AlertsPanel
            dashboardMode={dashboardMode}
            isCollapsed={isAlertsCollapsed}
            onToggle={() => setIsAlertsCollapsed(!isAlertsCollapsed)}
            onNavigateToChat={handleNavigateToChat}
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;