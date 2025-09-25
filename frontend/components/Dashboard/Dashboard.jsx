"use client";

import React from 'react';
import Card from '@leafygreen-ui/card';
import FabPulseBar from './FabPulseBar';
import ProcessHealthMatrix from './ProcessHealthMatrix';
import AlertsPanel from './AlertsPanel';
import DemoControlPanel from './DemoControlPanel';
import LiveParticleMonitor from './LiveParticleMonitor';
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

          {/* Live Monitoring Charts */}
          <div className={styles.chartsContainer}>
            <LiveParticleMonitor />
            <EquipmentMetricsChart />
          </div>

          {/* Bottom Visualizations */}
          <div className={styles.bottomVisualizationsContainer}>
            {/* Wafer Defect Images - Half Width */}
            <LiveWaferImageMapCompact />

            {/* Space for another visualization */}
            <Card style={{
              background: 'white',
              borderRadius: '12px',
              padding: '20px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              minHeight: '280px'
            }}>
              <div style={{ textAlign: 'center', color: '#6b778c' }}>
                <h3 style={{ margin: '0 0 10px 0', color: '#1e2d3d' }}>Additional Visualization</h3>
                <p style={{ margin: 0 }}>Space for Alert Trends, Yield History, or Process Analytics</p>
              </div>
            </Card>
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