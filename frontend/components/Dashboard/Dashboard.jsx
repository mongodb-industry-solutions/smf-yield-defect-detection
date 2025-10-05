"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import FabPulseBar from './FabPulseBar';
import ProcessHealthMatrix from './ProcessHealthMatrix';
import AlertsPanel from './AlertsPanel';
import DemoControlPanel from './DemoControlPanel';
import MongoDBConsolePanel from './MongoDBConsolePanel';
import LiveParticleMonitor from './LiveParticleMonitor';
import LiveTemperatureMonitor from './LiveTemperatureMonitor';
import LiveRFPowerMonitor from './LiveRFPowerMonitor';
import LiveWaferImageMapCompact from './LiveWaferImageMapCompact';
import EquipmentMetricsChart from './EquipmentMetricsChart';
import { useDashboardData } from '@/contexts/DashboardDataProvider';
import styles from './Dashboard.module.css';

const Dashboard = () => {
  const { refresh } = useDashboardData();

  return (
    <div className={styles.dashboard}>
      <FabPulseBar />
      <div className={styles.dashboardBody}>
        <div className={styles.leftPanel}>
          <ProcessHealthMatrix />
        </div>
        <div className={styles.centerPanel}>
          {/* Demo Control Panel */}
          <DemoControlPanel />

          {/* MongoDB Console Panel - Shows live operations flow */}
          <MongoDBConsolePanel />

          {/* First Row: Three Atlas Charts */}
          <div className={styles.chartsRowThree}>
            <LiveParticleMonitor />
            <LiveTemperatureMonitor />
            <LiveRFPowerMonitor />
          </div>

          {/* Second Row: Wafer Map and Equipment Metrics */}
          <div className={styles.chartsRowTwo}>
            <LiveWaferImageMapCompact />
            <EquipmentMetricsChart />
          </div>
        </div>
        <div className={styles.rightPanel}>
          <AlertsPanel />
        </div>
      </div>
    </div>
  );
};

export default Dashboard;