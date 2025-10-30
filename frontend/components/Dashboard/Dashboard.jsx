"use client";

import React, { useState } from 'react';
import FabPulseBar from './FabPulseBar';
import ProcessHealthMatrix from './ProcessHealthMatrix';
import AlertsPanel from './AlertsPanel';
import DemoControlPanel from './DemoControlPanel';
import DashboardModeToggle from './DashboardModeToggle';
import UnifiedSearchPanel from './UnifiedSearchPanel';
import LiveParticleMonitor from './LiveParticleMonitor';
import LiveTemperatureMonitor from './LiveTemperatureMonitor';
import LiveRFPowerMonitor from './LiveRFPowerMonitor';
import LiveWaferImageMapCompact from './LiveWaferImageMapCompact';
import EquipmentMetricsChart from './EquipmentMetricsChart';
import MongoDBOperationsConsole from './MongoDBOperationsConsole';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './Dashboard.module.css';

const Dashboard = ({ onModeChange }) => {
  const { refresh } = useDashboardData();
  const [dashboardMode, setDashboardMode] = useState('normal'); // 'normal' or 'search'

  // Propagate mode changes to parent
  const handleModeChange = (newMode) => {
    setDashboardMode(newMode);
    if (onModeChange) {
      onModeChange(newMode);
    }
  };
  const [isMatrixCollapsed, setIsMatrixCollapsed] = useState(false);
  const [isAlertsCollapsed, setIsAlertsCollapsed] = useState(false);

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

          {/* Demo Control Panel - Hide in search mode */}
          {dashboardMode !== 'search' && (
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
          ) : (
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
          />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;